from pathlib import Path

import mujoco
import pytest

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.accelerometer import (
    SensorAccelerometer,
)
from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.actuatorfrc import SensorActuatorfrc
from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.framequat import SensorFramequat
from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.jointpos import SensorJointpos
from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.magnetometer import SensorMagnetometer
from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.touch import SensorTouch
from mujoco_mojo.runtime.signal_manager import SignalManager
from mujoco_mojo.typing import (
    ActuatorName,
    BodyName,
    JointName,
    SensorName,
    SensorObjectType,
)
from mujoco_mojo.typing import SiteName as SiteNameType

_XML = """
<mujoco>
    <worldbody>
        <body name="b1">
            <joint name="h" type="hinge" axis="0 1 0"/>
            <geom name="g1" type="sphere" size="0.1"/>
            <site name="site1" size="0.05"/>
        </body>
        <body name="b2" pos="1 0 0">
            <joint name="s" type="slide" axis="1 0 0"/>
            <geom name="g2" type="sphere" size="0.1"/>
        </body>
    </worldbody>
    <actuator>
        <motor name="m1" joint="h"/>
    </actuator>
    <sensor>
        <touch name="tch" site="site1"/>
        <accelerometer name="acc" site="site1"/>
        <framequat name="fq" objtype="body" objname="b1"/>
        <jointpos name="jp_h" joint="h"/>
        <jointpos name="jp_s" joint="s"/>
        <actuatorfrc name="af" actuator="m1"/>
        <magnetometer name="mag" site="site1"/>
    </sensor>
</mujoco>
"""


@pytest.fixture
def state() -> MjState:
    model = mujoco.MjModel.from_xml_string(_XML)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    return MjState(model, data)


def test_touch_request_tags_force_metadata(state: MjState, tmp_path: Path) -> None:
    """A scalar sensor (touch) is tagged with the force dimension."""
    sensor = SensorTouch(name=SensorName("tch"), site=SiteNameType("site1"))
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    sensor.request(sm)
    sm.record(state)

    assert sm._column_metadata["Sensors/tch:touch"] == {
        "dimension": "[mass] * [length] / [time] ** 2"
    }


def test_accelerometer_request_tags_acceleration_metadata(
    state: MjState, tmp_path: Path
) -> None:
    """An xyzm sensor (accelerometer) is tagged with the acceleration dimension."""
    sensor = SensorAccelerometer(name=SensorName("acc"), site=SiteNameType("site1"))
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    sensor.request(sm)
    sm.record(state)

    assert sm._column_metadata["Sensors/acc/accelerometer:x"] == {
        "dimension": "[length] / [time] ** 2"
    }


def test_framequat_request_tags_dimensionless_metadata(
    state: MjState, tmp_path: Path
) -> None:
    """A quat sensor (framequat) is tagged as dimensionless."""
    sensor = SensorFramequat(
        name=SensorName("fq"),
        objtype=SensorObjectType.BODY,
        objname=BodyName("b1"),
        reftype=SensorObjectType.BODY,
        refname=BodyName("b1"),
    )
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    sensor.request(sm)
    sm.record(state)

    assert sm._column_metadata["Sensors/fq/framequat:w"] == {"dimension": "[]"}


def test_jointpos_request_resolves_hinge_to_angle_metadata(
    state: MjState, tmp_path: Path
) -> None:
    """Jointpos on a hinge joint resolves to concrete radian units."""
    sensor = SensorJointpos(name=SensorName("jp_h"), joint=JointName("h"))
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    sensor.request(sm)
    sm.record(state)

    assert sm._column_metadata["Sensors/jp_h:jointpos"] == {"units": "radian"}


def test_jointpos_request_resolves_slide_to_length_metadata(
    state: MjState, tmp_path: Path
) -> None:
    """Jointpos on a slide joint resolves to the scale-ambiguous length dimension."""
    sensor = SensorJointpos(name=SensorName("jp_s"), joint=JointName("s"))
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    sensor.request(sm)
    sm.record(state)

    assert sm._column_metadata["Sensors/jp_s:jointpos"] == {"dimension": "[length]"}


def test_actuatorfrc_request_resolves_transmission_to_torque_metadata(
    state: MjState, tmp_path: Path
) -> None:
    """Actuatorfrc on a hinge-driving actuator resolves to torque metadata."""
    sensor = SensorActuatorfrc(name=SensorName("af"), actuator=ActuatorName("m1"))
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    sensor.request(sm)
    sm.record(state)

    assert sm._column_metadata["Sensors/af:actuatorfrc"] == {
        "dimension": "[length] ** 2 * [mass] / [time] ** 2",
        "quantity": "torque",
    }


def test_magnetometer_request_has_no_builtin_default(
    state: MjState, tmp_path: Path
) -> None:
    """Magnetometer's unit is genuinely unspecified by MuJoCo, so no built-in default is applied."""
    sensor = SensorMagnetometer(name=SensorName("mag"), site=SiteNameType("site1"))
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    sensor.request(sm)
    sm.record(state)

    assert "Sensors/mag/magnetometer:x" not in sm._column_metadata


def test_request_metadata_override(state: MjState, tmp_path: Path) -> None:
    """A caller-supplied metadata dict extends the built-in default for the sensor's tag."""
    sensor = SensorTouch(name=SensorName("tch"), site=SiteNameType("site1"))
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    sensor.request(sm, metadata={"touch": {"display_name": "Touch Force"}})
    sm.record(state)

    assert sm._column_metadata["Sensors/tch:touch"] == {
        "dimension": "[mass] * [length] / [time] ** 2",
        "display_name": "Touch Force",
    }
