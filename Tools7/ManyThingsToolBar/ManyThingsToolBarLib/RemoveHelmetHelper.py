import qt, vtk, slicer
from ManyThingsToolBarLib.Utils import *

slicer.segmentEditorWidget = None

class RemoveHelmetHelper():
  @staticmethod
  def removeHelmet(margin, tolerance):
    node = slicer.app.layoutManager().sliceWidget("Red").sliceLogic().GetBackgroundLayer().GetVolumeNode()
    if node is None:
        informInStatusBar("No background volume node in Red slice view.")
        return

    combo = slicer.modules.markups.toolBar().findChild(slicer.qMRMLNodeComboBox, "MarkupsNodeSelector")
    currentNode = combo.currentNode()
    if currentNode is None:
        informInStatusBar("No markups node selected.")
        return
    if not currentNode.IsTypeOf("vtkMRMLMarkupsFiducialNode"):
        informInStatusBar("Selected markups node is not a fiducial node.")
        return
    if currentNode.GetNumberOfUndefinedControlPoints():
        informInStatusBar("Selected fiducial node has undefined control points.")
        return
    if currentNode.GetNumberOfDefinedControlPoints() < 1:
        informInStatusBar("Selected fiducial node has < 1 control point.")
        return
    """
    Else, without slicer.segmentEditorWidget:
    Exception ignored in: <function AbstractScriptedSegmentEditorAutoCompleteEffect.__del__ at 0x7f8adc3945e0>
Traceback (most recent call last):
  File "/home/user/programs/Slicer/lib/Slicer-5.9/qt-scripted-modules/SegmentEditorEffects/AbstractScriptedSegmentEditorAutoCompleteEffect.py", line 67, in __del__
    self.observeSegmentation(False)
  File "/home/user/programs/Slicer/lib/Slicer-5.9/qt-scripted-modules/SegmentEditorEffects/AbstractScriptedSegmentEditorAutoCompleteEffect.py", line 212, in observeSegmentation
    parameterSetNode = self.scriptedEffect.parameterSetNode()
                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

    """
    if not slicer.segmentEditorWidget:
        slicer.segmentEditorWidget = slicer.qMRMLSegmentEditorWidget()
    seWidget = slicer.segmentEditorWidget
    seWidget.setMRMLScene(slicer.mrmlScene)
    mrmlSegmentEditorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
    seWidget.setMRMLSegmentEditorNode(mrmlSegmentEditorNode)

    segmentationNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
    segmentationNode.CreateDefaultDisplayNodes()
    seWidget.setSegmentationNode(segmentationNode)
    seWidget.setSourceVolumeNode(node)

    # Add a new segment and select it.
    segmentID = segmentationNode.GetSegmentation().AddEmptySegment()
    segment = segmentationNode.GetSegmentation().GetSegment(segmentID)
    seWidget.setCurrentSegmentID(segmentID)

    seWidget.setActiveEffectByName("Flood filling")
    ffEffect = seWidget.activeEffect()
    ffEffect.setParameter("IntensityTolerance", tolerance)
    ffEffect.setParameter("NeighborhoodSizeMm", "1.0")
    ffEffect.parameterSetNode().SetNodeReferenceID("FloodFilling.ROI", None)
    ffEffect.updateGUIFromMRML()
    # Reset segment editor masking widgets. Values set by previous work must not interfere here.
    seWidget.mrmlSegmentEditorNode().SetMaskMode(slicer.vtkMRMLSegmentationNode.EditAllowedEverywhere)
    seWidget.mrmlSegmentEditorNode().SourceVolumeIntensityMaskOff()
    seWidget.mrmlSegmentEditorNode().SetOverwriteMode(seWidget.mrmlSegmentEditorNode().OverwriteNone)

    # Apply flood filling at each fiducial point.
    points=vtk.vtkPoints()
    currentNode.GetControlPointPositionsWorld(points)
    numberOfFiducialControlPoints = points.GetNumberOfPoints()
    sliceWidget = slicer.app.layoutManager().sliceWidget("Red")
    for i in range(numberOfFiducialControlPoints):
      rasPoint = points.GetPoint(i)
      slicer.vtkMRMLSliceNode.JumpSlice(sliceWidget.sliceLogic().GetSliceNode(), *rasPoint)
      point3D = qt.QVector3D(rasPoint[0], rasPoint[1], rasPoint[2])
      point2D = ffEffect.rasToXy(point3D, sliceWidget)
      qIjkPoint = ffEffect.xyToIjk(point2D, sliceWidget, ffEffect.self().getClippedSourceImageData())
      ffEffect.self().floodFillFromPoint((int(qIjkPoint.x()), int(qIjkPoint.y()), int(qIjkPoint.z())))
    seWidget.setActiveEffect(None)
    # Hide the fiducial node.
    currentNode.GetDisplayNode().SetVisibility(False)
    # Grow
    seWidget.setActiveEffectByName("Margin")
    effect = seWidget.activeEffect()
    effect.setParameter("ApplyToAllVisibleSegments", str(0))
    effect.setParameter("MarginSizeMm", str(margin))
    effect.self().onApply()
    seWidget.setActiveEffectByName(None)
    # Mask volume
    seWidget.setActiveEffectByName("Mask volume")
    effect = seWidget.activeEffect()
    effect.parameterSetNode().SetMaskSegmentID(segmentID)
    effect.setNodeReference("InputVolume", node)
    effect.setParameter("Operation", "FILL_INSIDE")
    effect.setParameter("FillValue", str(node.GetImageData().GetScalarRange()[0] - 1))
    effect.self().updateGUIFromMRML()
    effect.self().onApply()
    outputNode = effect.self().outputVolumeSelector.currentNode()
    seWidget.setActiveEffectByName(None)
    # Show masked volume.
    slicer.util.setSliceViewerLayers(background = outputNode)

    # Cleanup.
    segmentationNode.GetSegmentation().RemoveSegment(segmentID)
    slicer.segmentEditorWidget.setSourceVolumeNode(None)
    slicer.segmentEditorWidget.setSegmentationNode(None)
    slicer.mrmlScene.RemoveNode(segmentationNode)
    slicer.mrmlScene.RemoveNode(mrmlSegmentEditorNode)
    del segmentationNode
    del mrmlSegmentEditorNode

