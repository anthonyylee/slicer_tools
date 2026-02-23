import qt, vtk, slicer

# ******************************************************************************
def informInStatusBar(message, timeout = 3000):
    slicer.util.showStatusMessage(message, timeout)
    slicer.app.processEvents()

# ******************************************************************************
def getToolBarObjects():
    mw = slicer.util.mainWindow()
    manyThingsButton = None
    manyThingsMenu = None
    manyThingsWidgetAction = None
    manyThingsTabWidget = None
    customToolBar = mw.findChild(qt.QToolBar, "ManyThingsToolBar")
    if customToolBar:
        manyThingsButton =  mw.findChild(qt.QToolButton, "ManyThingsButton")
        manyThingsMenu =  mw.findChild(qt.QMenu, "ManyThingsMenu")
        manyThingsWidgetAction =  mw.findChild(qt.QWidgetAction, "ManyThingsWidgetAction")
        manyThingsTabWidget =  mw.findChild(qt.QTabWidget, "ManyThingsTabWidget")
    else:
        informInStatusBar("ManyThingsToolBar not found.")
        return None
    if not manyThingsButton or not manyThingsMenu or not manyThingsWidgetAction or not manyThingsTabWidget :
        informInStatusBar("Any in ManyThings{Button,Menu,WidgetAction,TabWidget} not found.")
        return None
    return [manyThingsButton, manyThingsMenu, manyThingsWidgetAction, manyThingsTabWidget]

# *******************************************************************************
def hideManyThingsMenu():
    mw = slicer.util.mainWindow()
    manyThingsButton = None
    customToolBar = mw.findChild(qt.QToolBar, "ManyThingsToolBar")
    if customToolBar:
        manyThingsButton =  mw.findChild(qt.QToolButton, "ManyThingsButton")
    else:
        informInStatusBar("ManyThingsToolBar not found.")
        return False
    if manyThingsButton:
        manyThingsButton.menu().hide()
    else:
        informInStatusBar("ManyThingsButton not found.")
        return False
    return True

# ******************************************************************************
def getSegmentEditorSelections():
    # Create slicer.modules.SegmentEditorWidget
    slicer.modules.segmenteditor.widgetRepresentation()
    seWidget = slicer.modules.SegmentEditorWidget.editor
    if (seWidget is None) \
        or (seWidget.segmentationNode() is None) \
        or (seWidget.sourceVolumeNode() is None) \
        or (seWidget.currentSegmentID() == "") :
        informInStatusBar("Is None : editor or segmentationNode or volumeNode or currentSegmentID .")
        return [None, None, None]
    segmentation = seWidget.segmentationNode()
    volume = seWidget.sourceVolumeNode()
    segmentID = seWidget.currentSegmentID()
    if segmentID == "" :
        informInStatusBar("No segment is selected.")
        return [segmentation,volume, None]
    return [segmentation, volume, segmentID]

# ******************************************************************************
def doCropVolume(inputVolume, roi,
                fillValue = 0,
                interpolate = False,
                spacingScalingConst = 1.0,
                isotropicResampling = False,
                interpolationMode = slicer.vtkMRMLCropVolumeParametersNode().InterpolationLinear):
    cropLogic = slicer.modules.cropvolume.logic()
    cvpn = slicer.vtkMRMLCropVolumeParametersNode()

    cvpn.SetROINodeID(roi.GetID())
    cvpn.SetInputVolumeNodeID(inputVolume.GetID())
    cvpn.SetFillValue(fillValue)
    cvpn.SetVoxelBased(not interpolate)
    cvpn.SetSpacingScalingConst(spacingScalingConst)
    cvpn.SetIsotropicResampling(isotropicResampling)
    cvpn.SetInterpolationMode(interpolationMode)
    cropLogic.Apply(cvpn)
    roi.SetDisplayVisibility(False)

    outputVolumeNodeID = cvpn.GetOutputVolumeNodeID()
    #https://www.slicer.org/wiki/Documentation/4.3/Developers/Python_scripting
    views = slicer.app.layoutManager().sliceViewNames()
    for view in views:
        view_logic = slicer.app.layoutManager().sliceWidget(view).sliceLogic()
        view_cn = view_logic.GetSliceCompositeNode()
        view_cn.SetBackgroundVolumeID(outputVolumeNodeID)
        view_logic.FitSliceToAll()

    return outputVolumeNodeID

