import qt, vtk, slicer
from ManyThingsToolBarLib.Utils import *

class SegmentationHelper():
  @staticmethod
  def apply(plane):
    if (plane is None):
      return
    seSelections = getSegmentEditorSelections()
    segmentation = seSelections[0]
    segmentID = seSelections[2]
    if (segmentation is None) or (segmentID is None):
      return
    if (plane.IsTypeOf("vtkMRMLMarkupsPlaneNode")):
      # We don't use GetObjectToWorldMatrix() because it has an intrinsic rotation.
      # https://discourse.slicer.org/t/rotation-in-plane-created-by-api-is-it-normal/38148
      planeOrigin = plane.GetOriginWorld()
      planeNormal = plane.GetNormalWorld()
    elif (plane.IsTypeOf("vtkMRMLSliceNode")):
      sliceToRas = plane.GetSliceToRAS()
      planeOrigin = [sliceToRas.GetElement(0, 3), sliceToRas.GetElement(1, 3), sliceToRas.GetElement(2, 3)]
      planeNormal = [sliceToRas.GetElement(0, 2), sliceToRas.GetElement(1, 2), sliceToRas.GetElement(2, 2)]
    else:
      raise ValueError("Input plane is not a markups plane node nor a slice node.")
    sideIDs = SegmentationHelper.planeCutSegment(segmentation, segmentID, planeOrigin, planeNormal)
    hideManyThingsMenu()

  @staticmethod
  def planeCutSegment(segmentation, segmentID, planeOrigin, planeNormal):

    # segmentation = getNode("Segmentation")
    # segmentID = segmentation.GetSegmentation().GetSegmentIdBySegmentName("Segment_F")
    # plane = getNode("P")

    if (segmentation is None) or (segmentID is None):
      return
    if (planeNormal[0] == 0) and (planeNormal[1] == 0) and (planeNormal[2] == 0):
      raise RuntimeError("Invalid vector: " + planeNormal)

    oid = slicer.vtkOrientedImageData()
    segmentation.CreateBinaryLabelmapRepresentation()
    segmentation.GetBinaryLabelmapRepresentation(segmentID, oid)
    segmentName =  segmentation.GetSegmentation().GetSegment(segmentID).GetName()

    planeTransform = getTransformFromVector(planeOrigin, planeNormal)

    dims = oid.GetDimensions()
    extent = oid.GetExtent()

    sideA = slicer.vtkOrientedImageData()
    sideA.DeepCopy(oid)

    sideB = slicer.vtkOrientedImageData()
    sideB.DeepCopy(oid)

    iwTransform = vtk.vtkTransform()
    iwMatrix = vtk.vtkMatrix4x4()
    oid.GetImageToWorldMatrix(iwMatrix)
    iwTransform.SetMatrix(iwMatrix)

    # Set plane at origin with normal [0, 0, 1].
    planeTransform.Inverse()

    for z in range(dims[2]):
      stack = ((dims[0]) * (dims[1]) * z)
      for y in range(dims[1]):
        rows = ((dims[0]) * y)
        for x in range(dims[0]):
          index = x + rows + stack
          ras0 = [0.0] * 3
          ras = [0.0] * 3
          ijk = [x + extent[0], y + extent[2], z + extent[4]] # Add the extent +++.
          iwTransform.TransformPoint(ijk, ras0)
          planeTransform.TransformPoint(ras0, ras)
          if (ras[2] < 0.0):
            sideB.GetPointData().GetArray(0).SetValue(index, 0)
          else:
            sideA.GetPointData().GetArray(0).SetValue(index, 0)

    updatedExtentA = SegmentationHelper.getSegmentMinimumExtent(sideA)
    updatedExtentB = SegmentationHelper.getSegmentMinimumExtent(sideB)
    updatedImageDataA = SegmentationHelper.padSegment(sideA, updatedExtentA)
    updatedImageDataB = SegmentationHelper.padSegment(sideB, updatedExtentB)

    sideAId = segmentation.AddSegmentFromBinaryLabelmapRepresentation(updatedImageDataA, slicer.mrmlScene.GenerateUniqueName(segmentName + "_A"))
    sideBId = segmentation.AddSegmentFromBinaryLabelmapRepresentation(updatedImageDataB, slicer.mrmlScene.GenerateUniqueName(segmentName + "_B"))
    
    return [sideAId, sideBId]

