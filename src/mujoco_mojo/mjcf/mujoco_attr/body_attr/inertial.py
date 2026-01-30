from __future__ import annotations

from typing import Optional

import numpy as np
from pydantic import field_validator, model_validator

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.orientation import Orientation
from mujoco_mojo.types import Vec3, Vec6

__all__ = ["Inertial"]


class Inertial(XMLModel):
    """This element specifies the mass and inertial properties of the body. If this element is not included in a given body, the inertial properties are inferred from the geoms attached to the body. When a compiled MJCF model is saved, the XML writer saves the inertial properties explicitly using this element, even if they were inferred from geoms. The inertial frame is such that its center coincides with the center of mass of the body, and its axes coincide with the principal axes of inertia of the body. Thus the inertia matrix is diagonal in this frame."""

    tag = "inertial"

    attributes = (
        "pos",
        "orientation",
        "mass",
        "diaginertia",
        "fullinertia",
    )
    __exclusive_groups__ = (("diaginertia", "fullinertia"),)

    pos: Vec3
    """Position of the inertial frame. This attribute is required even when the inertial properties can be inferred from geoms. This is because the presence of the inertial element itself disables the automatic inference mechanism."""

    orientation: Optional[Orientation] = None
    """Orientation of the inertial frame. See Frame orientations."""

    mass: float
    """Mass of the body. Negative values are not allowed. MuJoCo requires the inertia matrix in generalized coordinates to be positive-definite, which can sometimes be achieved even if some bodies have zero mass. In general however there is no reason to use massless bodies. Such bodies are often used in other engines to bypass the limitation that joints cannot be combined, or to attach sensors and cameras. In MuJoCo primitive joint types can be combined, and we have sites which are a more efficient attachment mechanism."""

    diaginertia: Optional[Vec3] = None
    """Diagonal inertia matrix, expressing the body inertia relative to the inertial frame. If this attribute is omitted, the next attribute becomes required."""

    fullinertia: Optional[Vec6] = None
    """Full inertia matrix M. Since M is 3-by-3 and symmetric, it is specified using only 6 numbers in the following order: M(1,1), M(2,2), M(3,3), M(1,2), M(1,3), M(2,3). The compiler computes the eigenvalue decomposition of M and sets the frame orientation and diagonal inertia accordingly. If non-positive eigenvalues are encountered (i.e., if M is not positive definite) a compile error is generated."""

    @property
    def using_diag(self) -> bool:
        if self.diaginertia is not None and self.fullinertia is None:
            return True
        if self.diaginertia is None and self.fullinertia is not None:
            return False
        if self.diaginertia is None and self.fullinertia is None:
            raise ValueError("Neither diaginertia nor fullinertia were specified.")
        raise ValueError("Both diaginertia and fullinertia were specified (invalid).")

    @property
    def inertia_matrix(self) -> np.ndarray:
        if self.using_diag:
            d = self.diaginertia
            assert d is not None
            return np.diag(np.asarray(d))

        f = np.asarray(self.fullinertia)
        assert f is not None

        return np.array(
            [
                [f[0], f[3], f[4]],
                [f[3], f[1], f[5]],
                [f[4], f[5], f[2]],
            ],
            dtype=np.float64,
        )

    @property
    def i_xx(self) -> float:
        return float(self.inertia_matrix[0, 0])

    @property
    def i_yy(self) -> float:
        return float(self.inertia_matrix[1, 1])

    @property
    def i_zz(self) -> float:
        return float(self.inertia_matrix[2, 2])

    @property
    def i_xy(self) -> float:
        return float(self.inertia_matrix[0, 1])

    @property
    def i_xz(self) -> float:
        return float(self.inertia_matrix[0, 2])

    @property
    def i_yz(self) -> float:
        return float(self.inertia_matrix[1, 2])

    @property
    def i_yx(self) -> float:
        return self.i_xy

    @property
    def i_zx(self) -> float:
        return self.i_xz

    @property
    def i_zy(self) -> float:
        return self.i_yz

    @field_validator("mass")
    @classmethod
    def validate_mass(cls, v: float) -> float:
        if not np.isfinite(v):
            raise ValueError("mass must be finite")
        if v < 0:
            raise ValueError("mass must be non-negative")
        return v

    @field_validator("diaginertia")
    @classmethod
    def validate_diaginertia(cls, v: Vec3 | None) -> Vec3 | None:
        if v is None:
            return v

        arr = np.asarray(v, dtype=np.float64)

        if arr.shape != (3,):
            raise ValueError("diaginertia must be length 3")

        if not np.all(np.isfinite(arr)):
            raise ValueError("diaginertia must be finite")

        if np.any(arr <= 0):
            raise ValueError("diaginertia values must be positive")

        return arr

    @field_validator("fullinertia")
    @classmethod
    def validate_fullinertia(cls, v: Vec6 | None) -> Vec6 | None:
        if v is None:
            return v

        arr = np.asarray(v, dtype=np.float64)

        if arr.shape != (6,):
            raise ValueError("fullinertia must have length 6")

        if not np.all(np.isfinite(arr)):
            raise ValueError("fullinertia must be finite")

        return arr

    @model_validator(mode="after")
    def validate_inertia_physics(self) -> Inertial:
        if self.diaginertia is None and self.fullinertia is None:
            raise ValueError("Either diaginertia or fullinertia must be specified")

        if self.diaginertia is not None and self.fullinertia is not None:
            raise ValueError("Only one of diaginertia or fullinertia may be specified")

        M = self.inertia_matrix

        # Symmetry sanity check (numerical)
        if not np.allclose(M, M.T, atol=1e-12):
            raise ValueError("Inertia matrix is not symmetric")

        # Eigenvalue check (MuJoCo uses this too)
        eigvals = np.linalg.eigvalsh(M)

        if np.any(eigvals <= 0):
            raise ValueError(
                f"Inertia matrix must be positive definite. Eigenvalues: {eigvals}"
            )

        return self
