import numpy as np
import pytest

from mujoco_mojo.mjcf import (
    Body,
    FreeJoint,
    GeomSphere,
    Mujoco,
    PoseQuat,
    Sensor,
    WorldBody,
)
from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.contact import SensorContact
from mujoco_mojo.typing import BodyName, ContactData, ContactReduce, GeomName

G1, G2 = GeomName("g1"), GeomName("g2")


def _sensor(
    data: tuple[ContactData, ...], reduce: ContactReduce = ContactReduce.NONE
) -> SensorContact:
    return SensorContact(geom1=G1, geom2=G2, num=2, data=data, reduce=reduce)


def test_contact_data_is_put_in_the_order_mujoco_requires() -> None:
    """MuJoCo rejects data listed out of order, so the sensor sorts what it is given."""
    sensor = _sensor(
        (
            ContactData.ANGVEL,
            ContactData.FOUND,
            ContactData.LINVEL,
            ContactData.TANGENT,
        )
    )

    assert sensor.data == (
        ContactData.FOUND,
        ContactData.TANGENT,
        ContactData.LINVEL,
        ContactData.ANGVEL,
    )


@pytest.mark.parametrize(
    "data",
    [
        (ContactData.LINVEL,),
        (ContactData.ANGVEL,),
        (ContactData.FOUND, ContactData.LINVEL, ContactData.ANGVEL),
    ],
)
def test_relative_velocities_cannot_be_combined_with_netforce(
    data: tuple[ContactData, ...],
) -> None:
    with pytest.raises(ValueError, match="netforce"):
        _sensor(data, ContactReduce.NETFORCE)


def test_netforce_is_still_allowed_for_the_other_data() -> None:
    sensor = _sensor((ContactData.FOUND, ContactData.FORCE), ContactReduce.NETFORCE)

    assert sensor.reduce == ContactReduce.NETFORCE


def test_relative_velocity_data_sizes_the_sensor_block_like_mujoco_does() -> None:
    """Each slot holds found (1), linvel (3) and angvel (3), and the sensor reports two slots."""
    ball = Body(name=BodyName("ball"))
    ball.freejoints.append(FreeJoint())
    ball.geoms.append(GeomSphere(name=G1, size=0.1))
    worldbody = WorldBody()
    worldbody.bodies.append(ball)
    worldbody.geoms.append(
        GeomSphere(name=G2, size=0.1, pose=PoseQuat(pos=np.array((0.0, 0.0, -0.15))))
    )
    sensor = _sensor((ContactData.FOUND, ContactData.LINVEL, ContactData.ANGVEL))

    mj_model = Mujoco(
        worldbody=worldbody, sensors=[Sensor(contacts=[sensor])]
    ).to_mj_model()

    assert mj_model.sensor_dim[0] == 2 * (1 + 3 + 3)