# ******************************************************************************
def doCropAndResampleVolumeToIsoVoxel(inputVolume, roi, spacing):
    if inputVolume is None or roi is None:
        informInStatusBar("Invalid input.")
        return
    spacingStr = str(spacing) + "," + str(spacing) + "," + str(spacing)
    outputVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
    outputVolumeName = inputVolume.GetName() + " (Iso " + str(spacing) + ")"

    doCropVolume(inputVolume, roi)
    croppedVolume = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode()

    cliParams = {
        "InputVolume": croppedVolume.GetID(),
        "OutputVolume": outputVolume.GetID(),
        "outputPixelSpacing": spacingStr,
        "interpolationType": "linear",
    }
    cliNode = slicer.cli.run(slicer.modules.resamplescalarvolume, parameters=cliParams, wait_for_completion=True, update_display=True)

    outputVolume.SetName(outputVolumeName)
    slicer.mrmlScene.RemoveNode(cliNode)
    slicer.mrmlScene.RemoveNode(croppedVolume)

# ******************************************************************************
def quickCropVolume(veryQuick):
    volumeNode = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode()
    if volumeNode is None:
        informInStatusBar("No background volume node in Red slice view.")
        return

    combo = slicer.modules.markups.toolBar().findChild(slicer.qMRMLNodeComboBox, "MarkupsNodeSelector")
    currentMarkupsNode = combo.currentNode()
    if currentMarkupsNode is None:
        informInStatusBar("No markups node selected.")
        return
    if not currentMarkupsNode.IsTypeOf("vtkMRMLMarkupsROINode"):
        informInStatusBar("Selected markups node is not an ROI node.")
        return

    if (veryQuick):
        doCropVolume(volumeNode, currentMarkupsNode,
                     interpolate = False, spacingScalingConst = 1.0)
    else:
        doCropVolume(volumeNode, currentMarkupsNode,
                    interpolate = True, spacingScalingConst = 0.5)

# *******************************************************************************
def cropAndResampleVolumeToIsoVoxel(spacing):
    volumeNode = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode()
    if volumeNode is None:
        informInStatusBar("No background volume node in Red slice view.")
        return

    combo = slicer.modules.markups.toolBar().findChild(slicer.qMRMLNodeComboBox, "MarkupsNodeSelector")
    currentMarkupsNode = combo.currentNode()
    if currentMarkupsNode is None:
        informInStatusBar("No markups node selected.")
        return
    if not currentMarkupsNode.IsTypeOf("vtkMRMLMarkupsROINode"):
        informInStatusBar("Selected markups node is not an ROI node.")
        return

    doCropAndResampleVolumeToIsoVoxel(volumeNode, currentMarkupsNode, spacing)

# *******************************************************************************
def doResliceToAxis(sliceNode, point, normal, axis = 0):
    if sliceNode is None is None:
        informInStatusBar("Slice node is None.")
        return
    if (normal[0] == 0.0) and (normal[1] == 0.0) and (normal[2] == 0.0):
        informInStatusBar("Normal equals origin.")
        return
    tangent = [0.0, 0.0, 0.0]
    binormal = [0.0, 0.0, 0.0]
    vtk.vtkMath().Perpendiculars(normal, tangent, binormal, 0)
    if axis == 0:
        sliceNode.SetSliceToRASByNTP(normal[0], normal[1], normal[2],
                                    tangent[0], tangent[1], tangent[2],
                                    point[0], point[1], point[2],
                                    0)
    elif axis == 1:
        sliceNode.SetSliceToRASByNTP(binormal[0], binormal[1], binormal[2],
                                    tangent[0], tangent[1], tangent[2],
                                    point[0], point[1], point[2],
                                    0)
    elif axis == 2:
        sliceNode.SetSliceToRASByNTP(tangent[0], tangent[1], tangent[2],
                                    normal[0], normal[1], normal[2],
                                    point[0], point[1], point[2],
                                    0)
    else:
        informInStatusBar("Bad axis.")

