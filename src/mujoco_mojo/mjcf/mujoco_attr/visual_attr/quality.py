from mujoco_mojo.mjcf.xml_model import XMLModel

__all__ = ["VisualQuality"]


class VisualQuality(XMLModel):
    """
    This element specifies settings that affect the quality of the rendering. Larger values result in higher quality but possibly slower speed. Note that simulate.cc displays the frames per second (FPS). The target FPS is 60 Hz; if the number shown in the visualizer is substantially lower, this means that the GPU is over-loaded and the visualization should somehow be simplified.
    """

    tag = "quality"

    attributes = ("shadowsize", "offsamples", "numslices", "numstacks", "numquads")

    shadowsize: int = 4096
    """This attribute specifies the size of the square texture used for shadow mapping. Higher values result is smoother shadows. The size of the area over which a light can cast shadows also affects smoothness, so these settings should be adjusted jointly. The default here is somewhat conservative. Most modern GPUs are able to handle significantly larger textures without slowing down."""

    offsamples: int = 4
    """This attribute specifies the number of multi-samples for offscreen rendering. Larger values produce better anti-aliasing but can slow down the GPU. Set this to 0 to disable multi-sampling. Note that this attribute only affects offscreen rendering. For regular window rendering, multi-sampling is specified in an OS-dependent way when the OpenGL context for the window is first created, and cannot be changed from within MuJoCo.

    When rendering segmentation images, multi-sampling is automatically disabled so as not to average segmentation indices. However, some rendering backends ignore the automatic disabling. If your segmentation images contain bad indices, try manually setting this attribute to 0."""

    numslices: int = 28
    """This and the next three attributes specify the density of internally-generated meshes for geometric primitives. Such meshes are only used for rendering, while the collision detector works with the underlying analytic surfaces. This value is passed to the various visualizer functions as the "slices" parameter as used in GLU. It specifies the number of subdivisions around the Z-axis, similar to lines of longitude."""

    numstacks: int = 16
    """This value of this attribute is passed to the various visualization functions as the "stacks" parameter as used in GLU. It specifies the number of subdivisions along the Z-axis, similar to lines of latitude."""

    numquads: int = 4
    """This attribute specifies the number of rectangles for rendering box faces, automatically-generated planes (as opposed to geom planes which have an element-specific attribute with the same function), and sides of height fields. Even though a geometrically correct rendering can be obtained by setting this value to 1, illumination works better for larger values because we use per-vertex illumination (as opposed to per-fragment)."""
