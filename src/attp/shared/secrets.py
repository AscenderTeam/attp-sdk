from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


@dataclass(slots=True)
class SecretRef:
    env: str | None = None
    file: str | None = None
    value: str | None = None
    _cached: str | None = field(default=None, init=False, repr=False)

    def resolve(self) -> str:
        if self._cached is not None:
            return self._cached

        if self.value is not None:
            self._cached = self.value
            return self._cached

        if self.env:
            secret = os.getenv(self.env)
            if secret is None:
                raise ValueError(f"Secret env var '{self.env}' is not set.")
            self._cached = secret
            return self._cached

        if self.file:
            secret = Path(self.file).expanduser().read_text(encoding="utf-8").strip()
            if not secret:
                raise ValueError(f"Secret file '{self.file}' is empty.")
            self._cached = secret
            return self._cached

        raise ValueError("SecretRef has no source (env/file/value).")


def parse_secret_ref(value: Any) -> SecretRef | None:
    if value is None:
        return None

    if isinstance(value, SecretRef):
        return value

    if isinstance(value, str):
        if value.startswith("env:"):
            return SecretRef(env=value[4:])
        if value.startswith("file:"):
            return SecretRef(file=value[5:])
        if value.startswith("value:"):
            return SecretRef(value=value[6:])
        if value.startswith("${") and value.endswith("}"):
            return SecretRef(env=value[2:-1])
        return SecretRef(value=value)

    if isinstance(value, Mapping):
        env = value.get("env")
        file = value.get("file")
        val = value.get("value")
        if env is not None or file is not None or val is not None:
            return SecretRef(env=env, file=file, value=val)

    return None


def resolve_secret_if_ref(value: Any) -> Any:
    ref = parse_secret_ref(value)
    if ref is None:
        return value
    return ref.resolve()
