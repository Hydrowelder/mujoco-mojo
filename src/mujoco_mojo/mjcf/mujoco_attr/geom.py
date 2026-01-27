from __future__ import annotations

from typing import Optional, Tuple

from pydantic import model_validator

from mujoco_mojo.base import XMLModel
from mujoco_mojo.types import GeomType, Vec3, Vec4

__all__ = ["Geom"]


class Geom(XMLModel):
    tag = "geom"

    attributes = ("name", "type", "size", "rgba", "pos")

    name: Optional[str] = None
    type: GeomType = GeomType.SPHERE
    size: Optional[Tuple[float, ...] | float] = None
    rgba: Optional[Vec4] = None
    pos: Optional[Vec3] = None

    @model_validator(mode="after")
    def validate_vectors(self) -> "Geom":
        if self.rgba is not None and len(self.rgba) != 4:
            raise ValueError("geom.rgba must be length 4")

        if self.pos is not None and len(self.pos) != 3:
            raise ValueError("geom.pos must be length 3")

        if self.size is not None:
            expected = {
                GeomType.SPHERE: 1,
                GeomType.CAPSULE: 2,
                GeomType.CYLINDER: 2,
                GeomType.BOX: 3,
                GeomType.ELLIPSOID: 3,
                GeomType.PLANE: 3,
                GeomType.MESH: 3,
                GeomType.SDF: 3,
            }[self.type]

            if isinstance(self.size, tuple) and len(self.size) != expected:
                if self.type == GeomType.SPHERE:
                    raise TypeError(
                        f"geom.size for {self.type} must be a float, got a sequence with length {len(self.size)}"
                    )
                raise ValueError(
                    f"geom.size for {self.type} must have length {expected}, got {len(self.size)}"
                )

        return self
