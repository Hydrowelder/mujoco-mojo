from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
from numpydantic import NDArray, Shape
from pydantic import field_validator, model_validator

from mujoco_mojo.base import XMLModel
from mujoco_mojo.types import Vec4

__all__ = ["HField"]


class HField(XMLModel):
    """This element creates a height field asset, which can then be referenced from geoms with type "hfield". A height field, also known as terrain map, is a 2D matrix of elevation data. The data can be specified in one of three ways:

    1. The elevation data can be loaded from a PNG file. The image is converted internally to gray scale, and the intensity of each pixel is used to define elevation; white is high and black is low.

    2. The elevation data can be loaded from a binary file in the custom format described below. As with all other matrices used in MuJoCo, the data ordering is row-major, like pixels in an image. If the data size is nrow-by-ncol, the file must have 4*(2+nrow*ncol) bytes:
        ```
        (int32)   nrow
        (int32)   ncol
        (float32) data[nrow*ncol]
        ```
    3. The elevation data can be left undefined at compile time. This is done by specifying the attributes nrow and ncol. The compiler allocates space for the height field data in mjModel and sets it to 0. The user can then generate a custom height field at runtime, either programmatically or using sensor data.

    Regardless of which method is used to specify the elevation data, the compiler always normalizes it to the range [0 1]. However if the data is left undefined at compile time and generated later at runtime, it is the user's responsibility to normalize it.

    The position and orientation of the height field is determined by the geom that references it. The spatial extent on the other hand is specified by the height field asset itself via the size attribute, and cannot be modified by the referencing geom (the geom size parameters are ignored in this case). The same approach is used for meshes below: positioning is done by the geom while sizing is done by the asset. This is because height fields and meshes involve sizing operations that are not common to other geoms.

    For collision detection, a height field is treated as a union of triangular prisms. Collisions between height fields and other geoms (except for planes and other height fields which are not supported) are computed by first selecting the sub-grid of prisms that could collide with the geom based on its bounding box, and then using the general convex collider. The number of possible contacts between a height field and a geom is limited to 50 (mjMAXCONPAIR); any contacts beyond that are discarded. To avoid penetration due to discarded contacts, the spatial features of the height field should be large compared to the geoms it collides with.
    """

    tag = "hfield"

    attributes = (
        "name",
        "content_type",
        "file",
        "nrow",
        "ncol",
        "elevation",
        "size",
    )

    name: Optional[str] = None
    """Name of the height field, used for referencing. If the name is omitted and a file name is specified, the height field name equals the file name without the path and extension."""

    content_type: Optional[str] = None
    """If the file attribute is specified, then this sets the Media Type (formerly known as MIME types) of the file to be loaded. Any filename extensions will be overloaded. Currently image/png and image/vnd.mujoco.hfield are supported."""

    file: Optional[Path] = None
    """If this attribute is specified, the elevation data is loaded from the given file. If the file extension is ".png", not case-sensitive, the file is treated as a PNG file. Otherwise it is treated as a binary file in the above custom format. The number of rows and columns in the data are determined from the file contents. Loading data from a file and setting nrow or ncol below to non-zero values results is compile error, even if these settings are consistent with the file contents."""

    nrow: Optional[int] = None
    """This attribute and the next are used to allocate a height field in mjModel. If the elevation attribute is not set, the elevation data is set to 0. This attribute specifies the number of rows in the elevation data matrix. The default value of 0 means that the data will be loaded from a file, which will be used to infer the size of the matrix."""

    ncol: Optional[int] = None
    """This attribute specifies the number of columns in the elevation data matrix."""

    elevation: Optional[NDArray[Shape["0"], float | int]] = None  # type: ignore
    """This attribute specifies the elevation data matrix. Values are automatically normalized to lie between 0 and 1 by first subtracting the minimum value and then dividing by the (maximum-minimum) difference, if not 0. If not provided, values are set to 0."""

    size: Vec4
    """The four numbers here are (radius_x, radius_y, elevation_z, base_z). The height field is centered at the referencing geom's local frame. Elevation is in the +Z direction. The first two numbers specify the X and Y extent (or "radius") of the rectangle over which the height field is defined. This may seem unnatural for rectangles, but it is natural for spheres and other geom types, and we prefer to use the same convention throughout the model. The third number is the maximum elevation; it scales the elevation data which is normalized to [0-1]. Thus the minimum elevation point is at Z=0 and the maximum elevation point is at Z=elevation_z. The last number is the depth of a box in the -Z direction serving as a "base" for the height field. Without this automatically generated box, the height field would have zero thickness at places there the normalized elevation data is zero. Unlike planes which impose global unilateral constraints, height fields are treated as unions of regular geoms, so there is no notion of being "under" the height field. Instead a geom is either inside or outside the height field - which is why the inside part must have non-zero thickness. The example on the right is the MATLAB "peaks" surface saved in our custom height field format, and loaded as an asset with size = "1 1 1 0.1". The horizontal size of the box is 2, the difference between the maximum and minimum elevation is 1, and the depth of the base added below the minimum elevation point is 0.1."""

    @model_validator(mode="before")
    def coerce_elevation(self) -> HField:
        elev = self.elevation
        nrow = self.nrow
        ncol = self.ncol

        if elev is None:
            return self

        elev = np.asarray(elev, dtype=np.float64)

        if nrow is not None and ncol is not None:
            expected_len = nrow * ncol
            if elev.size != expected_len:
                raise ValueError(
                    f"Elevation length {elev.size} does not match nrow*ncol={expected_len}"
                )

        # Normalize
        min_val = elev.min()
        max_val = elev.max()
        if max_val > min_val:
            elev = (elev - min_val) / (max_val - min_val)

        self.elevation = elev
        return self

    @field_validator("nrow", "ncol")
    @classmethod
    def validate_positive(cls, v: int) -> int:
        if v is not None and v < 0:
            raise ValueError("nrow and ncol must be non-negative")
        return v