# *******************************************************************************
  @staticmethod
  def getSegmentMinimumExtent(source):
    if (source is None):
      return
    if (not source.IsTypeOf("vtkOrientedImageData")):
      raise ValueError("An input vtkOrientedImageData is expected.")
    
    scalarArray = source.GetPointData().GetArray(0)
    dims = source.GetDimensions()
    sourceExtent = source.GetExtent()
    minx = sourceExtent[0]
    miny = sourceExtent[2]
    minz = sourceExtent[4]
    maxx = sourceExtent[1]
    maxy = sourceExtent[3]
    maxz = sourceExtent[5]
    
    # Get the bounds of a scalar value of 1 on each axis.
    for z in range(dims[2]):
      stack = ((dims[0]) * (dims[1]) * z)
      for y in range(dims[1]):
        rows = ((dims[0]) * y)
        for x in range(dims[0]):
          index = x + rows + stack
          value = scalarArray.GetValue(index)
          if value == 0:
            continue
          """
          With this approach, min? ends up with max?,
          and max? with min?.
          They are swapped below.
          """
          minx = max(minx, x + sourceExtent[0])
          miny = max(miny, y + sourceExtent[2])
          minz = max(minz, z + sourceExtent[4])
          maxx = min(maxx, x + sourceExtent[0])
          maxy = min(maxy, y + sourceExtent[2])
          maxz = min(maxz, z + sourceExtent[4])
    
    # min and max are inverted.
    updatedExtent = [min(minx, maxx), max(minx, maxx),
                    min(miny, maxy), max(miny, maxy),
                    min(minz, maxz), max(minz, maxz)]
    
    return updatedExtent

# *******************************************************************************
  @staticmethod
  def padSegment(source, extent):
    if (source is None):
      return
    if (not source.IsTypeOf("vtkOrientedImageData")):
      raise ValueError("An input vtkOrientedImageData is expected.")
    
    padder = vtk.vtkImageConstantPad()
    padder.SetInputData(source)
    padder.SetOutputWholeExtent(extent)
    padder.Update()
    
    padded = slicer.vtkOrientedImageData()
    padded.ShallowCopy(padder.GetOutput())
    iwMatrix = vtk.vtkMatrix4x4()
    source.GetImageToWorldMatrix(iwMatrix)
    padded.SetImageToWorldMatrix(iwMatrix)
    
    return padded

# *******************************************************************************
  @staticmethod
  def createPlaneCutSegmentHelperWidget():
    csWidget = qt.QWidget()
    csWidget.setObjectName("CSWidget")
    csWidgetVLayout = qt.QVBoxLayout()
    csWidgetVLayout.setObjectName("CSWidgetVLayout")
    csWidget.setLayout(csWidgetVLayout)
    csWidgetFormLayout = qt.QFormLayout()
    csWidgetFormLayout.setObjectName("CSWidgetFormLayout")
    csWidgetVLayout.addLayout(csWidgetFormLayout)
    # Plane node selector
    csSliceNodeLabel = qt.QLabel("Plane:", csWidget)
    csSliceNodeLabel.setObjectName("CSSliceNodeLabel")
    csPlaneComboBox = slicer.qMRMLNodeComboBox(csWidget)
    csPlaneComboBox.setObjectName("CSPlaneComboBox")
    csPlaneComboBox.nodeTypes = ["vtkMRMLSliceNode", "vtkMRMLMarkupsPlaneNode"]
    csPlaneComboBox.addEnabled = False
    csPlaneComboBox.removeEnabled = False
    csPlaneComboBox.renameEnabled = False
    csPlaneComboBox.noneEnabled = True
    csPlaneComboBox.setMRMLScene( slicer.mrmlScene )
    csPlaneComboBox.setToolTip("Select a plane.")
    csWidgetFormLayout.addRow(csSliceNodeLabel, csPlaneComboBox)
    # Apply button
    csApplyButton = qt.QToolButton(csWidget)
    csApplyButton.setObjectName("CSApplyButton")
    csApplyButton.setText("Apply")
    csApplyButton.setSizePolicy(qt.QSizePolicy.Minimum, qt.QSizePolicy.Fixed)
    csApplyButton.connect("clicked()", lambda: SegmentationHelper.apply( csPlaneComboBox.currentNode()))
    csWidgetVLayout.addWidget(csApplyButton)
    
    return csWidget
