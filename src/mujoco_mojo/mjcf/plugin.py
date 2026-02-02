from __future__ import annotations

from typing import Self

from pydantic import model_validator

from mujoco_mojo.base import XMLModel
from mujoco_mojo.typing import InstanceName, PluginName

__all__ = ["Plugin"]


class Plugin(XMLModel):
    """
    Engine plugins, introduced in MuJoCo 2.3.0, allow user-defined logic to be inserted into various parts of MuJoCo's computational pipeline. For example, custom sensor and actuator types can be implemented as plugins. Plugin features are referenced in the XML content of an MJCF model, allowing MJCF to remain an abstract physical description of a system even if the simulation requirements extend beyond MuJoCo's built-in capabilities.

    The plugin mechanism was designed to overcome the disadvantages of MuJoCo's physics callbacks. These global callbacks (usage example) are still available and useful for fast prototyping or when the user wishes to implement functionality in Python, but are generally deprecated as a stable mechanism for extended functionality. The central features of the plugin mechanism are:

    * Thread safety: Plugin instances (see below) are thread-local, avoiding collisions.
    * Statefulness: Plugins can be stateful, and their state will be (de)serialized correctly.
    * Interoperability: Different plugins can coexist without interference.
    """

    tag = "plugin"

    attributes = ("plugin", "instance")

    plugin: PluginName | None = None
    """Plugin identifier, used for implicit plugin instantiation.

    A plugin is a collection of functions and static attributes that implement its capabilities, bundled into an mjpPlugin struct. Plugin functions are stateless: they depend only on the arguments passed to them. When a plugin requires an internal state, it declares this state and allows MuJoCo to manage it and pass it in. This enables (de)serialization of the full simulation state. A plugin can therefore be regarded as the "pure logic" part of the functionality and is often bundled as a C library. A plugin is neither a model element nor is it associated with specific model elements.
    """

    instance: InstanceName | None = None
    """Instance name, used for explicit plugin instantiation.

    A plugin instance represents the self-contained runtime state that is operated on by the plugin: when the plugin logic is executed, the instance state is passed in by the engine. A plugin instance is itself a model element of type mjOBJ_PLUGIN. There are mjModel.nplugin instances with id's in [0 nplugin-1]. Like other elements, instances can have names, with mj_name2id and mj_id2name mapping between id's and names. Unlike the plugin code which is loaded once into a global table, multiple instances of the same plugin can be defined and have a one-to-many relationship with other model elements.
    """

    @model_validator(mode="after")
    def validate_plugin(self) -> Self:
        if not self.plugin or self.instance:
            raise ValueError("Must specify at least one of 'plugin' or 'instance'")
        return self
