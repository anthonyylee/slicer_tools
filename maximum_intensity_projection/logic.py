"""
3D Slicer Script for Maximum Intensity Projection (MIP)

Author: Anthony Y. Lee
Created Date: 2026-02-23

These are scripts used in 3D Slicer software Python console. It can be read into
the 3D Slicer software using the `~/.slicerrc.py` file in the following manner.

```
exec(
    open(
        Path.home() 
        / Path("Projects/slicer_tools/maximum_intensity_projection/logic.py")
    ).read()
)
```

"""
## 3D Slicer built-in libraries - Can be installed via conda or pip when testing outside
import numpy as np

## 3D Slicer built-in libraries - Unable to install via conda or pip
import SampleData

## 3D Slicer auto-imported libraries
# import slicer  # Added for clarity

# TODO: Separate out the functionalities that are dependent on packages only available inside the 3D Slicer environment. So that the code can be tested without 3D Slicer.


def demo_axes_orientation():
    sampleDataName = "CTAAbdomenPanoramix"
    volNodes = {f"volNode{idxVolNode}": SampleData.downloadSample(sampleDataName) for idxVolNode in range(3)}

    for (key, volNode), axis in zip(volNodes.items(), ("R", "A", "S")):
       volNode.SetName(key) 
       
       mip(volNode, axis)

    return


def mip(volNode: "vtkMRMLScalarVolumeNode", axis:int="A") -> "vtkMRMLScalarVolumeNode": 
    """Maximum Intensity Projection (MIP) along R, A, or S axis.
    """

    axisOptions = ("S", "A", "R")  # NumPy array axis order is k, j, i
    axisIndices = {key: value for key, value in zip(axisOptions, range(len(axisOptions)))}
    axisIdx = axisIndices[axis]
    assert axis in axisOptions, f"`axis` has to be 'R', 'A', or 'S'. Got {axis}"
    
    npArray = np.copy(slicer.util.arrayFromVolume(volNode))
    greyScaleMin = np.min(npArray)
    right, anterior, superior = np.shape(npArray)

    match axisIdx: 
        case 0:  # Projecting along the inferior/superior axis
            npArrayMip = np.max(npArray, 0)
            npArray = np.ones_like(npArray) * greyScaleMin
            npArray[0, :, :] = npArrayMip
        case 1:  # Projecting along the posterior/anterior axis
            npArrayMip = np.max(npArray, 1)
            npArray = np.ones_like(npArray) * greyScaleMin
            npArray[:, 0, :] = npArrayMip
        case 2:  # Projecting along the left/right axis
            npArrayMip = np.max(npArray, 2)
            npArray = np.ones_like(npArray) * greyScaleMin
            npArray[:, :, 0] = npArrayMip
        case _:
            raise ValueError

    slicer.util.updateVolumeFromArray(volNode, npArray)

    return volNode