# ----------------------------------------------------------------------------
  @staticmethod
  def createHelperWidget():
    rhWidget = qt.QWidget()
    rhWidget.setObjectName("RHWidget")
    rhWidgetVLayout = qt.QVBoxLayout()
    rhWidgetVLayout.setObjectName("RHWidgetVLayout")
    rhWidget.setLayout(rhWidgetVLayout)
    rhWidgetFormLayout = qt.QFormLayout()
    rhWidgetFormLayout.setObjectName("RHWidgetFormLayout")
    rhWidgetVLayout.addLayout(rhWidgetFormLayout)
    # Grow by.
    rhGrowByLabel = qt.QLabel("Grow by:", rhWidget)
    rhGrowByLabel.setObjectName("RHGrowByLabel")
    rhGrowBySpinBox = qt.QDoubleSpinBox(rhWidget)
    rhGrowBySpinBox.setObjectName("RHGrowBySpinBox")
    rhGrowBySpinBox.setMaximum(10.0)
    rhGrowBySpinBox.setSingleStep(0.5)
    rhGrowBySpinBox.setDecimals(1)
    rhGrowBySpinBox.setValue(3.0)
    rhGrowBySpinBox.setSuffix(" mm")
    rhGrowBySpinBox.setToolTip("Grow the segment by this amount.")
    rhGrowBySpinBox.setSizePolicy(qt.QSizePolicy.Fixed, qt.QSizePolicy.Fixed)
    rhWidgetFormLayout.addRow(rhGrowByLabel, rhGrowBySpinBox)
    # Flodd filling tolerance.
    rhToleranceLabel = qt.QLabel("Tolerance:", rhWidget)
    rhToleranceLabel.setObjectName("RHToleranceLabel")
    rhToleranceSpinBox = qt.QDoubleSpinBox(rhWidget)
    rhToleranceSpinBox.setObjectName("RHToleranceSpinBox")
    rhToleranceSpinBox.setMaximum(1000.0)
    rhToleranceSpinBox.setSingleStep(5.0)
    rhToleranceSpinBox.setDecimals(0)
    rhToleranceSpinBox.setValue(150)
    rhToleranceSpinBox.setSuffix("")
    rhToleranceSpinBox.setToolTip("Flood filling tolerance.")
    rhToleranceSpinBox.setSizePolicy(qt.QSizePolicy.Fixed, qt.QSizePolicy.Fixed)
    rhWidgetFormLayout.addRow(rhToleranceLabel, rhToleranceSpinBox)
    rhApplyButton = qt.QToolButton(rhWidget)
    # Apply button.
    rhApplyButton.setObjectName("RHApplyButton")
    rhApplyButton.setText("Apply")
    rhApplyButton.setSizePolicy(qt.QSizePolicy.Minimum, qt.QSizePolicy.Fixed)
    rhApplyButton.connect("clicked()", lambda: RemoveHelmetHelper.removeHelmet(rhGrowBySpinBox.value, rhToleranceSpinBox.value))
    rhWidgetVLayout.addWidget(rhApplyButton)
    
    return rhWidget

