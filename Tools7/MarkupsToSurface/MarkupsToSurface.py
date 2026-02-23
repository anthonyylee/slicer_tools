import logging
import os
from typing import Annotated, Optional

import vtk

import slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
from slicer.parameterNodeWrapper import (
    parameterNodeWrapper,
    WithinRange,
)

from slicer import vtkMRMLScalarVolumeNode

from scipy.optimize import least_squares
import numpy as np
#
# MarkupsToSurface
#

class MarkupsToSurface(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "Markups to surface"  # TODO: make this more human readable by adding spaces
        self.parent.categories = ["Utilities.Tools7"]  # TODO: set categories (folders where the module shows up in the module selector)
        self.parent.dependencies = []  # TODO: add here list of module names that this module requires
        self.parent.contributors = ["Saleem Edah-Tally [Surgeon] [Hobbyist developer]"]  # TODO: replace with "Firstname Lastname (Organization)"
        # TODO: update with short description of the module and a link to online module documentation
        self.parent.helpText = """
Create models and segments from markups nodes.
See more information in the <a href="https://gitlab.com/chir-set/Tools7/">documentation</a>.
"""
        # TODO: replace with organization, grant and thanks
        self.parent.acknowledgementText = """
This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc., Andras Lasso, PerkLab,
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
"""

#
# MarkupsToSurfaceParameterNode
#

@parameterNodeWrapper
class MarkupsToSurfaceParameterNode:
    sphereTypeBestFit = True


#
# MarkupsToSurfaceWidget
#

class MarkupsToSurfaceWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None) -> None:
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)  # needed for parameter node observation
        self.logic = None
        self._parameterNode = None
        self._parameterNodeGuiTag = None

    def setup(self) -> None:
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.setup(self)

        # Load widget from .ui file (created by Qt Designer).
        # Additional widgets can be instantiated manually and added to self.layout.
        uiWidget = slicer.util.loadUI(self.resourcePath('UI/MarkupsToSurface.ui'))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)
        
        self.ui.sphereTypeLabel.setVisible(False)
        self.ui.sphereTypeGroupBox.setVisible(False)

        # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
        # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
        # "setMRMLScene(vtkMRMLScene*)" slot.
        uiWidget.setMRMLScene(slicer.mrmlScene)

        # Create logic class. Logic implements all computations that should be possible to run
        # in batch mode, without a graphical user interface.
        self.logic = MarkupsToSurfaceLogic()

        # Connections

        # These connections ensure that we update parameter node when scene is closed
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

        # Buttons
        self.ui.applyButton.connect('clicked(bool)', self.onApplyButton)
        self.ui.inputSelector.connect('currentNodeChanged(vtkMRMLNode*)', self.onMarkupsChanged)
        self.ui.sphereBestFitRadioButton.connect('toggled(bool)', self.onSphereBestFitRadioButton)
        
        self.ui.resultLineEdit.setVisible(False)
        # Make sure parameter node is initialized (needed for module reload)
        self.initializeParameterNode()
        
        extensionName = "ExtraMarkups"
        em = slicer.app.extensionsManagerModel()
        em.interactive = True
        restart = True
        if not em.installExtensionFromServer(extensionName, restart):
            raise ValueError(("Failed to install {nameOfExtension} extension").format(nameOfExtension=extensionName))

    def cleanup(self) -> None:
        """
        Called when the application closes and the module widget is destroyed.
        """
        self.removeObservers()

    def enter(self) -> None:
        """
        Called each time the user opens this module.
        """
        # Make sure parameter node exists and observed
        self.initializeParameterNode()

    def exit(self) -> None:
        """
        Called each time the user opens a different module.
        """
        # Do not react to parameter node changes (GUI will be updated when the user enters into the module)
        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self._parameterNodeGuiTag = None

    def onSceneStartClose(self, caller, event) -> None:
        """
        Called just before the scene is closed.
        """
        # Parameter node will be reset, do not use it anymore
        self.setParameterNode(None)
        self.logic.setFiducialResultCallback(None)

    def onSceneEndClose(self, caller, event) -> None:
        """
        Called just after the scene is closed.
        """
        # If this module is shown while the scene is closed then recreate a new parameter node immediately
        if self.parent.isEntered:
            self.initializeParameterNode()

    def initializeParameterNode(self) -> None:
        """
        Ensure parameter node exists and observed.
        """
        # Parameter node stores all user choices in parameter values, node selections, etc.
        # so that when the scene is saved and reloaded, these settings are restored.

        self.setParameterNode(self.logic.getParameterNode())

    def setParameterNode(self, inputParameterNode: Optional[MarkupsToSurfaceParameterNode]) -> None:
        """
        Set and observe parameter node.
        Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
        """

        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
        self._parameterNode = inputParameterNode
        if self._parameterNode:
            # Note: in the .ui file, a Qt dynamic property called "SlicerParameterName" is set on each
            # ui element that needs connection.
            self._parameterNodeGuiTag = self._parameterNode.connectGui(self.ui)

    def onApplyButton(self) -> None:
        inputMarkups = self.ui.inputSelector.currentNode()
        if inputMarkups is None:
            self.showStatusMessage("Provide an input markups node.")
            return
        
        outputModel = self.ui.outputModelSelector.currentNode()
        outputSegmentation = self.ui.outputSegmentationSelector.currentNode()
        if outputModel is None and outputSegmentation is None:
            self.showStatusMessage("Provide at least a model or a segmentation node to hold the output surface.")
            return
        
        with slicer.util.tryWithErrorDisplay("Failed to compute results.", waitCursor=True):
            # Only a fiducial node will call that.
            self.logic.setFiducialResultCallback(self.updateFiducialResultWidget)
            
            self.logic.process(inputMarkups, outputModel, outputSegmentation)
            if not inputMarkups.IsTypeOf("vtkMRMLMarkupsFiducialNode"):
                self.ui.resultLineEdit.clear()
                self.ui.resultLineEdit.setVisible(False)
                self.ui.resultLineEdit.setToolTip(None)

    def showStatusMessage(self, message, timeout = 3000) -> None:
        slicer.util.showStatusMessage(message, timeout)
        slicer.app.processEvents()
    
    def onMarkupsChanged(self, node) -> None:
        self.ui.resultLineEdit.clear()
        self.ui.resultLineEdit.setVisible(False)
        self.ui.resultLineEdit.setToolTip(None)
        
        isFiducialNode = False
        if node:
            isFiducialNode = node.IsTypeOf("vtkMRMLMarkupsFiducialNode")
        self.ui.sphereTypeLabel.setVisible(isFiducialNode)
        self.ui.sphereTypeGroupBox.setVisible(isFiducialNode)
        if self._parameterNode:
            self._parameterNode.sphereTypeBestFit = self.ui.sphereBestFitRadioButton.checked
    
    # result = [(centerX, centerY, centerZ), radius]
    def updateFiducialResultWidget(self, result):
        centre = (round(result[0][0], 3), round(result[0][1], 3), round(result[0][2], 3))
        tipText = "Centre: " + str(result[0]) + "\n\nRadius: " + str(result[1])
        text = (
            "Centre: (" + str(centre[0]) + ", "
            + str(centre[1]) + ", "
            + str(centre[2]) + "); Radius: "
            + str(round(result[1], 3))
            )
        self.ui.resultLineEdit.setText(text)
        self.ui.resultLineEdit.setVisible(True)
        self.ui.resultLineEdit.setToolTip(tipText)
    
    def onSphereBestFitRadioButton(self, value):
        if self._parameterNode:
            self._parameterNode.sphereTypeBestFit = value
