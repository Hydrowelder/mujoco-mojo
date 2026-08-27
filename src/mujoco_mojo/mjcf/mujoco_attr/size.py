from __future__ import annotations

from mujoco_mojo.mjcf.xml_model import XMLModel

__all__ = ["Size"]


class Size(XMLModel):
    """This element specifies size parameters that cannot be inferred from the number of elements in the model. Unlike the fields of mjOption which can be modified at runtime, sizes are structural parameters and should not be modified after compilation."""

    tag = "size"

    attributes = (
        "memory",
        "njmax",
        "nconmax",
        "nstack",
        "nuserdata",
        "nkey",
        "nuser_body",
        "nuser_jnt",
        "nuser_geom",
        "nuser_site",
        "nuser_cam",
        "nuser_tendon",
        "nuser_actuator",
        "nuser_sensor",
    )

    memory: str = "-1"
    """This attribute specifies the size of memory allocated for dynamic arrays in the mjData.arena memory space, in bytes. The default setting of -1 instructs the compiler to guess how much space to allocate. Appending the digits with one of the letters {K, M, G, T, P, E} sets the unit to be {kilo, mega, giga, tera, peta, exa}-byte, respectively. Thus "16M" means "allocate 16 megabytes of arena memory". See the Memory allocation section for details."""

    njmax: int = -1
    """This is a deprecated legacy attribute. It previously determined the maximum allowed number of constraints. Currently it means "allocate as much memory as would have previously been required for this number of constraints". Specifying both njmax and memory leads to an error."""

    nconmax: int = -1
    """This attribute specifies the maximum number of contacts that will be generated at runtime. If the number of active contacts is about to exceed this value, the extra contacts are discarded and a warning is generated. This is a deprecated legacy attribute which previously affected memory allocation. It is kept for backwards compatibility and debugging purposes."""

    nstack: int = -1
    """This is a deprecated legacy attribute. It previously determined the maximum size of the stack. If nstack is specified, then the size of mjData.narena is `nstack * sizeof(mjtNum)` bytes, plus an additional space for the constraint solver. Specifying both nstack and memory leads to an error."""

    nuserdata: int = 0
    """The size of the field mjData.userdata of mjData. This field should be used to store custom dynamic variables. See also User parameters."""

    nkey: int = 0
    """The number of key frames allocated in mjModel is the larger of this value and the number of key elements below. Note that the interactive simulator has the ability to take snapshots of the system state and save them as key frames."""

    nuser_body: int = -1
    """The number of custom user parameters added to the definition of each body. See also User parameters. The parameter values are set via the user attribute of the body element. These values are not accessed by MuJoCo. They can be used to define element properties needed in user callbacks and other custom code."""

    nuser_jnt: int = -1
    """The number of custom user parameters added to the definition of each joint."""

    nuser_geom: int = -1
    """The number of custom user parameters added to the definition of each geom."""

    nuser_site: int = -1
    """The number of custom user parameters added to the definition of each site."""

    nuser_cam: int = -1
    """The number of custom user parameters added to the definition of each camera."""

    nuser_tendon: int = -1
    """The number of custom user parameters added to the definition of each tendon."""

    nuser_actuator: int = -1
    """The number of custom user parameters added to the definition of each actuator."""

    nuser_sensor: int = -1
    """The number of custom user parameters added to the definition of each sensor."""
