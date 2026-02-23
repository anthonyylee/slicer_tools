import qt, vtk, slicer
from ManyThingsToolBarLib.Utils import *

class VirtualCathLabHelper():
  nodeReferenceRoleName = "Role_LaserBeam"
  observationAttributeName = "Observation_LaserBeam"

# *******************************************************************************
  @staticmethod
  def _onLaserMarkMoved(caller, event):
    if (not caller):
      return
    lineNode = caller
    # Get the X-ray beam.
    xrayBeamID = lineNode.GetNodeReferenceID(VirtualCathLabHelper.nodeReferenceRoleName)
    if (not xrayBeamID):
      informInStatusBar("X-ray beam ID is None.", 3000)
      raise RuntimeError("X-ray beam ID is None.")
    xrayBeam = slicer.mrmlScene.GetNodeByID(xrayBeamID)
    if (not xrayBeam):
      informInStatusBar("X-ray beam is None.", 3000)
      raise RuntimeError("X-ray beam is None.")
    
    # Get the transform of the X-ray beam.
    transformNode = xrayBeam.GetParentTransformNode().GetParentTransformNode()
    if (transformNode is None):
      informInStatusBar("X-Ray beam does have a transform node.", 3000)
      return

    # Naive check of the X-ray beam. It can be fooled.
    xrayBeamPolyData = xrayBeam.GetPolyData()
    if (xrayBeamPolyData.GetNumberOfCells() != 5) and (xrayBeamPolyData.GetNumberOfPoints() != 5):
      informInStatusBar("Invalid X-ray beam model.")
      return
    
    # Get the frontal and lateral transforms from logic.
    logic = slicer.util.getModuleLogic("VirtualCathLab")
    parameterNode = logic.getParameterNode()
    frontalTransformID = parameterNode.GetNodeReferenceID("frontal-arm-detector-rotation-transform")
    lateralTransformID = parameterNode.GetNodeReferenceID("lateral-arm-detector-rotation-transform")
    # There must be at least a frontal transform.
    if (not frontalTransformID):
      informInStatusBar("No frontal transform found.", 3000)
      return

    slicer.app.pauseRender()
    # Determine the projection of p2 of the line at origin.
    p2 = [0.0] * 3
    projectedP2 = [0.0] * 3
    lineParentTransformNode = lineNode.GetParentTransformNode()
    """
    When we switch between beams, the projection on the used axis is 0.
    Use the line length for p2.
    """
    lineLength = lineNode.GetMeasurement("length").GetValue()
    # Put at origin.
    lineNode.SetAndObserveTransformNodeID(None)
    lineNode.GetNthControlPointPositionWorld(1, p2)
    
    if (transformNode.GetID() == frontalTransformID):
      projectedP2 = [0, -abs(p2[1]) if abs(p2[1]) != 0 else -lineLength, 0]
    elif lateralTransformID and (transformNode.GetID() == lateralTransformID):
      projectedP2 = [-abs(p2[0]) if abs(p2[0]) != 0 else -lineLength, 0, 0]
    else:
      informInStatusBar("Laser beam placement error.")
      lineNode.SetAndObserveTransformNodeID(lineParentTransformNode.GetID() if lineParentTransformNode else None)
      slicer.app.resumeRender()
      raise RuntimeError("Laser beam placement error.")
    
    # p1 at origin, p2 is projected on the axis.
    lineNode.SetNthControlPointPositionWorld(0, [0, 0, 0])
    lineNode.SetNthControlPointPositionWorld(1, projectedP2)
    # Put in place.
    lineNode.SetAndObserveTransformNodeID(transformNode.GetID())

    slicer.app.resumeRender()
    logic.updateCurrentLayout()

