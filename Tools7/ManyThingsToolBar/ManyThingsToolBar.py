import logging
import os
from typing import Annotated

import vtk, qt

import slicer
from slicer.i18n import tr as _
from slicer.i18n import translate
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

from ManyThingsToolBarLib.Utils import *
from ManyThingsToolBarLib.VirtualCathLabHelper import *
from ManyThingsToolBarLib.ResliceHelper import *
from ManyThingsToolBarLib.RemoveHelmetHelper import *
from ManyThingsToolBarLib.MISToTubeHelper import *
from ManyThingsToolBarLib.SegmentationHelper import *

# ******************************************************************************
def addQuickCropVolumeMenuItems():
    toolbarObjects = getToolBarObjects()
    if (toolbarObjects is None):
        return
    manyThingsMenu = toolbarObjects[1]
    if (manyThingsMenu is None):
        return

    separator0 = manyThingsMenu.addSeparator()
    actionCropVolumeFast = manyThingsMenu.addAction("Crop volume to current ROI")
    actionCropVolumeFast.setObjectName("ActionCropVolumeFast")
    actionCropVolumeHigh = manyThingsMenu.addAction("Crop volume to current ROI x 2")
    actionCropVolumeHigh.setObjectName("ActionCropVolumeHigh")
    actionCropVolumeFast.connect("triggered()", lambda: quickCropVolume(True))
    actionCropVolumeHigh.connect("triggered()", lambda: quickCropVolume(False))
    actionCropAndResampleVolume3 = manyThingsMenu.addAction("Crop volume to current ROI (Iso 0.3)")
    actionCropAndResampleVolume3.setObjectName("ActionCropAndResampleVolume3")
    actionCropAndResampleVolume5 = manyThingsMenu.addAction("Crop volume to current ROI (Iso 0.5)")
    actionCropAndResampleVolume5.setObjectName("ActionCropAndResampleVolume5")
    actionCropAndResampleVolume3.connect("triggered()", lambda: cropAndResampleVolumeToIsoVoxel(0.3))
    actionCropAndResampleVolume5.connect("triggered()", lambda: cropAndResampleVolumeToIsoVoxel(0.5))

# *******************************************************************************
def addResliceWidget():
    toolbarObjects = getToolBarObjects()
    if (toolbarObjects is None):
        return
    manyThingsTabWidget = toolbarObjects[3]
    if (manyThingsTabWidget is None):
        return
    
    rsWidget = ResliceHelper.createHelperWidget()
    rsWidget.setParent(manyThingsTabWidget)
    rsTabIndex = manyThingsTabWidget.addTab(rsWidget, "RS")
    manyThingsTabWidget.setTabToolTip(rsTabIndex, "Reslice to current line, plane or angle node")

# *******************************************************************************
def addMISToTubeWidget():
    toolbarObjects = getToolBarObjects()
    if (toolbarObjects is None):
        return
    manyThingsTabWidget = toolbarObjects[3]
    if (manyThingsTabWidget is None):
        return
        
    ## M2T
    m2tWidget = MISToTubeHelper.createHelperWidget()
    m2tWidget.setParent(manyThingsTabWidget)
    m2tWidget.setObjectName("M2TWidget")
    m2tTabIndex = manyThingsTabWidget.addTab(m2tWidget, "M2T")
    manyThingsTabWidget.setTabToolTip(m2tTabIndex, "Create a tube from the 'Maximum inscribed sphere' radius of a non-bifurcated centerline.")
 
# *******************************************************************************
def setupUndoRedo():
    slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.NodeAddedEvent, onNodeAdded)
    
    redoShortcuts = []
    redoKeyBindings = qt.QKeySequence.keyBindings(qt.QKeySequence.Redo)
    for redoBinding in redoKeyBindings:
        redoShortcut = qt.QShortcut(slicer.util.mainWindow())
        redoShortcut.setKey(redoBinding)
        redoShortcut.connect("activated()", onRedo)
        redoShortcuts.append(redoShortcut)

    undoShortcuts = []
    undoKeyBindings = qt.QKeySequence.keyBindings(qt.QKeySequence.Undo)
    for undoBinding in undoKeyBindings:
        undoShortcut = qt.QShortcut(slicer.util.mainWindow())
        undoShortcut.setKey(undoBinding)
        undoShortcut.connect("activated()", onUndo)
        undoShortcuts.append(undoShortcut)
    
    mw = slicer.util.mainWindow()
    customToolBar = mw.findChild(qt.QToolBar, "ManyThingsToolBar")
    if not customToolBar:
        print("Target toolbar with name 'ManyThingsToolBar' not found.")
        return
    
    undoAction = customToolBar.addAction(qt.QIcon(":/Icons/Medium/SlicerUndo.png"), "Undo", onUndo)
    redoAction = customToolBar.addAction(qt.QIcon(":/Icons/Medium/SlicerRedo.png"), "Redo", onRedo)
    # So as to access them easily with findChild()
    undoAction.setObjectName("UndoAction")
    redoAction.setObjectName("RedoAction")

