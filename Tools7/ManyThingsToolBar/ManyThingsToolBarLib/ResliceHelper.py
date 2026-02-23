import qt, vtk, slicer
from ManyThingsToolBarLib.Utils import *

class ResliceHelper():

  @staticmethod
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
      
# *******************************************************************************
  @staticmethod
  def resliceToAxis(sliceNode, axis = 0, orthogonal = False):
      if sliceNode is None:
          informInStatusBar("Slice node is none.")
          return
      combo = slicer.modules.markups.toolBar().findChild(slicer.qMRMLNodeComboBox, "MarkupsNodeSelector")
      currentMarkupsNode = combo.currentNode()
      if currentMarkupsNode is None:
          informInStatusBar("No markups node selected.")
          hideManyThingsMenu()
          return
      if ((not currentMarkupsNode.IsTypeOf("vtkMRMLMarkupsLineNode"))
          and (not currentMarkupsNode.IsTypeOf("vtkMRMLMarkupsPlaneNode"))
          and (not currentMarkupsNode.IsTypeOf("vtkMRMLMarkupsAngleNode"))
          and (not currentMarkupsNode.IsTypeOf("vtkMRMLMarkupsFiducialNode"))):
          informInStatusBar("Selected markups node must be a line, plane, angle or fiducial  node.")
          hideManyThingsMenu()
          return
      point = [0.0, 0.0, 0.0]
      normal = [0.0, 0.0, 0.0]
      currentMarkupsNode.GetNthControlPointPositionWorld(0, point)
      if currentMarkupsNode.IsTypeOf("vtkMRMLMarkupsLineNode"):
          p2 = [0.0, 0.0, 0.0]
          currentMarkupsNode.GetNthControlPointPositionWorld(1, p2)
          vtk.vtkMath().Subtract(p2, point, normal)
      elif currentMarkupsNode.IsTypeOf("vtkMRMLMarkupsPlaneNode"):
          point = currentMarkupsNode.GetCenterWorld()
          normal = currentMarkupsNode.GetNormalWorld()
      elif currentMarkupsNode.IsTypeOf("vtkMRMLMarkupsAngleNode"):
          # Only the Normal axis if really of interest. Mainly to reposition points in the same plane.
          p1 = [0.0, 0.0, 0.0]
          p3 = [0.0, 0.0, 0.0]
          currentMarkupsNode.GetNthControlPointPositionWorld(0, p1)
          currentMarkupsNode.GetNthControlPointPositionWorld(1, point)
          currentMarkupsNode.GetNthControlPointPositionWorld(2, p3)
          p1Direction = [0.0, 0.0, 0.0]
          p3Direction = [0.0, 0.0, 0.0]
          vtk.vtkMath().Subtract(p1, point, p1Direction)
          vtk.vtkMath().Subtract(p3, point, p3Direction)
          vtk.vtkMath().Cross(p1Direction, p3Direction, normal)
      elif currentMarkupsNode.IsTypeOf("vtkMRMLMarkupsFiducialNode"):
          if currentMarkupsNode.GetNumberOfDefinedControlPoints() == 1:
              # Use the point itself as a normal.
              vtk.vtkMath().Assign(point, normal)
          elif currentMarkupsNode.GetNumberOfDefinedControlPoints() == 2:
              # Use the line between the 2 points.
              p2 = [0.0, 0.0, 0.0]
              currentMarkupsNode.GetNthControlPointPositionWorld(1, p2)
              vtk.vtkMath().Subtract(p2, point, normal)
          elif currentMarkupsNode.GetNumberOfDefinedControlPoints() == 3:
              p2 = [0.0, 0.0, 0.0]
              p3 = [0.0, 0.0, 0.0]
              currentMarkupsNode.GetNthControlPointPositionWorld(1, p2)
              currentMarkupsNode.GetNthControlPointPositionWorld(2, p3)
              p2Direction = [0.0, 0.0, 0.0]
              p3Direction = [0.0, 0.0, 0.0]
              vtk.vtkMath().Subtract(p2, point, p2Direction)
              vtk.vtkMath().Subtract(p3, point, p3Direction)
              vtk.vtkMath().Cross(p2Direction, p3Direction, normal)
          elif currentMarkupsNode.GetNumberOfDefinedControlPoints() > 3:
              # Cheat with a temporary markups plane.
              tempPlane = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsPlaneNode")
              tempPlane.SetPlaneType(slicer.vtkMRMLMarkupsPlaneNode.PlaneTypePlaneFit)
              tempPlane.CreateDefaultDisplayNodes()
              tempPlane.GetDisplayNode().SetVisibility(False)
              # N.B. : In the tool bar's combobox, the temporary plane is now selected.
              # currentMarkupsNode is already referenced hare as the ficucial node.
              for idx in range (currentMarkupsNode.GetNumberOfDefinedControlPoints()):
                  p = [0.0, 0.0, 0.0]
                  currentMarkupsNode.GetNthControlPointPositionWorld(idx, p)
                  tempPlane.AddControlPointWorld(p)
              point = tempPlane.GetCenterWorld()
              normal = tempPlane.GetNormalWorld()
              slicer.mrmlScene.RemoveNode(tempPlane)
              combo.setCurrentNode(currentMarkupsNode)
          else:
              informInStatusBar("Fiducial node does not have enough points.")
              hideManyThingsMenu()
              return
      else:
          informInStatusBar("Markups node must be line, plane, angle or fiducial.")
          hideManyThingsMenu()
          return
      ResliceHelper.doResliceToAxis(sliceNode, point, normal, axis)
      if (orthogonal):
          ResliceHelper.setSliceIntersectionToOrthogonal(sliceNode)

