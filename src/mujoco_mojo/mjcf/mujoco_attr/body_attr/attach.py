from __future__ import annotations

from typing import Optional

from mujoco_mojo.base import XMLModel
from mujoco_mojo.typing import BodyName, ModelName

__all__ = ["Attach"]


class Attach(XMLModel):
    """The attach element is used to insert a sub-tree of bodies from another model into this model's kinematic tree. Unlike include, which is implemented in the parser and is equivalent to copying and pasting XML from one file into another, attach is implemented in the model compiler. In order to use this element, the sub-model must first be defined as an asset. When creating an attachment, the top body of the attached subtree is specified, and all referencing elements outside the kinematic tree (e.g., sensors and actuators), are also copied into the top-level model. Additionally, any elements referenced from within the attached subtree (e.g. defaults and assets) will be copied in to the top-level model. attach is a Meta elements, so upon saving all attachments will appear in the saved XML file. Note that this element is a subset of the functionality of the procedural attachment functionality. As such, it shares the same limitations as described there. In addition, when the attach element is used, it is not possible to attach an entire model (i.e. including all elements, referenced or not)."""

    tag = "attach"
    attributes = ("model", "body", "prefix")

    model: ModelName
    """The sub-model from which to attach a subtree."""

    body: Optional[BodyName] = None
    """Name of the body in the sub-model to attach here. The body and its subtree will be attached. If this attribute is not specified, the contents of the world body will be attached in a new frame."""

    prefix: str
    """Prefix to prepend to names of elements in the sub-model. This attribute is required to prevent name collisions with the parent or when attaching the same sub-tree multiple times."""