# ******************************************************************************
def addRemoveHelmetWidget():
    toolbarObjects = getToolBarObjects()
    if (toolbarObjects is None):
        return
    manyThingsTabWidget = toolbarObjects[3]
    if (manyThingsTabWidget is None):
        return

    # Remove helmet.
    rhWidget = RemoveHelmetHelper.createHelperWidget()
    rhWidget.setParent(manyThingsTabWidget)
    rhTabIndex = manyThingsTabWidget.addTab(rhWidget, "RH")
    manyThingsTabWidget.setTabToolTip(rhTabIndex, "Remove metal artifacts on a CT scan of the head.")

# ******************************************************************************
def addAnonymiseSceneMenuItems():
    toolbarObjects = getToolBarObjects()
    if (toolbarObjects is None):
        return
    manyThingsMenu = toolbarObjects[1]
    if (manyThingsMenu is None):
        return
    
    separator0 = manyThingsMenu.addSeparator()
    actionAnonymiseScene = manyThingsMenu.addAction("Anonymise the scene")
    actionAnonymiseScene.setObjectName("ActionAnonymiseScene")
    actionAnonymiseScene.connect("triggered()", lambda: anonymiseScene())

# ----------------------------------------------------------------------------
def addVirtualCathLabHelperWidget():
    toolbarObjects = getToolBarObjects()
    if (toolbarObjects is None):
        return
    manyThingsTabWidget = toolbarObjects[3]
    if (manyThingsTabWidget is None):
        return
    
    lzWidget = VirtualCathLabHelper.createHelperWidget()
    lzWidget.setParent(manyThingsTabWidget)
    lzTabIndex = manyThingsTabWidget.addTab(lzWidget, "LZ")
    manyThingsTabWidget.setTabToolTip(lzTabIndex, "Simulate a laser beam in the Virtual Cath Lab module, using the selected markups Line node.")

# ----------------------------------------------------------------------------
def addPlaneCutSegmentHelperWidget():
    toolbarObjects = getToolBarObjects()
    if (toolbarObjects is None):
        return
    manyThingsTabWidget = toolbarObjects[3]
    if (manyThingsTabWidget is None):
        return
    
    csWidget = SegmentationHelper().createPlaneCutSegmentHelperWidget()
    csWidget.setParent(manyThingsTabWidget)
    csTabIndex = manyThingsTabWidget.addTab(csWidget, "CS")
    manyThingsTabWidget.setTabToolTip(csTabIndex, "Cut the current segment of the segment editor with the selected plane.")

