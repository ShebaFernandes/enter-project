from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True)
class AITracingConfiguration:
    enabled: bool
    project: str
    include_prompt_bodies: bool = False


def tracing_configuration() -> AITracingConfiguration:
    production = settings.ENV.app_env == "production"
    explicitly_enabled = os.getenv("LANGSMITH_TRACING", "false").casefold() == "true"
    deidentified_only = os.getenv("LANGSMITH_DEIDENTIFIED_ONLY", "false").casefold() == "true"
    return AITracingConfiguration(
        enabled=bool(not production and explicitly_enabled and deidentified_only),
        project=os.getenv("LANGSMITH_PROJECT", "enter-synthetic-search-evals"),
        include_prompt_bodies=False,
    )


def redacted_trace_metadata(prompt: str, *, schema_version: str, result: str) -> dict[str, str]:
    return {
        "input_hash": hashlib.sha256(prompt.encode()).hexdigest(),
        "schema_version": schema_version,
        "result": result,
        "data_classification": "SYNTHETIC_OR_IRREVERSIBLY_DEIDENTIFIED_ONLY",
    }
