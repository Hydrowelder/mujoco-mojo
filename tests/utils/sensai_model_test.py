"""Tests for the fallback model SensAI builds from `sensai.models`."""

from collections.abc import Sequence

import pytest
from pydantic import BaseModel
from pydantic_ai.messages import ModelResponse
from pydantic_ai.models import Model
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.profiles import ModelProfile

from mujoco_mojo.settings import (
    SensAIModelEntry,
    SensAISettings,
)
from mujoco_mojo.typing import ModelProvider
from mujoco_mojo.utils.sensai import model as sensai_model
from mujoco_mojo.utils.sensai.model import smallest_context_window


class _Settings(BaseModel):
    sensai: SensAISettings


def _use(monkeypatch: pytest.MonkeyPatch, sensai: SensAISettings) -> None:
    settings = _Settings(sensai=sensai)
    monkeypatch.setattr(sensai_model, "MujocoMojoSettings", lambda: settings)


def _urls(models: Sequence[Model]) -> list[str]:
    return [str(model.base_url).rstrip("/") for model in models]


def test_each_entry_is_sent_to_its_own_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two entries of one provider can point at different gateways."""
    monkeypatch.setenv("OPENAI_API_KEY", "key-123")
    _use(
        monkeypatch,
        SensAISettings(
            models=[
                SensAIModelEntry(
                    provider=ModelProvider.OPEN_AI,
                    model_name="gpt-5",
                    base_url="http://one.example/v1",
                ),
                SensAIModelEntry(
                    provider=ModelProvider.OPEN_AI,
                    model_name="gpt-5-mini",
                    base_url="http://two.example/v1",
                ),
            ]
        ),
    )

    fallback = sensai_model.build_fallback_model()

    assert _urls(fallback.models) == ["http://one.example/v1", "http://two.example/v1"]


def test_an_entry_without_a_base_url_keeps_its_providers_default_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "key-123")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    _use(
        monkeypatch,
        SensAISettings(
            models=[
                SensAIModelEntry(provider=ModelProvider.OPEN_AI, model_name="gpt-5")
            ],
        ),
    )

    fallback = sensai_model.build_fallback_model()

    assert _urls(fallback.models) == ["https://api.openai.com/v1"]


def test_ollama_takes_its_base_url_from_its_entry_like_any_other_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    _use(
        monkeypatch,
        SensAISettings(
            models=[
                SensAIModelEntry(
                    provider=ModelProvider.OLLAMA,
                    model_name="llama3.2",
                    base_url="http://localhost:11434/v1",
                ),
            ],
        ),
    )

    fallback = sensai_model.build_fallback_model()

    assert _urls(fallback.models) == ["http://localhost:11434/v1"]


def test_a_saved_shared_base_url_still_loads_and_warns_when_an_ollama_model_needs_one() -> (
    None
):
    """SensAI's shared `base_url` was removed, and `save()` wrote it into every settings file, so a file that still has it must load."""
    with pytest.warns(UserWarning, match="Set `base_url` on each Ollama model"):
        settings = SensAISettings.model_validate(
            {
                "base_url": "http://localhost:11434/v1",
                "models": [{"provider": "Ollama", "model_name": "llama3.2"}],
            }
        )

    assert [entry.base_url for entry in settings.models] == [None]
    assert "base_url" not in settings.model_dump()


def test_a_saved_shared_base_url_is_silent_when_nothing_needs_it() -> None:
    """Every Ollama model already has its own URL, and a model that isn't Ollama never used the shared one, so there is nothing to tell the user."""
    settings = SensAISettings.model_validate(
        {
            "base_url": "http://localhost:11434/v1",
            "models": [
                {
                    "provider": "Ollama",
                    "model_name": "llama3.2",
                    "base_url": "http://own.example/v1",
                },
                {"provider": "OpenAI", "model_name": "gpt-5"},
            ],
        }
    )

    assert [entry.base_url for entry in settings.models] == [
        "http://own.example/v1",
        None,
    ]


def test_a_shared_base_url_with_no_models_loads() -> None:
    assert SensAISettings.model_validate({"base_url": "http://x/v1"}).models == []


def _window_model(window: int | None) -> FunctionModel:
    """A model that knows its context window, or does not (`None`), as one served by Ollama usually does not."""
    profile = ModelProfile(context_window=window) if window is not None else None
    return FunctionModel(
        lambda _messages, _info: ModelResponse(parts=[]), profile=profile
    )


def _entry(context_window: int | None = None) -> SensAIModelEntry:
    return SensAIModelEntry(
        provider=ModelProvider.OLLAMA,
        model_name="llama3.1",
        context_window=context_window,
    )


def test_the_smallest_window_of_the_chain_is_the_one_to_fit() -> None:
    chain = FallbackModel(_window_model(1_000_000), _window_model(128_000))

    assert smallest_context_window([_entry(), _entry()], chain) == 128_000


def test_an_entrys_context_window_is_used_over_what_the_model_knows() -> None:
    chain = FallbackModel(_window_model(1_000_000), _window_model(None))

    assert smallest_context_window([_entry(), _entry(8192)], chain) == 8192
    assert smallest_context_window([_entry(500_000), _entry()], chain) == 500_000


def test_no_window_known_anywhere_is_none() -> None:
    chain = FallbackModel(_window_model(None), _window_model(None))

    assert smallest_context_window([_entry(), _entry()], chain) is None


def test_a_single_model_is_read_like_a_chain_of_one() -> None:
    assert smallest_context_window([], _window_model(4096)) == 4096
