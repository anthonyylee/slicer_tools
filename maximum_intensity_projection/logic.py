import numpy as np
import SampleData


def demo_axes_orientation():
    sampleDataName = "CTAAbdomenPanoramix"
    volNodes = {f"volNode{idxVolNode}": SampleData.downloadSample(sampleDataName) for idxVolNode in range(3)}

    for (key, volNode), axis in zip(volNodes.items(), ("R", "A", "S")):
       volNode.SetName(key) 
       
       mip(volNode, axis)

    return


def mip(volNode: "vtkMRMLScalarVolumeNode", axis:int="R") -> "vtkMRMLScalarVolumeNode": 
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
