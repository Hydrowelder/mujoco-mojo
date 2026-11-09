from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, Self, cast

import numpy as np
from pydantic import field_validator, model_validator

from mujoco_mojo.mjcf.orientation import (
    AnyOrientation,
    OrientationBase,
    Quat,
)
from mujoco_mojo.mjcf.position import Pos
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.stochas import AnyDist, Distribution, NamedValue, TransactionAttempt
from mujoco_mojo.typing import EulerSeq, Mat3, Vec3, Vec6
from mujoco_mojo.utils.log import get_logger

if TYPE_CHECKING:
    from mujoco_mojo.mojo_model import MojoModel

logger = get_logger(__name__)

__all__ = ["Inertial"]

type _OrientationInput = (
    tuple[type[OrientationBase], list[float | AnyDist], EulerSeq | None]
    | AnyOrientation
    | None
)
"""The `orientation` argument of `Inertial.from_random`."""


class _RejectedDraw(Exception):
    """A random draw that does not make a physical `Inertial`. `Inertial.from_random` redraws on this and on nothing else, so any other error reaches the caller on the first attempt."""


def _distributions(*values: Any) -> list[Distribution[Any]]:
    """Every distribution among the `from_random` inputs, whether given whole or as a component of a tuple or list, in the order the inputs are given."""
    found: list[Distribution[Any]] = []
    for value in values:
        items = value if isinstance(value, (list, tuple)) else [value]
        found.extend(item for item in items if isinstance(item, Distribution))
    return found


def _attempts(mojo_model: MojoModel, max_retries: int) -> Iterator[TransactionAttempt]:
    """
    Yields the attempts of a transaction on `mojo_model`, which ends once one of them finishes without a `_RejectedDraw`.

    The error for running out of attempts is restated here in terms of `Inertial`. Only the transaction giving up can raise it: an error raised in the caller's `with attempt:` block never travels back into this generator.
    """
    try:
        yield from mojo_model.transaction(
            retry_on=_RejectedDraw, max_retries=max_retries
        )
    except RuntimeError as e:
        msg = f"Failed to generate valid Inertial after {max_retries} retries."
        logger.error(msg)
        raise RuntimeError(msg) from e


def _draw(attempt: TransactionAttempt, value: Any, reset_rng: bool) -> tuple[Any, int]:
    """
    Samples every distribution in `value`, which is one distribution, a tuple or list that mixes distributions with plain numbers, or a plain number or array.

    Each sample is registered on the model, replacing any value already registered under its name, unless the attempt is rejected. Returns what the `Inertial` is built from and how many distributions were sampled.
    """

    def sample(dist: Distribution[Any]) -> NamedValue[Any]:
        if reset_rng:
            return attempt.sample_dist(dist, force=True, warn=False)
        # the attempt reseeds a distribution the first time it sees it, so go around it to keep the caller's seed
        return attempt.base.sample_dist(dist, force=True, warn=False, reset_rng=False)

    if isinstance(value, (list, tuple)):
        resolved: list[Any] = []
        sampled = 0
        for item in value:
            if isinstance(item, Distribution):
                resolved.append(sample(item).squeeze())
                sampled += 1
            else:
                resolved.append(item)
        return np.asarray(resolved, dtype=float), sampled

    if isinstance(value, Distribution):
        return sample(value).value.squeeze(), 1

    return value, 0


