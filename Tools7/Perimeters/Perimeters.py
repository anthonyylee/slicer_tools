import logging
import os
from typing import Annotated

import vtk
import qt

import slicer
from slicer.i18n import tr as _
from slicer.i18n import translate
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

#
# Perimeters
# See https://discourse.slicer.org/t/how-to-measure-the-perimeter-of-slices-from-a-full-body-3d-model/43723.
#

class Perimeters(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = _("Perimeters")
        self.parent.categories = ["Utilities.Tools7"]
        self.parent.dependencies = []
        self.parent.contributors = ["Saleem Edah-Tally [Surgeon] [Hobbyist developer]"]
        self.parent.helpText = _("""
Cut a segmentation or a model with a plane and calculate the perimeters of each outline.
See more information in the <a href="https://gitlab.com/chir-set/Perimeters/">documentation</a>.
""")
        self.parent.acknowledgementText = _("""
This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc., Andras Lasso, PerkLab,
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
""")

#
# PerimetersWidget
#


class PerimetersWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)  # needed for parameter node observation
        self.logic = None
        self._parameterNode = None
        self._updatingGUIFromParameterNode = False
        self.tableMenu = qt.QMenu()
        self.populatingTable = False

    def setup(self) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.setup(self)

        # Load widget from .ui file (created by Qt Designer).
        # Additional widgets can be instantiated manually and added to self.layout.
        uiWidget = slicer.util.loadUI(self.resourcePath("UI/Perimeters.ui"))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)

        # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
        # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
        # "setMRMLScene(vtkMRMLScene*)" slot.
        uiWidget.setMRMLScene(slicer.mrmlScene)

        # Create logic class. Logic implements all computations that should be possible to run
        # in batch mode, without a graphical user interface.
        self.logic = PerimetersLogic()
        self.ui.parameterSetSelector.addAttribute("vtkMRMLScriptedModuleNode", "ModuleName", self.moduleName)
        self.initializeParameterNode()

        # Connections

        # These connections ensure that we update parameter node when scene is closed
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

        # Buttons
        self.ui.applyButton.connect("clicked(bool)", self.onApplyButton)
        self.ui.inputPlaneSelector.connect("currentNodeChanged(vtkMRMLNode*)", lambda node: self.onMrmlNodeChanged(ROLE_INPUT_PLANE, node))
        self.ui.inputSurfaceSelector.connect("currentNodeChanged(vtkMRMLNode*)", lambda node: self.onMrmlNodeChanged(ROLE_INPUT_SURFACE, node))
        self.ui.inputSurfaceSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSurfaceNodeChanged)
        self.ui.inputSegmentSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSegmentationChanged)
        self.ui.inputSegmentSelector.connect("currentSegmentChanged(QString)", self.onSegmentChanged)
        self.ui.parameterSetSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onParameterNodeChanged)

        # Prepare table
        outputTable = self.ui.presentationTableWidget
        outputTable.setColumnCount(2)
        columnLabels = ("Model", "Perimeter")
        outputTable.setHorizontalHeaderLabels(columnLabels)
        outputTable.setSelectionBehavior(qt.QAbstractItemView.SelectRows)
        outputTable.setSelectionMode(qt.QAbstractItemView.SingleSelection)
        outputTable.setColumnWidth(0, 200)
        outputTable.setColumnWidth(1, 150)
        """
        Table context menu.
        Using self.parent as the menu's parent allows the menu items to lay in the
        foreground.
        """
        outputTable.setContextMenuPolicy(qt.Qt.CustomContextMenu)
        outputTable.connect("customContextMenuRequested(QPoint)", self.showTableMenu)
        outputTable.connect("cellChanged(int, int)", self.onCellChanged)
        outputTable.connect("cellClicked(int, int)", self.onCellClicked)

        vtk.vtkMath.RandomSeed(7)
        # Make sure parameter node is initialized (needed for module reload)
        self.initializeParameterNode()

    def cleanup(self) -> None:
        """Called when the application closes and the module widget is destroyed."""
        self.removeObservers()

    def enter(self) -> None:
        """Called each time the user opens this module."""
        # Make sure parameter node exists and observed
        self.initializeParameterNode()

    def exit(self) -> None:
        """Called each time the user opens a different module."""
        # Do not react to parameter node changes (GUI will be updated when the user enters into the module)
        if self._parameterNode:
            pass

    def onSceneStartClose(self, caller, event) -> None:
        """
        Called just before the scene is closed.
        """
        # Parameter node will be reset, do not use it anymore
        self.setParameterNode(None)

    def onSceneEndClose(self, caller, event) -> None:
        """
        Called just after the scene is closed.
        """
        # If this module is shown while the scene is closed then recreate a new parameter node immediately
        if self.parent.isEntered:
            self.initializeParameterNode()

        while (self.ui.presentationTableWidget.rowCount):
            self.removeTableRow(0)

    def initializeParameterNode(self) -> None:
        # The initial parameter node originates from logic and is picked up by the parameter set combobox.
        # Other parameter nodes are created by the parameter set combobox and used here.
        if not self._parameterNode:
            self.setParameterNode(self.logic.getParameterNode())
        wasBlocked = self.ui.parameterSetSelector.blockSignals(True)
        self.ui.parameterSetSelector.setCurrentNode(self._parameterNode)
        self.ui.parameterSetSelector.blockSignals(wasBlocked)

    def setParameterNode(self, inputParameterNode: slicer.vtkMRMLScriptedModuleNode) -> None:
        if inputParameterNode == self._parameterNode:
            return
        self._parameterNode = inputParameterNode

        if self._parameterNode:
            self.updateGUIFromParameterNode()

    def onApplyButton(self) -> None:
        """Run processing when user clicks "Apply" button."""
        with slicer.util.tryWithErrorDisplay(_("Failed to compute results."), waitCursor=True):
            # Compute output
            inputSurfaceNode = self._parameterNode.GetNodeReference(ROLE_INPUT_SURFACE)
            inputSurfacePolyData = None
            if (inputSurfaceNode.IsTypeOf("vtkMRMLModelNode")):
                inputSurfacePolyData = inputSurfaceNode.GetPolyData()
            elif (inputSurfaceNode.IsTypeOf("vtkMRMLSegmentationNode")):
                inputSurfacePolyData = vtk.vtkPolyData()
                inputSurfaceNode.CreateClosedSurfaceRepresentation()
                inputSurfaceNode.GetClosedSurfaceRepresentation(self._parameterNode.GetParameter(ROLE_INPUT_SEGMENT), inputSurfacePolyData)
            else:
                raise ValueError("Unknown surface type.")

            planeNode = self._parameterNode.GetNodeReference(ROLE_INPUT_PLANE)
            plane = vtk.vtkPlane()
            if (planeNode.IsTypeOf("vtkMRMLMarkupsPlaneNode")):
                plane.SetOrigin(planeNode.GetOriginWorld())
                plane.SetNormal(planeNode.GetNormalWorld())
            elif (planeNode.IsTypeOf("vtkMRMLSliceNode")):
                sliceToRAS = planeNode.GetSliceToRAS()
                origin = [0.0] * 3
                normal = [0.0, 0.0, 1.0]
                for i in range(3):
                    origin[i] = sliceToRAS.GetElement(i, 3)
                    normal[i] = sliceToRAS.GetElement(i, 2)
                plane.SetOrigin(origin)
                plane.SetNormal(normal)
            else:
                raise ValueError("Unknown plane node.")

            result = self.logic.process(inputSurfacePolyData, plane)
            self.populateTable(result)

    def onMrmlNodeChanged(self, role, node):
        if self._parameterNode:
            self._parameterNode.SetNodeReferenceID(role, node.GetID() if node else None)

    def onSegmentChanged(self, value):
        if (self._parameterNode) and not (self._updatingGUIFromParameterNode):
            self._parameterNode.SetParameter(ROLE_INPUT_SEGMENT, str(value))

    def updateGUIFromParameterNode(self):
        if self._parameterNode is None or self._updatingGUIFromParameterNode:
            return

        # Make sure GUI changes do not call updateParameterNodeFromGUI (it could cause infinite loop)
        self._updatingGUIFromParameterNode = True

        self.ui.inputPlaneSelector.setCurrentNode(self._parameterNode.GetNodeReference(ROLE_INPUT_PLANE))
        self.ui.inputSurfaceSelector.setCurrentNode(self._parameterNode.GetNodeReference(ROLE_INPUT_SURFACE))

        self._updatingGUIFromParameterNode = False

    def onSurfaceNodeChanged(self, node):
        if node is None:
            self.ui.inputSegmentSelector.setVisible(False)
            return
        if (node.IsTypeOf("vtkMRMLModelNode")):
            self.ui.inputSegmentSelector.setVisible(False)
            return
        self.ui.inputSegmentSelector.setVisible(True)
        self.ui.inputSegmentSelector.setCurrentNode(node)

    def onSegmentationChanged(self, node):
        if (not self._parameterNode):
            return
        self.ui.inputSegmentSelector.setCurrentSegmentID(self._parameterNode.GetParameter(ROLE_INPUT_SEGMENT))

    def onParameterNodeChanged(self, parameterNode):
        self.setParameterNode(parameterNode)

    def populateTable(self, result):
        if (result is None):
            return
        self.populatingTable = True
        outputTable = self.ui.presentationTableWidget
        numberOfRegions = len(result)
        for regionId in range(numberOfRegions):
            region = result[regionId]

            regionPolyData = region[0]
            name = slicer.mrmlScene.GenerateUniqueName("Outline")
            model = slicer.modules.models.logic().AddModel(regionPolyData)
            model.SetName(name)
            colour = (vtk.vtkMath.Random(), vtk.vtkMath.Random(), vtk.vtkMath.Random())
            model.GetDisplayNode().SetColor(colour)
            model.GetDisplayNode().SetScalarVisibility(False)
            model.GetDisplayNode().LightingOff()
            model.SetAttribute("ModuleName.Role", self.moduleName)
            self._appendInTable(name, model, region[1])
        self.populatingTable = False

    def refreshTable(self):
        self.populatingTable = True
        outputTable = self.ui.presentationTableWidget
        while (outputTable.rowCount):
            outputTable.removeRow(0) # Not removeTableRow()

        nodes = slicer.mrmlScene.GetNodesByClass("vtkMRMLModelNode")
        for node in nodes:
            if (node.GetAttribute("ModuleName.Role")):
                perimeter = self.logic.calculatePerimeter(node.GetPolyData())
                self._appendInTable(node.GetName(), node, perimeter)
        self.populatingTable = False

    def _appendInTable(self, name, model, perimeter):
        outputTable = self.ui.presentationTableWidget
        rowIndex = outputTable.rowCount
        outputTable.insertRow(rowIndex)
        selectionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLSelectionNodeSingleton")
        lengthUnitNode = slicer.mrmlScene.GetNodeByID(selectionNode.GetUnitNodeID("length"))

        item = qt.QTableWidgetItem()
        item.setText(name)
        item.setData(qt.Qt.UserRole, model)
        outputTable.setItem(rowIndex, 0, item)

        item = qt.QTableWidgetItem()
        content = lengthUnitNode.GetDisplayStringFromValue(perimeter)
        item.setText(content)
        outputTable.setItem(rowIndex, 1, item)

    def showTableMenu(self, qpoint) -> None:
        # Start from zero.
        self.tableMenu.clear()
        self.tableMenu.setParent(self.ui.presentationTableWidget)

        # Simple menu item to remove a single row.
        actionRemoveRow = self.tableMenu.addAction(_("Remove row"))
        actionRemoveRow.setData(OUTPUT_TABLE_MENU_REMOVE_ROW)
        actionRemoveRow.connect("triggered()", self.onTableMenuItem)

        # Simple menu item to remove all rows.
        actionEmptyTable = self.tableMenu.addAction(_("Empty table"))
        actionEmptyTable.setData(OUTPUT_TABLE_MENU_EMPTY_TABLE)
        actionEmptyTable.connect("triggered()", self.onTableMenuItem)

        self.tableMenu.addSeparator()
        # Simple menu item to refresh the table.
        actionRefreshTable = self.tableMenu.addAction(_("Refresh table"))
        actionRefreshTable.setData(OUTPUT_TABLE_MENU_REFRESH_TABLE)
        actionRefreshTable.connect("triggered()", self.onTableMenuItem)

        self.tableMenu.addSeparator()
        # Clicking anywhere does not hide menu.
        actionCancel = self.tableMenu.addAction(_("Dismiss menu"))
        actionCancel.connect("triggered()", self.onTableMenuItem)

        self.tableMenu.popup(self.ui.presentationTableWidget.mapToParent(qpoint))

    def onTableMenuItem(self) -> None:
        action = self.tableMenu.activeAction()
        data = action.data()
        outputTable = self.ui.presentationTableWidget
        # Remove the current row.
        if data == OUTPUT_TABLE_MENU_REMOVE_ROW:
            self.removeTableRow(outputTable.currentRow())
        # Remove all rows.
        elif data == OUTPUT_TABLE_MENU_EMPTY_TABLE:
            while (outputTable.rowCount):
                self.removeTableRow(0)
        elif data == OUTPUT_TABLE_MENU_REFRESH_TABLE:
            self.refreshTable()
        self.tableMenu.hide()

    # Remove a single table row and an associated model.
    def removeTableRow(self, rowIndex) -> None:
        outputTable = self.ui.presentationTableWidget
        modelCellItem = outputTable.item(rowIndex, 0)
        if modelCellItem:
            cutModel = modelCellItem.data(qt.Qt.UserRole)
            if (cutModel) and (slicer.mrmlScene.GetNodeByID(cutModel.GetID())):
                slicer.mrmlScene.RemoveNode(cutModel)
        outputTable.removeRow(rowIndex)

    def onCellChanged(self, row, column):
        if (self.populatingTable) or (column != 0):
            return
        outputTable = self.ui.presentationTableWidget
        modelCellItem = outputTable.item(row, 0)
        if modelCellItem:
            cutModel = modelCellItem.data(qt.Qt.UserRole)
            if (cutModel) and (slicer.mrmlScene.GetNodeByID(cutModel.GetID())):
                cutModel.SetName(modelCellItem.text())

    def onCellClicked(self, row, column):
        if (self.populatingTable) or (column != 1):
            return
        outputTable = self.ui.presentationTableWidget
        modelCellItem = outputTable.item(row, 0)
        if modelCellItem:
            cutModel = modelCellItem.data(qt.Qt.UserRole)
            if (cutModel) and (slicer.mrmlScene.GetNodeByID(cutModel.GetID())):
                cutModel.GetDisplayNode().SetVisibility(not cutModel.GetDisplayNode().GetVisibility())
