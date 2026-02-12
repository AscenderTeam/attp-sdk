from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ascender.core.di.interface.provider import Provider

from attp.client.authenticator import ConnectionAuthenticator, HmacConnectionAuthenticator
from attp.client.configs import AttpClientConfigs, ServiceDiscoveryConfigs
from attp.client.service_discovery import ServiceDiscovery
from attp.loadbalancer.abc.cacher import StrategyCacher
from attp.loadbalancer.abc.strategy import BalancingStrategy
from attp.loadbalancer.balancer import AttpLoadBalancer
from attp.loadbalancer.caches.memory_cache import SimpleInMemoryCacher
from attp.loadbalancer.configs import BalancerConfigs
from attp.loadbalancer.strategies.round_robin import BasicRoundRobinStrategy
from attp.server.abc.auth_strategy import AuthStrategy
from attp.server.attp_server import AttpServer
from attp.server.configs import AttpServerConfigs
from attp.shared.limits import AttpLimits
from attp.shared.namespaces.dispatcher import NamespaceDispatcher
from attp.shared.namespaces.router import AttpRouter
from attp.shared.objects.dispatcher import AttpFrameDispatcher
from attp.shared.objects.eventbus import EventBus
from attp.shared.transmitter import AttpTransmitter


DEFAULT_CONFIG_FILES = ("attp.json", "attp.jsonc")


def _strip_json_comments(raw: str) -> str:
    result: list[str] = []
    i = 0
    in_string = False
    string_char = ""
    escape = False

    while i < len(raw):
        ch = raw[i]

        if in_string:
            result.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == string_char:
                in_string = False
            i += 1
            continue

        if ch in ("\"", "'"):
            in_string = True
            string_char = ch
            result.append(ch)
            i += 1
            continue

        if ch == "/" and i + 1 < len(raw):
            nxt = raw[i + 1]
            if nxt == "/":
                i += 2
                while i < len(raw) and raw[i] not in ("\n", "\r"):
                    i += 1
                continue
            if nxt == "*":
                i += 2
                while i + 1 < len(raw) and not (raw[i] == "*" and raw[i + 1] == "/"):
                    i += 1
                i += 2
                continue

        result.append(ch)
        i += 1

    return "".join(result)


def _load_config_from_path(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return json.loads(_strip_json_comments(raw))


def _resolve_config_path(
    *,
    config_path: str | Path | None,
    config_dir: str | Path | None,
) -> Path:
    base_dir = Path(config_dir) if config_dir else Path.cwd()

    if config_path is not None:
        path = Path(config_path)
        if not path.is_absolute():
            path = base_dir / path
        if not path.exists():
            raise FileNotFoundError(f"ATTP config not found: {path}")
        return path

    for name in DEFAULT_CONFIG_FILES:
        candidate = base_dir / name
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        f"No ATTP config found in {base_dir}. Looked for {', '.join(DEFAULT_CONFIG_FILES)}."
    )


def _coerce_limits(value: Any) -> AttpLimits | None:
    if value is None:
        return None
    if isinstance(value, AttpLimits):
        return value
    if isinstance(value, int):
        return AttpLimits(max_payload_size=value)
    if isinstance(value, Mapping):
        return AttpLimits(**value)
    raise TypeError(f"Unsupported limits value: {value!r}")


def _parse_bind(bind: Any, *, default_host: str, default_port: int) -> tuple[str, int]:
    if bind is None:
        return default_host, default_port
    if isinstance(bind, Mapping):
        host = bind.get("host", default_host)
        port = bind.get("port", default_port)
        return str(host), int(port)
    if not isinstance(bind, str):
        raise TypeError(f"Invalid bind value: {bind!r}")

    if ":" not in bind:
        return bind, default_port
    host, port_str = bind.rsplit(":", 1)
    return host, int(port_str)


