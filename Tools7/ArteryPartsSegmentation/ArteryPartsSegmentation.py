import logging
import os
from typing import Annotated, Optional

import vtk, qt

import slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
from slicer.parameterNodeWrapper import (
  parameterNodeWrapper,
  WithinRange,
)

from slicer import vtkMRMLScalarVolumeNode


#
# ArteryPartsSegmentation
#

class ArteryPartsSegmentation(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Artery parts segmentation"
    self.parent.categories = ["Utilities.Tools7"]
    self.parent.dependencies = []
    self.parent.contributors = ["Saleem Edah-Tally [Surgeon] [Hobbyist developer]"] 
    self.parent.helpText = """
Segment a contrasted diseased artery in three parts inside a Shape::Tube node.
See more information in the <a href="https://gitlab.com/chir-set/Tools7/">documentation</a>.
"""
    # TODO: replace with organization, grant and thanks
    self.parent.acknowledgementText = """
This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc., Andras Lasso, PerkLab,
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
"""

#
# ArteryPartsSegmentationWidget
#

class ArteryPartsSegmentationWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
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
    self._updatingGUIFromParameterNode = False
    # Keep track of these as they are used in many places.
    self.TubeSegmentID = ""
    self.LumenSegmentID = ""
    self.SegmentEditorWidget = None
    self.SplitVolumeNode = None
    self.menu = None
    self.actionShow3D = None
    self.actionShowLesion = None
    self.actionShowLumen = None
    self.actionShowCalcification = None

  def setup(self) -> None:
    """
    Called when the user opens the module the first time and the widget is initialized.
    """
    ScriptedLoadableModuleWidget.setup(self)

    # Load widget from .ui file (created by Qt Designer).
    # Additional widgets can be instantiated manually and added to self.layout.
    uiWidget = slicer.util.loadUI(self.resourcePath('UI/ArteryPartsSegmentation.ui'))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)

    # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
    # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
    # "setMRMLScene(vtkMRMLScene*)" slot.
    uiWidget.setMRMLScene(slicer.mrmlScene)

    # Create logic class. Logic implements all computations that should be possible to run
    # in batch mode, without a graphical user interface.
    self.logic = ArteryPartsSegmentationLogic()
    self.ui.parameterSetSelector.addAttribute("vtkMRMLScriptedModuleNode", "ModuleName", self.moduleName)

    # Whatever value is set in designer, minimum is shown as 99.0.
    self.ui.lumenIntensityRangeWidget.minimumValue = 200.0
    self.ui.lumenIntensityRangeWidget.maximumValue = 450.0
    self.ui.lumenIntensityRangeWidget.setRange(-100.0, 900.0)

    self.ui.optionsCollapsibleButton.setChecked(False)

    self.menu = qt.QMenu(self.ui.menuToolButton)
    self.menu.setObjectName("SegmentVisibilityMenu")
    self.ui.menuToolButton.setMenu(self.menu)
    self.ui.menuToolButton.connect("clicked()", lambda: self.ui.menuToolButton.showMenu())

    self.actionShow3D = self.menu.addAction("Show 3D")
    self.actionShow3D.setCheckable(True)
    self.actionShow3D.checked = True
    self.actionShow3D.setData(MENU_SHOW_3D_DATA)
    self.actionShow3D.connect("triggered(bool)", self.onShow3D)
    self.menu.addSeparator()

    self.actionShowSoftLesion = self.menu.addAction("Show soft lesion")
    self.actionShowSoftLesion.setCheckable(True)
    self.actionShowSoftLesion.checked = True
    self.actionShowSoftLesion.setData(MENU_SHOW_SOFTLESION_DATA)
    self.actionShowSoftLesion.connect("triggered(bool)", lambda data : self.onShowSegment(MENU_SHOW_SOFTLESION_DATA, data))

    self.actionShowLumen = self.menu.addAction("Show lumen")
    self.actionShowLumen.setCheckable(True)
    self.actionShowLumen.checked = True
    self.actionShowLumen.setData(MENU_SHOW_LUMEN_DATA)
    self.actionShowLumen.connect("triggered(bool)", lambda data : self.onShowSegment(MENU_SHOW_LUMEN_DATA, data))

    self.actionShowCalcification = self.menu.addAction("Show calcification")
    self.actionShowCalcification.setCheckable(True)
    self.actionShowCalcification.checked = True
    self.actionShowCalcification.setData(MENU_SHOW_CALCIFICATION_DATA)
    self.actionShowCalcification.connect("triggered(bool)", lambda data : self.onShowSegment(MENU_SHOW_CALCIFICATION_DATA, data))

    # Connections

    # These connections ensure that we update parameter node when scene is closed
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
    self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

    # Buttons
    self.ui.applyButton.connect('clicked(bool)', self.onApplyButton)
    self.ui.inputShapeSelector.connect("currentNodeChanged(vtkMRMLNode*)", lambda node: self.onMrmlNodeChanged(ROLE_INPUT_SHAPE, node))
    self.ui.inputVolumeSelector.connect("currentNodeChanged(vtkMRMLNode*)", lambda node: self.onMrmlNodeChanged(ROLE_INPUT_VOLUME, node))
    self.ui.outputSegmentationSelector.connect("currentNodeChanged(vtkMRMLNode*)", lambda node: self.onMrmlNodeChanged(ROLE_OUTPUT_SEGMENTATION, node))
    self.ui.outputSegmentationSelector.connect("currentSegmentChanged(QString)", self.onSegmentChanged)
    # rangeChanged(double, double) fails.
    self.ui.lumenIntensityRangeWidget.connect('minimumValueChanged(double)', lambda value: self.onIntensityRangeChanged(value, self.ui.lumenIntensityRangeWidget.maximumValue))
    self.ui.lumenIntensityRangeWidget.connect('maximumValueChanged(double)', lambda value: self.onIntensityRangeChanged(self.ui.lumenIntensityRangeWidget.minimumValue, value))
    self.ui.previewToolButton.connect('clicked(bool)', self.onPreview)
    self.ui.softCalcificationCheckBox.connect('toggled(bool)', self.onAccountForSoftCalcification)
    self.ui.extrusionGroupBox.connect('toggled(bool)', self.onExtrusionToggled)
    self.ui.extrusionKernelSizeSpinBox.connect("valueChanged(double)", lambda value: self.onSpinBoxChanged(ROLE_EXTRUSION_KERNEL_SIZE, value))

    self.ui.parameterSetSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.setParameterNode)
    self.ui.parameterSetUpdateUIToolButton.connect("clicked(bool)", self.onParameterSetUpdateUiClicked)

    # Make sure parameter node is initialized (needed for module reload)
    self.initializeParameterNode()

    extensionNames = ["SegmentEditorExtraEffects", "SlicerVMTK", "ExtraMarkups"]
    for extensionName in extensionNames:
      em = slicer.app.extensionsManagerModel()
      em.interactive = True
      restart = False
      if extensionName == "ExtraMarkups": # last
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

  def initializeParameterNode(self) -> None:
    """
    Ensure parameter node exists and observed.
    """
    # Parameter node stores all user choices in parameter values, node selections, etc.
    # so that when the scene is saved and reloaded, these settings are restored.

    # The initial parameter node originates from logic and is picked up by the parameter set combobox.
    # Other parameter nodes are created by the parameter set combobox and used here.
    if not self._parameterNode:
      self.setParameterNode(self.logic.getParameterNode())
      wasBlocked = self.ui.parameterSetSelector.blockSignals(True)
      self.ui.parameterSetSelector.setCurrentNode(self._parameterNode)
      self.ui.parameterSetSelector.blockSignals(wasBlocked)

  def setParameterNode(self, inputParameterNode: slicer.vtkMRMLScriptedModuleNode) -> None:
    self.ui.previewToolButton.setChecked(False)
    self.exitPreview()
    if inputParameterNode == self._parameterNode:
      return
    self._parameterNode = inputParameterNode

    self.logic.setParameterNode(self._parameterNode)
    if self._parameterNode:
      self.logic.setDefaultParameters()
      self.updateGUIFromParameterNode()
      self.onParameterSetUpdateUiClicked()

  def onApplyButton(self) -> None:

    with slicer.util.tryWithErrorDisplay("Failed to compute results.", waitCursor=True):
      if not self.checkNodes():
          return

      self.ui.previewToolButton.setChecked(False)
      self.exitPreview()

      self.logic.process()

    self.onShow3D(int(self._parameterNode.GetParameter(ROLE_SHOW3D)))

  def onParameterSetUpdateUiClicked(self):
    self.ui.previewToolButton.setChecked(False)
    self.exitPreview()
    if not self._parameterNode:
      return

    outputSegmentation = self._parameterNode.GetNodeReference(ROLE_OUTPUT_SEGMENTATION)
    inputVolume = self._parameterNode.GetNodeReference(ROLE_INPUT_VOLUME)

    if outputSegmentation:
      # Create segment editor object if needed.
      segmentEditorModuleWidget = slicer.util.getModuleWidget("SegmentEditor")
      seWidget = segmentEditorModuleWidget.editor
      seWidget.setSegmentationNode(outputSegmentation)
    if inputVolume:
      slicer.util.setSliceViewerLayers(background = inputVolume.GetID(), fit = True)

  def onMrmlNodeChanged(self, role, node):
      if self._parameterNode:
          self._parameterNode.SetNodeReferenceID(role, node.GetID() if node else None)

  def onSpinBoxChanged(self, role, value):
    if self._parameterNode:
      self._parameterNode.SetParameter(role, str(value))

  def onBooleanToggled(self, role, checked):
    if self._parameterNode:
      self._parameterNode.SetParameter(role, str(1) if checked else str(0))

  def onSegmentChanged(self, segmentID):
    if (segmentID is None) or (segmentID == ""):
      self.ui.previewToolButton.setText("Preview")
      self.ui.previewToolButton.setCheckable(True)
    else:
      self.ui.previewToolButton.setText("Probe")
      self.ui.previewToolButton.setCheckable(False)

  def updateGUIFromParameterNode(self):
    if self._parameterNode is None or self._updatingGUIFromParameterNode:
      return

    # Make sure GUI changes do not call updateParameterNodeFromGUI (it could cause infinite loop)
    self._updatingGUIFromParameterNode = True

    self.ui.inputShapeSelector.setCurrentNode(self._parameterNode.GetNodeReference(ROLE_INPUT_SHAPE))
    self.ui.inputVolumeSelector.setCurrentNode(self._parameterNode.GetNodeReference(ROLE_INPUT_VOLUME))
    self.ui.outputSegmentationSelector.setCurrentNode(self._parameterNode.GetNodeReference(ROLE_OUTPUT_SEGMENTATION))
    self.ui.lumenIntensityRangeWidget.setValues(float(self._parameterNode.GetParameter(ROLE_INTENSITY_MIN)), float(self._parameterNode.GetParameter(ROLE_INTENSITY_MAX)))
    self.ui.softCalcificationCheckBox.setChecked(int(self._parameterNode.GetParameter(ROLE_SOFT_CALCIFICATION)))
    self.ui.extrusionGroupBox.setChecked(int(self._parameterNode.GetParameter(ROLE_REMOVE_LUMEN_EXTRUSION)))
    self.ui.extrusionKernelSizeSpinBox.setValue(float(self._parameterNode.GetParameter(ROLE_EXTRUSION_KERNEL_SIZE)))
    self.actionShow3D.setChecked(int(self._parameterNode.GetParameter(ROLE_SHOW3D)))
    self.actionShowSoftLesion.setChecked(int(self._parameterNode.GetParameter(ROLE_SHOW_SOFTLESION)))
    self.actionShowLumen.setChecked(int(self._parameterNode.GetParameter(ROLE_SHOW_LUMEN)))
    self.actionShowCalcification.setChecked(int(self._parameterNode.GetParameter(ROLE_SHOW_CALCIFICATION)))

    self._updatingGUIFromParameterNode = False

  """
  Use the 'Threshold' effect to preview the lumen. The intensity range can be
  adjusted using the slider. Mouse dragging in slice views is not taken into
  account. The effect itself is never applied.
  If a lumen segment is provides, probe the intensity range of the volume
  enclosed in the tube and offer to use it.
  """
  def onPreview(self) -> None:
    if (not self._parameterNode):
      return
    if not self.checkNodes():
      return

    shapeNode = self._parameterNode.GetNodeReference(ROLE_INPUT_SHAPE)
    volumeNode = self._parameterNode.GetNodeReference(ROLE_INPUT_VOLUME)
    segmentationNode = self._parameterNode.GetNodeReference(ROLE_OUTPUT_SEGMENTATION)

    segmentID = self.ui.outputSegmentationSelector.currentSegmentID()
    if (segmentID):
      with slicer.util.tryWithErrorDisplay("Failed to compute results.", waitCursor=True):
        lumenIntensityRange = self.logic.getEnclosedVolumeIntensityRangeFromSegment(volumeNode, shapeNode, segmentationNode, segmentID)
        self.ui.lumenIntensityRangeWidget.setValues(lumenIntensityRange[0], lumenIntensityRange[1])
        if (volumeNode):
          slicer.util.setSliceViewerLayers(background = volumeNode.GetID())
      return

    # Clean everything if we exit preview mode.
    if (not self.ui.previewToolButton.isChecked()) or (not self._parameterNode):
      self.exitPreview()
      return
    
    # Create slicer.modules.SegmentEditorWidget
    slicer.modules.segmenteditor.widgetRepresentation()
    self.SegmentEditorWidget = slicer.modules.SegmentEditorWidget.editor
    seWidget = self.SegmentEditorWidget
    seWidget.setSegmentationNode(segmentationNode)
    seWidget.setSourceVolumeNode(volumeNode)
    segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(volumeNode)

    # Crop the volume to the inside of the Tube using 'Split volume'.
    tubePolyData = shapeNode.GetCappedTubeWorld()
    segmentationNode.CreateClosedSurfaceRepresentation()
    self.TubeSegmentID = segmentationNode.AddSegmentFromClosedSurfaceRepresentation(tubePolyData, "Tube")
    seWidget.mrmlSegmentEditorNode().SetSelectedSegmentID(self.TubeSegmentID)

    intensityRange = volumeNode.GetImageData().GetScalarRange()
    seWidget.setActiveEffectByName("Split volume")
    effect = seWidget.activeEffect()
    # Fill with an intensity that does not exist in the volume, to avoid space outside the Tube later.
    effect.setParameter("FillValue", intensityRange[0] - 1)
    effect.setParameter("ApplyToAllVisibleSegments", 0)
    effect.self().onApply()
    seWidget.setActiveEffectByName(None)

    # Get the split volume. 'Split volume' effect does not provide it.
    allScalarVolumeNodes = slicer.mrmlScene.GetNodesByClass("vtkMRMLScalarVolumeNode")
    self.SplitVolumeNode = allScalarVolumeNodes.GetItemAsObject(allScalarVolumeNodes.GetNumberOfItems() - 1)
    splitVolumeNode = self.SplitVolumeNode
    seWidget.setSourceVolumeNode(splitVolumeNode)
    segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(splitVolumeNode)

    # The tube segment passed to 'Split volume' is no longer needed.
    if segmentationNode.GetSegmentation().GetSegment(self.TubeSegmentID):
      segmentationNode.GetSegmentation().RemoveSegment(self.TubeSegmentID)
    self.TubeSegmentID = ""

    # Create a segment to preview the lumen in slice views using 'Threshold' effect.
    self.LumenSegmentID = segmentationNode.GetSegmentation().AddEmptySegment("LumenPreview")
    seWidget.mrmlSegmentEditorNode().SetSelectedSegmentID(self.LumenSegmentID)
    seWidget.setActiveEffectByName("Threshold")
    effect = seWidget.activeEffect()
    effect.setParameter("MinimumThreshold", str(self.ui.lumenIntensityRangeWidget.minimumValue))
    effect.setParameter("MaximumThreshold", str(self.ui.lumenIntensityRangeWidget.maximumValue))
    # Don't apply, just a preview to get intensity range.

    # Reparent subject hierarchy items.
    shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
    shSplitVolumeId = shNode.GetItemByDataNode(splitVolumeNode)
    shSplitVolumeFolderId = shNode.GetItemParent(shSplitVolumeId) # To be removed.
    shSplitVolumeStudyId = shNode.GetItemParent(shSplitVolumeFolderId) # Is root scene ID for NRRD files.
    shSegmentationId = shNode.GetItemByDataNode(segmentationNode)
    shNode.SetItemParent(shSplitVolumeId, shSplitVolumeStudyId)
    shNode.SetItemParent(shSegmentationId, shSplitVolumeStudyId)
    if shNode.GetItemLevel(shSplitVolumeFolderId) == "Folder":
      shNode.RemoveItem(shSplitVolumeFolderId)

    slicer.util.setSliceViewerLayers(fit = True)

  # Remove all temporary objects.
  def exitPreview(self) -> None:
    segmentationNode = self.ui.outputSegmentationSelector.currentNode()
    # Terminate any active effect.
    if self.SegmentEditorWidget:
      self.SegmentEditorWidget.setActiveEffectByName(None)
      self.SegmentEditorWidget = None
    if segmentationNode and segmentationNode.GetSegmentation().GetSegment(self.TubeSegmentID):
      segmentationNode.GetSegmentation().RemoveSegment(self.TubeSegmentID)
      self.TubeSegmentID = ""
    if segmentationNode and segmentationNode.GetSegmentation().GetSegment(self.LumenSegmentID):
      segmentationNode.GetSegmentation().RemoveSegment(self.LumenSegmentID)
      self.LumenSegmentID = ""
    if self.SplitVolumeNode:
      slicer.mrmlScene.RemoveNode(self.SplitVolumeNode)
      self.SplitVolumeNode = None
    if not self._parameterNode:
      return
    volumeNode = self._parameterNode.GetNodeReference(ROLE_INPUT_VOLUME)
    if (volumeNode):
      slicer.util.setSliceViewerLayers(background = volumeNode.GetID()) # +++, else, it would be the last of the loaded volumes.

  # Tune the active 'Threshold' effect, used for preview only.
  def onIntensityRangeChanged(self, min, max) -> None:
    if (not self._parameterNode):
      return
    self.ui.lumenIntensityRangeWidget.setRange(-100.0, 900.0)
    self._parameterNode.SetParameter(ROLE_INTENSITY_MIN, str(min))
    self._parameterNode.SetParameter(ROLE_INTENSITY_MAX, str(max))
    if self.SegmentEditorWidget:
      seWidget = self.SegmentEditorWidget
      seWidget.setActiveEffectByName("Threshold")
      effect = seWidget.activeEffect()
      effect.setParameter("MinimumThreshold", str(min))
      effect.setParameter("MaximumThreshold", str(max))

  def onAccountForSoftCalcification(self, value) -> None:
    self.onBooleanToggled(ROLE_SOFT_CALCIFICATION, value)
    if value:
      self.ui.extrusionGroupBox.setChecked(True)
      self.onBooleanToggled(ROLE_REMOVE_LUMEN_EXTRUSION, 1)

  def onExtrusionToggled(self, value) -> None:
    self.onSpinBoxChanged(ROLE_EXTRUSION_KERNEL_SIZE, self.ui.extrusionKernelSizeSpinBox.value)
    self.onBooleanToggled(ROLE_REMOVE_LUMEN_EXTRUSION, value)
    if self.ui.softCalcificationCheckBox.isChecked(): # Force extrusion removal.
      self.ui.extrusionGroupBox.setChecked(True)
      self.onBooleanToggled(ROLE_REMOVE_LUMEN_EXTRUSION, 1)

  def showStatusMessage(self, message, timeout = 3000) -> None:
    slicer.util.showStatusMessage(message, timeout)
    slicer.app.processEvents()

  def checkNodes(self) -> None:
    shapeNode = self._parameterNode.GetNodeReference(ROLE_INPUT_SHAPE)
    if not shapeNode:
      self.showStatusMessage("No shape node selected.")
      return False
    if shapeNode.GetShapeName() != slicer.vtkMRMLMarkupsShapeNode.Tube:
      self.showStatusMessage("Shape node is not a Tube.")
      return False
    if shapeNode.GetNumberOfUndefinedControlPoints():
      self.showStatusMessage("Shape node has undefined control points.")
      return False
    if shapeNode.GetNumberOfControlPoints() < 4:
      self.showStatusMessage("Shape node has less than 4 control points.")
      return False
    volumeNode = self._parameterNode.GetNodeReference(ROLE_INPUT_VOLUME)
    if not volumeNode:
      self.showStatusMessage("No volume node selected.")
      return False

    segmentationNode = self._parameterNode.GetNodeReference(ROLE_OUTPUT_SEGMENTATION)
    if not segmentationNode:
      segmentationNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
      segmentationNode.CreateDefaultDisplayNodes()
      self.ui.outputSegmentationSelector.setCurrentNode(segmentationNode)
    return True

  def onShow3D(self, checked) -> None:
    if (not self._parameterNode):
      return
    segmentationNode = self._parameterNode.GetNodeReference(ROLE_OUTPUT_SEGMENTATION)
    if (not segmentationNode):
      return
    self.onBooleanToggled(ROLE_SHOW3D, checked)
    if checked:
      # Poked from qMRMLSegmentationShow3DButton.cxx
      if segmentationNode.GetSegmentation().CreateRepresentation(slicer.vtkSegmentationConverter.GetSegmentationClosedSurfaceRepresentationName()):
        segmentationNode.GetDisplayNode().SetPreferredDisplayRepresentationName3D(slicer.vtkSegmentationConverter.GetSegmentationClosedSurfaceRepresentationName())
    else:
      segmentationNode.GetSegmentation().RemoveRepresentation(slicer.vtkSegmentationConverter.GetSegmentationClosedSurfaceRepresentationName())

  def onShowSegment(self, data, checked):
    if (not self._parameterNode):
      return
    segmentationNode = self._parameterNode.GetNodeReference(ROLE_OUTPUT_SEGMENTATION)
    if (not segmentationNode):
      return

    segmentID = ""
    if data == MENU_SHOW_SOFTLESION_DATA:
      segmentID = SEGMENT_NAME_SOFTLESION
      self.onBooleanToggled(ROLE_SHOW_SOFTLESION, checked)
    elif data == MENU_SHOW_LUMEN_DATA:
      segmentID = SEGMENT_NAME_LUMEN
      self.onBooleanToggled(ROLE_SHOW_LUMEN, checked)
    elif data == MENU_SHOW_CALCIFICATION_DATA:
      segmentID = SEGMENT_NAME_CALCIFICATION
      self.onBooleanToggled(ROLE_SHOW_CALCIFICATION, checked)
    else:
      raise ValueError("Unknown segment.")
    
    segmentationNode.GetDisplayNode().SetSegmentVisibility(segmentID, checked)
