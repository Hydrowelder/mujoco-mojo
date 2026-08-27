from __future__ import annotations

from typing import ClassVar

import mujoco
from pydantic import Field

from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import PluginName
from mujoco_mojo.utils.utils import is_empty_list

__all__ = [
    "Extension",
    "ExtensionPlugin",
    "ExtensionPluginInstance",
    "ExtensionPluginInstanceConfig",
]


class ExtensionPluginInstanceConfig(XMLModel):
    """Configuration of a plugin instance. When implicitly declaring a plugin under a model element, configuration is performed with identical semantics using element/plugin/config. The elements which currently support plugins are body, composite, actuator and sensor."""

    tag = "config"

    attributes = ("key", "value")

    key: str
    """Key used for plugin configuration."""

    value: str | None = None
    """Value associated with key."""


class ExtensionPluginInstance(XMLModel):
    """Declares a plugin instance. Explicit instances declaration is required when multiple elements are backed by the same plugin, or when global plugin configuration is desired. See plugin declaration and configuration for more details."""

    tag = "instance"

    attributes = ("name",)
    children = ("configs",)

    name: PluginName
    """Name of the plugin instance."""

    configs: list[ExtensionPluginInstanceConfig] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Extension plugins definitions grouping."""

    _mjt_obj: ClassVar[mujoco.mjtObj | None] = mujoco.mjtObj.mjOBJ_PLUGIN


class ExtensionPlugin(XMLModel):
    """This element specifies that an engine plugin is required in order to simulate this model. See Engine plugins for more details."""

    tag = "plugin"

    attributes = ("plugin",)
    children = ("instances",)

    plugin: PluginName
    """Identifier of the plugin."""

    instances: list[ExtensionPluginInstance] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Extension plugins instance definitions grouping."""


class Extension(XMLModel):
    """This is a grouping element for MuJoCo extensions. Extensions allow the user to extend MuJoCo's capabilities with custom code and are described in detail in the Programming chapter's Extensions page. Currently, the only available extension type are Engine plugins."""

    tag = "extension"

    children = ("plugins",)

    plugins: list[ExtensionPlugin] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Extension plugins definitions grouping."""
