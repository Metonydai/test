from sis_maxwell.post_processing import SISPost
from data_access import get_config
from data_access.logger import LoggerManager
from data_access import utilities as utils
from data_access import geometry

import json 
import pyaedt
import sys
import requests
from pathlib import Path

SERIALIZED_DICT = sys.argv[1]
ENV_TYPE = sys.argv[2]
CORRELATION_ID = int(sys.argv[3])

FLASK_PORT = str(get_config.get_flask_port())

DEV_FOLDER_PATH = Path(get_config.get_dev_folder_path())
STAGE_FOLDER_PATH = Path(get_config.get_stage_folder_path())
PROD_FOLDER_PATH = Path(get_config.get_prod_folder_path())
LOCAL_FOLDER_PATH = Path(get_config.get_local_folder_path())

LOG = LoggerManager(env=ENV_TYPE).getlog()

if ENV_TYPE == 'dev':
    ENV_PATH = DEV_FOLDER_PATH
elif ENV_TYPE == 'stage':
    ENV_PATH = STAGE_FOLDER_PATH
elif ENV_TYPE == 'prod':
    ENV_PATH = PROD_FOLDER_PATH
else:
    ENV_PATH = LOCAL_FOLDER_PATH


def simulate():
    receive_dict = json.loads(SERIALIZED_DICT)

    # Get core + winding step file
    macro_path = Path(ENV_PATH / receive_dict['core']['macroFilePath'])
    macro_dir = Path(ENV_PATH / receive_dict['core']['macroFilePath']).parent
    glb_file_dir = Path(macro_dir.parent) / "glb-file" 
    glb_file_dir.mkdir(parents=True, exist_ok=True)

    common_name = Path(macro_path).stem + "_winding"
    step_file_path = Path(glb_file_dir) / (common_name + '.stp')

    # AEDT project related
    project_directory = Path(macro_dir).parent.parent / "AEDT_project"
    model_directory = Path(project_directory) / "model"
    project_directory.mkdir(parents=True, exist_ok=True)
    model_directory.mkdir(parents=True, exist_ok=True)
    model_path = Path(model_directory) / (common_name + '.stp')

    #[POST] 
    url='http://127.0.0.1:' + str(FLASK_PORT) + '/ddc/sis/magnetic.algorithm/v1.0/generate_core_winding_glb'

    new_dict = receive_dict.copy()
    new_dict.update({"glbFileDirectory" : str(glb_file_dir.relative_to(ENV_PATH))})

    headers = {'SIS-Application-Environment': ENV_TYPE}
    resp = requests.post(url, json=new_dict, headers=headers, allow_redirects=True)
    if resp.status_code == 200: # Success in generate glb and step
        # Copy the step file to model_path
        model_path.write_text(step_file_path.read_text())
    else:
        log_msg = "Simulation: Failed to generate the step!"
        LOG.error('(%s) %s', __name__, log_msg , extra={'correlationId': '['+ CORRELATION_ID+']'})
        print("Simulation: Failed to generate the step!")
        raise Exception("Simulation: Failed to generate the step!")

    ###############################################################################
    # Set non-graphical mode
    # ~~~~~~~~~~~~~~~~~~~~~~
    # Set non-graphical mode. 
    # You can define ``non_graphical`` either to ``True`` or ``False``.

    project_name = "SIMULATION_HUI"
    non_graphical = False
    version = "2023.2"
    new_desktop_session = False

    ###############################################################################
    # Launch Maxwell3D
    # ~~~~~~~~~~~~~~~~
    # Launch Maxwell 3D 2023 R2 in graphical mode.
    eddy_design_name = "Maxwell3DDesign_Eddy"
    m3d = pyaedt.Maxwell3d(project=project_name,
                        design=eddy_design_name,
                        solution_type="EddyCurrent",
                        version=version,
                        non_graphical=non_graphical,
                        new_desktop=new_desktop_session
                        )

    m3d.set_active_design(eddy_design_name)

    ###############################################################################
    # Import 3d model
    # ~~~~~~~~~~~~
    core_name = "Core" # Case Sensitive!
    core_mat = receive_dict["core"]["material"]
    m3d.modeler.import_3d_cad(str(model_path))
    eddy_list = m3d.modeler.object_names
    eddy_list.remove(core_name)

    # Get the length, width, height, only the core+ winding
    cw_bbox = m3d.modeler.get_model_bounding_box()
    total_length = cw_bbox[3]- cw_bbox[0]
    total_width = cw_bbox[4]- cw_bbox[1]
    total_height = cw_bbox[5]- cw_bbox[2]

    ###############################################################################
    # Assign material
    # ~~~~~~~~~~~~~~~~~~
    if m3d.assign_material(core_name, core_mat):
        print("Assign Material to Core Success!")
    else:
        print(f"No Material Named {core_mat}")

    type_count = [0,0,0,0] # counts for [primary, secondary, bias, shied]
    winding_dict = dict() # {winding_name : winding number}
    for wp in receive_dict["windingProperties"]:
        if wp["type"] == "primary":
            winding_name = f"Primary_{type_count[0]}"
            winding_mat = "copper - {} {}_{}".format(wp["material"]["composition"], wp["material"]["wireDiameter"], wp["material"]["strandNumber"])
            my_hui = m3d.materials.add_material(winding_mat)
            my_hui.permittivity = 0.999991
            my_hui.conductivity = 58000000
            my_hui.stacking_type = "Litz Wire"
            my_hui.wire_diameter = wp["material"]["wireDiameter"]
            my_hui.strand_number = wp["material"]["strandNumber"]
            m3d.assign_material(winding_name, winding_mat)
            winding_dict[winding_name] = int(wp["windingNumber"])
            type_count[0] += 1
            
        elif wp["type"] == "secondary":
            winding_name = f"Secondary_{type_count[1]}"
            winding_mat = "copper - {} {}_{}".format(wp["material"]["composition"], wp["material"]["wireDiameter"], wp["material"]["strandNumber"])
            my_hui = m3d.materials.add_material(winding_mat)
            my_hui.permittivity = 0.999991
            my_hui.conductivity = 58000000
            my_hui.stacking_type = "Litz Wire"
            my_hui.wire_diameter = wp["material"]["wireDiameter"]
            my_hui.strand_number = wp["material"]["strandNumber"]
            m3d.assign_material(winding_name, winding_mat)
            winding_dict[winding_name] = int(wp["windingNumber"])
            type_count[1] += 1
            
        elif wp["type"] == "bias":
            winding_name = f"Bias_{type_count[2]}"
            winding_mat = "copper - {} {}_{}".format(wp["material"]["composition"], wp["material"]["wireDiameter"], wp["material"]["strandNumber"])
            my_hui = m3d.materials.add_material(winding_mat)
            my_hui.permittivity = 0.999991
            my_hui.conductivity = 58000000
            my_hui.stacking_type = "Litz Wire"
            my_hui.wire_diameter = wp["material"]["wireDiameter"]
            my_hui.strand_number = wp["material"]["strandNumber"]
            m3d.assign_material(winding_name, winding_mat)
            type_count[2] += 1
            
        else:
            winding_name = f"Shield_{type_count[3]}"
            winding_mat = "copper - {} {}_{}".format(wp["material"]["composition"], wp["material"]["wireDiameter"], wp["material"]["strandNumber"])
            my_hui = m3d.materials.add_material(winding_mat)
            my_hui.permittivity = 0.999991
            my_hui.conductivity = 58000000
            if wp["material"]["composition"] == "Litz":
                my_hui.stacking_type = "Litz Wire"
                my_hui.wire_diameter = wp["material"]["wireDiameter"]
                my_hui.strand_number = wp["material"]["strandNumber"]
            else:
                my_hui.stacking_type = "Solid"

            m3d.assign_material(winding_name, winding_mat)
            type_count[3] += 1

    ###############################################################################
    # Create boundaries
    # ~~~~~~~~~~~~~~~~~
    # Create the boundaries. A region with openings is needed to run the analysis.
    region = m3d.modeler.create_air_region(x_pos=100, y_pos=100, z_pos=100, x_neg=100, y_neg=100, z_neg=100)
    m3d.assign_material(region, "vacuum")

    ###############################################################################
    # Create Sheets
    # ~~~~~~~~~~~~~~~~~
    winding_p = []
    winding_s = []
    for name in m3d.modeler.model_objects:
        if "Primary" in name:
            winding_p.append(name)
        if "Secondary" in name:
            winding_s.append(name)

    winding_list = winding_p+ winding_s
    m3d.modeler.section(winding_list, "YZ")


    # Separate Sheets
    sheet_list = []
    for name in winding_list:
        #sheet_obj_list.append(m3d.modeler.get_object_from_name(name + "_Section1"))
        sheet_list.append(name + "_Section1")

    del_sheet_list = m3d.modeler.separate_bodies(sheet_list)
    m3d.modeler.delete(del_sheet_list)

    ###############################################################################
    # Assign excitations
    # ~~~~~~~~~~~~~~~~~~
    windingname_p = "Winding_p"
    windingname_s = "Winding_s"

    winConfig = receive_dict["winding"]["windingConfiguration"]
    # Assign coil.
    # Create Winding1 
    winding1 = m3d.assign_winding(assignment=None)
    winding1.name = windingname_p
    winding1.props['Type'] = 'Current'
    winding1.props['Current'] = '1A'
    winding1.props['IsSolid'] = False
    #winding1.props['ParallelBranchesNum'] = '3'

    # Winding2
    # Create Winding2
    winding2 = m3d.assign_winding(assignment=None)
    winding2.name = windingname_s
    winding2.props['Type'] = 'Current'
    winding2.props['Current'] = '0A'
    winding2.props['IsSolid'] = False
    #winding2.props['ParallelBranchesNum'] = '1'

    for wcon in winConfig:
        if wcon["type"] == "primary":
            if wcon["parallel"] == True:
                winding1.props['ParallelBranchesNum'] = f'{len(winding_p)}'
            else:
                winding1.props['ParallelBranchesNum'] = '1'
        if wcon["type"] == "secondary":
            if wcon["parallel"] == True:
                winding2.props['ParallelBranchesNum'] = f'{len(winding_s)}'
            else:
                winding2.props['ParallelBranchesNum'] = '1'          

    # Winding1
    i = 1
    winding1_coils = []
    winding2_coils = []
    for sh in sheet_list:
        prefix = sh.replace('_Section1', '')
        coil = m3d.assign_coil(sh, conductors_number=winding_dict[prefix], polarity="Positive", name=f"CoilTerminal_{i}")
        if "Primary" in prefix:
            winding1_coils.append(coil.name)
        elif "Secondary" in prefix:
            winding2_coils.append(coil.name)
        i += 1

    m3d.add_winding_coils(windingname_p , winding1_coils)
    m3d.add_winding_coils(windingname_s, winding2_coils)

    # Assign core_losses
    m3d.set_core_losses(core_name, False)
    # Assign eddy_effect
    m3d.eddy_effects_on(eddy_list, enable_eddy_effects=True, enable_displacement_current=True)

    ###############################################################################
    # Create Core Gap
    # ~~~~~~~~~~~~
    gap2 = 0.01
    gap = receive_dict["config"]["gap"]

    midFace_id = m3d.modeler.get_faceid_from_position([0, 0, gap2/2], core_name)
    midFace = m3d.modeler.get_face_by_id(midFace_id)
    midFace_obj = midFace.create_object()

    if gap < 2:
        midFace_obj.move([0, 0, 0])
        cut_cube = midFace_obj.sweep_along_vector([0, 0, gap])
    else:
        midFace_obj.move([0, 0, -(gap2+ gap/2)])
        cut_cube = midFace_obj.sweep_along_vector([0, 0, gap+ gap2])

    core_obj = m3d.modeler.get_object_from_name(core_name)
    core_obj.subtract(cut_cube, keep_originals=False)

    ###############################################################################
    # Assign Matrix
    # ~~~~~~~~~~~~
    matrix_name = "MyMatrix"
    m3d.assign_matrix([windingname_p, windingname_s], matrix_name=matrix_name)

    ###############################################################################
    # Create setup
    # ~~~~~~~~~~~~
    # Create a setup with a sweep to run the simulation. Depending on your machine's
    # computing power, the simulation can take some time to run.
    freq = receive_dict["config"]["fs"] # unit kHz

    setup_name = "MySetup"
    setup = m3d.create_setup(name=setup_name)
    #print(setup.props)
    setup['MaximumPasses'] = 10
    setup['PercentError'] = 1
    setup['MinimumPasses'] = 2
    setup['MinimumConvergedPasses'] = 2
    setup['Frequency'] = f'{freq}kHz'

    ###############################################################################
    # Analyze the setup
    # ~~~~~~~~~~~~
    m3d.analyze_setup(setup_name)

    post = m3d.post

    p_expressions = [f"{matrix_name}.L({windingname_p},{windingname_p})"]
    p_setup_sweep_name = f"{setup_name} : LastAdaptive"

    solution = post.get_solution_data(expressions = p_expressions,
                                    setup_sweep_name = p_setup_sweep_name)

    #solution.export_data_to_csv('E:\\FreeCAD\\Maxwell\\Example\\txthui.csv', ',')
    #solution.plot()
    sim_lmp = solution.data_real()[0]

    true_lmp = receive_dict["config"]["lmp"]


    alpha = true_lmp / sim_lmp  
    pre_gap = gap
    adj_gap = pre_gap

    error = 0.03 

    oEditor = m3d.modeler.oeditor
    iterate_times = 0

    while(not (1-error <= alpha <= 1+error)):
        # Adjust gap
        iterate_times += 1
        
        adj_gap = pre_gap / alpha
        print("iterate_times:", iterate_times)
        print("true_lmp:", true_lmp)
        print("sim_lmp:", sim_lmp)
        print("pre_gap:", pre_gap)
        print("adj_gap:", adj_gap)
        if adj_gap < 2:
            move_z = 0
            sweep_z = adj_gap
        else:
            move_z = -(gap2+ adj_gap/2)
            sweep_z = gap2+ adj_gap
        
        oEditor.ChangeProperty(
            [
                "NAME:AllTabs",
                [
                    "NAME:Geometry3DCmdTab",
                    [
                        "NAME:PropServers", 
                        f"{midFace_obj.name}:Move:1"
                    ],
                    [
                        "NAME:ChangedProps",
                        [
                            "NAME:Move Vector",
                            "X:="			, "0mm",
                            "Y:="			, "0mm",
                            "Z:="			, f"{move_z}mm"
                        ]
                    ]
                ]
            ])    
        
        oEditor.ChangeProperty(
            [
                "NAME:AllTabs",
                [
                    "NAME:Geometry3DCmdTab",
                    [
                        "NAME:PropServers", 
                        f"{midFace_obj.name}:SweepAlongVector:1"
                    ],
                    [
                        "NAME:ChangedProps",
                        [
                            "NAME:Vector",
                            "X:="			, "0mm",
                            "Y:="			, "0mm",
                            "Z:="			, f"{sweep_z}mm"
                        ]
                    ]
                ]
            ])
        
        m3d.analyze_setup(setup_name)
        
        p_expressions = [f"{matrix_name}.L({windingname_p},{windingname_p})"]
        p_setup_sweep_name = f"{setup_name} : LastAdaptive"

        solution = post.get_solution_data(expressions = p_expressions,
                                        setup_sweep_name = p_setup_sweep_name)

        sim_lmp = solution.data_real()[0]
        # Update the alpha & pre_gap
        alpha = true_lmp / sim_lmp
        pre_gap = adj_gap
    else:
        print("final_lmp:", sim_lmp)  
        print("final_gap:", adj_gap)

    ###############################################################################

    p_expressions = [f"{matrix_name}.CplCoef({windingname_p},{windingname_s})"]
    p_setup_sweep_name = f"{setup_name} : LastAdaptive"

    solution = post.get_solution_data(expressions = p_expressions,
                                    setup_sweep_name = p_setup_sweep_name)

    lm = sim_lmp
    k12 = solution.data_real()[0]
    lk = lm * (1 - k12**2)

    # Get the volume of the core_obj
    vol_core = core_obj.volume

    ###############################################################################
    # Add Transient Design
    # ~~~~~~~~~~~~
    trans_design_name = 'Maxwell3DDesign_Trans'
    oProject = m3d.oproject
    oProject.CopyDesign(eddy_design_name)
    oProject.Paste()
    oDesign = oProject.GetActiveDesign()
    #oDesign.GetName()
    oDesign.SetSolutionType("Transient")
    oDesign.RenameDesignInstance(oDesign.GetName(), trans_design_name)

    #oProject.InsertDesign("Maxwell 3D", trans_design_name, "Transient", "")
    m3d.set_active_design(trans_design_name)

    ###############################################################################
    # Assign excitations
    # ~~~~~~~~~~~~~~~~~~
    # Add Datasets
    oModule = oDesign.GetModule("BoundarySetup")
    oModule.DeleteAllExcitations()

    windingname_p = "Winding_p"
    windingname_s = "Winding_s"

    winConfig = receive_dict["winding"]["windingConfiguration"]
    # Assign coil.
    # Create Winding1 
    winding1 = m3d.assign_winding(assignment=None)
    winding1.name = windingname_p
    winding1.props['Type'] = 'Current'
    #winding1.props['Current'] = '1A'
    winding1.props['IsSolid'] = False
    #winding1.props['ParallelBranchesNum'] = '3'

    # Winding2
    # Create Winding2
    winding2 = m3d.assign_winding(assignment=None)
    winding2.name = windingname_s
    winding2.props['Type'] = 'Current'
    #winding2.props['Current'] = '0A'
    winding2.props['IsSolid'] = False
    #winding2.props['ParallelBranchesNum'] = '1'

    for wcon in winConfig:
        if wcon["type"] == "primary":
            tab_ip1_path = str(Path(ENV_PATH) / Path(wcon["tabFilePath"]))
            if wcon["parallel"] == True:
                winding1.props['ParallelBranchesNum'] = f'{len(winding_p)}'
            else:
                winding1.props['ParallelBranchesNum'] = '1'
        if wcon["type"] == "secondary":
            tab_is1_path = str(Path(ENV_PATH) / Path(wcon["tabFilePath"]))
            if wcon["parallel"] == True:
                winding2.props['ParallelBranchesNum'] = f'{len(winding_s)}'
            else:
                winding2.props['ParallelBranchesNum'] = '1'          

    m3d.import_dataset1d(tab_ip1_path, name="Ip1", is_project_dataset=False)
    m3d.import_dataset1d(tab_is1_path, name="Is1", is_project_dataset=False)
    winding1.props['Current'] = 'pwl_periodic(Ip1, time)'
    winding2.props['Current'] = 'pwl_periodic(Is1, time)'

    # Winding1
    i = 1
    winding1_coils = []
    winding2_coils = []
    for sh in sheet_list:
        prefix = sh.replace('_Section1', '')
        coil = m3d.assign_coil(sh, conductors_number=winding_dict[prefix], polarity="Positive", name=f"CoilTerminal_{i}")
        if "Primary" in prefix:
            winding1_coils.append(coil.name)
        elif "Secondary" in prefix:
            winding2_coils.append(coil.name)
        i += 1

    m3d.add_winding_coils(windingname_p , winding1_coils)
    m3d.add_winding_coils(windingname_s, winding2_coils)

    # Assign core_losses
    m3d.set_core_losses(core_name, False)
    # Assign eddy_effect
    m3d.eddy_effects_on(eddy_list, enable_eddy_effects=True, enable_displacement_current=True)
    ###############################################################################
    # Create setup
    # ~~~~~~~~~~~~
    # Create a setup with a sweep to run the simulation. Depending on your machine's
    # computing power, the simulation can take some time to run.
    #freq = receive_dict["config"]["fs"] # unit kHz

    setup_name = "MySetup"
    setup = m3d.create_setup(name=setup_name)
    oModule = setup.omodule
    #samples = 101
    period_count = 2
    samples_period = 50

    full_period_simu = True
    time_step = f"{1e03/freq/samples_period}us"
    stop_time = f"{period_count*1e03/freq}us"
    if full_period_simu:
        field_start = "0.0us"
        field_end = stop_time
    else:
        field_start = f"{1e03/freq}us"
        field_end = stop_time


    """
    setup['MeshLink'] = {"ImportMesh" : True,
                        "Project" : "This Project",
                        "Product" : "Maxwell",
                        "Design" : eddy_design_name,
                        "Solu"  : "{setup_name} : LastAdaptive",
                        "Params" : {},
                        "ForceSourceToSolve" : False,
                        "PreservePartnerSoln" : False,
                        "PathRelativeTo" :  "TargetProject",
                        "ApplyMeshOp": True
                        }
    """  

    oModule.EditSetup(setup_name, 
        [
            f"NAME:{setup_name}",
            "Enabled:="		, True,
            [
                "NAME:MeshLink",
                "ImportMesh:="		, True,
                "Project:="		, "This Project*",
                "Product:="		, "Maxwell",
                "Design:="		, eddy_design_name,
                "Soln:="		, f"{setup_name} : LastAdaptive",
                [
                    "NAME:Params"
                ],
                "ForceSourceToSolve:="	, False,
                "PreservePartnerSoln:="	, False,
                "PathRelativeTo:="	, "TargetProject",
                "ApplyMeshOp:="		, True
            ],
            "NonlinearSolverResidual:=", "0.005",
            "ScalarPotential:="	, "Second Order",
            "SmoothBHCurve:="	, False,
            "StopTime:="		, stop_time,
            "TimeStep:="		, time_step,
            "OutputError:="		, False,
            "OutputPerObjectCoreLoss:=", True,
            "OutputPerObjectSolidLoss:=", False,
            "UseControlProgram:="	, False,
            "ControlProgramName:="	, "",
            "ControlProgramArg:="	, "",
            "CallCtrlProgAfterLastStep:=", False,
            "FastReachSteadyState:=", False,
            "AutoDetectSteadyState:=", False,
            "IsGeneralTransient:="	, True,
            "IsHalfPeriodicTransient:=", False,
            "SaveFieldsType:="	, "Custom",
            [
                "NAME:SweepRanges",
                [
                    "NAME:Subrange",
                    "RangeType:="		, "LinearStep",
                    "RangeStart:="		, field_start,
                    "RangeEnd:="		, field_end,
                    "RangeStep:="		, time_step
                ]
            ],
            "UseNonLinearIterNum:="	, False,
            "CacheSaveKind:="	, "Count",
            "NumberSolveSteps:="	, 1,
            "RangeStart:="		, "0s",
            "RangeEnd:="		, "0.1s"
        ])


    m3d.analyze_setup(setup_name)
    post = SISPost(m3d)

    # To get dcr, First find PerWindingStrandedLoss(Winding_p) & PerWindingStrandedLoss(Winding_s)
    # And find the average loss for the "2nd" period
    # Find the Irms for Winding_p & Wunding_s
    # Then use the formula P = I^2 * R

    #==========Transient : Time Domain==========
    p_expressions = ["CoreLoss"]
    sol_coreloss = post.get_solution_data(expressions = p_expressions)
    sol_coreloss.data_real(convert_to_SI=True) # Unit : W
    sol_coreloss.primary_sweep_values # Unit : ns

    #--------------------------------------------
    p_expressions = ["StrandedLoss"]
    sol_strandedloss = post.get_solution_data(expressions = p_expressions)
    sol_strandedloss.data_real(convert_to_SI=True) # Unit : W
    sol_strandedloss.primary_sweep_values # Unit : ns

    #--------------------------------------------
    p_expressions = ["StrandedLossAC"]
    sol_strandedlossac = post.get_solution_data(expressions = p_expressions)
    sol_strandedlossac.data_real(convert_to_SI=True) # Unit : W
    sol_strandedlossac.primary_sweep_values # Unit : ns

    #--------------------------------------------
    p_expressions = [f"PerWindingStrandedLoss({windingname_p})"]
    sol_dcloss_p = post.get_solution_data(expressions = p_expressions)
    #sol_dcloss_p.data_real(convert_to_SI=True) # Unit : W
    #sol_dcloss_p.primary_sweep_values # Unit : ns
    avg_dcloss_p = utils.avg_second_period(sol_dcloss_p.data_real(convert_to_SI=True))
    #--------------------------------------------
    p_expressions = [f"PerWindingStrandedLoss({windingname_s})"]
    sol_dcloss_s = post.get_solution_data(expressions = p_expressions)

    avg_dcloss_s = utils.avg_second_period(sol_dcloss_s.data_real(convert_to_SI=True))
    #--------------------------------------------
    p_expressions = [f"PerWindingStrandedLossAC({windingname_p})"]
    sol_acloss_p = post.get_solution_data(expressions = p_expressions)

    avg_acloss_p = utils.avg_second_period(sol_acloss_p.data_real(convert_to_SI=True))
    avg_acloss_p -= avg_dcloss_p
    #--------------------------------------------
    p_expressions = [f"PerWindingStrandedLossAC({windingname_s})"]
    sol_acloss_s = post.get_solution_data(expressions = p_expressions)

    avg_acloss_s = utils.avg_second_period(sol_acloss_s.data_real(convert_to_SI=True))
    avg_acloss_s -= avg_dcloss_s
    #--------------------------------------------
    avg_copper_loss = avg_dcloss_p + avg_dcloss_s + avg_acloss_p + avg_acloss_s
    #--------------------------------------------
    avg_coreloss = utils.avg_second_period(sol_coreloss.data_real(convert_to_SI=True))
    #--------------------------------------------
    total_loss = avg_copper_loss + avg_coreloss

    p_expressions = [f"InputCurrent({windingname_p})"]
    sol_inputIp = post.get_solution_data(expressions = p_expressions)
    rms_imputIp = utils.get_rms(sol_inputIp.data_real(convert_to_SI=True))

    p_expressions = [f"InputCurrent({windingname_s})"]
    sol_inputIs = post.get_solution_data(expressions = p_expressions)
    rms_imputIs = utils.get_rms(sol_inputIs.data_real(convert_to_SI=True))
    #--------------------------------------------
    dcrPri = avg_dcloss_p / rms_imputIp**2
    dcrSec = avg_dcloss_s / rms_imputIs**2

    full_period_list = [f"{round(i * 0.16, 2)}us" for i in range(period_count*samples_period+1)]
    if full_period_simu:
        vari_list = full_period_list
    else:
        vari_list = full_period_list[period_count::]

    slice_x, slice_y, slice_z = geometry.slice_core(receive_dict)

    plots_dir = Path(ENV_PATH) / receive_dict["magneticFieldPlotFileDirectory"]
    plots_dir.mkdir(parents=True, exist_ok=True)

    anime = post.sis_plot(
        quantity="Mag_B",
        object_list=core_obj,
        plot_type="Volume",
        variation_variable="Time",
        variation_list=vari_list,
        view="isometric",
        export_vtksz=True,
        export_plots_dir=plots_dir,
        plot_cad_objs=False,
        #scale_min=0.0,
        #scale_max=500.0
        slice_x=slice_x,
        slice_y=slice_y,
        slice_z=slice_z
        )

    ###############################################################################
    # Save project
    # ~~~~~~~~~~~~
    m3d.save_project(str(Path(project_directory) / (project_name+ ".aedt")))
    #m3d.modeler.fit_all()
    #m3d.plot(show=False, export_path=str(Path(project_directory) / "Image.jpg"), plot_air_objects=False)

    ###############################################################################
    # Close the project
    # ~~~~~~~~~~~~
    #oDesktop = m3d.odesktop
    #oDesktop.closeProject(project_name)
    m3d.close_project(project_name, save=False)
    m3d.odesktop.GetProcessID()

    ###############################################################################
    # Close AEDT
    # ~~~~~~~~~~
    # After the simulation completes, you can close AEDT or release it using the
    # :func:`pyaedt.Desktop.release_desktop` method.
    # All methods provide for saving the project before closing.

    m3d.release_desktop()

    success_file = Path(project_directory) / "SUCCESS.txt"

    return_dict = {}
    # Success
    return_dict['taskId'] = receive_dict['taskId']
    return_dict['status'] = "SUCCESS"
    return_dict['message'] = "HUIIIIIIIIIIIIIIIIYU"
    return_dict['gap'] = {
        "recommendedGap" : adj_gap,
        "lm" : lm,
        "lk" : lk,
        "dcrPri" : dcrPri,
        "dcrSec" : dcrSec
    }
    return_dict["loss"]["coreLossData"] = []
    for x, y in zip(sol_coreloss.data_real(conver_to_SI=True), sol_coreloss.primary_sweep_values):
        coord = {"xAxis": x, "y_Axis": y}
        return_dict["loss"]["coreLossData"].append(coord)

    return_dict["loss"]["strandedLossData"] = []
    for x, y in zip(sol_strandedloss.data_real(conver_to_SI=True), sol_strandedloss.primary_sweep_values):
        coord = {"xAxis": x, "y_Axis": y}
        return_dict["loss"]["strandedLossData"].append(coord)

    return_dict["loss"]["strandedLossAcData"] = []
    for x, y in zip(sol_strandedlossac.data_real(conver_to_SI=True), sol_strandedlossac.primary_sweep_values):
        coord = {"xAxis": x, "y_Axis": y}
        return_dict["loss"]["strandedLossAcData"].append(coord)

    return_dict["loss"]["avgDcLoss"] = {"pri": avg_dcloss_p, "sec": avg_dcloss_s}
    return_dict["loss"]["avgAcLoss"] = {"pri": avg_acloss_p, "sec": avg_acloss_s}
    return_dict["loss"]["avgCopperLoss"] = avg_copper_loss
    return_dict["loss"]["avgIronLoss"] = avg_coreloss
    return_dict["loss"]["avgTotalLoss"] = total_loss

    return_dict["block"] = {"length": total_length, "width": total_width, "height": total_height}
    return_dict["cost"]["coreVolume"] = vol_core

    return_dict["magneticFieldPlot"] = []
    for i, time in enumerate(vari_list):
        ftime = float(time.replace('us', ''))
        imgs = {
            "timePoint": ftime,
            "imgXY": str(plots_dir.relative_to(ENV_PATH) / f"xy_{i}.jpg"),
            "imgZX": str(plots_dir.relative_to(ENV_PATH) / f"zx_{i}.jpg"),
            "imgYZ": str(plots_dir.relative_to(ENV_PATH) / f"yz_{i}.jpg"),
            "vtk3D": str(plots_dir.relative_to(ENV_PATH) / f"3d_{i}.vtksz"),
            "centerLeg": 0.0,
            "sideLeg": 0.0,
            "topPlate": 0.0,
            "bottomPlate": 0.0
        }
        return_dict["magneticFieldPlot"].append(imgs)

    success_file.write_text(json.dumps(return_dict))

if __name__ == "__main__":
    try:
        simulate()
    except Exception as e:
        receive_dict = json.loads(SERIALIZED_DICT)

        project_directory = Path(receive_dict["macroFilePath"]).parent[2] / "AEDT_project"
        error_file = Path(project_directory) / "ERROR.txt"

        return_dict = {}
        return_dict['taskId'] = receive_dict['taskId']
        return_dict['status'] = "ERROR"
        return_dict["message"] = str(e)
        
        error_file.write_text(json.dumps(return_dict))


    