# *******************************************************************************
  @staticmethod
  def handleLaserBeam(xrayBeam, fire, shadow = False):
    if (not xrayBeam):
      informInStatusBar("No X-ray beam model node selected.")
      return
    combo = slicer.modules.markups.toolBar().findChild(slicer.qMRMLNodeComboBox, "MarkupsNodeSelector")
    lineNode = combo.currentNode()
    if lineNode is None:
      informInStatusBar("No markups node selected.")
      return
    if not lineNode.IsTypeOf("vtkMRMLMarkupsLineNode"):
      informInStatusBar("Selected markups node is not a Line.")
      return

    if (lineNode.GetNumberOfDefinedControlPoints() != 2):
      informInStatusBar("Line node does not have 2 defined control points.", 3000)
      return

    # Remove the references that have been added to the line node.
    observation = lineNode.GetAttribute(VirtualCathLabHelper.observationAttributeName)
    if (observation):
      lineNode.RemoveObserver(int(observation))
    lineNode.RemoveAttribute(VirtualCathLabHelper.observationAttributeName)
    lineNode.RemoveNodeReferenceIDs(VirtualCathLabHelper.nodeReferenceRoleName)
    if (not fire):
      # Reset properties.
      lineNode.GetDisplayNode().Reset(slicer.vtkMRMLMarkupsDisplayNode())
      lineNode.SetNthControlPointVisibility(0, True)
      lineNode.SetNthControlPointLocked(0, False)
      lineNode.SetNthControlPointLabel(1, "Laser mark") # No label is shown.
      lineNode.GetDisplayNode().SetViewNodeIDs([])
      return
    
    # Add references to the line node.
    observation = lineNode.AddObserver(lineNode.PointEndInteractionEvent, VirtualCathLabHelper._onLaserMarkMoved)
    lineNode.SetAttribute(VirtualCathLabHelper.observationAttributeName, str(observation))
    lineNode.SetNodeReferenceID(VirtualCathLabHelper.nodeReferenceRoleName, xrayBeam.GetID())
    
    # Fully hijack a line node from its purpose.
    dn = lineNode.GetDisplayNode()
    dn.SetPropertiesLabelVisibility(False)
    dn.SetSelectedColor([1, 0, 0])
    dn.SetGlyphType(3) # CrossDot2D
    dn.SetPointLabelsVisibility(True)
    dn.SetSnapMode(dn.SnapModeUnconstrained) # Because of the X-ray beam model.
    lineNode.SetNthControlPointVisibility(0, False)
    lineNode.SetNthControlPointLocked(0, True)
    lineNode.SetNthControlPointLabel(1, "")
    lineName = lineNode.GetName()
    laserBeamBasename = "Laser beam"
    if (lineName[0:10] != laserBeamBasename):
      lineNode.SetName(slicer.mrmlScene.GenerateUniqueName(laserBeamBasename))
    
    # Visibility of the line in the C-arm view nodes.
    logic = slicer.util.getModuleLogic("VirtualCathLab")
    filteredNodeIDs = []
    if (not shadow): # Don't show in the C-arm view nodes.
      filteredNodeIDs = VirtualCathLabHelper().getStandardDisplayNodeIDs()
    lineNode.GetDisplayNode().SetViewNodeIDs(filteredNodeIDs)
    
    # Orient the laser beam.
    VirtualCathLabHelper._onLaserMarkMoved(lineNode, -1)

# *******************************************************************************
  @staticmethod
  def repositionCamera(fromRight = True, withPatientSpin = False):
    # withPatientSpin: make the table horizontal.
    cam = slicer.util.getNode("Camera") # It may have been renamed; let go.
    if (not cam):
      informInStatusBar("No camera node with name 'Camera' found.")
      return
    logic = slicer.util.getModuleLogic("VirtualCathLab")
    parameterNode = logic.getParameterNode()
    if (not parameterNode.HasParameter("GenericFluoro_patientSpin")):
      msg = "VirtualCathLab module is not set up yet, or no positioning action has been performed."
      informInStatusBar(msg)
      raise RuntimeError(msg)
    patientSpin = float(parameterNode.GetParameter("GenericFluoro_patientSpin"))
    
    refDir = [1.0, 0.0, 0.0] if fromRight else [-1.0, 0.0, 0.0]
    transform = vtk.vtkTransform()
    if (withPatientSpin):
      transform.RotateZ(patientSpin)
    refDirTransformed = transform.TransformVector(refDir)
    
    camAlignment = relateCameraToDirection(refDirTransformed)

    """
    refDir looks towards right or left.
    The camera looks towards the focal point (GetDirectionOfProjection()).
    """
    if (camAlignment == -1.0): # Aligned and oriented in opposite directions.
      return
    
    cam.SetViewUp([0, 1.0, 0])
    position = cam.GetPosition()
    focus = cam.GetFocalPoint()
    if (fromRight):
      cam.SetPosition(abs(position[0]), focus[1], focus[2])
    else:
      cam.SetPosition(-abs(position[0]), focus[1], focus[2])
    
    position = cam.GetPosition()
    positionTransformed = transform.TransformVector(position)
    cam.SetPosition(positionTransformed)

