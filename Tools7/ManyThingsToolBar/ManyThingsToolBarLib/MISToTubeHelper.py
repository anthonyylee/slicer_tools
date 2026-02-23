import qt, vtk, slicer
from ManyThingsToolBarLib.Utils import *

class MISToTubeHelper():
  @staticmethod
  def MISToTube(centerlineNode, cap):
    if not centerlineNode:
        informInStatusBar("Input centerline is None.")
        return
    if centerlineNode.IsTypeOf("vtkMRMLModelNode"):
        centerlinePoints = centerlineNode.GetPolyData().GetPoints()
        radiusArray = centerlineNode.GetPolyData().GetPointData().GetArray("Radius")
    elif centerlineNode.IsTypeOf("vtkMRMLMarkupsCurveNode"):
        centerlinePoints = centerlineNode.GetCurveWorld().GetPoints()
        radiusArray = centerlineNode.GetCurveWorld().GetPointData().GetArray("Radius")
    else:
        informInStatusBar("Centerline is of unknown class.")
        return
    if radiusArray is None:
        informInStatusBar("Input node does not have a 'Radius' array.")
        return
    
    numberOfCenterlinePoints = centerlinePoints.GetNumberOfPoints()

    parametricSpline = vtk.vtkParametricSpline()
    parametricSpline.SetPoints(centerlinePoints)

    splineFunctionSource = vtk.vtkParametricFunctionSource()
    splineFunctionSource.SetParametricFunction(parametricSpline)
    # These functions use input + 1. Without subtraction, a single end of the tube is capped.
    splineFunctionSource.SetUResolution(numberOfCenterlinePoints - 1)
    splineFunctionSource.SetVResolution(numberOfCenterlinePoints - 1)
    splineFunctionSource.SetWResolution(numberOfCenterlinePoints - 1)
    splineFunctionSource.Update()

    splinePolyData = splineFunctionSource.GetOutput()
    splinePolyData.GetPointData().AddArray(radiusArray)
    splinePolyData.GetPointData().SetActiveScalars("Radius")

    tube = vtk.vtkTubeFilter()
    tube.SetNumberOfSides(20)
    tube.SetVaryRadiusToVaryRadiusByAbsoluteScalar()
    tube.SetInputConnection(splineFunctionSource.GetOutputPort())
    tube.SetCapping(cap)
    tube.Update()

    model = slicer.modules.models.logic().AddModel(tube.GetOutput())
    # So that we don't reprocess the tube.
    model.GetPolyData().GetPointData().GetArray("Radius").SetName("MISRadius")

# -----------------------------------------------------------------------------
  @staticmethod
  def createHelperWidget():
    m2tWidget = qt.QWidget()
    m2tWidget.setObjectName("M2TWidget")
    m2tWidgetVLayout = qt.QVBoxLayout()
    m2tWidgetVLayout.setObjectName("M2TWidgetVLayout")
    m2tWidget.setLayout(m2tWidgetVLayout)
    m2tWidgetFormLayout = qt.QFormLayout()
    m2tWidgetFormLayout.setObjectName("M2TWidgetFormLayout")
    m2tWidgetVLayout.addLayout(m2tWidgetFormLayout)
    # Centerline selector
    m2tCenterlineLabel = qt.QLabel("Centerline:", m2tWidget)
    m2tCenterlineLabel.setObjectName("M2TSliceNodeLabel")
    m2tCenterlineNodeComboBox = slicer.qMRMLNodeComboBox(m2tWidget)
    m2tCenterlineNodeComboBox.setObjectName("M2TSliceNodeComboBox")
    m2tCenterlineNodeComboBox.nodeTypes = ["vtkMRMLModelNode", "vtkMRMLMarkupsCurveNode"]
    m2tCenterlineNodeComboBox.addEnabled = False
    m2tCenterlineNodeComboBox.removeEnabled = False
    m2tCenterlineNodeComboBox.renameEnabled = False
    m2tCenterlineNodeComboBox.noneEnabled = True
    m2tCenterlineNodeComboBox.setMRMLScene( slicer.mrmlScene )
    m2tCenterlineNodeComboBox.setToolTip("Select a centerline node")
    m2tWidgetFormLayout.addRow(m2tCenterlineLabel, m2tCenterlineNodeComboBox)
    m2tCapButton = qt.QToolButton(m2tWidget)
    m2tCapButton.setObjectName("M2TCapButton")
    m2tCapButton.setText("Cap")
    m2tCapButton.setCheckable(True)
    m2tCapButton.setSizePolicy(qt.QSizePolicy.Minimum, qt.QSizePolicy.Fixed)
    m2tWidgetFormLayout.addRow(None, m2tCapButton)
    # Apply button
    m2tApplyButton = qt.QToolButton(m2tWidget)
    m2tApplyButton.setObjectName("M2TApplyButton")
    m2tApplyButton.setText("Apply")
    m2tApplyButton.setSizePolicy(qt.QSizePolicy.Minimum, qt.QSizePolicy.Fixed)
    m2tApplyButton.connect("clicked()", lambda: MISToTubeHelper.MISToTube(m2tCenterlineNodeComboBox.currentNode(), m2tCapButton.checked))
    m2tWidgetVLayout.addWidget(m2tApplyButton)
    
    return m2tWidget