def _coerce_peer(peer: Any) -> str | AttpClientConfigs:
    if isinstance(peer, AttpClientConfigs):
        return peer
    if isinstance(peer, str):
        return peer
    if isinstance(peer, Mapping):
        data = dict(peer)
        if "remote_uri" not in data:
            if "uri" in data:
                data["remote_uri"] = data.pop("uri")
            elif "url" in data:
                data["remote_uri"] = data.pop("url")
        if "remote_uri" not in data:
            raise ValueError(f"Peer config missing remote_uri: {data}")
        return AttpClientConfigs(**data)
    raise TypeError(f"Unsupported peer entry: {peer!r}")


def _coerce_auth_strategy(auth_strategy: AuthStrategy | type[AuthStrategy]) -> AuthStrategy:
    if isinstance(auth_strategy, AuthStrategy):
        return auth_strategy
    if isinstance(auth_strategy, type) and issubclass(auth_strategy, AuthStrategy):
        try:
            return auth_strategy()
        except Exception as exc:  # pragma: no cover - defensive
            raise TypeError("AuthStrategy class must be instantiable with no args.") from exc
    raise TypeError("auth_strategy must be an AuthStrategy instance or subclass.")


def provideAttp(  # noqa: N802 - keep Ascender-style naming
    *,
    auth_strategy: AuthStrategy | type[AuthStrategy],
    connection_authenticator: (
        ConnectionAuthenticator
        | type[ConnectionAuthenticator]
        | Callable[[AttpClientConfigs], ConnectionAuthenticator]
        | None
    ) = None,
    balancing_strategies: Sequence[type[BalancingStrategy]] | None = None,
    balancing_cacher: StrategyCacher | None = None,
    config_path: str | Path | None = None,
    config_dir: str | Path | None = None,
    config: Mapping[str, Any] | None = None,
    default_limits: AttpLimits | Mapping[str, Any] | int | None = None,
    server_limits: AttpLimits | Mapping[str, Any] | int | None = None,
    client_limits: AttpLimits | Mapping[str, Any] | int | None = None,
    logger: Any | None = None,
) -> list[Provider]:
    """
    Provide ATTP-related dependencies from `attp.json` / `attp.jsonc`.
    Manual params are required for dynamic pieces like AuthStrategy and ConnectionAuthenticator.
    """
    if config is None:
        path = _resolve_config_path(config_path=config_path, config_dir=config_dir)
        config = _load_config_from_path(path)
    if not isinstance(config, Mapping):
        raise TypeError("config must be a mapping.")

    node_cfg = dict(config.get("node", {}) or {})
    server_cfg = dict(config.get("server", {}) or {})
    client_cfg = dict(config.get("client", {}) or {})
    services_cfg = dict(config.get("services", {}) or {})

    bind = server_cfg.get("bind") or node_cfg.get("bind") or config.get("bind")
    host, port = _parse_bind(bind, default_host="0.0.0.0", default_port=6563)

    raw_server_limits = server_limits or server_cfg.get("limits") or config.get("limits") or default_limits
    raw_client_limits = client_limits or client_cfg.get("limits") or config.get("limits") or default_limits

    resolved_server_limits = _coerce_limits(raw_server_limits)
    resolved_client_limits = _coerce_limits(raw_client_limits)

    if not resolved_server_limits or not resolved_client_limits:
        raise ValueError(
            "Missing limits configuration. Provide `default_limits` or per-side limits "
            "via config or function arguments."
        )

    auth_strategy_instance = _coerce_auth_strategy(auth_strategy)

    balancer_cfg = dict(services_cfg.get("balancer", {}) or {})
    balancing_strategy = (
        balancer_cfg.get("strategy")
        or config.get("balancer_strategy")
        or "round-robin"
    )
    strategy_parameters = balancer_cfg.get("strategy_parameters") or balancer_cfg.get("params")

    balancer_configs = BalancerConfigs(
        balancing_strategy=balancing_strategy,
        strategy_parameters=strategy_parameters,
    )

    peers_raw = services_cfg.get("peers") or config.get("peers") or []
    if isinstance(peers_raw, (str, Mapping)):
        peers_raw = [peers_raw]
    peers = [_coerce_peer(peer) for peer in peers_raw]

    if connection_authenticator is None:
        auth_cfg = client_cfg.get("auth") or services_cfg.get("auth")
        if isinstance(auth_cfg, Mapping):
            mode = str(auth_cfg.get("mode", "hmac")).lower()
            if mode != "hmac":
                raise ValueError(f"Unsupported client auth mode: {mode}")

            default_secret = auth_cfg.get("secret") or auth_cfg.get("shared_secret")
            if default_secret is None:
                raise ValueError("Client auth mode=hmac requires `secret` or `shared_secret`.")

            node_id = auth_cfg.get("node_id") or node_cfg.get("name")
            key_id = auth_cfg.get("key_id") or auth_cfg.get("kid")
            ttl_seconds = int(auth_cfg.get("ttl_seconds", auth_cfg.get("ttl", 30)))
            max_clock_skew = int(auth_cfg.get("max_clock_skew", auth_cfg.get("skew", 5)))

            def _auth_factory(peer: AttpClientConfigs) -> ConnectionAuthenticator:
                peer_auth = peer.auth if isinstance(peer.auth, Mapping) else {}
                peer_secret = (
                    peer_auth.get("secret")
                    or peer_auth.get("shared_secret")
                    or peer.authorization
                    or default_secret
                )
                if peer_secret is None:
                    raise ValueError("HMAC auth requires a secret for each peer.")

                return HmacConnectionAuthenticator(
                    peer.remote_uri,
                    peer.namespace,
                    secret=peer_secret,
                    node_id=peer_auth.get("node_id") or node_id,
                    key_id=peer_auth.get("key_id") or peer_auth.get("kid") or key_id,
                    ttl_seconds=int(peer_auth.get("ttl_seconds", peer_auth.get("ttl", ttl_seconds))),
                    max_clock_skew=int(peer_auth.get("max_clock_skew", peer_auth.get("skew", max_clock_skew))),
                )

            connection_authenticator = _auth_factory

    service_discovery_configs = ServiceDiscoveryConfigs(
        peers=peers,
        limits=resolved_client_limits,
        authenticator=connection_authenticator,
        reconnection=client_cfg.get("reconnection", services_cfg.get("reconnection", True)),
        max_retries=client_cfg.get("max_retries", services_cfg.get("max_retries", 20)),
    )

    server_configs = AttpServerConfigs(
        host=host,
        port=port,
        limits=resolved_server_limits,
        authentication=auth_strategy_instance,
        verbose=server_cfg.get("verbose", False),
        verbosity_level=server_cfg.get("verbosity_level", "info"),
    )

    strategies = list(balancing_strategies or [BasicRoundRobinStrategy])
    if not strategies:
        raise ValueError("balancing_strategies cannot be empty.")

    cacher = balancing_cacher or SimpleInMemoryCacher()

    providers: list[Provider] = [
        {"provide": "ATTP_AUTH_STRATEGY", "value": auth_strategy_instance},
        {"provide": "ATTP_BALANCING_STRATEGIES", "value": strategies},
        {"provide": "ATTP_BALANCING_CONFIGS", "value": balancer_configs},
        {"provide": "ATTP_BALANCING_CACHER", "value": cacher},
        {"provide": AttpServerConfigs, "value": server_configs},
        {"provide": ServiceDiscoveryConfigs, "value": service_discovery_configs},
        {"provide": BalancerConfigs, "value": balancer_configs},
        AttpRouter,
        NamespaceDispatcher,
        EventBus,
        AttpFrameDispatcher,
        AttpLoadBalancer,
        AttpServer,
        ServiceDiscovery,
        AttpTransmitter,
    ]

    if logger is not None:
        providers.insert(0, {"provide": "ASC_LOGGER", "value": logger})

    return providers
