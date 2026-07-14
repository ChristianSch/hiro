from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Any

import yaml


def load_layered_config(global_path: Path, service_path: Path) -> dict[str, Any]:
    global_config = _load_yaml(global_path)
    service_config = _load_yaml(service_path)
    return _deep_merge(global_config, service_config)


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text())
    except OSError as error:
        raise ValueError(f"cannot read configuration file {path}: {error}") from error
    except yaml.YAMLError as error:
        raise ValueError(f"invalid YAML in {path}: {error}") from error
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"configuration file {path} must contain a mapping")
    return value


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def section(config: dict[str, Any], name: str) -> dict[str, Any]:
    value = config.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"configuration section {name!r} is required")
    return value


def required_string(config: dict[str, Any], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"configuration value {key!r} must be a non-empty string")
    return value


def optional_string(config: dict[str, Any], key: str) -> str | None:
    value = config.get(key)
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError(f"configuration value {key!r} must be a string")
    return value


def number(config: dict[str, Any], key: str) -> float:
    value = config.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"configuration value {key!r} must be a number")
    return float(value)


def positive_int(config: dict[str, Any], key: str) -> int:
    value = config.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"configuration value {key!r} must be a positive integer")
    return value


def boolean(config: dict[str, Any], key: str) -> bool:
    value = config.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"configuration value {key!r} must be a boolean")
    return value


def tls_paths(server: dict[str, Any]) -> tuple[Path | None, Path | None]:
    certificate = optional_string(server, "tls_certificate")
    private_key = optional_string(server, "tls_private_key")
    if bool(certificate) != bool(private_key):
        raise ValueError("tls_certificate and tls_private_key must be configured together")
    return (
        Path(certificate) if certificate else None,
        Path(private_key) if private_key else None,
    )


def validate_listener(address: str, token: str | None) -> None:
    host = address.rsplit(":", 1)[0].strip("[]")
    if host.lower() == "localhost":
        return
    try:
        loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = False
    if not loopback and not token:
        raise ValueError("a service token is required when listening outside loopback")