# ----------------------------------------------------------------------------
def anonymiseSubjectHierarchyFrom(startItemId):
  shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
  startItemChildrenIds = vtk.vtkIdList()
  shNode.GetItemChildren(startItemId, startItemChildrenIds)

  for i in range(startItemChildrenIds.GetNumberOfIds()):
    startItemNextChildId = startItemChildrenIds.GetId(i)
    if (shNode.GetItemLevel(startItemNextChildId) != "Patient"):
      continue
    if (shNode.HasItemAttribute(startItemNextChildId, "DICOM.PatientName")):
      shNode.SetItemAttribute(startItemNextChildId, "DICOM.PatientName", "Anonymous")
    if (shNode.HasItemAttribute(startItemNextChildId, "DICOM.PatientBirthDate")):
      shNode.SetItemAttribute(startItemNextChildId, "DICOM.PatientBirthDate", "11111111")

    anonymiseSubjectHierarchyFrom(startItemNextChildId)

# ----------------------------------------------------------------------------
def anonymiseScene():
  shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
  sceneItemId = shNode.GetSceneItemID()
  anonymiseSubjectHierarchyFrom(sceneItemId)

# ******************************************************************************* 

# https://projectweek.na-mic.org/PW39_2023_Montreal/Projects/UndoRedo/
# With permission from Kyle Sunderland.

def onRedo():
  slicer.mrmlScene.Redo()

def onUndo():
  slicer.mrmlScene.Undo()

@vtk.calldata_type(vtk.VTK_OBJECT)
def onNodeAdded(caller, event, calldata):
    node = calldata
    if not node:
        return

    undoEnabledNodeClassNames = [
        "vtkMRMLMarkupsFiducialNode",
        "vtkMRMLMarkupsLineNode",
        "vtkMRMLMarkupsAngleNode",
        "vtkMRMLMarkupsCurveNode",
        "vtkMRMLMarkupsClosedCurveNode",
        "vtkMRMLMarkupsPlaneNode",
        "vtkMRMLMarkupsROINode",
        "vtkMRMLMarkupsShapeNode",
        "vtkMRMLMarkupsLabelNode",
        ]
    try:
        # Filter out any other node added to scene.
        undoEnabledNodeClassNames.index(node.GetClassName())
        node.SetUndoEnabled(True)
    except Exception as e:
        pass

# *******************************************************************************
def getTransformFromVector(point, vector):
  """
  Get the transform that rotates and translates [0, 0, 1] to vector.
  """
  normal = [0.0] * 3
  vtk.vtkMath.Assign(vector, normal)
  vtk.vtkMath.Normalize(normal)

  referenceAxis = [0.0, 0.0, 1.0]
  rotationAxis = [0.0] * 3

  angle = vtk.vtkMath.DegreesFromRadians(vtk.vtkMath.AngleBetweenVectors(normal, referenceAxis))
  vtk.vtkMath.Cross(referenceAxis, normal, rotationAxis)

  transform = vtk.vtkTransform()
  transform.RotateWXYZ(angle, rotationAxis)
  transform.PostMultiply()
  transform.Translate(point)
  transform.PreMultiply()

  return transform

# *******************************************************************************
def relateCameraToDirection(vector, precision = 6):
  # Relation between the orientation of vector and GetDirectionOfProjection(), normalised.
  direction = [vector[0], vector[1], vector[2]] # May be ().
  vtk.vtkMath.Normalize(direction)

  cam = slicer.util.getNode("Camera") # It may have been renamed; let go.
  dop = cam.GetCamera().GetDirectionOfProjection() # Is ().
  dot = vtk.vtkMath.Dot(direction, dop)

  return round(dot, precision) # Is signed.
