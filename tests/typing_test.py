import importlib.util
import sys
from typing import TYPE_CHECKING

import pytest

from mujoco_mojo.settings import GenerateJsonSchemaWithDefaults, MujocoMojoSettings
from mujoco_mojo.typing import ModelProvider

if TYPE_CHECKING:
    from anthropic import AsyncAnthropic
    from pydantic_ai.models import Model


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


@pytest.fixture
def no_provider_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """The Anthropic and OpenAI settings a developer's shell may have, cleared so a test sets exactly what it checks."""
    pytest.importorskip("pydantic_ai")
    for name in (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def _anthropic_client(model: "Model") -> "AsyncAnthropic":
    from anthropic import AsyncAnthropic
    from pydantic_ai.models.anthropic import AnthropicModel

    assert isinstance(model, AnthropicModel)
    assert isinstance(model.client, AsyncAnthropic)
    return model.client


def test_anthropic_authenticates_with_a_bearer_token_when_only_the_token_is_set(
    no_provider_env: pytest.MonkeyPatch,
) -> None:
    """`pydantic_ai`'s own provider raises without `ANTHROPIC_API_KEY` and never reads `ANTHROPIC_AUTH_TOKEN`, so a gateway that wants a bearer token was unreachable."""
    no_provider_env.setenv("ANTHROPIC_AUTH_TOKEN", "tok-123")

    model = ModelProvider.ANTHROPIC.build_model(
        "claude-sonnet-5-5", base_url="http://gateway.example"
    )

    assert str(model.base_url).rstrip("/") == "http://gateway.example"
    client = _anthropic_client(model)
    assert client.auth_token == "tok-123"
    assert client.api_key is None


def test_anthropic_bearer_token_follows_anthropic_base_url_without_an_entry_url(
    no_provider_env: pytest.MonkeyPatch,
) -> None:
    no_provider_env.setenv("ANTHROPIC_AUTH_TOKEN", "tok-123")
    no_provider_env.setenv("ANTHROPIC_BASE_URL", "http://from-env.example")

    model = ModelProvider.ANTHROPIC.build_model("claude-sonnet-5-5")

    assert str(model.base_url).rstrip("/") == "http://from-env.example"


def test_anthropic_api_key_still_wins_when_a_token_is_also_set(
    no_provider_env: pytest.MonkeyPatch,
) -> None:
    """A setup that works with a key today must not change because a token also happens to be in the environment."""
    no_provider_env.setenv("ANTHROPIC_API_KEY", "key-123")
    no_provider_env.setenv("ANTHROPIC_AUTH_TOKEN", "tok-123")

    model = ModelProvider.ANTHROPIC.build_model("claude-sonnet-5-5")

    client = _anthropic_client(model)
    assert client.api_key == "key-123"
    assert client.auth_token is None


def test_anthropic_without_any_credential_still_raises(
    no_provider_env: pytest.MonkeyPatch,
) -> None:
    from pydantic_ai.exceptions import UserError

    with pytest.raises(UserError, match="ANTHROPIC_API_KEY"):
        ModelProvider.ANTHROPIC.build_model("claude-sonnet-5-5")


def test_base_url_reaches_a_provider_that_accepts_one(
    no_provider_env: pytest.MonkeyPatch,
) -> None:
    no_provider_env.setenv("OPENAI_API_KEY", "key-123")

    model = ModelProvider.OPEN_AI.build_model(
        "gpt-5", base_url="http://gateway.example/v1"
    )

    assert str(model.base_url).rstrip("/") == "http://gateway.example/v1"


def test_base_url_for_a_provider_that_cannot_take_one_is_an_error_not_ignored(
    no_provider_env: pytest.MonkeyPatch,
) -> None:
    """Ignoring it would send the request to the provider's real endpoint, not the one the user asked for."""
    no_provider_env.setenv("CEREBRAS_API_KEY", "key-123")

    with pytest.raises(ValueError, match="base_url"):
        ModelProvider.CEREBRAS.build_model(
            "llama3.1-8b", base_url="http://gateway.example/v1"
        )
