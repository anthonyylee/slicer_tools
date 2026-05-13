import numpy as np
import matplotlib.pyplot as plt
from collections import namedtuple

Linear_Fit_Coef = namedtuple("Linear_Fit_Coef", ["intercept", "slope"])

def linear_fit_coef(air_mean_gv:float, water_mean_gv:float) -> Linear_Fit_Coef:
    """Calculate the intercept and slope given the air and water greyscale values
    
    This calculation assumes that the greyscale value is a simple shift and scale
    adjustment to find the pseudo Hounsfield Units.
    """
    if not isinstance(air_mean_gv, float): 
        raise TypeError
    if not isinstance(water_mean_gv, float):
        raise TypeError
    
    if air_mean_gv >= water_mean_gv:
        raise ValueError(f"Water mean greyscale value is not greater than air, which is typically the case.")

    polynomial_order = 1 # Linear fit
    known_hu = {
        "air": -1000,
        "water": 0,
    }
    coef = np.polyfit(
        [known_hu["air"], known_hu["water"]],
        [air_mean_gv, water_mean_gv],
        polynomial_order,
    )

    return Linear_Fit_Coef(
        slope=coef[0],
        intercept=coef[1],
    )

def plot_polynomial(coef, x_array): 

    result_array = np.polyval(coef, x_array)

    fig, ax = plt.subplots(1, 1)
    ax.plot(x_array, result_array)

    return fig

def example(): 
    known_hu = [-1000, 0]
    measured_gv = [5323.07, 6788.4]

    z = np.polyfit(known_hu, measured_gv, 1)
    print(z)

    z2 = linear_fit_coef(measured_gv[0], measured_gv[1])
    print(z2)

    fig = plot_polynomial(z, np.linspace(-10000, 10000))

    fig2 = plot_polynomial(z2, np.linspace(-10000, 10000))

    return [fig, fig2]

# %%
coef = linear_fit_coef(air_mean_gv=12070.4, water_mean_gv=26187.6)
print(coef)
fig = plot_polynomial(coef, np.linspace(-100000, 100000))
fig.show()