#
# MarkupsToSurfaceLogic
#

class MarkupsToSurfaceLogic(ScriptedLoadableModuleLogic):
    """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self) -> None:
        """
        Called when the logic class is instantiated. Can be used for initializing member variables.
        """
        ScriptedLoadableModuleLogic.__init__(self)
        # To react when resized by the usual handles, the first entry is ModifiedEvent.
        self._ContentModifiedEvents = slicer.vtkMRMLMarkupsFiducialNode().GetContentModifiedEvents() # vtkIntArray, all markups nodes have 33, 19008.
        self._ioMap = {} # ioMap[markupsID] = [Model, Segmentation, [Observations, ]]
        self._fiducialResultCallback = None
        self._parameterNode = MarkupsToSurfaceParameterNode(super().getParameterNode())

    def getParameterNode(self):
        return self._parameterNode
    
    def setFiducialResultCallback(self, callback) -> None:
        self._fiducialResultCallback = callback

    def _processROINode(self, caller) -> None:
        inputMarkups = slicer.vtkMRMLMarkupsROINode.SafeDownCast(caller)
        inputMarkupsID = inputMarkups.GetID()
        # Account for transforms.
        bounds = [ 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 ]
        inputMarkups.GetObjectBounds(bounds)
        matrix = inputMarkups.GetObjectToWorldMatrix()
        cube = vtk.vtkCubeSource()
        cube.SetCenter(inputMarkups.GetCenter())
        cube.SetBounds(bounds)
        cube.Update()
        
        transform = vtk.vtkTransform()
        transform.SetMatrix(matrix)
        filter = vtk.vtkTransformPolyDataFilter()
        filter.SetInputConnection(cube.GetOutputPort())
        filter.SetTransform(transform)
        filter.Update()
        
        if self._ioMap[inputMarkupsID][0]: # outputModel
            self._ioMap[inputMarkupsID][0].SetPolyDataConnection(filter.GetOutputPort())
        if self._ioMap[inputMarkupsID][1]:
            outputSegmentation = self._ioMap[inputMarkupsID][1]
            segmentName = "Segment_" + inputMarkups.GetName()
            segmentID = "Segment_" + inputMarkups.GetID()
            outputSegmentation.CreateClosedSurfaceRepresentation()
            if outputSegmentation.GetSegmentation().GetSegment(segmentID):
                outputSegmentation.GetSegmentation().RemoveSegment(segmentID)
            outputSegmentation.AddSegmentFromClosedSurfaceRepresentation(filter.GetOutput(), segmentName, None, segmentID)
    
    def _onROIModified(self, caller, event) -> None:
        self._processROINode(caller)
    
    def _processFiducialNode(self, caller) -> None:
        """
        A special case : create a sphere from cloud points, because of :
        https://discourse.slicer.org/t/how-i-can-find-the-center-of-the-humeroulnar-joint-using-3d-slicer/27779
        Source : 
        https://github.com/thompson318/scikit-surgery-sphere-fitting/blob/master/sksurgeryspherefitting/algorithms/sphere_fitting.py
        """
        inputMarkups = slicer.vtkMRMLMarkupsFiducialNode.SafeDownCast(caller)
        inputMarkupsID = inputMarkups.GetID()
        if (not self.getParameterNode().sphereTypeBestFit) and (inputMarkups.GetNumberOfControlPoints() < 2):
            raise ValueError("At least 2 control points are required.") # See note (**).
        
        sphere = vtk.vtkSphereSource()
        sphere.SetPhiResolution(45)
        sphere.SetThetaResolution(45)
        centerX = centerY = centerZ = radius = 0.0
        
        if self.getParameterNode().sphereTypeBestFit:
            markupsPositions = slicer.util.arrayFromMarkupsControlPoints(inputMarkups)
            numberOfControlPoints = inputMarkups.GetNumberOfControlPoints()
            center0 = np.mean(markupsPositions, 0)
            radius0 = np.linalg.norm(np.amin(markupsPositions,0)-np.amax(markupsPositions,0))/2.0
            fittingResult = self._fit_sphere_least_squares(markupsPositions[:,0], markupsPositions[:,1], markupsPositions[:,2], [center0[0], center0[1], center0[2], radius0])
            [centerX, centerY, centerZ, radius] = fittingResult["x"]
            
            sphere.SetCenter(centerX, centerY, centerZ)
            sphere.SetRadius(radius)
            sphere.Update()
        else:
            '''
            (**) Since we are working with vtkPoints, arrayFromMarkupsControlPoints does not fit in here.
            GetCurveWorld() and GetCurvePointsWorld() return zero point
            when there is only one fiducial control point.
            '''
            points = inputMarkups.GetCurvePointsWorld()
            pointsBuffer = []
            numberOfPoints = points.GetNumberOfPoints()
            for i in range(numberOfPoints):
                point = points.GetPoint(i)
                for dimension in range(3):
                    pointsBuffer.append(point[dimension])
            resultBuffer = [0.0] * 4
            vtk.vtkSphere.ComputeBoundingSphere(pointsBuffer, numberOfPoints, resultBuffer)
            centerX = resultBuffer[0]
            centerY = resultBuffer[1]
            centerZ = resultBuffer[2]
            radius = resultBuffer[3]
            
            sphere.SetCenter(centerX, centerY, centerZ)
            sphere.SetRadius(radius)
            sphere.Update()
        
        outputModel = self._ioMap[inputMarkupsID][0]
        outputSegmentation = self._ioMap[inputMarkupsID][1]
        
        if outputModel:
            outputModel.SetPolyDataConnection(sphere.GetOutputPort())
            
        if outputSegmentation:
            segmentName = "Segment_" + inputMarkups.GetName()
            segmentID = "Segment_" + inputMarkups.GetID()
            outputSegmentation.CreateClosedSurfaceRepresentation()
            if outputSegmentation.GetSegmentation().GetSegment(segmentID):
                outputSegmentation.GetSegmentation().RemoveSegment(segmentID)
            outputSegmentation.AddSegmentFromClosedSurfaceRepresentation(sphere.GetOutput(), segmentName, None, segmentID)
        
        result = [(centerX, centerY, centerZ), radius]
        if self._fiducialResultCallback:
            self._fiducialResultCallback(result)
    
    def _onFiducialModified(self, caller, event) -> None:
        self._processFiducialNode(caller)
    
    def _processPlaneNode(self, caller) -> None:
        inputMarkups = slicer.vtkMRMLMarkupsPlaneNode.SafeDownCast(caller)
        inputMarkupsID = inputMarkups.GetID()
        corners = vtk.vtkPoints()
        inputMarkups.GetPlaneCornerPointsWorld(corners)
        planeSource = vtk.vtkPlaneSource()
        planeSource.SetCenter(corners.GetPoint(0))
        planeSource.SetPoint1(corners.GetPoint(1))
        planeSource.SetPoint2(corners.GetPoint(3))
        planeSource.SetResolution(45, 45)
        planeSource.Update()
        
        if self._ioMap[inputMarkupsID][0]: # outputModel
            self._ioMap[inputMarkupsID][0].SetPolyDataConnection(planeSource.GetOutputPort())
        if self._ioMap[inputMarkupsID][1]:
            outputSegmentation = self._ioMap[inputMarkupsID][1]
            segmentName = "Segment_" + inputMarkups.GetName()
            segmentID = "Segment_" + inputMarkups.GetID()
            outputSegmentation.CreateClosedSurfaceRepresentation()
            if outputSegmentation.GetSegmentation().GetSegment(segmentID):
                outputSegmentation.GetSegmentation().RemoveSegment(segmentID)
            outputSegmentation.AddSegmentFromClosedSurfaceRepresentation(planeSource.GetOutput(), segmentName, None, segmentID)
    
    def _onPlaneModified(self, caller, event) -> None:
        self._processPlaneNode(caller)
        
    def _removeObservation(self, inputMarkups):
        if not inputMarkups:
            return
        inputMarkupsID = inputMarkups.GetID()
        if (not self._ioMap.get(inputMarkupsID)):
            return
        if (len(self._ioMap[inputMarkupsID]) != 3):
            return
        observations = self._ioMap[inputMarkupsID][2]
        if observations:
            for i in range(len(observations)):
                inputMarkups.RemoveObserver(observations[0])

    def process(self,
                inputMarkups: slicer.vtkMRMLMarkupsNode,
                outputModel: slicer.vtkMRMLModelNode = None,
                outputSegmentation: slicer.vtkMRMLSegmentationNode = None) -> None:
        
        if inputMarkups is None:
            logging.error("Provide an input markups node.")
            return None
        if outputModel is None and outputSegmentation is None:
            logging.error("Provide at least a model or a segmentation node to hold the output surface.")
            return None
        
        import time
        startTime = time.time()
        logging.info('Processing started')
        
        self._removeObservation(inputMarkups) # Previous observation, if any.
        inputMarkupsID = inputMarkups.GetID()
        self._ioMap[inputMarkupsID] = [outputModel, outputSegmentation, None]
        if outputModel and outputModel.GetNumberOfDisplayNodes() == 0:
            outputModel.CreateDefaultDisplayNodes()
        if outputSegmentation and outputSegmentation.GetNumberOfDisplayNodes() == 0:
            outputSegmentation.CreateDefaultDisplayNodes()
        
        if inputMarkups.IsTypeOf("vtkMRMLMarkupsROINode"):
            self._processROINode(inputMarkups)
            observation = inputMarkups.AddObserver(self._ContentModifiedEvents.GetValue(0), self._onROIModified)
            self._ioMap[inputMarkupsID][2] = [observation,]
        
        elif inputMarkups.IsTypeOf("vtkMRMLMarkupsShapeNode"):
            node = slicer.vtkMRMLMarkupsShapeNode.SafeDownCast(inputMarkups)
            nodePolyData = node.GetShapeWorld()
            if node.GetShapeName() == slicer.vtkMRMLMarkupsShapeNode.Tube:
                nodePolyData = node.GetCappedTubeWorld()
            
            if outputModel:
                outputModel.SetAndObservePolyData(nodePolyData)
                
            if outputSegmentation:
                """
                1. Disk and Ring will appear nicely as long as they are not 'binary
                labelmap'. When 'Show 3D' button is disabled and enabled again,
                they just don't show up, too thin.
                2. Didn't find an equivalent of SetAndObservePolyData()
                for segments. They update in 3D views only when control points
                or interaction handles are moved. We must hit 'Apply' button
                again for slice views. Let go.'
                """
                segmentName = "Segment_" + node.GetName()
                segmentID = "Segment_" + node.GetID()
                outputSegmentation.CreateClosedSurfaceRepresentation()
                if outputSegmentation.GetSegmentation().GetSegment(segmentID):
                    outputSegmentation.GetSegmentation().RemoveSegment(segmentID)
                outputSegmentation.AddSegmentFromClosedSurfaceRepresentation(nodePolyData, segmentName, None, segmentID)

        elif inputMarkups.IsTypeOf("vtkMRMLMarkupsFiducialNode"):
            self._processFiducialNode(inputMarkups)
            endObservation = inputMarkups.AddObserver(slicer.vtkMRMLMarkupsFiducialNode.PointEndInteractionEvent, self._onFiducialModified)
            definedObservation = inputMarkups.AddObserver(slicer.vtkMRMLMarkupsFiducialNode.PointPositionDefinedEvent, self._onFiducialModified)
            removeObservation = inputMarkups.AddObserver(slicer.vtkMRMLMarkupsFiducialNode.PointRemovedEvent, self._onFiducialModified)
            self._ioMap[inputMarkupsID][2] = [endObservation, definedObservation, removeObservation]

        elif inputMarkups.IsTypeOf("vtkMRMLMarkupsPlaneNode"):
            self._processPlaneNode(inputMarkups)
            observation = inputMarkups.AddObserver(self._ContentModifiedEvents.GetValue(0), self._onPlaneModified)
            self._ioMap[inputMarkupsID][2] = [observation,]
            
        else:
            logging.error("Input object is not managed.")
            
        stopTime = time.time()
        logging.info(f'Processing completed in {stopTime-startTime:.2f} seconds')

    def _fit_sphere_least_squares(self, x_values, y_values, z_values, initial_parameters, bounds=((-np.inf, -np.inf, -np.inf, -np.inf),(np.inf, np.inf, np.inf, np.inf))):
        return least_squares(self._calculate_residual_sphere, initial_parameters, bounds=bounds, method="trf", jac="3-point", args=(x_values, y_values, z_values))


    def _calculate_residual_sphere(self, parameters, x_values, y_values, z_values):
        #extract the parameters
        x_centre, y_centre, z_centre, radius = parameters
        #use np's sqrt function here, which works by element on arrays
        distance_from_centre = np.sqrt((x_values - x_centre)**2 + (y_values - y_centre)**2 + (z_values - z_centre)**2)
        return distance_from_centre - radius

#
# MarkupsToSurfaceTest
#

class MarkupsToSurfaceTest(ScriptedLoadableModuleTest):
    """
    This is the test case for your scripted module.
    Uses ScriptedLoadableModuleTest base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def setUp(self):
        slicer.mrmlScene.Clear()

    def runTest(self):
        self.setUp()
        self.test_MarkupsToSurface1()

    def test_MarkupsToSurface1(self):
        self.delayDisplay("Starting the test")

        self.delayDisplay('Test passed')
