import FreeCAD
import os
import glob
import logging

def get_param(param_name):
    FSParam = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/PCAP")
    return FSParam.GetString(param_name)

# Router
def get_rt_hole_width():
    return get_param("rtHoleWidth")
def get_rt_hole_add_len():
    return get_param("rtHoleAddLen")
def get_rt_d_guide_pin_inside():
    return get_param("rtDGuidePinInside")
def get_rt_d_guide_pin_break_away():
    return get_param("rtDGuidePinBreakAway")

def get_rt_layer_of_guide_pin():
    return get_param("rtLayerOfGuidePin")
def get_rt_layer_of_router_edge():
    return get_param("rtLayerOfRouterEdge")
def get_rt_layers():
    return get_param("rtLayers")

# Wave
def get_pcap_dxf_file_path():
    return get_param("prefPCAPDXFFilePath")

def get_pcap_dr():
    return get_param("prefPCAPDr")

def get_pcap_d_board():
    return get_param("prefPCAPDboard")

def get_pcap_do():
    return get_param("prefPCAPDo")

def get_pcap_dl():
    return get_param("prefPCAPDl")

def get_pcap_dw():
    return get_param("prefPCAPDw")

def get_pcap_area_bound():
    return get_param("prefPCAPAreaBound")

def get_pcap_layer_of_botsilk():
    return get_param("prefPCAPLayerOfBotsilk")

def get_pcap_layer_of_botpaste():
    return get_param("prefPCAPLayerOfBotpaste")

def get_pcap_layer_of_botmask():
    return get_param("prefPCAPLayerOfBotmask")

def get_pcap_layer_of_open():
    return get_param("prefPCAPLayerOfOpen")

def get_pcap_layer_of_board_sink():
    return get_param("prefPCAPLayerOfBoardSink")

def get_pcap_dxf_layers():
    return get_param("prefPCAPLayers")

# Pressfit
def get_press_block_keep_dist():
    return get_param("pressBlockKeepDist")
def get_press_sb_keep_dist():
    return get_param("pressSBKeepDist")
def get_press_dist_support():
    return get_param("pressDistSupport")

def get_press_layer_of_fixed_pin():
    return get_param("pressLayerOfFixedPin")
def get_press_layer_of_support_pin():
    return get_param("pressLayerOfSupportPin")
def get_press_layer_of_support_block():
    return get_param("pressLayerOfSupportBlock")
def get_press_layer_of_stop_block():
    return get_param("pressLayerOfStopBlock")
def get_press_layer_of_pressfit():
    return get_param("pressLayerOfPressfit")
def get_press_layers():
    return get_param("pressLayers")
    
#=============================== 
def get_pcap_output_folder():
    return get_param("prefPCAPOutputFolder")

def set_param(param_name, value, type="String"):
    FSParam = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/PCAP")
    if type == "String":
        FSParam.SetString(param_name, value)
    if type == "Bool":
        FSParam.SetBool(param_name, value)

def get_token_by_plugin():
    folder_path = os.path.join('C:\\Users\\', os.environ.get('USERNAME'), 'AppData\\Local\\FreeCAD\\QtWebEngine\\Default\\Local Storage\\leveldb\\*.log')
    files = glob.glob(folder_path)
    
    latest_file_path = max(files, key=os.path.getctime)

    with open(latest_file_path, encoding='latin-1') as f:
        line = f.read()

    token = line[line.rfind("user.token") + 13:]
    return token

def validate_token():
    plugin_token = get_token_by_plugin()

    if not plugin_token:
        logging.error("Token is illegal! Please check that you are logged in as a user.")
        raise Exception("Token is illegal!")



