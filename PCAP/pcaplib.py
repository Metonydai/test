import FreeCAD
import os
import glob
import logging

def get_param(param_name):
    FSParam = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/PCAP")
    return FSParam.GetString(param_name)

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

def get_pcap_layer_of_botmask():
    return get_param("prefPCAPLayerOfBotmask")

def get_pcap_layer_of_open():
    return get_param("prefPCAPLayerOfOpen")

def get_pcap_layer_of_board_sink():
    return get_param("prefPCAPLayerOfBoardSink")

def get_pcap_dxf_layers():
    return get_param("prefPCAPLayers")
    
def get_pcap_output_folder():
    return get_param("prefPCAPOutputFolder")
    

def set_param(param_name, value):
    FSParam = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/PCAP")
    FSParam.SetString(param_name, value)

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



