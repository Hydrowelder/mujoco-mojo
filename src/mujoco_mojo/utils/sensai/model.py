"""The model every SensAI agent runs on, and the cap on how many requests one question may send it."""

from __future__ import annotations

from google.genai import errors as google_errors
from pydantic_ai import ModelAPIError, UsageLimits
from pydantic_ai.models.fallback import FallbackModel

from mujoco_mojo.settings import MujocoMojoSettings


def build_fallback_model() -> FallbackModel:
    """
    Builds the `FallbackModel` shared by every SensAI agent from `SensAISettings.models`, in the priority order the user configured there - the first `(provider, model name)` pair is tried first, and each later one is only used if every earlier one errors.

    Each entry's `Model` comes from `ModelProvider.build_model`, which builds that entry's provider exactly as `Agent('provider:model')` would - reading whatever environment variable that provider looks for by default (see `ModelProvider.env_var_name`) - and sends its requests to the entry's own `base_url` when it has one. Every provider is treated alike, Ollama included: an entry with no `base_url` keeps its provider's own default endpoint.

    Raises:
        ValueError: If `SensAISettings.models` is empty - `FallbackModel` needs at least one model to try - or an entry sets a `base_url` its provider doesn't accept.

    """
    settings = MujocoMojoSettings().sensai
    if not settings.models:
        msg = "sensai.models is empty; configure at least one (provider, model name) pair."
        raise ValueError(msg)

    models = [
        entry.provider.build_model(entry.model_name, base_url=entry.base_url)
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


def usage_limits(max_requests: int) -> UsageLimits:
    """
    The cap on model requests for one question, to pass to the run that answers it and, in the Dojo, to each specialist's run, so that the specialists count against the same total (they share the run's `usage`).

    `max_requests` is `sensai.max_requests`. A request takes one to three (route it, edit, answer) and a refused edit adds one to three more, so the default of 12 leaves room to correct a mistake or two. When a model loops, or rate limits make every request cost several attempts, it is what stops the question from sending dozens.
    """
    return UsageLimits(request_limit=max_requests)
