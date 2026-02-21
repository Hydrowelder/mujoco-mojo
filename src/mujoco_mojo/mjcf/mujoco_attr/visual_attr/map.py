from mujoco_mojo.mjcf.xml_model import XMLModel

__all__ = ["VisualMap"]


class VisualMap(XMLModel):
    """
    This element is used to specify scaling quantities that affect both the visualization and built-in mouse perturbations. Unlike the scaling quantities in the next element which are specific to spatial extent, the quantities here are miscellaneous.
    """

    tag = "map"

    attributes = (
        "stiffness",
        "stiffnessrot",
        "force",
        "torque",
        "alpha",
        "fogstart",
        "fogend",
        "znear",
        "zfar",
        "haze",
        "shadowclip",
        "shadowscale",
        "actuatortendon",
    )

    stiffness: float = 100
    """This attribute controls the strength of mouse perturbations. The internal perturbation mechanism simulates a mass-spring-damper with critical damping, unit mass, and stiffness given here. Larger values mean that a larger force will be applied for the same displacement between the selected body and the mouse-controlled target."""

    stiffnessrot: float = 500
    """Same as above but applies to rotational perturbations rather than translational perturbations. Empirically, the rotational stiffness needs to be larger in order for rotational mouse perturbations to have an effect."""

    force: float = 0.005
    """This attributes controls the visualization of both contact forces and perturbation forces. The length of the rendered force vector equals the force magnitude multiplied by the value of this attribute and divided by the mean body mass for the model (see statistic element)."""

    torque: float = 0.1
    """Same as above, but controls the rendering of contact torque and perturbation torque rather than force (currently disabled)."""

    alpha: float = 0.3
    """When transparency is turned on in the visualizer, the geoms attached to all moving bodies are made more transparent. This is done by multiplying the geom-specific alpha values by this value."""

    fogstart: float = 3
    """The visualizer can simulate linear fog, in the sense of OpenGL. The start position of the fog is the model extent (see statistic element) multiplied by the value of this attribute."""

    fogend: float = 10
    """The end position of the fog is the model extent multiplied by the value of this attribute."""

    znear: float = 0.01
    """This and the next attribute determine the clipping planes of the OpenGL projection. The near clipping plane is particularly important: setting it too close causes (often severe) loss of resolution in the depth buffer, while setting it too far causes objects of interest to be clipped, making it impossible to zoom in. The distance to the near clipping plane is the model extent multiplied by the value of this attribute. Must be strictly positive."""

    zfar: float = 50
    """The distance to the far clipping plane is the model extent multiplied by the value of this attribute."""

    haze: float = 0.3
    """Proportion of the distance-to-horizon that is covered by haze (when haze rendering is enabled and a skybox is present)."""

    shadowclip: float = 1
    """As mentioned above, shadow quality depends on the size of the shadow texture as well as the area where a given light can cast shadows. For directional lights, the area would be infinite unless we limited it somehow. This attribute specifies the limits, as +/- the model extent multiplied by the present value. These limits define a square in the plane orthogonal to the light direction. If a shadow crosses the boundary of this virtual square, it will disappear abruptly, revealing the edges of the square."""

    shadowscale: float = 0.6
    """This attribute plays a similar role as the previous one, but applies to spotlights rather than directional lights. Spotlights have a cutoff angle, limited internally to 80 deg. However this angle is often too large to obtain good quality shadows, and it is necessary to limit the shadow to a smaller cone. The angle of the cone in which shadows can be cast is the light cutoff multiplied by the present value."""

    actuatortendon: float = 2
    """Ratio of actuator width to tendon width for rendering of actuators attached to tendons."""