# ******************************************************************************
def setupCustomToolBar():
    settings = slicer.app.settings()
    if (settings.contains(keySkipManyThingsToolBar) == False):
        settings.setValue(keySkipManyThingsToolBar, 0)
    if (str(settings.value(keySkipManyThingsToolBar)) == "1"):
        return

    mw = slicer.util.mainWindow()
    toolBar = qt.QToolBar()
    toolBar.setObjectName("ManyThingsToolBar")
    toolBar.setWindowTitle("Miscellaneous tools")
    mw.addToolBar(toolBar)
    
    manyThingsButton = qt.QToolButton()
    manyThingsButton.setObjectName("ManyThingsButton")
    manyThingsButton.setText("MT")
    manyThingsButton.setToolTip("Miscellaneous utilities")
    # Menu, action
    manyThingsMenu = qt.QMenu(manyThingsButton)
    manyThingsMenu.setObjectName("ManyThingsMenu")
    manyThingsButton.setMenu(manyThingsMenu)
    manyThingsWidgetAction = qt.QWidgetAction(manyThingsMenu)
    manyThingsWidgetAction.setObjectName("ManyThingsWidgetAction")
    manyThingsTabWidget = qt.QTabWidget(manyThingsMenu)
    manyThingsTabWidget.setObjectName("ManyThingsTabWidget")
    manyThingsWidgetAction.setDefaultWidget(manyThingsTabWidget)
    manyThingsMenu.addAction(manyThingsWidgetAction)
    manyThingsButton.connect("clicked()", lambda: manyThingsButton.showMenu())
    
    toolBar.addWidget(manyThingsButton)

    if (settings.contains(keySkipQuickCropVolume) == False):
        settings.setValue(keySkipQuickCropVolume, 0)
    if (settings.contains(keySkipReslice) == False):
        settings.setValue(keySkipReslice, 0)
    if (settings.contains(keySkipMisToTube) == False):
        settings.setValue(keySkipMisToTube, 1)
    if (settings.contains(keySkipUndoRedo) == False):
        settings.setValue(keySkipUndoRedo, 0)
    if (settings.contains(keySkipRemoveHelmet) == False):
        settings.setValue(keySkipRemoveHelmet, 0)
    if (settings.contains(keySkipAnonymiseScene) == False):
        settings.setValue(keySkipAnonymiseScene, 0)
    if (settings.contains(keySkipVirtualCathLabHelper) == False):
        settings.setValue(keySkipVirtualCathLabHelper, 1)
    if (settings.contains(keySkipPlaneCutSegmentHelper) == False):
        settings.setValue(keySkipPlaneCutSegmentHelper, 0)

    if (str(settings.value(keySkipQuickCropVolume)) != "1"):
        addQuickCropVolumeMenuItems()
    if (str(settings.value(keySkipReslice)) != "1"):
        addResliceWidget()
    if (str(settings.value(keySkipMisToTube)) != "1"):
        addMISToTubeWidget()
    if (str(settings.value(keySkipUndoRedo)) != "1"):
        slicer.mrmlScene.SetUndoOn()
        setupUndoRedo()
    if (str(settings.value(keySkipRemoveHelmet)) != "1"):
        addRemoveHelmetWidget()
    if (str(settings.value(keySkipAnonymiseScene)) != "1"):
        addAnonymiseSceneMenuItems()
    if (str(settings.value(keySkipVirtualCathLabHelper)) != "1"):
        addVirtualCathLabHelperWidget()
    if (str(settings.value(keySkipPlaneCutSegmentHelper)) != "1"):
        addPlaneCutSegmentHelperWidget()

# °°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°°

#
# ManyThingsToolBar
#


