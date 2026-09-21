"""Writer agreement: every column the built-in `request()` methods emit parses back to the same parts through `Column`, so the writer and the readers cannot drift apart."""

from pathlib import Path
from typing import Any

import mujoco
import pytest

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.motor import ActuatorMotor
from mujoco_mojo.mjcf.mujoco_attr.body import Body
from mujoco_mojo.mjcf.mujoco_attr.body_attr.geom import GeomSphere
from mujoco_mojo.mjcf.mujoco_attr.body_attr.joint import Joint
from mujoco_mojo.mjcf.mujoco_attr.body_attr.site import SiteSphere
from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.accelerometer import (
    SensorAccelerometer,
)
from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.framequat import SensorFramequat
from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.jointpos import SensorJointpos
from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.touch import SensorTouch
from mujoco_mojo.runtime.signal_manager import SignalManager
from mujoco_mojo.typing import (
    ActuatorName,
    BodyName,
    GeomName,
    JointName,
    SensorName,
    SensorObjectType,
    SiteName,
)
from mujoco_mojo.utils.column import Column

_XML = """
<mujoco>
    <worldbody>
        <body name="box" pos="0 0 1">
            <freejoint name="root"/>
            <geom name="g1" type="sphere" size="0.1" mass="2"/>
            <site name="site1" size="0.05"/>
        </body>
        <body name="arm" pos="1 0 1">
            <joint name="elbow" type="hinge" axis="0 1 0"/>
            <geom name="g2" type="capsule" size="0.05" fromto="0 0 0 0.3 0 0"/>
        </body>
        <body name="ball" pos="2 0 1">
            <joint name="socket" type="ball"/>
            <geom name="g3" type="sphere" size="0.05"/>
        </body>
        <body name="cart" pos="3 0 1">
            <joint name="rail" type="slide" axis="1 0 0"/>
            <geom name="g4" type="box" size="0.1 0.1 0.1"/>
        </body>
    </worldbody>
    <actuator>
        <motor name="drive" joint="elbow"/>
    </actuator>
    <sensor>
        <touch name="tch" site="site1"/>
        <accelerometer name="acc" site="site1"/>
        <framequat name="fq" objtype="body" objname="box"/>
        <jointpos name="jp" joint="elbow"/>
    </sensor>
</mujoco>
"""


@pytest.fixture
def state() -> MjState:
    model = mujoco.MjModel.from_xml_string(_XML)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    return MjState(model, data)


def _requesters() -> list[Any]:
    """One object per built-in `request()` family: a body, site, geom, every joint kind, an actuator, and several sensors."""
    return [
        Body(name=BodyName("box")),
        SiteSphere(name=SiteName("site1"), size=0.05),
        GeomSphere(name=GeomName("g1"), size=0.1),
        Joint(name=JointName("root")),
        Joint(name=JointName("elbow")),
        Joint(name=JointName("socket")),
        Joint(name=JointName("rail")),
        ActuatorMotor(name=ActuatorName("drive"), joint=JointName("elbow")),
        SensorTouch(name=SensorName("tch"), site=SiteName("site1")),
        SensorAccelerometer(name=SensorName("acc"), site=SiteName("site1")),
        SensorFramequat(
            name=SensorName("fq"),
            objtype=SensorObjectType.BODY,
            objname=BodyName("box"),
            reftype=SensorObjectType.BODY,
            refname=BodyName("box"),
        ),
        SensorJointpos(name=SensorName("jp"), joint=JointName("elbow")),
    ]


def test_every_emitted_column_parses_back_unchanged(
    state: MjState, tmp_path: Path
) -> None:
    sm = SignalManager(export_path=tmp_path / "tel.parquet")
    for requester in _requesters():
        requester.get_id(state.model)
        requester.request(sm)
    sm.record(state)

    # guards against the loop below passing vacuously
    categories = {column.category for column in sm._columns.values()}
    assert {"Bodies", "Sites", "Geoms", "Joints", "Sensors", "Actuators"} <= categories
    assert len(sm._columns) > 100

    assert set(sm._columns) == set(sm._key_to_idx)
    for name, column in sm._columns.items():
        parsed = Column.parse(name)
        assert str(parsed) == name
        assert (parsed.category, parsed.subgroups, parsed.attr) == (
            column.category,
            column.subgroups,
            column.attr,
        )
