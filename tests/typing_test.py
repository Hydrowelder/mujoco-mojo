import importlib.util
import sys

import pytest

from mujoco_mojo.settings import GenerateJsonSchemaWithDefaults, MujocoMojoSettings
from mujoco_mojo.typing import ModelProvider


def test_env_var_name_is_none_when_pydantic_ai_is_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`pydantic_ai` is an optional dependency, so looking up a provider's env var must degrade to `None`, not raise."""
    monkeypatch.setitem(sys.modules, "pydantic_ai", None)

    assert all(member.env_var_name is None for member in ModelProvider)


def test_settings_schema_builds_when_pydantic_ai_is_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The settings schema (written whenever settings are saved) describes each provider's env var, which must not require `pydantic_ai`."""
    monkeypatch.setitem(sys.modules, "pydantic_ai", None)

    schema = MujocoMojoSettings.model_json_schema(
        schema_generator=GenerateJsonSchemaWithDefaults
    )

    assert schema["properties"]


def test_env_var_name_reads_the_provider_source_when_pydantic_ai_is_installed() -> None:
    if importlib.util.find_spec("pydantic_ai") is None:
        pytest.skip("pydantic_ai is not installed")

    assert ModelProvider.OPEN_AI.env_var_name == "OPENAI_API_KEY"
    # OpenAI Codex uses an OAuth device-code flow instead of a single env var
    assert ModelProvider.OPEN_AI_CODEX.env_var_name is None