class ManyThingsToolBar(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = _("ManyThings ToolBar")
        self.parent.categories = ["Utilities.Tools7"]
        self.parent.dependencies = []
        self.parent.contributors = ["Saleem Edah-Tally [Surgeon] [Hobbyist developer]"]
        self.parent.helpText = """
A few custom functions in a toolbar.
See more information in the <a href="https://gitlab.com/chir-set/Tools7/">documentation</a>.
"""
        self.parent.acknowledgementText = """
This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc., Andras Lasso, PerkLab,
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1. <br/>

Icon source <a href="https://icons8.com/icon/sAbwKDoQ3Idp/toolbar">acknowledgement</a>.
"""

        # Additional initialization step after application startup is complete
        slicer.app.connect("startupCompleted()", setupCustomToolBar)

#
# ManyThingsToolBarWidget
#


class ManyThingsToolBarWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)  # needed for parameter node observation
        self.logic = None

    def setup(self) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.setup(self)

        # Load widget from .ui file (created by Qt Designer).
        # Additional widgets can be instantiated manually and added to self.layout.
        uiWidget = slicer.util.loadUI(self.resourcePath("UI/ManyThingsToolBar.ui"))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)

        # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
        # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
        # "setMRMLScene(vtkMRMLScene*)" slot.
        uiWidget.setMRMLScene(slicer.mrmlScene)

        # Create logic class. Logic implements all computations that should be possible to run
        # in batch mode, without a graphical user interface.
        self.logic = ManyThingsToolBarLogic()
        self._updateGUIFromSettings()

        # Connections
        self.ui.loadToolBarCheckBox.connect("toggled(bool)", self.showManyThingsToolBar)
        self.ui.cropCheckBox.connect("toggled(bool)", self.showCropMenuItems)
        self.ui.undoRedoCheckBox.connect("toggled(bool)", self.showUndoRedo)
        self.ui.resliceCheckBox.connect("toggled(bool)", lambda value: self.showTabChildWidget(value, keySkipReslice))
        self.ui.misToTubeCheckBox.connect("toggled(bool)", lambda value: self.showTabChildWidget(value, keySkipMisToTube))
        self.ui.removeHelmetCheckBox.connect("toggled(bool)", lambda value: self.showTabChildWidget(value, keySkipRemoveHelmet))
        self.ui.anonymiseSceneCheckBox.connect("toggled(bool)", self.showAnonymiseMenuItems)
        self.ui.virtualCathLabCheckBox.connect("toggled(bool)", lambda value: self.showTabChildWidget(value, keySkipVirtualCathLabHelper))
        self.ui.planeCutSegmentCheckBox.connect("toggled(bool)", lambda value: self.showTabChildWidget(value, keySkipPlaneCutSegmentHelper))

        # These connections ensure that we update parameter node when scene is closed
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)
        
        # Check if the module is available.
        virtualCathLabIsAvailable = hasattr(slicer.modules, "virtualcathlab")
        self.ui.virtualCathLabCheckBox.setVisible(virtualCathLabIsAvailable)

    def cleanup(self) -> None:
        pass

    def enter(self) -> None:
        pass

    def exit(self) -> None:
        pass

    def onSceneStartClose(self, caller, event) -> None:
        pass

    def onSceneEndClose(self, caller, event) -> None:
        pass

    def _updateGUIFromSettings(self):
        settings = slicer.app.settings()
        value = str(settings.value(keySkipManyThingsToolBar))
        self.ui.loadToolBarCheckBox.setChecked((value is not None) and (value != "1"))
        value = str(settings.value(keySkipQuickCropVolume))
        self.ui.cropCheckBox.setChecked((value is not None) and (value != "1"))
        value = str(settings.value(keySkipReslice))
        self.ui.resliceCheckBox.setChecked((value is not None) and (value != "1"))
        value = str(settings.value(keySkipMisToTube))
        self.ui.misToTubeCheckBox.setChecked((value is not None) and (value != "1"))
        value = str(settings.value(keySkipUndoRedo))
        self.ui.undoRedoCheckBox.setChecked((value is not None) and (value != "1"))
        value = str(settings.value(keySkipRemoveHelmet))
        self.ui.removeHelmetCheckBox.setChecked((value is not None) and (value != "1"))
        value = str(settings.value(keySkipAnonymiseScene))
        self.ui.anonymiseSceneCheckBox.setChecked((value is not None) and (value != "1"))
        value = str(settings.value(keySkipVirtualCathLabHelper))
        self.ui.virtualCathLabCheckBox.setChecked((value is not None) and (value != "1"))
        value = str(settings.value(keySkipPlaneCutSegmentHelper))
        self.ui.planeCutSegmentCheckBox.setChecked((value is not None) and (value != "1"))

        value = str(settings.value(keySkipManyThingsToolBar))
        self.ui.scopeGroupBox.setVisible((value is not None) and (value != "1"))

    def showManyThingsToolBar(self, show):
        settings = slicer.app.settings()
        settings.setValue(keySkipManyThingsToolBar, 1 if (not show) else 0)

        mw = slicer.util.mainWindow()
        customToolBar = mw.findChild(qt.QToolBar, "ManyThingsToolBar")
        if (customToolBar):
            customToolBar.setVisible(show)
        else:
            setupCustomToolBar()
        self.ui.scopeGroupBox.setVisible(show)

    def showCropMenuItems(self, show):
        settings = slicer.app.settings()
        settings.setValue(keySkipQuickCropVolume, 1 if (not show) else 0)

        mw = slicer.util.mainWindow()
        customToolBar = mw.findChild(qt.QToolBar, "ManyThingsToolBar")
        if (not customToolBar):
            return

        names = ["ActionCropVolumeFast", "ActionCropVolumeHigh", "ActionCropAndResampleVolume3", "ActionCropAndResampleVolume5"]
        found = False
        for name in names:
            menuItem = customToolBar.findChild(qt.QAction, name)
            if (menuItem):
                menuItem.setVisible(show)
                found = True
        if (not found):
            addQuickCropVolumeMenuItems()

    def showAnonymiseMenuItems(self, show):
        settings = slicer.app.settings()
        settings.setValue(keySkipAnonymiseScene, 1 if (not show) else 0)

        mw = slicer.util.mainWindow()
        customToolBar = mw.findChild(qt.QToolBar, "ManyThingsToolBar")
        if (not customToolBar):
            return

        menuItem = customToolBar.findChild(qt.QAction, "ActionAnonymiseScene")
        if (menuItem):
            menuItem.setVisible(show)
        else:
            addAnonymiseSceneMenuItems()

    def showTabChildWidget(self, show, key):
        if (key == keySkipReslice):
            widgetName = "RSWidget"
            addWidgetFunction = addResliceWidget
        elif (key == keySkipMisToTube):
            widgetName = "M2TWidget"
            addWidgetFunction = addMISToTubeWidget
        elif (key == keySkipRemoveHelmet):
            widgetName = "RHWidget"
            addWidgetFunction = addRemoveHelmetWidget
        elif (key == keySkipVirtualCathLabHelper):
            widgetName = "LZWidget"
            addWidgetFunction = addVirtualCathLabHelperWidget
        elif (key == keySkipPlaneCutSegmentHelper):
            widgetName = "CSWidget"
            addWidgetFunction = addPlaneCutSegmentHelperWidget
        else:
            raise ValueError("Key is not handled.")

        settings = slicer.app.settings()
        settings.setValue(key, 1 if (not show) else 0)

        mw = slicer.util.mainWindow()
        customToolBar = mw.findChild(qt.QToolBar, "ManyThingsToolBar")
        if (not customToolBar):
            return

        tabWidget =  mw.findChild(qt.QTabWidget, "ManyThingsTabWidget")
        if (not tabWidget):
            return

        widget = customToolBar.findChild(qt.QWidget, widgetName)
        if (widget):
            widget.setVisible(show)
            index = tabWidget.indexOf(widget)
            tabWidget.removeTab(index)
            if (not show):
                widget.setParent(self.parent) # Keep a reference.
            else:
                widget.setParent(tabWidget)
                tabWidget.addTab(widget)
        else:
            addWidgetFunction()

        manyThingsWidgetAction = customToolBar.findChild(qt.QWidgetAction, "ManyThingsWidgetAction")
        tabWidget.setVisible(tabWidget.count) # The space does not shrink if 0. Gets worse while fixing.
        # If manyThingsWidgetAction's visibility is toggled, the other menu items are not displayed while they occupy space.

    def showUndoRedo(self, show):
        settings = slicer.app.settings()
        settings.setValue(keySkipUndoRedo, 1 if (not show) else 0)

        mw = slicer.util.mainWindow()
        customToolBar = mw.findChild(qt.QToolBar, "ManyThingsToolBar")
        if (not customToolBar):
            return

        undoAction = mw.findChild(qt.QAction, "UndoAction")
        redoAction = mw.findChild(qt.QAction, "RedoAction")

        if (undoAction):
            undoAction.setVisible(show)
        if (redoAction):
            redoAction.setVisible(show)
        if (not undoAction) and (not redoAction):
            setupUndoRedo()
