import os
from PySide2 import QtCore, QtGui, QtWidgets, QtWebEngineWidgets
import FreeCAD 
import FreeCADGui
import pcaplib
import logging
import LayerAnalysis

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
        self.widget.tabWidget.currentChanged.connect(self.on_change_tab)
        
        # QtabWidget

        # Layer of open switch
        #self.widget.layerOfOpenSwitch.setCheckable(True)
        #self.widget.layerOfOpenSwitch.clicked.connect(self.on_openSwitch_clicked)
        # layers_open : for open switch swap use
        #self.layers_open = []


        # dxf doc
        self.dxfdoc = None

        # Remember user's last settings
        #self.widget.prefPCAPOutputFolder.setText(p.GetString("prefPCAPOutputFolder", ""))
        self.outputFolder = ""
        #=====router=====
        self.widget.rtDr.setText(p.GetString("prefPCAPDr", "3.0")) #shared_1
        self.widget.rtAreaBound.setText(p.GetString("prefPCAPAreaBound", "500")) #shared_2
        self.widget.rtDboard.setText(p.GetString("prefPCAPDboard", "0.15")) #shared_3
        self.widget.rtHoleWidth.setText(p.GetString("rtHoleWidth", "6.0"))
        self.widget.rtHoleAddLen.setText(p.GetString("rtHoleAddLen", "3.0"))
        #=====unloader=====
        self.widget.ulDr.setText(p.GetString("prefPCAPDr", "3.0")) #shared_1
        self.widget.ulAreaBound.setText(p.GetString("prefPCAPAreaBound", "500")) #shared_2
        self.widget.ulDboard.setText(p.GetString("prefPCAPDboard", "0.2")) #shared_3
        self.widget.ulDl.setText(p.GetString("prefPCAPDl", "12.0"))
        self.widget.ulDw.setText(p.GetString("prefPCAPDw", "3.0"))
        #=====wave=====
        self.widget.prefPCAPDr.setText(p.GetString("prefPCAPDr", "3.0")) #shared_1
        self.widget.prefPCAPAreaBound.setText(p.GetString("prefPCAPAreaBound", "500")) #shared_2
        self.widget.prefPCAPDboard.setText(p.GetString("prefPCAPDboard", "0.2")) #shared_3
        self.widget.prefPCAPDo.setText(p.GetString("prefPCAPDo", "1.0"))
        self.widget.prefPCAPDl.setText(p.GetString("prefPCAPDl", "12.0"))
        self.widget.prefPCAPDw.setText(p.GetString("prefPCAPDw", "3.0"))
        #=====press=====
        self.widget.pressAreaBound.setText(p.GetString("prefPCAPAreaBound", "500")) #shared_2
        self.widget.pressDr.setText(p.GetString("prefPCAPDr", "3.0")) #shared_1
        self.widget.pressBlockKeepDist.setText(p.GetString("pressBlockKeepDist", "3.0"))
        self.widget.pressDistSupport.setText(p.GetString("pressBlockKeepDist", "3.0"))
        self.widget.pressSBKeepDist.setText(p.GetString("pressSBKeepDist", "3.0"))

    def show(self):
        return self.widget.show()

    @QtCore.Slot()
    def on_pushButtonChooseDir_clicked(self):
        pcaplib.validate_token()
        dir_choose = QtWidgets.QFileDialog.getExistingDirectory(None, "FileDialog", self.outputFolder)
        if dir_choose:
            self.set_dir_path(dir_choose)
    
    @QtCore.Slot()
    def on_saveButton_clicked(self):
        if self.widget.tabWidget.currentIndex() == 0:
            pcaplib.set_param("prefPCAPDr", self.widget.rtDr.text())
            pcaplib.set_param("prefPCAPDboard", self.widget.rtDboard.text())
            pcaplib.set_param("rtHoleWidth", self.widget.rtHoleWidth.text())
            pcaplib.set_param("rtHoleAddLen", self.widget.rtHoleAddLen.text())
            pcaplib.set_param("prefPCAPAreaBound", self.widget.rtAreaBound.text())

            pcaplib.set_param("prefPCAPLayerOfBotsilk", self.widget.rtLayerOfBotsilk.currentText())
            pcaplib.set_param("prefPCAPLayerOfBotpaste", self.widget.rtLayerOfBotpaste.currentText())
            pcaplib.set_param("prefPCAPLayerOfBoardSink", self.widget.rtLayerOfBoardSink.currentText())
            pcaplib.set_param("prefPCAPLayerOfOpen", self.widget.rtLayerOfOpen.currentText())
            pcaplib.set_param("rtLayerOfRouterEdge", self.widget.rtLayerOfRouterEdge.currentText())
            delimiter = ','
            pcaplib.set_param("rtLayers", delimiter.join(self.get_item_text_from_selected_items(self.widget.rtListOfLayers)))
        elif self.widget.tabWidget.currentIndex() == 1:
            pcaplib.set_param("prefPCAPDr", self.widget.ulDr.text())
            pcaplib.set_param("prefPCAPDboard", self.widget.ulDboard.text())
            pcaplib.set_param("prefPCAPDl", self.widget.ulDl.text())
            pcaplib.set_param("prefPCAPDw", self.widget.ulDw.text())
            pcaplib.set_param("prefPCAPAreaBound", self.widget.ulAreaBound.text())

            pcaplib.set_param("prefPCAPLayerOfBotsilk", self.widget.ulLayerOfBotsilk.currentText())
            pcaplib.set_param("prefPCAPLayerOfBotpaste", self.widget.ulLayerOfBotpaste.currentText())
            pcaplib.set_param("prefPCAPLayerOfBotmask", self.widget.ulLayerOfBotmask.currentText())
            pcaplib.set_param("prefPCAPLayerOfBoardSink", self.widget.ulLayerOfBoardSink.currentText())
            delimiter = ','
            pcaplib.set_param("ulLayers", delimiter.join(self.get_item_text_from_selected_items(self.widget.ulListOfLayers)))
        elif self.widget.tabWidget.currentIndex() == 2:
            pcaplib.set_param("prefPCAPDr", self.widget.prefPCAPDr.text())
            pcaplib.set_param("prefPCAPDboard", self.widget.prefPCAPDboard.text())
            pcaplib.set_param("prefPCAPDo", self.widget.prefPCAPDo.text())
            pcaplib.set_param("prefPCAPDl", self.widget.prefPCAPDl.text())
            pcaplib.set_param("prefPCAPDw", self.widget.prefPCAPDw.text())
            pcaplib.set_param("prefPCAPAreaBound", self.widget.prefPCAPAreaBound.text())

            pcaplib.set_param("prefPCAPLayerOfBotsilk", self.widget.prefPCAPLayerOfBotsilk.currentText())
            pcaplib.set_param("prefPCAPLayerOfBotpaste", self.widget.prefPCAPLayerOfBotpaste.currentText())
            pcaplib.set_param("prefPCAPLayerOfBotmask", self.widget.prefPCAPLayerOfBotmask.currentText())
            pcaplib.set_param("prefPCAPLayerOfOpen", self.widget.prefPCAPLayerOfOpen.currentText())
            pcaplib.set_param("prefPCAPLayerOfBoardSink", self.widget.prefPCAPLayerOfBoardSink.currentText())
            delimiter = ','
            pcaplib.set_param("prefPCAPLayers", delimiter.join(self.get_item_text_from_selected_items(self.widget.prefPCAPListOfLayers)))
        elif self.widget.tabWidget.currentIndex() == 3:
            pcaplib.set_param("prefPCAPDr", self.widget.pressDr.text()) # Shared parameter
            pcaplib.set_param("pressBlockKeepDist", self.widget.pressBlockKeepDist.text())
            pcaplib.set_param("pressSBKeepDist", self.widget.pressSBKeepDist.text())
            pcaplib.set_param("pressDistSupport", self.widget.pressDistSupport.text())
            pcaplib.set_param("prefPCAPAreaBound", self.widget.pressAreaBound.text()) # Shared parameter

            pcaplib.set_param("prefPCAPLayerOfBotsilk", self.widget.pressLayerOfBotsilk.currentText())
            pcaplib.set_param("prefPCAPLayerOfBotpaste", self.widget.pressLayerOfBotpaste.currentText())
            pcaplib.set_param("pressLayerOfFixedPin", self.widget.pressLayerOfFixedPin.currentText())
            pcaplib.set_param("pressLayerOfSupportPin", self.widget.pressLayerOfSupportPin.currentText())
            pcaplib.set_param("pressLayerOfSupportBlock", self.widget.pressLayerOfSupportBlock.currentText())
            pcaplib.set_param("pressLayerOfStopBlock", self.widget.pressLayerOfStopBlock.currentText())
            pcaplib.set_param("pressLayerOfPressfit", self.widget.pressLayerOfPressfit.currentText())
            delimiter = ','
            pcaplib.set_param("pressLayers", delimiter.join(self.get_item_text_from_selected_items(self.widget.pressListOfLayers)))
        
        pcaplib.set_param("prefPCAPOutputFolder", self.widget.prefPCAPOutputFolder.text())
        # Enable play button not until click save button
        self.widget.playButton.setDisabled(False)

    @QtCore.Slot()
    def on_playButton_clicked(self):
        self.widget.hide()
        if self.widget.tabWidget.currentIndex() == 0:
            ezlib.ezprocessdxf(self.dxfdoc, self.get_all_selected_layers('router'), FreeCAD.ActiveDocument)
            #LayerAnalysis.run_router()
        elif self.widget.tabWidget.currentIndex() == 1:
            ezlib.ezprocessdxf(self.dxfdoc, self.get_all_selected_layers('unloader'), FreeCAD.ActiveDocument)
            #LayerAnalysis.run_unloader()
        elif self.widget.tabWidget.currentIndex() == 2:
            ezlib.ezprocessdxf(self.dxfdoc, self.get_all_selected_layers('wave'), FreeCAD.ActiveDocument)
            LayerAnalysis.run_wave()
        elif self.widget.tabWidget.currentIndex() == 3:
            ezlib.ezprocessdxf(self.dxfdoc, self.get_all_selected_layers('press'), FreeCAD.ActiveDocument)
            #LayerAnalysis.run_press()

    @QtCore.Slot()
    def on_change_tab(self):
        self.widget.playButton.setDisabled(True)

    #@QtCore.Slot()
    #def on_openSwitch_clicked(self):
    #    if self.widget.layerOfOpenSwitch.isChecked():
    #        pcaplib.set_param("prefPCAPLayerOfOpenSwitch", True, "Bool")
    #        if self.layers_open:
    #            self.widget.prefPCAPLayerOfOpen.addItems(self.layers_open)
    #            qListWidget = self.widget.prefPCAPListOfLayers
    #            for layer in self.layers_open:
    #                for i in reversed(range(qListWidget.count())):
    #                    if qListWidget.item(i).text() == layer:
    #                        qListWidget.takeItem(i)
    #                        break

    #    else:
    #        pcaplib.set_param("prefPCAPLayerOfOpenSwitch", False, "Bool")
    #        if self.layers_open:
    #            self.widget.prefPCAPLayerOfOpen.clear()
    #            self.widget.prefPCAPListOfLayers.addItems(self.layers_open)

    def set_dir_path(self, dir_path):
        self.widget.prefPCAPOutputFolder.setText(dir_path)

    def add_item_to_layer_selection(self):
        import re
        self.widget.rtListOfLayers.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.widget.ulListOfLayers.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.widget.prefPCAPListOfLayers.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.widget.pressListOfLayers.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)

        objects = [layer.dxf.name for layer in self.dxfdoc.layers]
        obj_array = []
        obj_botsilk = []
        obj_botpaste = []
        obj_botmask = []
        obj_open = []
        obj_board_sink = []
        obj_fixed_pin = []
        obj_support_pin = []
        obj_support_block = []
        obj_stop_block = []
        obj_pressfit = []
        obj_edge = []
        for i in range(len(objects)):
            if  re.search('bot', objects[i].lower()):
                if re.search('silk', objects[i].lower()):
                    obj_botsilk.append(objects[i])
                elif re.search('mask', objects[i].lower()):
                    obj_botmask.append(objects[i])
                elif re.search('paste', objects[i].lower()):
                    obj_botpaste.append(objects[i])
            elif re.search('open|through|thru', objects[i].lower()):
                obj_open.append(objects[i])
            elif re.search('2\.5|1\.6', objects[i].lower()):
                obj_board_sink.append(objects[i])
            elif re.search('fixed.*pin|pin.*fixed', objects[i].lower()):
                obj_fixed_pin.append(objects[i])
            elif re.search('support.*pin|pin.*support', objects[i].lower()):
                obj_support_pin.append(objects[i])
            elif re.search('support.*block|block.*support', objects[i].lower()):
                obj_support_block.append(objects[i])
            elif re.search('stop.*block|block.*stop', objects[i].lower()):
                obj_stop_block.append(objects[i])
            elif re.search('press.*fit', objects[i].lower()):
                obj_pressfit.append(objects[i])
            elif re.search('edge', objects[i].lower()):
                obj_edge.append(objects[i])
            else:
                obj_array.append(objects[i])
        
        # Add Layers For Unloader : tabWidget index = 0
        self.widget.rtLayerOfBotsilk.addItems(obj_botsilk)
        self.widget.rtLayerOfBotpaste.addItems(obj_botpaste)
        self.widget.rtLayerOfBoardSink.addItems(obj_board_sink)
        self.widget.rtLayerOfOpen.addItems(obj_open)
        self.widget.rtLayerOfRouterEdge.addItems(obj_edge)
        self.widget.rtListOfLayers.addItems(obj_array + obj_botmask + obj_fixed_pin + obj_stop_block + obj_pressfit + obj_support_pin + obj_support_block)

        # Add Layers For Unloader : tabWidget index = 1
        self.widget.ulLayerOfBotsilk.addItems(obj_botsilk)
        self.widget.ulLayerOfBotpaste.addItems(obj_botpaste)
        self.widget.ulLayerOfBotmask.addItems(obj_botmask)
        self.widget.ulLayerOfBoardSink.addItems(obj_board_sink)
        self.widget.ulListOfLayers.addItems(obj_array + obj_open + obj_fixed_pin + obj_stop_block + obj_pressfit + obj_edge+ obj_support_pin + obj_support_block)

        # Add Layers For Wave_Solder : tabWidget index = 2
        self.widget.prefPCAPLayerOfBotsilk.addItems(obj_botsilk)
        self.widget.prefPCAPLayerOfBotpaste.addItems(obj_botpaste)
        self.widget.prefPCAPLayerOfBotmask.addItems(obj_botmask)
        self.widget.prefPCAPLayerOfOpen.addItems(obj_open)
        self.widget.prefPCAPLayerOfBoardSink.addItems(obj_board_sink)
        self.widget.prefPCAPListOfLayers.addItems(obj_array + obj_fixed_pin + obj_stop_block + obj_pressfit + obj_edge+ obj_support_pin + obj_support_block)
        
        # Add Layers For Press_Fit : tabWidget index = 3
        self.widget.pressLayerOfBotsilk.addItems(obj_botsilk)
        self.widget.pressLayerOfBotpaste.addItems(obj_botpaste)
        self.widget.pressLayerOfFixedPin.addItems(obj_fixed_pin)
        self.widget.pressLayerOfSupportPin.addItems(obj_support_pin)
        self.widget.pressLayerOfSupportBlock.addItems(obj_support_block)
        self.widget.pressLayerOfStopBlock.addItems(obj_stop_block)
        self.widget.pressLayerOfPressfit.addItems(obj_pressfit)
        self.widget.pressListOfLayers.addItems(obj_array + obj_botmask +  obj_board_sink + obj_open + obj_edge)

        # layers_open : for open switch swap use
        #self.layers_open = obj_open 
        #if obj_open:
        #    pcaplib.set_param("prefPCAPLayerOfOpenSwitch", True, "Bool")
        #    self.widget.layerOfOpenSwitch.setChecked(True)
        #else:
        #    pcaplib.set_param("prefPCAPLayerOfOpenSwitch", False, "Bool")
        #    self.widget.layerOfOpenSwitch.setChecked(False)

    
    def del_item_to_layer_selection(self):
        # Delete Layers For Router : tabWidget index = 0
        self.widget.rtLayerOfBotsilk.clear()
        self.widget.rtLayerOfBotpaste.clear()
        self.widget.rtLayerOfBoardSink.clear()
        self.widget.rtLayerOfOpen.clear()
        self.widget.rtLayerOfRouterEdge.clear()
        self.widget.rtListOfLayers.clear()

        # Delete Layers For Unloader tabWidget index = 1
        self.widget.ulLayerOfBotsilk.clear()
        self.widget.ulLayerOfBotpaste.clear()
        self.widget.ulLayerOfBotmask.clear()
        self.widget.ulLayerOfBoardSink.clear()
        self.widget.ulListOfLayers.clear()

        # Delete Layers For Wave_Solder : tabWidget index = 2
        self.widget.prefPCAPLayerOfBotsilk.clear()
        self.widget.prefPCAPLayerOfBotpaste.clear()
        self.widget.prefPCAPLayerOfBotmask.clear()
        self.widget.prefPCAPLayerOfOpen.clear()
        self.widget.prefPCAPLayerOfBoardSink.clear()
        self.widget.prefPCAPListOfLayers.clear()

        # Delete Layers For Press_Fit : tabWidget index = 3
        self.widget.pressLayerOfBotsilk.clear()
        self.widget.pressLayerOfBotpaste.clear()
        self.widget.pressLayerOfFixedPin.clear()
        self.widget.pressLayerOfSupportPin.clear()
        self.widget.pressLayerOfSupportBlock.clear()
        self.widget.pressLayerOfStopBlock.clear()
        self.widget.pressLayerOfPressfit.clear()
        self.widget.pressListOfLayers.clear()
    
    def get_item_text_from_selected_items(self, listWidget):
        items = listWidget.selectedItems()
        x = []
        for i in range(len(items)):
            x.append(str(listWidget.selectedItems()[i].text()))
        return x
    
    def get_all_selected_layers(self, case):
        l = []
        if case == "router":
            l.extend(self.get_item_text_from_selected_items(self.widget.rtListOfLayers))
            if (self.widget.rtLayerOfBotsilk.currentText()):
                l.append(self.widget.rtLayerOfBotsilk.currentText())
            if (self.widget.rtLayerOfBotpaste.currentText()):
                l.append(self.widget.rtLayerOfBotpaste.currentText())
            if (self.widget.rtLayerOfBoardSink.currentText()):
                l.append(self.widget.rtLayerOfBoardSink.currentText())
            if (self.widget.rtLayerOfOpen.currentText()):
                l.append(self.widget.rtLayerOfOpen.currentText())
            if (self.widget.rtLayerOfRouterEdge.currentText()):
                l.append(self.widget.rtLayerOfRouterEdge.currentText())
        elif case == "unloader":
            l.extend(self.get_item_text_from_selected_items(self.widget.ulListOfLayers))
            if (self.widget.ulLayerOfBotsilk.currentText()):
                l.append(self.widget.ulLayerOfBotsilk.currentText())
            if (self.widget.ulLayerOfBotpaste.currentText()):
                l.append(self.widget.ulLayerOfBotpaste.currentText())
            if (self.widget.ulLayerOfBotmask.currentText()):
                l.append(self.widget.ulLayerOfBotmask.currentText())
            if (self.widget.ulLayerOfBoardSink.currentText()):
                l.append(self.widget.ulLayerOfBoardSink.currentText())
        elif case == "wave":
            l.extend(self.get_item_text_from_selected_items(self.widget.prefPCAPListOfLayers))
            if (self.widget.prefPCAPLayerOfBotsilk.currentText()):
                l.append(self.widget.prefPCAPLayerOfBotsilk.currentText())
            if (self.widget.prefPCAPLayerOfBotpaste.currentText()):
                l.append(self.widget.prefPCAPLayerOfBotpaste.currentText())
            if (self.widget.prefPCAPLayerOfBotmask.currentText()):
                l.append(self.widget.prefPCAPLayerOfBotmask.currentText())
            if (self.widget.prefPCAPLayerOfOpen.currentText()):
                l.append(self.widget.prefPCAPLayerOfOpen.currentText())
            if (self.widget.prefPCAPLayerOfBoardSink.currentText()):
                l.append(self.widget.prefPCAPLayerOfBoardSink.currentText())
        elif case == "press":
            l.extend(self.get_item_text_from_selected_items(self.widget.pressListOfLayers))
            if (self.widget.pressLayerOfBotsilk.currentText()):
                l.append(self.widget.pressLayerOfBotsilk.currentText())
            if (self.widget.pressLayerOfBotpaste.currentText()):
                l.append(self.widget.pressLayerOfBotpaste.currentText())
            if (self.widget.pressLayerOfFixedPin.currentText()):
                l.append(self.widget.pressLayerOfFixedPin.currentText())
            if (self.widget.pressLayerOfSupportPin.currentText()):
                l.append(self.widget.pressLayerOfSupportPin.currentText())
            if (self.widget.pressLayerOfSupportBlock.currentText()):
                l.append(self.widget.pressLayerOfSupportBlock.currentText())
            if (self.widget.pressLayerOfStopBlock.currentText()):
                l.append(self.widget.pressLayerOfStopBlock.currentText())
            if (self.widget.pressLayerOfPressfit.currentText()):
                l.append(self.widget.pressLayerOfPressfit.currentText())
        
        return l

    def set_dxfdoc(self, file_path):
        self.outputFolder = os.path.dirname(file_path)
        self.dxfdoc = ezdxf.readfile(file_path)
        FCC.PrintMessage("successfully loaded " + file_path + "\n")
