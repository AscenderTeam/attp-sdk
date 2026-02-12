from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from collections import deque
from typing import Any, Mapping, MutableMapping, Sequence

from attp.server.abc.auth_strategy import AuthStrategy
from attp.shared.secrets import SecretRef, parse_secret_ref


class ReplayCache:
    def __init__(self, ttl_seconds: int, *, max_entries: int = 10_000) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._entries: MutableMapping[str, int] = {}
        self._order: deque[tuple[int, str]] = deque()

    def _prune(self, now: int) -> None:
        cutoff = now - self.ttl_seconds
        while self._order and (
            self._order[0][0] < cutoff or len(self._entries) > self.max_entries
        ):
            ts, key = self._order.popleft()
            if self._entries.get(key) == ts:
                del self._entries[key]

    def seen(self, key: str, now: int) -> bool:
        self._prune(now)
        return key in self._entries

    def add(self, key: str, now: int) -> None:
        self._entries[key] = now
        self._order.append((now, key))
        self._prune(now)


class HmacAuthStrategy(AuthStrategy):
    def __init__(
        self,
        *,
        secret: str | SecretRef | Mapping[str, Any],
        keyring: Mapping[str, str | SecretRef | Mapping[str, Any]] | None = None,
        ttl_seconds: int = 30,
        max_clock_skew: int = 5,
        allowed_namespaces: Sequence[str] | None = None,
        allowed_nodes: Sequence[str] | None = None,
        max_replay_entries: int = 10_000,
    ) -> None:
        super().__init__()
        self._default_secret = parse_secret_ref(secret)
        if self._default_secret is None:
            raise TypeError("secret must be a string or secret reference.")

        self._keyring: dict[str, SecretRef] = {}
        if keyring:
            for key_id, value in keyring.items():
                ref = parse_secret_ref(value)
                if ref is None:
                    raise TypeError(f"Invalid secret ref for key id '{key_id}'.")
                self._keyring[key_id] = ref

        self.ttl_seconds = ttl_seconds
        self.max_clock_skew = max_clock_skew
        self.allowed_namespaces = set(allowed_namespaces or [])
        self.allowed_nodes = set(allowed_nodes or [])
        self.replay_cache = ReplayCache(ttl_seconds + max_clock_skew, max_entries=max_replay_entries)
        self.AUTH_TIMEOUT = float(ttl_seconds + max_clock_skew + 5)

    def _resolve_secret(self, kid: str | None) -> str:
        if kid and kid in self._keyring:
            return self._keyring[kid].resolve()
        return self._default_secret.resolve() # type: ignore

    def _expected_sig(self, namespace: str, node_id: str, ts: int, nonce: str, secret: str) -> str:
        message = f"{namespace}:{node_id}:{ts}:{nonce}".encode("utf-8")
        return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

    async def authenticate(self, namespace: str, frame: Any) -> bool:
        debug = os.getenv("ATTP_AUTH_DEBUG") == "1"
        logger = logging.getLogger("attp.auth")

        if self.allowed_namespaces and namespace not in self.allowed_namespaces:
            if debug:
                logger.info("Auth failed: namespace %s not allowed", namespace)
            return False

        if not isinstance(frame, Mapping):
            if debug:
                logger.info("Auth failed: frame not mapping (%s)", type(frame))
            return False

        def _get(key: str):
            if key in frame:
                return frame[key]
            bkey = key.encode()
            if bkey in frame:
                return frame[bkey]
            return None

        def _to_str(value: Any) -> str | None:
            if value is None:
                return None
            if isinstance(value, str):
                return value
            if isinstance(value, (bytes, bytearray)):
                return bytes(value).decode("utf-8", errors="ignore")
            return str(value)

        try:
            ts_val = _get("ts")
            if isinstance(ts_val, (bytes, bytearray)):
                ts_val = _to_str(ts_val)
            ts = int(ts_val)
        except Exception:
            if debug:
                logger.info("Auth failed: invalid timestamp in frame %s", frame)
            return False

        nonce = _to_str(_get("nonce"))
        sig = _to_str(_get("sig"))
        node_id = _to_str(_get("node_id"))
        if not nonce or not sig or not node_id:
            if debug:
                logger.info("Auth failed: missing nonce/sig/node_id in frame %s", frame)
            return False

        if self.allowed_nodes and node_id not in self.allowed_nodes:
            if debug:
                logger.info("Auth failed: node_id %s not allowed", node_id)
            return False

        now = int(time.time())
        if abs(now - ts) > (self.ttl_seconds + self.max_clock_skew):
            if debug:
                logger.info("Auth failed: timestamp skew too large ts=%s now=%s", ts, now)
            return False

        replay_key = f"{namespace}:{node_id}:{nonce}"
        if self.replay_cache.seen(replay_key, now):
            if debug:
                logger.info("Auth failed: replay detected %s", replay_key)
            return False

        kid = _to_str(_get("kid"))
        secret = self._resolve_secret(kid if kid else None)
        expected = self._expected_sig(namespace, node_id, ts, nonce, secret)
        if not hmac.compare_digest(sig, expected):
            if debug:
                logger.info(
                    "Auth failed: signature mismatch got=%s expected=%s frame=%s",
                    sig,
                    expected,
                    frame,
                )
            return False

        self.replay_cache.add(replay_key, now)
        return True
