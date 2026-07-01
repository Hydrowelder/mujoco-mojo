"""
Physical unit system for MuJoCo Mojo models.

Declare the unit system used in a model so that values in the generate step can be
expressed in any unit and converted automatically, and so that telemetry metadata can
report concrete units instead of abstract Pint dimensions.
"""

from __future__ import annotations

from typing import Any

import pint
from pydantic import BaseModel

__all__ = ["UnitDescriptor", "UnitSystem", "ureg"]

ureg = pint.UnitRegistry()
try:
    ureg.define("lbm = pound")
    ureg.define("lbf = force_pound")
    ureg.define("ozf = force_ounce")
except pint.errors.RedefinitionError:
    pass


class UnitDescriptor:
    """
    A named unit with a float conversion factor to the model's base unit for that dimension.

    `float(descriptor)` returns the conversion factor: multiply by this to convert FROM this unit INTO the model's base unit for the same physical dimension. `str(descriptor)` returns the unit name (e.g. `"inch"`, `"meter"`).

    Example usage::

        mojo_model.u = UnitSystem.si()  # base units: meter, kilogram, second

        body.inertial = mj.Inertial(
            mass=2.5,
            pos=Pos(np.array([0, 1, 2]) * mojo_model.u.inch),  # converts inches to meters
        )
    """

    __slots__ = ("_factor", "_name")

    def __init__(self, name: str, factor: float) -> None:
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_factor", factor)

    def __float__(self) -> float:
        return self._factor

    def __str__(self) -> str:
        return self._name

    def __repr__(self) -> str:
        return f"UnitDescriptor({self._name!r}, factor={self._factor!r})"

    def __mul__(self, other: Any) -> Any:
        return other * self._factor

    def __rmul__(self, other: Any) -> Any:
        return other * self._factor

    def __truediv__(self, other: Any) -> Any:
        return self._factor / other

    def __rtruediv__(self, other: Any) -> Any:
        return other / self._factor


