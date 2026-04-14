from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

import numpy as np
from pydantic import field_validator, model_validator

from mujoco_mojo.mjcf.orientation import (
    Orientation,
    OrientationBase,
    Quat,
)
from mujoco_mojo.mjcf.pose import (
    Pose,
)
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.stochas import Dist, Distribution, NamedValue
from mujoco_mojo.typing import EulerSeq, Mat3, Vec3, Vec6
from mujoco_mojo.utils.log import get_logger

if TYPE_CHECKING:
    from mujoco_mojo.mojo_model import MojoModel

logger = get_logger(__name__)

__all__ = ["Inertial"]


class Inertial(XMLModel):
    """This element specifies the mass and inertial properties of the body. If this element is not included in a given body, the inertial properties are inferred from the geoms attached to the body. When a compiled MJCF model is saved, the XML writer saves the inertial properties explicitly using this element, even if they were inferred from geoms. The inertial frame is such that its center coincides with the center of mass of the body, and its axes coincide with the principal axes of inertia of the body. Thus the inertia matrix is diagonal in this frame."""

    tag = "inertial"

    attributes = (
        "pose",
        "mass",
        "diaginertia",
        "fullinertia",
    )
    __exclusive_groups__ = (("diaginertia", "fullinertia"),)

    pose: Pose
    """Position and orientation of the inertial frame. The position attribute is required even when the inertial properties can be inferred from geoms. This is because the presence of the inertial element itself disables the automatic inference mechanism."""

    mass: float
    """Mass of the body. Negative values are not allowed. MuJoCo requires the inertia matrix in generalized coordinates to be positive-definite, which can sometimes be achieved even if some bodies have zero mass. In general however there is no reason to use massless bodies. Such bodies are often used in other engines to bypass the limitation that joints cannot be combined, or to attach sensors and cameras. In MuJoCo primitive joint types can be combined, and we have sites which are a more efficient attachment mechanism."""

    diaginertia: Vec3 | None = None
    """Diagonal inertia matrix, expressing the body inertia relative to the inertial frame. If this attribute is omitted, the next attribute becomes required."""

    fullinertia: Vec6 | None = None
    """Full inertia matrix M. Since M is 3-by-3 and symmetric, it is specified using only 6 numbers in the following order: M(1,1), M(2,2), M(3,3), M(1,2), M(1,3), M(2,3). The compiler computes the eigenvalue decomposition of M and sets the frame orientation and diagonal inertia accordingly. If non-positive eigenvalues are encountered (i.e., if M is not positive definite) a compile error is generated."""

    @property
    def using_diag(self) -> bool:
        """Returns True if the element uses diaginertia, False if using fullinertia."""
        if self.diaginertia is not None and self.fullinertia is None:
            return True
        if self.diaginertia is None and self.fullinertia is not None:
            return False
        if self.diaginertia is None and self.fullinertia is None:
            msg = "Neither diaginertia nor fullinertia were specified."
            logger.error(msg)
            raise ValueError(msg)
        msg = "Both diaginertia and fullinertia were specified (invalid)."
        logger.error(msg)
        raise ValueError(msg)

    @property
    def inertia_matrix(self) -> Mat3:
        """Returns the 3x3 inertia matrix reconstruction."""
        if self.using_diag:
            d = self.diaginertia
            assert d is not None
            return np.diag(d)

        f = self.fullinertia
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
            msg = "mass must be finite"
            logger.error(msg)
            raise ValueError(msg)
        if v < 0:
            msg = "mass must be non-negative"
            logger.error(msg)
            raise ValueError(msg)
        return v

    @field_validator("diaginertia")
    @classmethod
    def validate_diaginertia(cls, v: Vec3 | None) -> Vec3 | None:
        if v is None:
            return v

        arr = np.asarray(v, dtype=np.float64)

        if arr.shape != (3,):
            msg = "diaginertia must be length 3"
            logger.error(msg)
            raise ValueError(msg)

        if not np.all(np.isfinite(arr)):
            msg = "diaginertia must be finite"
            logger.error(msg)
            raise ValueError(msg)

        if np.any(arr <= 0):
            msg = "diaginertia values must be positive"
            logger.error(msg)
            raise ValueError(msg)

        return arr

    @field_validator("fullinertia")
    @classmethod
    def validate_fullinertia(cls, v: Vec6 | None) -> Vec6 | None:
        if v is None:
            return v

        arr = np.asarray(v, dtype=np.float64)

        if arr.shape != (6,):
            msg = "fullinertia must have length 6"
            logger.error(msg)
            raise ValueError(msg)

        if not np.all(np.isfinite(arr)):
            msg = "fullinertia must be finite"
            logger.error(msg)
            raise ValueError(msg)

        return arr

    @model_validator(mode="after")
    def validate_inertia_physics(self) -> Self:
        if self.diaginertia is None and self.fullinertia is None:
            msg = "Either diaginertia or fullinertia must be specified"
            logger.error(msg)
            raise ValueError(msg)

        if self.diaginertia is not None and self.fullinertia is not None:
            msg = "Only one of diaginertia or fullinertia may be specified"
            logger.error(msg)
            raise ValueError(msg)

        M = self.inertia_matrix

        # Symmetry sanity check (numerical)
        if not np.allclose(M, M.T, atol=1e-12):
            msg = "Inertia matrix is not symmetric"
            logger.error(msg)
            raise ValueError(msg)

        # Eigenvalue check (MuJoCo uses this too)
        eigvals = np.linalg.eigvalsh(M)

        if np.any(eigvals <= 0):
            msg = (f"Inertia matrix must be positive definite. Eigenvalues: {eigvals}",)
            logger.error(msg)
            raise ValueError(msg)

        return self

    def get_body_frame_inertia(self) -> Mat3:
        """
        Calculates the 3x3 inertia matrix expressed in the parent body's frame.

        This uses the Parallel Axis Theorem (Steiner's Theorem) to shift the moment of inertia from the center of mass to the parent body origin based on the 'pos' and 'orientation' attributes.

        Returns:
            np.ndarray: A 3x3 symmetric inertia matrix in the body frame.

        """
        # rotate into body frame axes
        R = self.pose.as_matrix()
        I_local = self.inertia_matrix
        I_rot = R @ I_local @ R.T

        # parallel axis theorem
        # I_body = I_com + m ([r_skew]^2) -> I_com + m * ( (p.T @ p) * eye(3) - p @ p.T )
        p = self.pose.pos
        m = self.mass

        # cross product matrix
        p_sq = np.dot(p, p) * np.eye(3) - np.outer(p, p)

        return I_rot + m * p_sq

    @classmethod
    def from_body_frame(cls, mass: float, pos: Vec3, inertia_matrix: Mat3) -> Self:
        """
        Factory to create an Inertial element from properties in a parent frame.

        This method shifts the inertia from the parent body frame back to the center of mass and diagonalizes the resulting matrix to find the principal axes (orientation) and principal moments (diaginertia).

        Args:
            mass (float): Total mass of the body.
            pos (Vec3): Position of the center of mass in the parent frame.
            inertia_matrix (np.ndarray): The 3x3 inertia matrix expressed in the parent frame.

        Returns:
            Inertial: A new instance with diagonalized inertial properties.

        """
        # shift inertia from body frame back to the center of mass
        p = pos
        p_sq = np.dot(p, p) * np.eye(3) - np.outer(p, p)
        I_com = inertia_matrix - mass * p_sq

        # diagonalize
        eigvals, eigvecs = np.linalg.eigh(I_com)

        # ensure positive definite
        if np.linalg.det(eigvecs) < 0:
            eigvecs[:, 2] *= -1

        return cls(
            mass=mass,
            pose=Quat.from_matrix(eigvecs).as_pose(pos=pos),
            diaginertia=eigvals,
        )

    def __add__(self, other: Inertial) -> Inertial:
        """
        Combines two Inertial elements into one.

        Calculates the compound mass, center of mass, and resulting principal inertia properties using the Parallel Axis Theorem.

        Args:
            other (Inertial): The other Inertial element to add.

        Returns:
            Inertial: The combined inertial properties.

        """
        if not isinstance(other, Inertial):
            return NotImplemented

        # new mass
        m1 = self.mass
        m2 = other.mass
        m_total = m1 + m2

        if m_total <= 0:
            msg = f"Adding inertials would result in a negative mass ({m1} + {m2} = {m_total})"
            logger.error(msg)
            raise ValueError(msg)

        # new CoM
        p1, p2 = self.pose.pos, other.pose.pos
        assert isinstance(p1, np.ndarray)
        assert isinstance(p2, np.ndarray)
        pos_total = (m1 * p1 + m2 * p2) / m_total

        # sum inertias in the common body frame
        I_total_body = self.get_body_frame_inertia() + other.get_body_frame_inertia()

        return Inertial.from_body_frame(
            mass=m_total, pos=pos_total, inertia_matrix=I_total_body
        )

    def __sub__(self, other: Inertial) -> Inertial:
        """
        Subtracts one Inertial element from another.

        This is useful for modeling material removal. Note that subtracting valid physical properties can result in a non-physical remainder (e.g., an inertia matrix that is no longer positive-definite).

        Args:
            other (Inertial): The Inertial element to subtract.

        Raises:
            ValueError: If the resulting mass is non-positive or the resulting inertia matrix is non-physical.

        Returns:
            Inertial: The remaining inertial properties.

        """
        # new mass
        m1 = self.mass
        m2 = other.mass
        m_total = m1 - m2

        if m_total <= 0:
            msg = f"Inertial subtraction resulted in non-positive mass: {m1} - {m2} = {m_total}"
            logger.error(msg)
            raise ValueError(msg)

        # new CoM
        p1, p2 = self.pose.pos, other.pose.pos
        assert isinstance(p1, np.ndarray)
        assert isinstance(p2, np.ndarray)

        pos_total = (m1 * p1 - m2 * p2) / m_total

        # sum inertias in the common body frame
        I_total_body = self.get_body_frame_inertia() - other.get_body_frame_inertia()

        # this one also may fail the eigenvalue calculation
        try:
            return Inertial.from_body_frame(
                mass=m_total, pos=pos_total, inertia_matrix=I_total_body
            )
        except ValueError as e:
            # resulting inertial was not valid (such as subtracting a Venn-diagram).
            msg = f"Resulting inertia matrix is non-physical: {e}"
            logger.exception(msg)
            raise ValueError(msg)

    @classmethod
    def from_random(
        cls,
        mojo_model: MojoModel,
        mass: float | Dist,
        pos: Vec3 | tuple[float | Dist, float | Dist, float | Dist],
        diaginertia: Vec3
        | tuple[float | Dist, float | Dist, float | Dist]
        | None = None,
        fullinertia: Vec6
        | tuple[
            float | Dist,
            float | Dist,
            float | Dist,
            float | Dist,
            float | Dist,
            float | Dist,
        ]
        | None = None,
        orientation: tuple[type[OrientationBase], list[float | Dist], EulerSeq | None]
        | Orientation
        | None = None,
        max_retries: int = 10,
    ) -> Inertial:
        """
        Generates an Inertial element by sampling from provided distributions.

        Supports both vector-level and component-level randomization. This method will re-sample until a physically valid configuration is found or max_retries is reached.

        Args:
            mojo_model (MojoModel): The MojoModel instance for sampling and registration.
            mass (float | Dist): Mass value or distribution.
            pos (Vec3 | tuple[float  |  Dist, float  |  Dist, float  |  Dist]): Position vector or tuple of component distributions.
            diaginertia (Vec3 | tuple[float  |  Dist, float  |  Dist, float  |  Dist] | None, optional): Principal moments or tuple of component distributions. Defaults to None.
            fullinertia (Vec6 | tuple[ float  |  Dist, float  |  Dist, float  |  Dist, float  |  Dist, float  |  Dist, float  |  Dist, ] | None, optional): Full inertia vector or tuple of component distributions. Defaults to None.
            orientation (tuple[type[OrientationBase], list[float | Dist], EulerSeq | None] | Orientation | None, optional): Orientation for the inertial frame. Defaults to None.
            max_retries (int, optional): Maximum number of re-samples on physics failure. Defaults to 10.

        Raises:
            ValueError: If neither diaginertia nor fullinertia are provided.
            RuntimeError: If a valid configuration is not found within max_retries.

        Returns:
            Inertial: A physically valid randomized Inertial element.

        """
        if diaginertia is None and fullinertia is None:
            msg = "diaginertia or fullinertia must be defined"
            logger.exception(msg)
            raise ValueError(msg)

        def _resolve_and_track(input_val: Any) -> tuple[np.ndarray, list[NamedValue]]:
            """Samples distributions and prepares NamedValues for registration."""
            resolved_values = []
            pending_named_values = []

            # case 1: tuple/list of components [(Dist|float), ...]
            if isinstance(input_val, (list, tuple)):
                for item in input_val:
                    if isinstance(item, Distribution):
                        # sample raw, but create the NamedValue container
                        item.with_seed(mojo_model.seed).with_trial_num(
                            mojo_model.trial_num
                        )
                        nv = item.sample_to_named_value()
                        resolved_values.append(nv.squeeze())
                        pending_named_values.append(nv)
                    else:
                        resolved_values.append(item)
                return np.asarray(resolved_values, dtype=float), pending_named_values

            # case 2: single vector-level distribution
            if isinstance(input_val, Distribution):
                input_val.with_seed(mojo_model.seed).with_trial_num(
                    mojo_model.trial_num
                )
                nv = input_val.sample_to_named_value()
                return nv.value.squeeze(), [nv]

            # case 3: raw numeric value
            return input_val, []

        attempts = 0
        while attempts < max_retries:
            # gather all potential random values for this attempt
            m_val, m_nv = _resolve_and_track(mass)
            p_val, p_nv = _resolve_and_track(pos)
            d_val, d_nv = (
                _resolve_and_track(diaginertia)
                if diaginertia is not None
                else (None, [])
            )
            f_val, f_nv = (
                _resolve_and_track(fullinertia)
                if fullinertia is not None
                else (None, [])
            )

            resolved_ori = None
            ori_nv = []

            if orientation is None:
                resolved_ori = Quat()
            elif isinstance(orientation, OrientationBase):
                resolved_ori = orientation
            elif isinstance(orientation, tuple) and len(orientation) == 3:
                ori_type, ori_data, extra_val = orientation
                ori_val, ori_nv = _resolve_and_track(ori_data)

                field_name = ori_type._rotation_attr
                data_dict: dict[str, Any] = {
                    "type": ori_type.model_fields["type"].default,
                    field_name: ori_val,
                }

                # If the 3rd element is an EulerSeq, add it to the dict
                if extra_val is not None:
                    assert isinstance(extra_val, EulerSeq)
                    data_dict["eulerseq"] = extra_val

                resolved_ori = ori_type(**data_dict)
            else:
                msg = "orientation must be None, an Orientation object, or (Class, Data) tuple."
                logger.error(msg)
                raise TypeError(msg)

            try:
                instance_pose = resolved_ori.as_pose(pos=p_val)

                instance = cls(
                    mass=float(m_val),
                    pose=instance_pose,
                    diaginertia=d_val,
                    fullinertia=f_val,
                )

                # success! commiting all Namedvalues to the registry
                all_pending = m_nv + p_nv + d_nv + f_nv + ori_nv
                for nv in all_pending:
                    mojo_model.named.force_update(nv, warn=False)

                return instance

            except ValueError as e:
                attempts += 1
                if attempts > max_retries // 2:
                    logger.warning(
                        f"High rejection rate detected for Inertial sampling. Current attempt: {attempts}/{max_retries}. Latest error: {e}"
                    )

        msg = f"Failed to generate valid Inertial after {max_retries} retries."
        logger.error(msg)
        raise RuntimeError(msg)