def _draw_orientation(
    attempt: TransactionAttempt, orientation: _OrientationInput, reset_rng: bool
) -> tuple[AnyOrientation, int]:
    """Resolves the `orientation` argument of `Inertial.from_random` into an orientation, drawing from the distributions of a `(Class, Data, EulerSeq)` tuple."""
    if orientation is None:
        return Quat(), 0

    if isinstance(orientation, OrientationBase):
        return orientation, 0

    if isinstance(orientation, tuple):
        ori_type, ori_data, eulerseq = orientation
        ori_val, sampled = _draw(attempt, ori_data, reset_rng)

        data_dict: dict[str, Any] = {
            "type": ori_type.model_fields["type"].default,
            ori_type._rotation_attr: ori_val,
        }
        if eulerseq:
            data_dict["eulerseq"] = eulerseq

        return cast(AnyOrientation, ori_type(**data_dict)), sampled

    msg = "orientation must be None, an Orientation object, or (Class, Data) tuple."
    logger.error(msg)
    raise TypeError(msg)


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

    pos: Pos
    """Position of the inertial frame. It is required even when the inertial properties can be inferred from geoms. This is because the presence of the inertial element itself disables the automatic inference mechanism."""

    orientation: AnyOrientation | None = None
    """Orientation of the inertial frame."""

    mass: float
    """Mass of the body. Negative values are not allowed. MuJoCo requires the inertia matrix in generalized coordinates to be positive-definite, which can sometimes be achieved even if some bodies have zero mass. In general however there is no reason to use massless bodies. Such bodies are often used in other engines to bypass the limitation that joints cannot be combined, or to attach sensors and cameras. In MuJoCo primitive joint types can be combined, and we have sites which are a more efficient attachment mechanism."""

    diaginertia: Vec3 | None = None
    """Diagonal inertia matrix, expressing the body inertia relative to the inertial frame. If this attribute is omitted, the next attribute becomes required."""

    fullinertia: Vec6 | None = None
    """Full inertia matrix M. Since M is 3-by-3 and symmetric, it is specified using only 6 numbers in the following order: M(1,1), M(2,2), M(3,3), M(1,2), M(1,3), M(2,3). The compiler computes the eigenvalue decomposition of M and sets the frame orientation and diagonal inertia accordingly. If non-positive eigenvalues are encountered (i.e., if M is not positive definite) a compile error is generated, unless boundinertia is positive, in which case the eigenvalues are bounded below by it."""

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
    def cg_x(self) -> float:
        return self.pos.x

    @property
    def cg_y(self) -> float:
        return self.pos.y

    @property
    def cg_z(self) -> float:
        return self.pos.z

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

        if self.fullinertia is not None and self.orientation is not None:
            msg = "orientation cannot be provided when using 'fullinertia'. The orientation is automatically derived from the full inertia matrix."
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
            msg = f"Inertia matrix must be positive definite. Eigenvalues: {eigvals}"
            logger.error(msg)
            raise ValueError(msg)

        # triangle inequality check
        # eigvalsh returns eigenvalues in ascending order, so e1 + e3 >= e2 and
        # e2 + e3 >= e1 always hold; only the largest-vs-sum-of-others case can fail
        e1, e2, e3 = eigvals
        if e1 + e2 < e3:
            msg = f"Inertia tensor violates the triangle inequality: the largest principal moment of inertia ({e3:.6e}) exceeds the sum of the other two ({e1:.6e} + {e2:.6e} = {e1 + e2:.6e})."
            logger.error(msg)
            raise ValueError(msg)

        return self

    @property
    def rotation_matrix(self) -> Mat3:
        """Returns the 3x3 rotation matrix for the inertial frame."""
        if self.orientation:
            return self.orientation.as_matrix()
        return np.eye(3)

    def get_body_frame_inertia(self) -> Mat3:
        """
        Calculates the 3x3 inertia matrix expressed in the parent body's frame.

        This uses the Parallel Axis Theorem (Steiner's Theorem) to shift the moment of inertia from the center of mass to the parent body origin based on the 'pos' and 'orientation' attributes.

        Returns:
            np.ndarray: A 3x3 symmetric inertia matrix in the body frame.

        """
        # rotate into body frame axes
        R = self.rotation_matrix
        I_local = self.inertia_matrix
        I_rot = R @ I_local @ R.T

        # parallel axis theorem
        # I_body = I_com + m ([r_skew]^2) -> I_com + m * ( (p.T @ p) * eye(3) - p @ p.T )
        p = self.pos.pos
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
            pos=Pos(pos=pos),
            orientation=Quat.from_matrix(eigvecs),
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
        p1, p2 = self.pos.pos, other.pos.pos
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
        p1, p2 = self.pos.pos, other.pos.pos
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
        mass: float | AnyDist,
        pos: Vec3 | tuple[float | AnyDist, float | AnyDist, float | AnyDist] | Pos,
        diaginertia: Vec3
        | tuple[float | AnyDist, float | AnyDist, float | AnyDist]
        | None = None,
        fullinertia: Vec6
        | tuple[
            float | AnyDist,
            float | AnyDist,
            float | AnyDist,
            float | AnyDist,
            float | AnyDist,
            float | AnyDist,
        ]
        | None = None,
        orientation: tuple[
            type[OrientationBase], list[float | AnyDist], EulerSeq | None
        ]
        | AnyOrientation
        | None = None,
        max_retries: int = 10,
        reset_rng: bool = True,
    ) -> Inertial:
        """
        Generates an Inertial element by sampling from provided distributions.

        Supports both vector-level and component-level randomization. This method will re-sample until a physically valid configuration is found or max_retries is reached.

        Args:
            mojo_model (MojoModel): The MojoModel instance for sampling and registration.
            mass (float | AnyDist): Mass value or distribution.
            pos (Vec3 | tuple[float  |  AnyDist, float  |  AnyDist, float  |  AnyDist]): Position vector or tuple of component distributions.
            diaginertia (Vec3 | tuple[float  |  AnyDist, float  |  AnyDist, float  |  AnyDist] | None, optional): Principal moments or tuple of component distributions. Defaults to None.
            fullinertia (Vec6 | tuple[ float  |  AnyDist, float  |  AnyDist, float  |  AnyDist, float  |  AnyDist, float  |  AnyDist, float  |  AnyDist, ] | None, optional): Full inertia vector or tuple of component distributions. Defaults to None.
            orientation (tuple[type[OrientationBase], list[float | AnyDist], EulerSeq | None] | Orientation | None, optional): Orientation for the inertial frame. Defaults to None.
            max_retries (int, optional): Maximum number of re-samples on physics failure. Defaults to 10.
            reset_rng (bool, optional): Whether or not to reset the seed and trial number for the distribution. Setting the seed and trial number will reset the random number cycle. This will not skip registering the distribution or NamedValues to the MojoModel. If you want pseudorandom number generation, setting to False will require you to manually set the seed and trial number before passing the distribution into `from_random`. Defaults to True.

        Raises:
            ValueError: If neither diaginertia nor fullinertia are provided.
            RuntimeError: If a valid configuration is not found within max_retries.

        Returns:
            Inertial: A physically valid randomized Inertial element.

        """
        if isinstance(pos, Pos):
            pos = pos.pos

        if diaginertia is None and fullinertia is None:
            msg = "diaginertia or fullinertia must be defined"
            logger.exception(msg)
            raise ValueError(msg)

        if fullinertia is not None and orientation is not None:
            msg = "fullinertia and orientation cannot simultaneously be defiend."
            logger.exception(msg)
            raise ValueError(msg)

        # a name can be registered once, so reusing one (or one the model already holds) is refused before anything is drawn
        registered = set(mojo_model.dists)
        for dist in _distributions(
            mass,
            pos,
            diaginertia,
            fullinertia,
            orientation[1] if isinstance(orientation, tuple) else None,
        ):
            if dist.name in registered:
                msg = f"{dist.name} has already been registered."
                logger.error(msg)
                raise KeyError(msg)
            registered.add(dist.name)

        instance: Inertial | None = None
        for attempt in _attempts(mojo_model, max_retries):
            with attempt:
                mass_val, sampled = _draw(attempt, mass, reset_rng)
                pos_val, n = _draw(attempt, pos, reset_rng)
                sampled += n
                diag_val, n = (
                    _draw(attempt, diaginertia, reset_rng)
                    if diaginertia is not None
                    else (None, 0)
                )
                sampled += n
                full_val, n = (
                    _draw(attempt, fullinertia, reset_rng)
                    if fullinertia is not None
                    else (None, 0)
                )
                sampled += n
                orientation_val, n = (
                    _draw_orientation(attempt, orientation, reset_rng)
                    if fullinertia is None
                    else (None, 0)
                )
                sampled += n

                # only an invalid inertial is redrawn; an error from drawing itself is a real error
                try:
                    instance = cls(
                        mass=float(mass_val),
                        pos=Pos(pos=pos_val),
                        orientation=orientation_val,
                        diaginertia=diag_val,
                        fullinertia=full_val,
                    )
                except ValueError as e:
                    raise _RejectedDraw(str(e)) from e

                if sampled:
                    logger.info(
                        f"Generated valid Inertial after {attempt.attempt_number} attempt(s) by sampling {sampled} distribution(s)"
                    )

        # the attempts only run out by raising, so the loop ends with a valid inertial
        assert instance is not None
        return instance