#
# ManyThingsToolBarLogic
#


class ManyThingsToolBarLogic(ScriptedLoadableModuleLogic):

    def __init__(self) -> None:
        """Called when the logic class is instantiated. Can be used for initializing member variables."""
        ScriptedLoadableModuleLogic.__init__(self)

#
# ManyThingsToolBarTest
#


class ManyThingsToolBarTest(ScriptedLoadableModuleTest):

    def setUp(self):
        """Do whatever is needed to reset the state - typically a scene clear will be enough."""
        slicer.mrmlScene.Clear()

    def runTest(self):
        """Run as few or as many tests as needed here."""
        self.setUp()
        self.test_ManyThingsToolBar1()

    def test_ManyThingsToolBar1(self):

        self.delayDisplay("Starting the test")

        self.delayDisplay("Test passed")

keySkipManyThingsToolBar = "/ManyThingsToolBar/skipManyThingsToolbar"
keySkipQuickCropVolume = "/ManyThingsToolBar/skipQuickCropVolume"
keySkipReslice = "/ManyThingsToolBar/skipReslice"
keySkipMisToTube = "/ManyThingsToolBar/skipMisToTube"
keySkipUndoRedo = "/ManyThingsToolBar/skipUndoRedo"
keySkipRemoveHelmet = "/ManyThingsToolBar/skipRemoveHelmet"
keySkipAnonymiseScene = "/ManyThingsToolBar/skipAnonymiseScene"
keySkipVirtualCathLabHelper = "/ManyThingsToolBar/skipVirtualCathLabHelper"
keySkipPlaneCutSegmentHelper = "/ManyThingsToolBar/skipPlaneCutSegmentHelper"