#
# ArteryPartsSegmentationLogic
#

class ArteryPartsSegmentationLogic(ScriptedLoadableModuleLogic):
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
      self._parameterNode = None
      """
      Avoid on repeat calls:
        Exception ignored in: <function AbstractScriptedSegmentEditorAutoCompleteEffect.__del__ at 0x7f5cf0394540>
        Traceback (most recent call last):
          File "/home/user/programs/Slicer/lib/Slicer-5.9/qt-scripted-modules/SegmentEditorEffects/AbstractScriptedSegmentEditorAutoCompleteEffect.py", line 67, in __del__
            self.observeSegmentation(False)
          File "/home/user/programs/Slicer/lib/Slicer-5.9/qt-scripted-modules/SegmentEditorEffects/AbstractScriptedSegmentEditorAutoCompleteEffect.py", line 212, in observeSegmentation
            parameterSetNode = self.scriptedEffect.parameterSetNode()
                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        ValueError: Trying to call 'parameterSetNode' on a destroyed qSlicerSegmentEditorScriptedEffect object
      """
      self._segmentEditorWidget = None

  def setParameterNode(self, inputParameterNode):
      self._parameterNode = inputParameterNode

  def setDefaultParameters(self):
    if not self._parameterNode:
      return

    if (not self._parameterNode.HasParameter(ROLE_INTENSITY_MIN)):
      self._parameterNode.SetParameter(ROLE_INTENSITY_MIN, str(200.0))
    if (not self._parameterNode.HasParameter(ROLE_INTENSITY_MAX)):
      self._parameterNode.SetParameter(ROLE_INTENSITY_MAX, str(450.0))
    if (not self._parameterNode.HasParameter(ROLE_SOFT_CALCIFICATION)):
      self._parameterNode.SetParameter(ROLE_SOFT_CALCIFICATION, str(0))
    if (not self._parameterNode.HasParameter(ROLE_REMOVE_LUMEN_EXTRUSION)):
      self._parameterNode.SetParameter(ROLE_REMOVE_LUMEN_EXTRUSION, str(0))
    if (not self._parameterNode.HasParameter(ROLE_EXTRUSION_KERNEL_SIZE)):
      self._parameterNode.SetParameter(ROLE_EXTRUSION_KERNEL_SIZE, str(1.70))
    if (not self._parameterNode.HasParameter(ROLE_SHOW3D)):
      self._parameterNode.SetParameter(ROLE_SHOW3D, str(1))
    if (not self._parameterNode.HasParameter(ROLE_SHOW_SOFTLESION)):
      self._parameterNode.SetParameter(ROLE_SHOW_SOFTLESION, str(1))
    if (not self._parameterNode.HasParameter(ROLE_SHOW_LUMEN)):
      self._parameterNode.SetParameter(ROLE_SHOW_LUMEN, str(1))
    if (not self._parameterNode.HasParameter(ROLE_SHOW_CALCIFICATION)):
      self._parameterNode.SetParameter(ROLE_SHOW_CALCIFICATION, str(1))

  def process(self) -> None:

    if not self._parameterNode:
      raise ValueError(_("Parameter node is None."))

    shapeNode = self._parameterNode.GetNodeReference(ROLE_INPUT_SHAPE)
    volumeNode = self._parameterNode.GetNodeReference(ROLE_INPUT_VOLUME)
    segmentationNode = self._parameterNode.GetNodeReference(ROLE_OUTPUT_SEGMENTATION)
    lumenIntensityMin = float(self._parameterNode.GetParameter(ROLE_INTENSITY_MIN))
    lumenIntensityMax = float(self._parameterNode.GetParameter(ROLE_INTENSITY_MAX))
    accountForSoftCalcification = int(self._parameterNode.GetParameter(ROLE_SOFT_CALCIFICATION))
    extrusionKernelSize = 0.0
    if int(self._parameterNode.GetParameter(ROLE_REMOVE_LUMEN_EXTRUSION)):
      extrusionKernelSize = float(self._parameterNode.GetParameter(ROLE_EXTRUSION_KERNEL_SIZE))

    if not shapeNode or not volumeNode or not segmentationNode:
      raise ValueError("Invalid input or output nodes.")
    if shapeNode.GetShapeName() != slicer.vtkMRMLMarkupsShapeNode.Tube:
      raise ValueError("Shape node is not a Tube.")
    if shapeNode.GetNumberOfUndefinedControlPoints():
      raise ValueError("Shape node has undefined control points.")
    if shapeNode.GetNumberOfControlPoints() < 4:
      raise ValueError("Shape node has less than 4 control points.")

    import time
    startTime = time.time()
    logging.info('Processing started')

    # Create slicer.modules.SegmentEditorWidget
    slicer.modules.segmenteditor.widgetRepresentation()
    seWidget = slicer.modules.SegmentEditorWidget.editor
    seWidget.setSegmentationNode(segmentationNode)
    seWidget.setSourceVolumeNode(volumeNode)
    segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(volumeNode)

    # Use OverwriteNone to preserve alien segments.
    seWidget.mrmlSegmentEditorNode().SetMaskMode(slicer.vtkMRMLSegmentationNode.EditAllowedEverywhere)
    seWidget.mrmlSegmentEditorNode().SourceVolumeIntensityMaskOff()
    seWidget.mrmlSegmentEditorNode().SetOverwriteMode(seWidget.mrmlSegmentEditorNode().OverwriteNone)

    # Crop the volume to the inside of the Tube using 'Split volume'.
    tubePolyData = shapeNode.GetCappedTubeWorld()
    segmentationNode.CreateClosedSurfaceRepresentation()
    tubeSegmentID = segmentationNode.AddSegmentFromClosedSurfaceRepresentation(tubePolyData, "Tube")
    seWidget.mrmlSegmentEditorNode().SetSelectedSegmentID(tubeSegmentID)

    intensityRange = volumeNode.GetImageData().GetScalarRange()
    seWidget.setActiveEffectByName("Split volume")
    effect = seWidget.activeEffect()
    # Fill with an intensity that does not exist in the volume, to avoid space outside the Tube later.
    effect.setParameter("FillValue", intensityRange[0] - 1)
    effect.setParameter("ApplyToAllVisibleSegments", 0)
    effect.self().onApply()
    seWidget.setActiveEffectByName(None)

    # Get the split volume. 'Split volume' effect does not provide it.
    allScalarVolumeNodes = slicer.mrmlScene.GetNodesByClass("vtkMRMLScalarVolumeNode")
    splitVolumeNode = allScalarVolumeNodes.GetItemAsObject(allScalarVolumeNodes.GetNumberOfItems() - 1)
    # Use the split volume.
    segmentationNode.GetSegmentation().RemoveSegment(tubeSegmentID)
    seWidget.setSourceVolumeNode(splitVolumeNode)
    segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(splitVolumeNode)

    # Create Lumen segment first.
    segmentName = slicer.mrmlScene.GenerateUniqueName("Lumen")
    if segmentationNode.GetSegmentation().GetSegment(SEGMENT_NAME_LUMEN):
      segmentationNode.GetSegmentation().RemoveSegment(SEGMENT_NAME_LUMEN)
    """
    Specified colours are badly handled. In slice views, it is not the
    expected colour. In the segment editor colour column, and in the 3D
    view, it's always white.
    Same results if the colour is set separately.
    But it works as expected in the python console!
    """
    # lumenSegmentID = segmentationNode.GetSegmentation().AddEmptySegment(SEGMENT_NAME_LUMEN, segmentName, [216.0, 101.0, 79.0])    
    lumenSegmentID = segmentationNode.GetSegmentation().AddEmptySegment(SEGMENT_NAME_LUMEN, segmentName)
    # segmentationNode.GetSegmentation().GetSegment(lumenSegmentID).SetColor([216.0, 101.0, 79.0])
    seWidget.mrmlSegmentEditorNode().SetSelectedSegmentID(lumenSegmentID)
    seWidget.setActiveEffectByName("Threshold")
    effect = seWidget.activeEffect()
    effect.setParameter("MinimumThreshold", str(lumenIntensityMin))
    effect.setParameter("MaximumThreshold", str(lumenIntensityMax))
    effect.self().onApply()
    seWidget.setActiveEffectByName(None)

    """
    Threshold effect will include 'soft' calcification, the intensities of
    which are in the lumen intensity range. Hairy extrusions may connect
    them to the lumen. Break these.
    """
    if accountForSoftCalcification or (extrusionKernelSize > 0.0):
      import SegmentEditorSmoothingEffect
      seWidget.setActiveEffectByName("Smoothing")
      effect = seWidget.activeEffect()
      effect.setParameter("SmoothingMethod", SegmentEditorSmoothingEffect.MORPHOLOGICAL_OPENING)
      effect.setParameter("KernelSizeMm", str(extrusionKernelSize))
      effect.self().onApply()
      seWidget.setActiveEffectByName(None)

    """
    The 'soft' calcification is usually islands on the artery's wall. Remove
    them so that they are later rightly segmented as calcification.
    Caveat : an artery with an obliterated portion cannot be fully segmented
    in parts with this effect, only one part of the lumen will remain.
    Very badly diseased arteries with too much 'soft' calcification may be
    also bad candidates for this approach.
    """
    if accountForSoftCalcification:
      seWidget.setActiveEffectByName("Islands")
      effect = seWidget.activeEffect()
      effect.setParameter("Operation", "KEEP_LARGEST_ISLAND")
      effect.self().onApply()
      seWidget.setActiveEffectByName(None)

    """
    Threshold the calcification. On request, try to include the 'soft' calcification
    too. Their intensities are within the intensity range of the lumen, so
    we segment outside all other segments.
    """
    seWidget.mrmlSegmentEditorNode().SetMaskMode(slicer.vtkMRMLSegmentationNode.EditAllowedOutsideAllSegments)
    seWidget.mrmlSegmentEditorNode().SourceVolumeIntensityMaskOff()
    seWidget.mrmlSegmentEditorNode().SetOverwriteMode(seWidget.mrmlSegmentEditorNode().OverwriteNone)

    segmentName = slicer.mrmlScene.GenerateUniqueName("Calcification")
    if segmentationNode.GetSegmentation().GetSegment(SEGMENT_NAME_CALCIFICATION):
      segmentationNode.GetSegmentation().RemoveSegment(SEGMENT_NAME_CALCIFICATION)
    # calcifiedLesionSegmentID = segmentationNode.GetSegmentation().AddEmptySegment(SEGMENT_NAME_CALCIFICATION, segmentName, [241.0, 214.0, 145.0])
    calcifiedLesionSegmentID = segmentationNode.GetSegmentation().AddEmptySegment(SEGMENT_NAME_CALCIFICATION, segmentName)
    # segmentationNode.GetSegmentation().GetSegment(calcifiedLesionSegmentID).SetColor([241.0, 214.0, 145.0])
    seWidget.mrmlSegmentEditorNode().SetSelectedSegmentID(calcifiedLesionSegmentID)
    seWidget.setActiveEffectByName("Threshold")
    effect = seWidget.activeEffect()
    # 2.0 seems a good minimal, may be optimized later, or given a UI widget.
    minimumThresholdIntensity = lumenIntensityMax + 1
    if accountForSoftCalcification:
      # Grab some intensities that overlap with those of the lumen.
      minimumThresholdIntensity = (lumenIntensityMin + lumenIntensityMax) / 2.0
    effect.setParameter("MinimumThreshold", str(minimumThresholdIntensity))
    effect.setParameter("MaximumThreshold", str(intensityRange[1]))
    effect.self().onApply()
    seWidget.setActiveEffectByName(None)
    """
    It is probable that the calcification segment will need an extrusion
    smoothing too if it *predominates much* on soft lesion.
    Manual cleaning with the brush may be helpful too.
    """

    # Let everything else be soft lesion, or simply patches of the wall.
    seWidget.mrmlSegmentEditorNode().SetMaskMode(slicer.vtkMRMLSegmentationNode.EditAllowedEverywhere)
    seWidget.mrmlSegmentEditorNode().SourceVolumeIntensityMaskOff()
    seWidget.mrmlSegmentEditorNode().SetOverwriteMode(seWidget.mrmlSegmentEditorNode().OverwriteNone)

    segmentName = slicer.mrmlScene.GenerateUniqueName("Soft lesion")
    if segmentationNode.GetSegmentation().GetSegment(SEGMENT_NAME_SOFTLESION):
      segmentationNode.GetSegmentation().RemoveSegment(SEGMENT_NAME_SOFTLESION)
    # softLesionSegmentID = segmentationNode.GetSegmentation().AddEmptySegment(SEGMENT_NAME_SOFTLESION, segmentName, [47.0, 150.0, 103.0])
    softLesionSegmentID = segmentationNode.GetSegmentation().AddEmptySegment(SEGMENT_NAME_SOFTLESION, segmentName)
    # segmentationNode.GetSegmentation().GetSegment(softLesionSegmentID).SetColor([47.0, 150.0, 103.0])
    seWidget.mrmlSegmentEditorNode().SetSelectedSegmentID(softLesionSegmentID)
    seWidget.setActiveEffectByName("Threshold")
    effect = seWidget.activeEffect()
    effect.setParameter("MinimumThreshold", str(intensityRange[0]))
    # Leave lumenIntensityMin to the lumen.
    effect.setParameter("MaximumThreshold", str(lumenIntensityMin - 1))
    effect.self().onApply()
    seWidget.setActiveEffectByName(None)
    """
    It is probable that the soft lesion segment will need an extrusion
    smoothing too if it *predominates much* on calcification.
    Manual cleaning with the brush may be helpful too.
    """

    # Reparent subject hierarchy items.
    shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
    shSplitVolumeId = shNode.GetItemByDataNode(splitVolumeNode)
    shSplitVolumeFolderId = shNode.GetItemParent(shSplitVolumeId) # To be removed.
    shSplitVolumeStudyId = shNode.GetItemParent(shSplitVolumeFolderId) # Is root scene ID for NRRD files.
    shSegmentationId = shNode.GetItemByDataNode(segmentationNode)
    shNode.SetItemParent(shSplitVolumeId, shSplitVolumeStudyId)
    shNode.SetItemParent(shSegmentationId, shSplitVolumeStudyId)
    if shNode.GetItemLevel(shSplitVolumeFolderId) == "Folder":
      shNode.RemoveItem(shSplitVolumeFolderId)
    # Remove temporary volume and get things back.
    slicer.mrmlScene.RemoveNode(splitVolumeNode)
    seWidget.setSourceVolumeNode(volumeNode)
    segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(volumeNode)

    stopTime = time.time()
    logging.info(f'Processing completed in {stopTime-startTime:.2f} seconds')
    return [lumenSegmentID, calcifiedLesionSegmentID, softLesionSegmentID]

  def getEnclosedVolumeIntensityRangeFromSegment(self, volume, tube, sourceSegmentation, segmentID):
    if (sourceSegmentation is None) or (volume is None) or (tube is None):
      raise ValueError("Segmentation, volume or tube is None.")
    if (segmentID is None) or (len(segmentID) == 0):
      raise ValueError("Invalid segment ID.")

    if (self._segmentEditorWidget is None):
      self._segmentEditorWidget = slicer.qMRMLSegmentEditorWidget()
    seWidget = self._segmentEditorWidget
    seWidget.setMRMLScene(slicer.mrmlScene)
    mrmlSegmentEditorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
    seWidget.setMRMLSegmentEditorNode(mrmlSegmentEditorNode)

    segmentationNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
    segmentationNode.CreateDefaultDisplayNodes()
    seWidget.setSegmentationNode(segmentationNode)
    seWidget.setSourceVolumeNode(volume)
    # The copied segment has the same ID.
    if not segmentationNode.GetSegmentation().CopySegmentFromSegmentation(sourceSegmentation.GetSegmentation(), segmentID):
      seWidget.setSourceVolumeNode(None)
      seWidget.setSegmentationNode(None)
      slicer.mrmlScene.RemoveNode(segmentationNode)
      slicer.mrmlScene.RemoveNode(mrmlSegmentEditorNode)
      raise RuntimeError("Could not copy source segment.")
    
    import CrossSectionAnalysis
    csaLogic = CrossSectionAnalysis.CrossSectionAnalysisLogic()
    enclosedLumen = vtk.vtkPolyData()
    csaLogic.setInputCenterlineNode(tube)
    csaLogic.setLumenSurface(segmentationNode, segmentID)
    try:
      csaLogic.clipLumenInTube(enclosedLumen)
    except Exception as e:
      seWidget.setSourceVolumeNode(None)
      seWidget.setSegmentationNode(None)
      slicer.mrmlScene.RemoveNode(segmentationNode)
      slicer.mrmlScene.RemoveNode(mrmlSegmentEditorNode)
      raise RuntimeError("Could not intersect the tube and the lumen segment.")

    clippedSegmentId = segmentationNode.AddSegmentFromClosedSurfaceRepresentation(enclosedLumen,
                                    "ClippedLumen")
    mrmlSegmentEditorNode.SetSelectedSegmentID(clippedSegmentId)

    preferredRepresentationName = slicer.vtkSegmentationConverter.GetSegmentationClosedSurfaceRepresentationName()
    segmentationNode.GetSegmentation().RemoveRepresentation(preferredRepresentationName)
    if segmentationNode.GetSegmentation().CreateRepresentation(preferredRepresentationName):
      segmentationNode.GetDisplayNode().SetPreferredDisplayRepresentationName3D(preferredRepresentationName)
    else:
      seWidget.setSourceVolumeNode(None)
      seWidget.setSegmentationNode(None)
      slicer.mrmlScene.RemoveNode(segmentationNode)
      slicer.mrmlScene.RemoveNode(mrmlSegmentEditorNode)
      raise RuntimeError("Error creating the segmentation's preferred representation.")

    import SegmentStatistics
    ssLogic = SegmentStatistics.SegmentStatisticsLogic()
    ssLogic.getParameterNode().SetParameter("Segmentation", segmentationNode.GetID())
    ssLogic.getParameterNode().SetParameter("ScalarVolume", volume.GetID())
    ssLogic.computeStatistics()
    
    # k = ssLogic.getNonEmptyKeys()
    minSegmentHU = float(ssLogic.getStatisticsValueAsString(segmentID, "ScalarVolumeSegmentStatisticsPlugin.min"))
    maxSegmentHU = float(ssLogic.getStatisticsValueAsString(segmentID, "ScalarVolumeSegmentStatisticsPlugin.max"))

    seWidget.setSourceVolumeNode(None)
    seWidget.setSegmentationNode(None)
    slicer.mrmlScene.RemoveNode(segmentationNode)
    slicer.mrmlScene.RemoveNode(mrmlSegmentEditorNode)

    return [minSegmentHU, maxSegmentHU]
    
