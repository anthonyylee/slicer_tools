# ManyThings Toolbar

This module exposes a few custom functions that are routinely useful to me. They are devised as quick access to repetitive tasks.

## 1. Quick crop volume functions

### Usage

- *Crop volume to current ROI* : Select an ROI and click this menu. The background volume in the Red slice node will be cropped to the selected ROI without interpolation.
- *Crop volume to current ROI x 2* : Select an ROI and click this menu. The background volume in the Red slice node will be cropped to the selected ROI with a spacing scale of 0.5.
- *Crop volume to current ROI (Iso 0.3)* : Select an ROI and click this menu. The background volume in the Red slice node will be cropped to the selected ROI and resampled to an isovoxel spacing of 0.3 mm. The ROI should be reasonably sized according to available RAM and CPU.
- *Crop volume to current ROI (Iso 0.5)* : Select an ROI and click this menu. The background volume in the Red slice node will be cropped to the selected ROI and resampled to an isovoxel spacing of 0.5 mm. The ROI should be reasonably sized according to available RAM and CPU.

## 2. Reslice functions

### Usage

Select a slice view, an axis and apply. The slice node will be reformatted to the currently selected markups line, plane, angle or fiducial node.

The axes are determined by the direction vector of the line, by the normal of the plane, or by the normal of the angle node at the middle point.

If a fiucial node is provided with a single point, it is itself used as a normal. If there are only 2 points, they are used as a line. If the fiducial node has 3 points, they are used as a plane. With more than 3 points, a best fit plane is determined according to the logic of a markups plane node.

## 3. MIS to tube functions

Create a tube from the 'Radius' scalar array of a non-bifurcated centerline model or curve.

Notes:

 - A bifurcated centerline model should be pre-processed with the [Centerline disassembly](https://github.com/vmtk/SlicerExtension-VMTK/blob/master/Docs/CenterlineDisassembly.md) module to suppress bifurcations.
 - This is legacy code, consider the [Edit centerline](https://github.com/vmtk/SlicerExtension-VMTK/blob/master/Docs/EditCenterline.md) module for an improved user experience.


## 4. Markups Undo/Redo functions

### Usage

To undo an action on a markups node, click on the Undo (yellow) button or press 'Ctrl+Z'.

To redo an action on a markups node, click on the Redo (green) button or press 'Ctrl+Shift+Z'.

#### Notes

This [functionality](https://projectweek.na-mic.org/PW39_2023_Montreal/Projects/UndoRedo/) is added here with permission from the author, Kyle Sunderland. It has been further modified.

## 5. Remove helmet

Remove metal artifacts from the stabilising helmet used during CT scans of the head.

### Usage

In a slice view, place at least one fiducial point on the metal artifacts surrounding the head and apply; set the provided parameters if necessary. A new volume without the artifacts is created.

The background volume in the Red slice node will be used as well as the currently selected markups fiducial node.


## 6. Anonymise scene


This menu item removes the patient's name and birth date from the subject hierarchy. This information is inserted as attributes of the patient's subject hierarchy item if a scalar volume is loaded from a DICOM series. They are replaced by constants in the subject hierarchy only, the DICOM files are not modified by this function.


## 7. Virtual cath lab helpers


If the [VirtualCathLab](https://github.com/SlicerHeart/SlicerHeart/blob/master/Docs/VirtualCathLab.md) module is installed:

 - Use a markups line node to simulate a laser beam from the detector towards the source.
 - Reposition the camera on either side of the table.


## 8. Plane cut segment


Cut a segment with a plane, whicn can be a slice view or a markups plane.



---


### Disclaimer

Use at your own risks.
