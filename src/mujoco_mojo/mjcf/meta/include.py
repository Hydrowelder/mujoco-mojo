"""
!!! failure "Not Implemented"
    The Include class is not implemented. There is no plan to implement as its functionality is duplicated by Attach and that of Python itself. Its functionality within the Mujoco class is not implemented.
"""

from __future__ import annotations

from pathlib import Path

from mujoco_mojo.base import XMLModel

raise NotImplementedError(
    "The Include class is not implemented. There is no plan to implement as its functionality is duplicated by Attach and that of Python itself."
)

__all__ = ["Include"]


class Include(XMLModel):
    """This element does not strictly belong to MJCF. Instead it is a meta-element, used to assemble multiple XML files in a single document object model (DOM) before parsing. The included file must be a valid XML file with a unique top-level element. This top-level element is removed by the parser, and the elements below it are inserted at the location of the include element. At least one element must be inserted as a result of this procedure. The include element can be used where ever an XML element is expected in the MJCF file. Nested includes are allowed, however a given XML file can be included at most once in the entire model. After all the included XML files have been assembled into a single DOM, it must correspond to a valid MJCF model. Other than that, it is up to the user to decide how to use includes and how to modularize large files if desired.

    !!! note "Prefer Attach to Include"
        While some use cases for include remain valid, it is recommended to use the attach element instead, where applicable.
    """

    tag = "include"

    attributes = ("file",)

    file: Path
    """The name of the XML file to be included. The file location is relative to the directory of the main MJCF file. If the file is not in the same directory, it should be prefixed with a relative path."""
