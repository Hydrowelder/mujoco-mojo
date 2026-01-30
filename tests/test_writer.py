from pathlib import Path

import mujoco
import numpy as np

import mujoco_mojo as mojo


def test_import():
    import mujoco_mojo as mojo

    mojo.__name__


quat = mojo.Quat(quat=np.array([1, 2, 3, 4]))
sphere = mojo.GeomSphere(size=0.2, rgba=np.asarray((1, 0, 0, 1)))
material = mojo.Material(name="material_name")

world = mojo.WorldBody(
    geoms=[
        mojo.GeomPlane(
            name="floor",
            size=np.asarray((5, 5, 0.1)),
            rgba=np.array((0.5, 0.5, 0.5, 1)),
            orientation=quat,
            material=material.name,
        )
    ],
    bodies=[
        mojo.Body(
            name="robot",
            geoms=[
                sphere,
                mojo.GeomCylinder(
                    size=np.asarray([1, 3]),
                    rgba=np.asarray((1, 0, 0, 1)),
                ),
            ],
        )
    ],
)

model = mojo.Mujoco(
    worldbody=world, model="hello", compilers=[mojo.Compiler(balanceinertia=True)]
)

# ensure it works with mujoco
xml = mojo.to_pretty_xml(model.to_xml())
save_as = Path(__file__).with_name("result_test_writer.xml")
save_as.write_text(xml)

m = mujoco.MjSpec.from_file(save_as.as_posix())

# serialize and deserialize
json_file = save_as.with_suffix(".json")

json_file.with_stem("quat").write_text(quat.model_dump_json(exclude_none=True))
assert "type" in quat.model_dump_json(exclude_none=True), (
    "Orientation type was not serialized"
)
quat = mojo.Quat.model_validate_json(json_file.with_stem("quat").read_text())

json_file.with_stem("sphere").write_text(sphere.model_dump_json(exclude_none=True))
assert "type" in sphere.model_dump_json(exclude_none=True), (
    "geom type was not serialized"
)
sphere = mojo.GeomSphere.model_validate_json(json_file.with_stem("sphere").read_text())


json_file.write_text(model.model_dump_json(exclude_none=True))
model = mojo.Mujoco.model_validate_json(json_file.read_text())
