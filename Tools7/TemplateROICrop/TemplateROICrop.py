import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging

from slicer import vtkMRMLScalarVolumeNode

#
# TemplateROICrop : see notes below
#
TITLE = "Template ROI Crop"
class TemplateROICrop(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = TITLE
    self.parent.categories = ["Utilities.Tools7"]
    self.parent.dependencies = []
    self.parent.contributors = ["Saleem Edah-Tally [Surgeon] [Hobbyist developer]"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
Crops a volume based on a saved template ROI.
See more information in the <a href="https://gitlab.com/chir-set/Tools7/">documentation</a>
<br/><br/>
Icon source <a href="https://icons8.com/icons/set/template--style-3d-fluency">acknowledgement</a>.
"""
    self.parent.acknowledgementText = """
This file was originally developed by Jean-Christophe Fillion-Robin, Kitware Inc.
and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 3P41RR013218-12S1.
""" # replace with organization, grant and thanks.
#
# TemplateROICropWidget
#

class TemplateROICropWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    uiWidget = slicer.util.loadUI(self.resourcePath('UI/TemplateROICrop.ui'))
    self.layout.addWidget(uiWidget)
    self.ui = slicer.util.childWidgetVariables(uiWidget)
    uiWidget.setMRMLScene(slicer.mrmlScene)
    self.ui.ROITemplateSelector.retrieveHistory()

    self.logic = TemplateROICropLogic()

    # connections
    self.ui.applyButton.connect('clicked(bool)', self.onApplyButton)
    self.ui.inputVolumeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onInputVolumeChanged)
    self.ui.gotoVRButton.connect('clicked(bool)', self.onGoToVR)
    # https://github.com/SlicerIGT/SlicerIGT/blob/master/Guidelet/GuideletLib/Guidelet.py
    #self.ui.ROITemplateSelector.connect('currentPathChanged(QString)', self.onPathChanged)
    self.ui.saveROIButton.connect('clicked()', self.onSaveROI)
    self.ui.removeROIButton.connect('clicked()', self.onRemoveROI)

  def cleanup(self):
    pass

  def onInputVolumeChanged(self):
    self.ui.outputVolumeSelector.setCurrentNode(None)
    
  def onApplyButton(self):
    outputVolumeNodeID = self.logic.run(self.ui.inputVolumeSelector.currentNode(), self.ui.ROITemplateSelector.currentPath)
    self.ui.outputVolumeSelector.setCurrentNodeID(outputVolumeNodeID)
    
  def onGoToVR(self):
    mainWindow = slicer.util.mainWindow()
    mainWindow.moduleSelector().selectModule('VolumeRendering')
  
  # Slicer hangs when a combobox item is selected !!!
  # def onPathChanged(self):
  #  self.ui.ROITemplateSelector.addCurrentPathToHistory()

  def onSaveROI(self):
    self.ui.ROITemplateSelector.addCurrentPathToHistory()

  def onRemoveROI(self):
    pathListWidget = self.ui.ROITemplateSelector
    currentPath = pathListWidget.currentPath
    if (currentPath is None) or (len(currentPath) == 0):
      return
    settings = slicer.app.settings()
    if (settings is None):
      return
    keyPath = "/" + pathListWidget.className() + "/" + pathListWidget.settingKey
    values = settings.value(keyPath)
    newValues = []
    for value in values:
      if value != currentPath:
        newValues.append(value)
    if (len(newValues)):
      settings.setValue(keyPath, newValues)
    else:
      settings.remove(keyPath)

    pathListWidget.setCurrentPath("")
    pathListWidget.retrieveHistory()

    if (len(newValues) == 1):
      self.onSaveROI() # So that the single path is human readable in the file.

#
# TemplateROICropLogic
#

class TemplateROICropLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def run(self, inputVolume, ROITemplateSelectorPath):
    """
    Run the actual algorithm
    """
    if inputVolume is None:
        return False
    """
    Add Data no longer loads DICOM series rightly
    See : 
    https://discourse.slicer.org/t/dicom-volume-orientation-may-be-bad/10068/1
    https://discourse.slicer.org/t/python-how-to-centre-volume-on-load/10220/1
    """
    volumesLogic = slicer.modules.volumes.logic()
    volumesLogic.CenterVolume(inputVolume)
    
    # https://www.slicer.org/wiki/Documentation/Nightly/ScriptRepository
    displayNode = inputVolume.GetDisplayNode()
    displayNode.AutoWindowLevelOff()
    # CT-Bones
    displayNode.SetWindow(1000)
    displayNode.SetLevel(400)
    
    roi=slicer.util.loadMarkups(ROITemplateSelectorPath)
    return self.doCropVolume(inputVolume, roi)
    """
    TODO: Prevent the file path from being added to the recent history list. Or delete the entry. Perhaps Slicer should prevent duplicate entries in that list.
    """

  def doCropVolume(self, inputVolume, roi,
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


class TemplateROICropTest(ScriptedLoadableModuleTest):

  def setUp(self):

    slicer.mrmlScene.Clear(0)

  def runTest(self):

    self.setUp()
    self.test_TemplateROICrop1()

  def test_TemplateROICrop1(self):

    self.delayDisplay("Starting the test")

    self.delayDisplay('Test passed!')