# *******************************************************************************
  @staticmethod
  def setSliceIntersectionToOrthogonal(refSliceNode):
    if (refSliceNode is None):
      return
    views = ['Red', 'Yellow', 'Green']
    viewIsManaged = False
    for view in views:
      sliceNode = slicer.app.layoutManager().sliceWidget(view).mrmlSliceNode()
      if sliceNode and (sliceNode == refSliceNode):
          viewIsManaged = True
          break
    if not viewIsManaged:
        return
    sliceToRAS = refSliceNode.GetSliceToRAS()
    col = 0 # orientation matrix column
    for view in views:
      sliceNode = slicer.app.layoutManager().sliceWidget(view).mrmlSliceNode()
      if sliceNode == refSliceNode:
        continue
      sliceNode.SetSliceToRASByNTP(
        sliceToRAS.GetElement(0, col),
        sliceToRAS.GetElement(1, col),
        sliceToRAS.GetElement(2, col),

        sliceToRAS.GetElement(0, col + 1),
        sliceToRAS.GetElement(1, col + 1),
        sliceToRAS.GetElement(2, col + 1),

        sliceToRAS.GetElement(0, 3),
        sliceToRAS.GetElement(1, 3),
        sliceToRAS.GetElement(2, 3),
        0)
      col = col + 1

# *******************************************************************************
  @staticmethod
  def createHelperWidget():
    rsWidget = qt.QWidget()
    rsWidget.setObjectName("RSWidget")
    rsWidgetVLayout = qt.QVBoxLayout()
    rsWidgetVLayout.setObjectName("RSWidgetVLayout")
    rsWidget.setLayout(rsWidgetVLayout)
    rsWidgetFormLayout = qt.QFormLayout()
    rsWidgetFormLayout.setObjectName("RSWidgetFormLayout")
    rsWidgetVLayout.addLayout(rsWidgetFormLayout)
    # Slice node selector
    rsSliceNodeLabel = qt.QLabel("Slice node:", rsWidget)
    rsSliceNodeLabel.setObjectName("RSSliceNodeLabel")
    rsSliceNodeComboBox = slicer.qMRMLNodeComboBox(rsWidget)
    rsSliceNodeComboBox.setObjectName("RSSliceNodeComboBox")
    rsSliceNodeComboBox.nodeTypes = ["vtkMRMLSliceNode"]
    rsSliceNodeComboBox.addEnabled = False
    rsSliceNodeComboBox.removeEnabled = False
    rsSliceNodeComboBox.renameEnabled = False
    rsSliceNodeComboBox.noneEnabled = True
    rsSliceNodeComboBox.setMRMLScene( slicer.mrmlScene )
    rsSliceNodeComboBox.setToolTip("Select a slice node")
    rsWidgetFormLayout.addRow(rsSliceNodeLabel, rsSliceNodeComboBox)
    # Axis
    rsAxisLabel = qt.QLabel("Axis:", rsWidget)
    rsAxisLabel.setObjectName("RSAxisLabel")
    rsAxisComboBox = qt.QComboBox(rsWidget)
    rsAxisComboBox.setObjectName("RSAxisComboBox")
    rsAxisComboBox.addItem("Normal", 0)
    rsAxisComboBox.addItem("Binormal", 1)
    rsAxisComboBox.addItem("Tangent", 2)
    rsAxisComboBox.setToolTip("Set this axis perpendicular to the slice")
    rsWidgetFormLayout.addRow(rsAxisLabel, rsAxisComboBox)
    # Keep orthogonal
    rsOrthogonalCheckBox = qt.QCheckBox("Orthogonal intersection", rsWidget)
    rsOrthogonalCheckBox.setObjectName("RSOrthogonalCheckBox")
    rsOrthogonalCheckBox.setToolTip("If the selected slice node is the Red, Green or Yellow node, intersect these nodes perpendicularly.")
    rsOrthogonalCheckBox.setChecked(False)
    rsWidgetFormLayout.addRow(None, rsOrthogonalCheckBox)
    # Apply button
    rsApplyButton = qt.QToolButton(rsWidget)
    rsApplyButton.setObjectName("RSApplyButton")
    rsApplyButton.setText("Apply")
    rsApplyButton.setSizePolicy(qt.QSizePolicy.Minimum, qt.QSizePolicy.Fixed)
    rsApplyButton.connect("clicked()", lambda: ResliceHelper.resliceToAxis(rsSliceNodeComboBox.currentNode(), rsAxisComboBox.itemData(rsAxisComboBox.currentIndex), rsOrthogonalCheckBox.checked))
    rsWidgetVLayout.addWidget(rsApplyButton)
    
    return rsWidget