# *******************************************************************************
  @staticmethod
  def createHelperWidget():
    lzWidget = qt.QWidget()
    lzWidget.setObjectName("LZWidget")
    lzWidgetVLayout = qt.QVBoxLayout()
    lzWidgetVLayout.setObjectName("LZWidgetVLayout")
    lzWidget.setLayout(lzWidgetVLayout)
    lzWidgetFormLayout = qt.QFormLayout()
    lzWidgetFormLayout.setObjectName("LZWidgetFormLayout")
    lzWidgetVLayout.addLayout(lzWidgetFormLayout)
    # X-ray beam selector
    lzBeamModelNodeLabel = qt.QLabel("X-ray beam:", lzWidget)
    lzBeamModelNodeLabel.setObjectName("LZSliceNodeLabel")
    lzBeamModelNodeComboBox = slicer.qMRMLNodeComboBox(lzWidget)
    lzBeamModelNodeComboBox.setObjectName("LZModelNodeComboBox")
    lzBeamModelNodeComboBox.nodeTypes = ["vtkMRMLModelNode"]
    lzBeamModelNodeComboBox.addEnabled = False
    lzBeamModelNodeComboBox.removeEnabled = False
    lzBeamModelNodeComboBox.renameEnabled = False
    lzBeamModelNodeComboBox.noneEnabled = True
    lzBeamModelNodeComboBox.setMRMLScene( slicer.mrmlScene )
    lzBeamModelNodeComboBox.setToolTip("Select an X-ray beam model.\n\nThe default names are: \n - frontal-beam\n - lateral-beam.")
    lzWidgetFormLayout.addRow(lzBeamModelNodeLabel, lzBeamModelNodeComboBox)
    # Shadow
    lzShadowCheckBox = qt.QCheckBox("Shadow", lzWidget)
    lzShadowCheckBox.setObjectName("LZShadowCheckBox")
    lzShadowCheckBox.setToolTip("Show the line in the DRR views.")
    lzShadowCheckBox.setChecked(False)
    lzWidgetFormLayout.addRow(None, lzShadowCheckBox)
    # Buttons
    lzButtonsHLayout = qt.QHBoxLayout()
    lzButtonsHLayout.setObjectName("LZButtonsHLayout")
    lzWidgetVLayout.addLayout(lzButtonsHLayout)
    ## Cease fire button
    lzCeaseFireButton = qt.QToolButton(lzWidget)
    lzCeaseFireButton.setObjectName("LZCeaseFireButton")
    lzCeaseFireButton.setText("Off")
    lzCeaseFireButton.setSizePolicy(qt.QSizePolicy.Minimum, qt.QSizePolicy.Fixed)
    lzCeaseFireButton.connect("clicked()", lambda: VirtualCathLabHelper.handleLaserBeam(lzBeamModelNodeComboBox.currentNode(), False, lzShadowCheckBox.checked))
    lzButtonsHLayout.addWidget(lzCeaseFireButton)
    ## Fire button
    lzFireButton = qt.QToolButton(lzWidget)
    lzFireButton.setObjectName("LZFireButton")
    lzFireButton.setText("On")
    lzFireButton.setSizePolicy(qt.QSizePolicy.Minimum, qt.QSizePolicy.Fixed)
    lzFireButton.connect("clicked()", lambda: VirtualCathLabHelper.handleLaserBeam(lzBeamModelNodeComboBox.currentNode(), True, lzShadowCheckBox.checked))
    lzButtonsHLayout.addWidget(lzFireButton)
    # Camera position buttons
    lzCameraPositionButtonsHLayout = qt.QHBoxLayout()
    lzCameraPositionButtonsHLayout.setObjectName("LZCameraPositionButtonsHLayout")
    lzWidgetVLayout.addLayout(lzCameraPositionButtonsHLayout)
    ## Look from the right.
    lzLookFromRightButton = qt.QToolButton(lzWidget)
    lzLookFromRightButton.setObjectName("LZLookFromRightButton")
    lzLookFromRightButton.setText("Look from the right")
    lzLookFromRightButton.setToolTip("Look from the right towards the current focal point.")
    lzLookFromRightButton.setSizePolicy(qt.QSizePolicy.Minimum, qt.QSizePolicy.Fixed)
    lzCameraPositionButtonsHLayout.addWidget(lzLookFromRightButton)
    ## Look from the left.
    lzLookFromLeftButton = qt.QToolButton(lzWidget)
    lzLookFromLeftButton.setObjectName("LZLookFromLeftButton")
    lzLookFromLeftButton.setText("Look from the left")
    lzLookFromLeftButton.setToolTip("Look from the left towards the current focal point.")
    lzLookFromLeftButton.setSizePolicy(qt.QSizePolicy.Minimum, qt.QSizePolicy.Fixed)
    lzCameraPositionButtonsHLayout.addWidget(lzLookFromLeftButton)
    # Keep table horizontal.
    lzPatientSpinCheckBox = qt.QCheckBox("Keep the table horizontal", lzWidget)
    lzPatientSpinCheckBox.setObjectName("LZPatientSpinCheckBox")
    lzPatientSpinCheckBox.setToolTip("Account for the patient spin parameter.")
    lzPatientSpinCheckBox.setChecked(False)
    lzWidgetVLayout.addWidget(lzPatientSpinCheckBox)
    # Connections to change orientation.
    lzLookFromRightButton.connect("clicked()", lambda: VirtualCathLabHelper.repositionCamera(True, lzPatientSpinCheckBox.checked))
    lzLookFromLeftButton.connect("clicked()", lambda: VirtualCathLabHelper.repositionCamera(False, lzPatientSpinCheckBox.checked))
    
    return lzWidget

# *******************************************************************************
  @staticmethod
  def getStandardDisplayNodeIDs():
    logic = slicer.util.getModuleLogic("VirtualCathLab")
    filteredNodeIDs = []
    sliceNodes = slicer.mrmlScene.GetNodesByClass("vtkMRMLSliceNode")
    for node in sliceNodes:
      # All slice nodes.
      filteredNodeIDs.append(node.GetID())
    viewNodes = slicer.mrmlScene.GetNodesByClass("vtkMRMLViewNode")
    for node in viewNodes:
      # Exclude the C-arm view nodes.
      if (not node) or (node.GetSingletonTag() == logic.C_ARM_FRONTAL_VIEW_NAME) or (node.GetSingletonTag() == logic.C_ARM_LATERAL_VIEW_NAME):
        continue
      filteredNodeIDs.append(node.GetID())
    return filteredNodeIDs
