from pathlib import Path

import mujoco
import pytest

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.accelerometer import (
    SensorAccelerometer,
)
from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.actuatorfrc import SensorActuatorfrc
from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.ballangvel import SensorBallangvel
from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.framepos import SensorFramepos
from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.framequat import SensorFramequat
from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.insidesite import SensorInsidesite
from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.jointpos import SensorJointpos
from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.magnetometer import SensorMagnetometer
from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.subtreecom import SensorSubtreecom
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


_INSIDESITE_XML = """
<mujoco>
    <worldbody>
        <body name="b1">
            <geom name="g1" type="sphere" size="0.1"/>
            <site name="site1" type="sphere" size="0.5"/>
        </body>
        <body name="b2" pos="0.1 0 0">
            <geom name="g2" type="sphere" size="0.05"/>
        </body>
    </worldbody>
    <sensor>
        <insidesite name="flag" site="site1" objtype="body" objname="b2"/>
        <insidesite name="gap" site="site1" objtype="body" objname="b2" enclosed="true"/>
    </sensor>
</mujoco>
"""


@pytest.fixture
def insidesite_state() -> MjState:
    model = mujoco.MjModel.from_xml_string(_INSIDESITE_XML)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    return MjState(model, data)


def test_touch_request_tags_force_metadata(state: MjState, tmp_path: Path) -> None:
    """A scalar sensor (touch) is tagged with the force dimension."""
    sensor = SensorTouch(name=SensorName("tch"), site=SiteNameType("site1"))
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    sensor.request(sm)
    sm.record(state)

    assert sm._column_metadata["Sensors/tch:touch"].model_dump() == {
        "description": "Output of touch sensor tch on site site1",
        "dimension": "[mass] * [length] / [time] ** 2",
        "transform_type": "scalar",
    }