#
# ArteryPartsSegmentationTest
#

class ArteryPartsSegmentationTest(ScriptedLoadableModuleTest):

  def setUp(self):
      slicer.mrmlScene.Clear()

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_ArteryPartsSegmentation1()

  def test_ArteryPartsSegmentation1(self):
    self.delayDisplay("Starting the test")

    self.delayDisplay('Test passed')

ROLE_INPUT_SHAPE = "InputShape"
ROLE_INPUT_VOLUME = "InputVolume"
ROLE_OUTPUT_SEGMENTATION = "OutputSegmentation"
ROLE_INTENSITY_MIN = "IntensityMin"
ROLE_INTENSITY_MAX = "IntensityMax"
ROLE_SOFT_CALCIFICATION = "SoftCalcification"
ROLE_REMOVE_LUMEN_EXTRUSION = "RemoveLumenExtrusion"
ROLE_EXTRUSION_KERNEL_SIZE = "ExtrusionKernelSize"
ROLE_SHOW3D = "Show3D"
ROLE_SHOW_SOFTLESION = "ShowSoftLesion"
ROLE_SHOW_LUMEN = "ShowLumen"
ROLE_SHOW_CALCIFICATION = "Show3D"

MENU_SHOW_3D_DATA = 0
MENU_SHOW_SOFTLESION_DATA = 1
MENU_SHOW_LUMEN_DATA = 2
MENU_SHOW_CALCIFICATION_DATA = 3

SEGMENT_NAME_SOFTLESION = "SoftLesion"
SEGMENT_NAME_LUMEN = "Lumen"
SEGMENT_NAME_CALCIFICATION = "Calcification"

