from pathlib import Path

import mujoco
import numpy as np

import mujoco_mojo as mojo
import mujoco_mojo.typing as mojot
from mujoco_mojo import mjcf


def test_import():
    import mujoco_mojo as mojo
    from mujoco_mojo import mjcf

    mojo.__name__
    mjcf.__name__


# =============== build a basic model ===============
quat = mjcf.Quat(quat=np.array((1, 2, 3, 4)))
sphere = mjcf.GeomSphere(size=0.2, rgba=np.asarray((1, 0, 0, 1)))

# using a mojo.typing.MaterialName helps make sure when connecting this later on
material = mjcf.Material(name=mojot.MaterialName("material_name"))

mojo_model = mjcf.Mujoco(
    model=mojot.ModelName("hello"),
    worldbody=mjcf.WorldBody(
        geoms=[
            mjcf.GeomPlane(
                name=mojot.GeomName("floor"),
                size=np.asarray((5, 5, 0.1)),
                rgba=np.array((0.5, 0.5, 0.5, 1)),
                pos=mjcf.Pos(pos=np.array((1, 2, 3))),
                orientation=quat,
                material=material.name,  # static analyzer warns you if this is not MaterialName type
            ),
        ],
        bodies=[
            mjcf.Body(
                name=mojot.BodyName("robot"),
                geoms=[
                    sphere,
                    mjcf.GeomCylinder(
                        size=np.asarray((1, 3)),
                        rgba=np.asarray((1, 0, 0, 1)),
                    ),
                ],
            ),
        ],
    ),
    assets=[mjcf.Asset(materials=[material])],
    compilers=[mjcf.Compiler(balanceinertia=True)],
)


# =============== ensure it works with mujoco ===============
xml = mojo.utils.to_pretty_xml(mojo_model.to_xml(exclude_default=True))
save_as = Path(__file__).with_name("result_test_writer.xml")
save_as.write_text(xml)

model = mojo_model.to_mj_model()
mujoco_material_id = mujoco.mj_name2id(
    m=model, type=mujoco.mjtObj.mjOBJ_MATERIAL, name=material.name
)
mojo_material_id = material.get_id(model)
assert mujoco_material_id == mojo_material_id, (
    f"{mujoco_material_id=} did not equal {mojo_material_id=}. There may be an issue with the XMLModel.get_id method"
)

# =============== serialize and deserialize ===============
json_file = save_as.with_suffix(".json")

# quaternion (this is a discriminated type)
json_file.with_stem("quat").write_text(quat.model_dump_json(exclude_none=True))
assert "type" in quat.model_dump_json(exclude_none=True), (
    "Orientation type was not serialized"
)
quat = type(quat).model_validate_json(json_file.with_stem("quat").read_text())


json_file.with_stem("sphere").write_text(sphere.model_dump_json(exclude_none=True))
assert "type" in sphere.model_dump_json(exclude_none=True), (
    "geom type was not serialized"
)
sphere = type(sphere).model_validate_json(json_file.with_stem("sphere").read_text())


json_file.write_text(mojo_model.model_dump_json(exclude_none=True))
mojo_model = type(mojo_model).model_validate_json(json_file.read_text())