#
# PerimetersLogic
#

class PerimetersLogic(ScriptedLoadableModuleLogic):
    def __init__(self) -> None:
        """Called when the logic class is instantiated. Can be used for initializing member variables."""
        ScriptedLoadableModuleLogic.__init__(self)

    def process(self, inputSurface: vtk.vtkPolyData, inputPlane: vtk.vtkPlane):
        if (inputSurface is None) or (inputPlane is None):
            raise ValueError("Invalid input.")
        """
        We don't check degenerate conditions like all points being coplanar
        or less than 3 points or invalid normal...
        """
        import time

        startTime = time.time()
        logging.info("Processing started")

        """
        VTK_LINEs are observed when the cut function is a plane, but not always.
        There are vertices sometimes, except if SetGenerateTriangles() is set
        to false in the cutter.
        If 'Surface net' is used in the segment editor, cell types other than
        VTK_LINE have not been seen yet with both SetGenerateTriangles()
        settings.
        """
        cutter = vtk.vtkCutter()
        cutter.SetCutFunction(inputPlane)
        cutter.SetInputData(inputSurface)
        # No vertices found in with the default smoothing methof of the segment editor.
        cutter.SetGenerateTriangles(False)
        cutter.Update()

        # Mark each region of the cut polydata.
        connectivity = vtk.vtkPolyDataConnectivityFilter()
        connectivity.SetInputConnection(cutter.GetOutputPort())
        connectivity.SetExtractionModeToAllRegions()
        connectivity.SetColorRegions(True) # +++
        connectivity.Update()
        numberOfContours = connectivity.GetNumberOfExtractedRegions()
        contours = connectivity.GetOutput()

        result = [] # [polydata, double]
        for contourId in range(numberOfContours):
            # Extract each connected region from the cut polydata.
            contourConnectivity = vtk.vtkPolyDataConnectivityFilter()
            contourConnectivity.SetExtractionModeToSpecifiedRegions()
            contourConnectivity.AddSpecifiedRegion(contourId)
            contourConnectivity.SetInputData(contours)
            contourConnectivity.Update()
            cleaner = vtk.vtkCleanPolyData() # +++
            cleaner.SetInputConnection(contourConnectivity.GetOutputPort())
            cleaner.Update()
            contour = cleaner.GetOutput()
            perimeter = self.calculatePerimeter(contour)
            

            result.append([contour, perimeter])

        stopTime = time.time()
        logging.info(f"Processing completed in {stopTime-startTime:.2f} seconds")

        return result

    # A perimeter implies a 2D space.
    def calculatePerimeter(self, contour):
        if (contour is None):
            return 0.0

        import math
        numberOfCells = contour.GetNumberOfCells()
        perimeter = 0.0
        if (contour.GetNumberOfLines() == numberOfCells):
            # Add the length of each VTK_LINE.
            for cell in range(numberOfCells):
                line = contour.GetCell(cell).GetPoints()
                distance2 = vtk.vtkMath.Distance2BetweenPoints(line.GetPoint(0), line.GetPoint(1))
                distance = math.sqrt(distance2)
                perimeter = perimeter + distance
        else:
            # All cells should be of VTK_LINE type.
            logging.warning("All cells in the input polydata are not of VTK_LINE type.")
            perimeter = -1.0

        return perimeter
#
# PerimetersTest
#


class PerimetersTest(ScriptedLoadableModuleTest):
    """
    This is the test case for your scripted module.
    Uses ScriptedLoadableModuleTest base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def setUp(self):
        """Do whatever is needed to reset the state - typically a scene clear will be enough."""
        slicer.mrmlScene.Clear()

    def runTest(self):
        """Run as few or as many tests as needed here."""
        self.setUp()

    def test_Perimeters1(self):
        self.delayDisplay("Starting the test")

        self.delayDisplay("Test passed")

# Menu constants.
MENU_CANCEL = 0
OUTPUT_TABLE_MENU_REMOVE_ROW = 1
OUTPUT_TABLE_MENU_EMPTY_TABLE = 2
# Intent: manually populate the table when a scene is loaded.
OUTPUT_TABLE_MENU_REFRESH_TABLE = 3

# Parameter node roles
ROLE_INPUT_PLANE = "InputPlane"
ROLE_INPUT_SURFACE = "InputSurface"
ROLE_INPUT_SEGMENT = "InputSegment"
