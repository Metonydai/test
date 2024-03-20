import os
from PySide import QtGui
import importDXF
import pcaplib
import FreeCAD
from FreeCAD import Console as FCC

class OpenFile:
    def __init__(self):
        self.file_path = ""
        self.active_folder = os.path.join('C:\\Users\\', os.environ.get('USERNAME'))

    def _open(self):
        try:
            # Called when FreeCAD opens a file.
            pcaplib.validate_token()
            return QtGui.QFileDialog.getOpenFileName(None, "Open DXF File", self.active_folder, "*.dxf")

        except Exception as e:
            print(f"Error in _open: {e}")

    def get_file_name(self):
        pcaplib.validate_token()
        file_dialog_result = self._open()
        self.file_path = file_dialog_result[0]
        pcaplib.set_param("prefPCAPDXFFilePath", self.file_path)
        return self.file_path
    
    def open_file_in_freecad(self):
        self.get_file_name()
        if self.file_path:
            #importDXF.open(self.file_path)
            self.active_folder = os.path.dirname(self.file_path)
            FreeCAD.newDocument("DXF_Analysis")
            FreeCAD.ActiveDocument.recompute()
        return self.file_path