class UnitSystem(BaseModel):
    """
    Declares the physical unit system for a MuJoCo model.

    Each field names the base unit for one Pint dimension. Any Pint-recognized unit -- base or compound -- can be accessed as an attribute and returns a `UnitDescriptor` whose float value is the conversion factor FROM that unit INTO the model's equivalent unit for the same dimensionality, and whose string value is the unit name. A dimension must be configured for every component that appears in the target unit's dimensionality; otherwise `AttributeError` is raised.

    Built-in coherent factory methods -- in each, the natural force unit is the product of the mass and length base units divided by time squared:

    - `UnitSystem.si()`: meter / kilogram / second -- force = newton
    - `UnitSystem.cgs()`: centimeter / gram / second -- force = dyne
    - `UnitSystem.fps()`: foot / slug / second -- force = lbf
    - `UnitSystem.ips()`: inch / slinch / second -- force = lbf  (slinch = 12 slugs = lbf*s^2/in)

    Example::

        mojo_model.u = UnitSystem.si()

        float(mojo_model.u.meter)        # -> 1.0
        float(mojo_model.u.inch)         # -> 0.0254
        float(mojo_model.u.newton)       # -> 1.0  (kg*m/s^2 in SI)
        float(mojo_model.u.lbf)          # -> 4.448...
        float(mojo_model.u.horsepower)   # -> 745.7...
        float(mojo_model.u.volt)         # -> 1.0  (requires current="ampere")
        float(mojo_model.u.degF)         # -> requires temperature="kelvin"
        str(mojo_model.u.inch)           # -> "inch"
        mojo_model.u.length              # -> "meter"
    """

    # --- mechanical base dimensions ---
    length: str
    """Base length unit (e.g. `"meter"`, `"inch"`, `"foot"`)."""
    mass: str
    """Base mass unit (e.g. `"kilogram"`, `"slug"`, `"slinch"`, `"gram"`). Use a coherent mass unit for the chosen length scale so that derived force units come out naturally -- see the factory methods for the standard combinations."""
    time: str = "second"
    """Base time unit. Defaults to `"second"`, which is the conventional choice, but MuJoCo has no intrinsic time scale -- it treats time as whatever unit the user treats it as."""

    # --- other SI base dimensions (all optional; only needed when resolving units in those dimensions) ---
    temperature: str | None = None
    """Base temperature unit (e.g. `"kelvin"`, `"degC"`). Required for thermal units like `joule_per_kelvin`."""
    current: str | None = None
    """Base electric current unit (e.g. `"ampere"`). Required for electromagnetic units like `volt`, `ohm`, `farad`."""
    amount: str | None = None
    """Base amount-of-substance unit (e.g. `"mole"`). Required for molar quantities."""
    luminosity: str | None = None
    """Base luminous intensity unit (e.g. `"candela"`). Required for photometric units like `lux`, `lumen`."""

    @classmethod
    def si(cls) -> UnitSystem:
        """SI base units: meter, kilogram, second, kelvin, ampere, mole, candela."""
        return cls(
            length="meter",
            mass="kilogram",
            temperature="kelvin",
            current="ampere",
            amount="mole",
            luminosity="candela",
        )

    @classmethod
    def cgs(cls) -> UnitSystem:
        """Centimeter-gram-second system (mechanical dimensions only). Coherent force unit: dyne (1 dyne = 1 g*cm/s^2 = 1e-5 N). Extend with `model_copy` to add thermal or electromagnetic base units."""
        return cls(length="centimeter", mass="gram")

    @classmethod
    def fps(cls) -> UnitSystem:
        """Foot-slug-second system (mechanical dimensions only). Coherent force unit: lbf (1 lbf = 1 slug*ft/s^2). Extend with `model_copy` to add thermal or electromagnetic base units."""
        return cls(length="foot", mass="slug")

    @classmethod
    def ips(cls) -> UnitSystem:
        """Inch-slinch-second system (mechanical dimensions only). Coherent force unit: lbf (1 lbf = 1 slinch*in/s^2; 1 slinch = 12 slugs). Extend with `model_copy` to add thermal or electromagnetic base units."""
        return cls(length="inch", mass="slinch")

    def __getattr__(self, name: str) -> UnitDescriptor:
        if name.startswith("_"):
            raise AttributeError(name)

        try:
            unit = ureg.parse_units(name)
        except Exception:
            raise AttributeError(
                f"{name!r} is not a recognized Pint unit and is not an attribute of UnitSystem"
            ) from None

        dim_dict = dict(ureg.get_dimensionality(unit))

        # map Pint dimension strings to the configured base unit name (None entries are skipped)
        base_unit_for_dim: dict[str, str] = {
            k: v
            for k, v in {
                "[length]": self.length,
                "[mass]": self.mass,
                "[time]": self.time,
                "[temperature]": self.temperature,
                "[current]": self.current,
                "[substance]": self.amount,
                "[luminosity]": self.luminosity,
            }.items()
            if v is not None
        }

        # build the compound model unit for this dimensionality by multiplying base units raised
        # to their exponents, e.g. {"[mass]": 1, "[length]": 1, "[time]": -2} (force) ->
        # kilogram * meter * second^-2 for SI.  dimensionless units (empty dim_dict) pass through
        # unchanged since the loop never executes.
        model_unit = ureg.dimensionless
        for dim_key, exp in dim_dict.items():
            base_name = base_unit_for_dim.get(dim_key)
            if base_name is None:
                configured = ", ".join(
                    f"{k}={v!r}" for k, v in base_unit_for_dim.items()
                )
                raise AttributeError(
                    f"UnitSystem cannot resolve a model unit for {name!r}: "
                    f"no base unit configured for Pint dimension {dim_key!r} "
                    f"(configured: {configured})"
                )
            model_unit = model_unit * ureg.parse_units(base_name) ** exp

        factor = float(ureg.Quantity(1, unit).to(model_unit).magnitude)
        return UnitDescriptor(name, factor)


if __name__ == "__main__":
    breakpoint()
