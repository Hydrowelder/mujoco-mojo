"""Builds the fallback model shared by every SensAI agent."""

from __future__ import annotations

from google.genai import errors as google_errors
from pydantic_ai import ModelAPIError  # pyright: ignore[reportMissingImports]
from pydantic_ai.models.fallback import (
    FallbackModel,  # pyright: ignore[reportMissingImports]
)

from mujoco_mojo.settings import MujocoMojoSettings
from mujoco_mojo.typing import ModelProvider


def build_fallback_model() -> FallbackModel:
    """
    Builds the `FallbackModel` shared by every SensAI agent from `SensAISettings.models`, in the priority order the user configured there - the first `(provider, model name)` pair is tried first, and each later one is only used if every earlier one errors.

    Each entry's `Model` comes from `ModelProvider.build_model`, which builds that entry's provider exactly as `Agent('provider:model')` would - reading whatever environment variable that provider looks for by default (see `ModelProvider.env_var_name`) - except for an `OLLAMA` entry, which gets `SensAISettings.base_url` explicitly: unlike most providers, `pydantic_ai`'s `OllamaProvider` has no built-in `localhost` default and raises without one. Only `OLLAMA` gets this - passing it to a provider that also happens to accept `base_url` (e.g. Google) would silently redirect that provider's real endpoint to Ollama's URL instead.

    Raises:
        ValueError: If `SensAISettings.models` is empty - `FallbackModel` needs at least one model to try.

    """
    settings = MujocoMojoSettings().dojo.sensai
    if not settings.models:
        msg = "dojo.sensai.models is empty; configure at least one (provider, model name) pair."
        raise ValueError(msg)

    models = [
        entry.provider.build_model(
            entry.model_name,
            base_url=settings.base_url
            if entry.provider is ModelProvider.OLLAMA
            else None,
        )
        for entry in settings.models
    ]

    return FallbackModel(
        models[0],
        *models[1:],
        # pydantic-ai's Google model only wraps errors.APIError as ModelAPIError when
        # opening the connection, not when the first streamed chunk raises it (the actual
        # 503 case). Include the raw SDK error type too so streaming failures still fall back.
        # This only helps entries that are actually Google models - a non-Google-only
        # fallback chain gets no equivalent coverage for its own provider's raw SDK errors.
        fallback_on=(ModelAPIError, google_errors.APIError),
    )
