import os
from PySide import QtCore, QtGui
import FreeCAD
import FreeCADGui
import pcaplib
from OpenFile import OpenFile
from PCAPSetting import Setting

__dir__ = os.path.dirname(__file__)
openF = OpenFile()
setting = Setting()

class _RunValidation:
    """Command to open a DXF file and run validation
    """

    def Activated(self):
        try:
            file_path = openF.open_file_in_freecad()
            if file_path:
                setting.set_dxfdoc(file_path)
                setting.del_item_to_layer_selection()
                setting.add_item_to_layer_selection()
                setting.widget.playButton.setDisabled(False)
        except Exception as e:
            print(f"Error: {e}")

    def GetResources(self):
        # Icon and command information
        menu_text = QtCore.QT_TRANSLATE_NOOP('Fixture Validation', 'Open file')
        tool_tip = QtCore.QT_TRANSLATE_NOOP('Open...', 'Open *.dxf file')
        return {
            'Pixmap': os.path.join(__dir__, 'icons', 'search.svg'),
            'MenuText': menu_text,
            'ToolTip': tool_tip}

    def IsActive(self):
        # The command will be active if there is an active document
        #return not FreeCAD.ActiveDocument is None
        return True

class _Setting:
    """Command to show the PCAP setting dialog
    """

    def Activated(self):
        setting.show()

    def GetResources(self):
        # Icon and command information
        menu_text = QtCore.QT_TRANSLATE_NOOP('Validation Setting', 'Setting')
        tool_tip = QtCore.QT_TRANSLATE_NOOP('Setting', 'Set up Parameters')
        return {
            'Pixmap': os.path.join(__dir__, 'icons', 'setting.svg'),
            'MenuText': menu_text,
            'ToolTip': tool_tip}

    def IsActive(self):
        # The command will be active if there is an active document
        return not FreeCAD.ActiveDocument is None

# GUI commands that link the Python scripts
FreeCADGui.addCommand('Open_File', _RunValidation())
FreeCADGui.addCommand('PCAP_Setting', _Setting())
