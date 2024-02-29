class PcapWorkbench(Workbench):
    Icon = os.path.join(App.getHomePath(), 'Mod', 'PCAP', 'icons', 'Font_P.svg')
    MenuText = "PCAP v0.1"
    ToolTip = "Parametric CAD Application Platform"

    def Initialize(self):
        "This function is executed when FreeCAD starts"
        # python file where the commands are:
        import MenuBar

        Log('Loading PCAP module... done\n')

        # list of commands
        cmdlist = ["Open_File", "PCAP_Setting"]

        self.appendToolbar(
            str(QtCore.QT_TRANSLATE_NOOP("PCAP", "PCAP")), cmdlist)
        self.appendMenu(
            str(QtCore.QT_TRANSLATE_NOOP("PCAP", "PCAP")), cmdlist)

        # set DXF preferences parameters
        p = App.ParamGet("User parameter:BaseApp/Preferences/Mod/Draft")
        p.SetBool("dxfShowDialog", False)
        p.SetBool("dxfUseLegacyImporter", True)
        p.SetBool("dxfUseLegacyExporter", True)
        p.SetBool("dxfAllowDownload", True)

        p.SetBool("dxftext", False)
        p.SetBool("dxfImportPoints", False)
        p.SetBool("dxflayout", False)
        p.SetBool("dxfstarblocks", False)

        p.SetBool("dxfCreatePart", True)
        p.SetBool("dxfCreateDraft", False)
        p.SetBool("dxfCreateSketch", False)

        p.SetBool("dxfGetOriginalColors", True)
        p.SetBool("joingeometry", True) #Join Geometry
        p.SetBool("groupLayers", False) #Group layers into blocks
        p.SetBool("dxfStdSize", False) #Use standard size for texts
        p.SetBool("dxfUseDraftVisGroups", False) #Use Layers
        p.SetBool("importDxfHatches", False) #Import hatch boundaries as wires
        p.SetBool("renderPolylineWidth", False) #Render polylines with width
        p.SetBool("DiscretizeEllipses", False) #Treat ellipses and splines as polylines

        p.SetBool("dxfmesh", False) #Export 3D objects as polyface meshes
        p.SetBool("dxfExportBlocks", False) #Export Drawing Views as blocks
        p.SetBool("dxfproject", False) #Project exported objects along current view direction

        # Additional Setting
        p.SetBool("fillmode", False)
        
        # directory of ODA converter
        p.SetString("TeighaFileConverter", "./ODAFileConverter 23.4.0/ODAFileConverter.exe")


    def GetClassName(self):
        return "Gui::PythonWorkbench"

# The workbench is added
Gui.addWorkbench(PcapWorkbench())
