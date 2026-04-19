from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Any, Literal

from pydantic import Field
from stochas.base_collections import BaseDict, BaseList
from stochas.named_value import NamedValue, ValueName

__all__ = [
    "DesignCategorical",
    "DesignFloat",
    "DesignValueDict",
    "DesignValueList",
]


class DesignFloat(NamedValue[float]):
    """
    A NamedValue that represents a floating point design parameter to be optimized.

    Contains bounds required for search space discovery.
    """

    type: Literal["float"] = "float"

    low: float
    """Lower bound for hyperparameter tuning."""

    high: float
    """Upper bound for hyperparameter tuning."""

    log: bool = False
    """Use support for log-scale search (useful for learning rates or stiffness)."""

    step: float | None = None
    """Discretize the search space (e.g., step=0.5)."""


class DesignCategorical[T](NamedValue[T]):
    """A NamedValue that represents a categorical design parameter to be optimized."""

    type: Literal["categorical"] = "categorical"

    choices: Sequence[T]
    """For categorical search (e.g., choices=['stiff', 'soft'])."""


AnyDesignValue = Annotated[
    DesignFloat | DesignCategorical,
    Field(discriminator="type"),
]


class DesignValueDict(BaseDict[AnyDesignValue]):
    """Dictionary specifically for sampled results."""

    def __contains__(self, key: object) -> bool:
        if isinstance(key, NamedValue):
            key = key.name
        return super().__contains__(key=key)

    def get_value(self, name: ValueName | str) -> Any:
        """Gets the NamedValue value of a key."""
        return self[name].value

    def get_raw_value(self, name: ValueName | str) -> Any | None:
        """Gets the NamedValue raw value. This includes None if the value has not yet been set."""
        return self[name].stored_value

    @property
    def named_value_list(self) -> DesignValueList:
        """Converts the DesignValueDict to a DesignValueList."""
        return DesignValueList(list(self.values()))


class DesignValueList(BaseList[AnyDesignValue]):
    """List specifically for sampled results."""

    @property
    def to_named_value_dict(self) -> DesignValueDict:
        """Converts the DesignValueList to a DesignValueDict."""
        d = DesignValueDict()
        d.update_many(self.root)
        return d
