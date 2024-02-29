import os
from PySide2 import QtCore, QtGui, QtWidgets, QtWebEngineWidgets
import FreeCAD 
import FreeCADGui
import pcaplib
import logging
import WorkSilk

import ezdxf
from FreeCAD import Console as FCC
import ezlib

__dir__ = os.path.dirname(__file__)

class Setting:
    def __init__(self):
        # Load the UI file from the same directory as this script
        ui_path = os.path.join(FreeCAD.getHomePath(), "Mod", "PCAP", "setting.ui")
        self.widget = FreeCADGui.PySideUic.loadUi(ui_path, self)

        icon_path = os.path.join(FreeCAD.getHomePath(), "Mod", "PCAP", "icons", "Font_P.svg")
        self.widget.setWindowIcon(QtGui.QIcon(icon_path))

        # Restore size and position
        p = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/PCAP")
        w = p.GetInt("PCAPWebViewWidth", 400)
        h = p.GetInt("PCAPWebViewHeight", 700)
        self.widget.resize(w, h)

        # Additional UI fixes and tweaks
        self.widget.pushButtonChooseDir.clicked.connect(self.on_pushButtonChooseDir_clicked)
        self.widget.playButton.setDisabled(True)
        self.widget.playButton.clicked.connect(self.on_playButton_clicked)
        self.widget.saveButton.clicked.connect(self.on_saveButton_clicked)

        # dxf doc
        self.dxfdoc = None

    def show(self):
        return self.widget.show()

    @QtCore.Slot()
    def on_pushButtonChooseDir_clicked(self):
        pcaplib.validate_token()
        dir_choose = QtWidgets.QFileDialog.getExistingDirectory(None, "FileDialog", "")
        if dir_choose:
            self.set_dir_path(dir_choose)

    def set_dir_path(self, dir_path):
        self.widget.prefPCAPOutputFolder.setText(dir_path)

    def add_item_to_layer_selection(self):
        import re
        self.widget.prefPCAPListOfLayers.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)

        objects = [layer.dxf.name for layer in self.dxfdoc.layers]
        obj_array = []
        obj_botsilk = []
        obj_botmask = []
        obj_open = []
        obj_board_sink =[]
        for i in range(len(objects)):
            if  re.search('bot', objects[i].lower()):
                if re.search('silk', objects[i].lower()):
                    obj_botsilk.append(objects[i])
                elif re.search('mask|solder|paste', objects[i].lower()):
                    obj_botmask.append(objects[i])
            elif re.search('open|through|thru', objects[i].lower()):
                obj_open.append(objects[i])
            elif re.search('2\.5|1\.6', objects[i].lower()):
                obj_board_sink.append(objects[i])
            else:
                obj_array.append(objects[i])
        
        self.widget.prefPCAPLayerOfBotsilk.addItems(obj_botsilk)
        self.widget.prefPCAPLayerOfBotmask.addItems(obj_botmask)
        self.widget.prefPCAPLayerOfOpen.addItems(obj_open)
        self.widget.prefPCAPLayerOfBoardSink.addItems(obj_board_sink)
        self.widget.prefPCAPListOfLayers.addItems(obj_array)
    
    def del_item_to_layer_selection(self):
        self.widget.prefPCAPLayerOfBotsilk.clear()
        self.widget.prefPCAPLayerOfBotmask.clear()
        self.widget.prefPCAPLayerOfOpen.clear()
        self.widget.prefPCAPLayerOfBoardSink.clear()
        self.widget.prefPCAPListOfLayers.clear()
    
    def get_item_text_from_selected_items(self):
        items = self.widget.prefPCAPListOfLayers.selectedItems()
        x = []
        for i in range(len(items)):
            x.append(str(self.widget.prefPCAPListOfLayers.selectedItems()[i].text()))
        return x
    
    def get_all_selected_layers(self):
        l = []
        l.extend(self.get_item_text_from_selected_items())
        if (self.widget.prefPCAPLayerOfBotsilk.currentText()):
            l.append(self.widget.prefPCAPLayerOfBotsilk.currentText())
        if (self.widget.prefPCAPLayerOfBotmask.currentText()):
            l.append(self.widget.prefPCAPLayerOfBotmask.currentText())
        if (self.widget.prefPCAPLayerOfOpen.currentText()):
            l.append(self.widget.prefPCAPLayerOfOpen.currentText())
        if (self.widget.prefPCAPLayerOfBoardSink.currentText()):
            l.append(self.widget.prefPCAPLayerOfBoardSink.currentText())
        return l

    @QtCore.Slot()
    def on_playButton_clicked(self):
        self.widget.hide()
        #print(self.get_all_selected_layers())
        ezlib.ezprocessdxf(self.dxfdoc, self.get_all_selected_layers(), FreeCAD.ActiveDocument)
        #WorkSilk.run()

    @QtCore.Slot()
    def on_saveButton_clicked(self):
        pcaplib.set_param("prefPCAPDr", self.widget.prefPCAPDr.text())
        pcaplib.set_param("prefPCAPDboard", self.widget.prefPCAPDboard.text())
        pcaplib.set_param("prefPCAPDo", self.widget.prefPCAPDo.text())
        pcaplib.set_param("prefPCAPDl", self.widget.prefPCAPDl.text())
        pcaplib.set_param("prefPCAPDw", self.widget.prefPCAPDw.text())
        pcaplib.set_param("prefPCAPAreaBound", self.widget.prefPCAPAreaBound.text())
        pcaplib.set_param("prefPCAPOutputFolder", self.widget.prefPCAPOutputFolder.text())

        pcaplib.set_param("prefPCAPLayerOfBotsilk", self.widget.prefPCAPLayerOfBotsilk.currentText())
        pcaplib.set_param("prefPCAPLayerOfBotmask", self.widget.prefPCAPLayerOfBotmask.currentText())
        pcaplib.set_param("prefPCAPLayerOfOpen", self.widget.prefPCAPLayerOfOpen.currentText())
        pcaplib.set_param("prefPCAPLayerOfBoardSink", self.widget.prefPCAPLayerOfBoardSink.currentText())
        delimiter = ','
        pcaplib.set_param("prefPCAPLayers", delimiter.join(self.get_item_text_from_selected_items()))

    def set_dxfdoc(self, file_path):
        self.dxfdoc = ezdxf.readfile(file_path)
        FCC.PrintMessage("successfully loaded " + file_path + "\n")


