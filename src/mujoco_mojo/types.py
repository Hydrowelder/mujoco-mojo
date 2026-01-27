from __future__ import annotations

from typing import Tuple

from pydantic import BaseModel, field_validator

__all__ = ["Vec3"]


class Vec3(BaseModel):
    value: Tuple[float, float, float]

    @field_validator("value")
    @classmethod
    def check_len(cls, v) -> Tuple[float, float, float]:
        if len(v) != 3:
            raise ValueError(f"Vec3 requires exactly 3 values (entered {len(v)})")
        return v

    def __str__(self) -> str:
        return " ".join(str(x) for x in self.value)
