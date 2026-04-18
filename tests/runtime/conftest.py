import mujoco
import pytest

from mujoco_mojo.runtime.results_manager import SignalManager


@pytest.fixture
def mj_setup():
    """A minimal 1-body arena for high-speed integration testing."""
    xml = """
    <mujoco>
        <worldbody>
            <body name="body1" pos="0 0 0">
                <joint name="joint1" type="slide" axis="1 0 0"/>
                <geom type="sphere" size="0.1"/>
                <site name="site1" pos="0 0 0"/>
            </body>
        </worldbody>
        <actuator>
            <motor joint="joint1" name="test_motor"/>
        </actuator>
    </mujoco>
    """
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    return model, data


@pytest.fixture
def rm(tmp_path):
    """Isolated ResultsManager for testing."""
    db_path = tmp_path / "test_telemetry.parquet"
    return SignalManager(export_path=db_path)