def test_accelerometer_request_tags_acceleration_metadata(
    state: MjState, tmp_path: Path
) -> None:
    """An xyzm sensor (accelerometer) is tagged with the acceleration dimension."""
    sensor = SensorAccelerometer(name=SensorName("acc"), site=SiteNameType("site1"))
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    sensor.request(sm)
    sm.record(state)

    assert sm._column_metadata["Sensors/acc/accelerometer:x"].model_dump() == {
        "description": "Output of accelerometer sensor acc on site site1, expressed in the frame of its site",
        "dimension": "[length] / [time] ** 2",
        "transform_type": "vector",
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

    assert sm._column_metadata["Sensors/fq/framequat:w"].model_dump() == {
        "description": "Output of framequat sensor fq on body b1, expressed in the world frame",
        "dimension": "[]",
        "transform_type": "quaternion",
    }


def test_insidesite_flag_is_labeled(insidesite_state: MjState, tmp_path: Path) -> None:
    """Without `enclosed` the sensor is a 0/1 flag, so its codes are labeled."""
    sensor = SensorInsidesite(
        name=SensorName("flag"),
        objtype=SensorObjectType.BODY,
        objname=BodyName("b2"),
        site=SiteNameType("site1"),
    )
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    sensor.request(sm)
    sm.record(insidesite_state)

    assert sm._column_metadata["Sensors/flag:insidesite"].model_dump() == {
        "description": "Output of insidesite sensor flag on body b2",
        "dimension": "[]",
        "transform_type": "scalar",
        "enumeration_map": {"OUTSIDE": 0, "INSIDE": 1},
    }


def test_insidesite_enclosed_is_not_labeled(
    insidesite_state: MjState, tmp_path: Path
) -> None:
    """With `enclosed` the sensor reports a distance, not a flag, so no labels apply."""
    sensor = SensorInsidesite(
        name=SensorName("gap"),
        objtype=SensorObjectType.BODY,
        objname=BodyName("b2"),
        site=SiteNameType("site1"),
        enclosed=True,
    )
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    sensor.request(sm)
    sm.record(insidesite_state)

    assert sm._column_metadata["Sensors/gap:insidesite"].enumeration_map is None


def test_jointpos_request_resolves_hinge_to_angle_metadata(
    state: MjState, tmp_path: Path
) -> None:
    """Jointpos on a hinge joint resolves to concrete radian unit."""
    sensor = SensorJointpos(name=SensorName("jp_h"), joint=JointName("h"))
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    sensor.request(sm)
    sm.record(state)

    assert sm._column_metadata["Sensors/jp_h:jointpos"].model_dump() == {
        "description": "Output of jointpos sensor jp_h on joint h",
        "unit": "radian",
    }


def test_jointpos_request_resolves_slide_to_length_metadata(
    state: MjState, tmp_path: Path
) -> None:
    """Jointpos on a slide joint resolves to the scale-ambiguous length dimension."""
    sensor = SensorJointpos(name=SensorName("jp_s"), joint=JointName("s"))
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    sensor.request(sm)
    sm.record(state)

    assert sm._column_metadata["Sensors/jp_s:jointpos"].model_dump() == {
        "description": "Output of jointpos sensor jp_s on joint s",
        "dimension": "[length]",
    }


def test_actuatorfrc_request_resolves_transmission_to_torque_metadata(
    state: MjState, tmp_path: Path
) -> None:
    """Actuatorfrc on a hinge-driving actuator resolves to torque metadata."""
    sensor = SensorActuatorfrc(name=SensorName("af"), actuator=ActuatorName("m1"))
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    sensor.request(sm)
    sm.record(state)

    assert sm._column_metadata["Sensors/af:actuatorfrc"].model_dump() == {
        "description": "Output of actuatorfrc sensor af on actuator m1",
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

    assert sm._column_metadata["Sensors/mag/magnetometer:x"].model_dump() == {
        "description": "Output of magnetometer sensor mag on site site1, expressed in the frame of its site"
    }


def test_request_metadata_override(state: MjState, tmp_path: Path) -> None:
    """A caller-supplied metadata dict extends the built-in default for the sensor's tag."""
    sensor = SensorTouch(name=SensorName("tch"), site=SiteNameType("site1"))
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    sensor.request(sm, metadata={"touch": {"display_name": "Touch Force"}})
    sm.record(state)

    assert sm._column_metadata["Sensors/tch:touch"].model_dump() == {
        "description": "Output of touch sensor tch on site site1",
        "dimension": "[mass] * [length] / [time] ** 2",
        "transform_type": "scalar",
        "display_name": "Touch Force",
    }


_FRAMES_XML = """
<mujoco>
    <worldbody>
        <body name="b1">
            <joint name="ball" type="ball"/>
            <geom type="sphere" size="0.1"/>
        </body>
        <body name="b2" pos="1 0 0">
            <geom type="sphere" size="0.1"/>
        </body>
    </worldbody>
    <sensor>
        <framepos name="fp_world" objtype="body" objname="b1"/>
        <framepos name="fp_ref" objtype="body" objname="b1" reftype="body" refname="b2"/>
        <subtreecom name="com" body="b1"/>
        <ballangvel name="bav" joint="ball"/>
    </sensor>
</mujoco>
"""


def test_sensor_description_names_the_frame_the_output_is_expressed_in(
    tmp_path: Path,
) -> None:
    """A frame sensor names its reference object, or the world frame when it has none; some tags have a fixed frame."""
    model = mujoco.MjModel.from_xml_string(_FRAMES_XML)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    state = MjState(model, data)
    sm = SignalManager(export_path=tmp_path / "tel.parquet")

    for sensor in (
        SensorFramepos(
            name=SensorName("fp_world"),
            objtype=SensorObjectType.BODY,
            objname=BodyName("b1"),
            reftype=SensorObjectType.BODY,
        ),
        SensorFramepos(
            name=SensorName("fp_ref"),
            objtype=SensorObjectType.BODY,
            objname=BodyName("b1"),
            reftype=SensorObjectType.BODY,
            refname=BodyName("b2"),
        ),
        SensorSubtreecom(name=SensorName("com"), body=BodyName("b1")),
        SensorBallangvel(name=SensorName("bav"), joint=JointName("ball")),
    ):
        sensor.request(sm)
    sm.record(state)

    described = {name: m.description for name, m in sm._column_metadata.items()}
    assert (
        described["Sensors/fp_world/framepos:x"]
        == "Output of framepos sensor fp_world on body b1, expressed in the world frame"
    )
    assert (
        described["Sensors/fp_ref/framepos:x"]
        == "Output of framepos sensor fp_ref on body b1, expressed in the frame of body b2"
    )
    assert (
        described["Sensors/com/subtreecom:x"]
        == "Output of subtreecom sensor com on body b1, expressed in the world frame"
    )
    assert (
        described["Sensors/bav/ballangvel:x"]
        == "Output of ballangvel sensor bav on joint ball, expressed in the local frame of its body"
    )
