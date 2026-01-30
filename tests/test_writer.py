from pathlib import Path

import numpy as np

import mujoco_mojo as mojo


def test_import():
    import mujoco_mojo as mojo

    mojo.__name__


floor = mojo.GeomPlane(
    name="floor",
    size=np.asarray((5, 5, 0.1)),
    rgba=np.array((0.5, 0.5, 0.5, 1)),
)

robot = mojo.Body(
    name="robot",
    geoms=[
        mojo.GeomSphere(
            size=0.2,
            rgba=np.asarray((1, 0, 0, 1)),
        ),
    ],
)

world = mojo.WorldBody(geoms=[floor], bodies=[robot])

model = mojo.Mujoco(
    worldbody=world, model="hello", compilers=[mojo.Compiler(balanceinertia=True)]
)

xml = mojo.to_pretty_xml(model.to_xml())

save_as = Path(__file__).with_name("result_test_writer.xml")
save_as.write_text(xml)
