from pathlib import Path

import mujoco_mojo as mojo

floor = mojo.Geom(
    name="floor",
    type=mojo.GeomType.PLANE,
    size=(5, 5, 0.1),
    rgba=(0.5, 0.5, 0.5, 1),
)

robot = mojo.Body(
    name="robot",
    geoms=[
        mojo.Geom(
            type=mojo.GeomType.SPHERE,
            size=0.2,
            rgba=(1, 0, 0, 1),
        ),
    ],
)

world = mojo.WorldBody(geoms=[floor], bodies=[robot])

model = mojo.Mujoco(worldbody=world, model="hello")

xml = mojo.to_pretty_xml(model.to_xml())

save_as = Path(__file__).with_name("result_test_writer.xml")
save_as.write_text(xml)
