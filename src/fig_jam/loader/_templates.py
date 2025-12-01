"""Render configuration templates from validators for error context."""

from __future__ import annotations

import dataclasses
import json
import types
import typing
from pathlib import Path
from typing import Any

try:  # optional dependency
    import yaml  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional
    yaml = None

try:  # optional dependency
    from pydantic import BaseModel, Undefined
except ImportError:  # pragma: no cover - optional
    BaseModel = None  # type: ignore[assignment]
    Undefined = object()

from fig_jam.pipeline._validators import (
    is_dataclass_validator,
    is_dict_validator,
    is_list_validator,
    is_pydantic_validator,
    iter_model_fields,
)


def render_template(
    validator: Any, path_hint: Path, env_overrides: dict[tuple[str, ...], str]
) -> str:
    """Render a suggested configuration template for the validator."""
    shape = _sanitize_shape(_build_shape(validator, env_overrides))
    if not shape:
        return ""

    suffix = path_hint.suffix.lower()
    if suffix in {".json"}:
        return json.dumps(shape, indent=2)
    if suffix in {".toml"}:
        return _render_toml(shape)
    if suffix in {".ini", ".cfg"}:
        return _render_ini(shape)
    # Default to YAML for directories or other suffixes
    return _render_yaml(shape)


def _build_shape(
    validator: Any,
    env_overrides: dict[tuple[str, ...], str],
    prefix: tuple[str, ...] = (),
) -> dict[str, Any]:
    if is_list_validator(validator):
        return dict.fromkeys(validator, "<value>")
    if is_dict_validator(validator):
        return {
            key: _value_hint(value, env_overrides.get((*prefix, key)))
            for key, value in validator.items()
        }
    if is_dataclass_validator(validator):
        shape: dict[str, Any] = {}
        for field in dataclasses.fields(validator):
            field_path = (*prefix, field.name)
            env = env_overrides.get(field_path)
            default = (
                field.default if field.default is not dataclasses.MISSING else None
            )
            expected_type = _normalize_type_hint(field.type, default)
            nested_type = _resolve_nested(expected_type)
            if nested_type is not None:
                shape[field.name] = _build_shape(nested_type, env_overrides, field_path)
                continue
            shape[field.name] = _value_hint(expected_type, env, default)
        return shape
    if is_pydantic_validator(validator):
        shape: dict[str, Any] = {}
        for name, annotation in iter_model_fields(validator):
            field_path = (*prefix, name)
            env = env_overrides.get(field_path)
            model_fields = getattr(validator, "model_fields", None) or {}
            default = None
            if model_fields:
                default = getattr(model_fields.get(name, None), "default", None)
                if default is Undefined:
                    default = None
            expected_type = _normalize_type_hint(annotation, default)
            nested_type = _resolve_nested(expected_type)
            if nested_type is not None:
                shape[name] = _build_shape(nested_type, env_overrides, field_path)
                continue
            shape[name] = _value_hint(expected_type, env, default)
        return shape
    return {}


def _value_hint(expected: Any, env_var: str | None, default: Any = None) -> Any:
    placeholder = _placeholder_for_type(expected)
    notes: list[str] = []
    if default is not None and not _is_undefined(default):
        notes.append(f"default: {_format_default(default)}")
    if env_var is not None:
        notes.append(f"env: {env_var}")
    if notes:
        return f"{placeholder} ({', '.join(notes)})"
    return placeholder


def _annotate_env(value: Any, env_var: str | None) -> Any:
    if env_var is None:
        return value
    if isinstance(value, (int, float, bool)):
        return f"{value} (env: {env_var})"
    return f"{value} (env: {env_var})"


def _placeholder_for_type(expected: Any) -> Any:
    mapping = {
        str: "<string>",
        int: "<int>",
        float: "<float>",
        bool: "<bool>",
        Path: "<path/to/existing/directory>",
    }
    if expected in mapping:
        return mapping[expected]
    origin = typing.get_origin(expected)
    if origin in {typing.Union, getattr(types, "UnionType", None)}:
        args = [arg for arg in typing.get_args(expected) if arg is not type(None)]
        if args:
            return _placeholder_for_type(args[0])
    if expected is Any:
        return "<value>"
    if isinstance(expected, type):
        return f"<{expected.__name__}>"
    return "<value>"


def _resolve_nested(annotation: Any) -> type | None:
    if isinstance(annotation, type) and (
        is_dataclass_validator(annotation) or is_pydantic_validator(annotation)
    ):
        return annotation
    return None


def _normalize_type_hint(annotation: Any, default: Any) -> Any:
    """Prefer explicit annotations; fall back to default types when absent."""
    if annotation is None:
        return type(default) if default is not None else Any
    return annotation


def _render_yaml(shape: dict[str, Any]) -> str:
    if yaml is None:
        return json.dumps(shape, indent=2)
    return yaml.safe_dump(shape, sort_keys=False)


def _render_toml(shape: dict[str, Any]) -> str:
    lines: list[str] = []

    def _walk(node: dict[str, Any], prefix: list[str]) -> None:
        scalars: dict[str, Any] = {}
        nested: dict[str, dict[str, Any]] = {}
        for key, value in node.items():
            if isinstance(value, dict):
                nested[key] = value
            else:
                scalars[key] = value
        if prefix or scalars:
            if prefix:
                lines.append(f"[{'.'.join(prefix)}]")
            for key, value in scalars.items():
                if isinstance(value, str):
                    lines.append(f'{key} = "{value}"')
                else:
                    lines.append(f"{key} = {value}")
            if scalars:
                lines.append("")
        for key, value in nested.items():
            _walk(value, [*prefix, key])

    _walk(shape, [])
    return "\n".join(line for line in lines if line.strip())


def _render_ini(shape: dict[str, Any]) -> str:
    lines: list[str] = []
    scalars: dict[str, Any] = {
        key: value for key, value in shape.items() if not isinstance(value, dict)
    }
    nested = {k: v for k, v in shape.items() if isinstance(v, dict)}
    if scalars:
        lines.append("[DEFAULT]")
        for key, value in scalars.items():
            lines.append(f"{key} = {value}")
        lines.append("")
    for section, values in nested.items():
        lines.append(f"[{section}]")
        for key, value in values.items():
            lines.append(f"{key} = {value}")
        lines.append("")
    return "\n".join(line for line in lines if line.strip())


def _sanitize_shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize_shape(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_sanitize_shape(item) for item in value]
    simple_types = (int, float, str, bool, type(None))
    class_name = (
        value.__class__.__name__ if not isinstance(value, simple_types) else None
    )
    if class_name and "Undefined" in class_name:
        return "<value>"
    try:
        json.dumps(value)
    except TypeError:
        return str(value)
    else:
        return value


def _is_undefined(value: Any) -> bool:
    """Detect Pydantic undefined sentinels."""
    if value is dataclasses.MISSING or value is Undefined:
        return True
    name = getattr(value, "__name__", "") or value.__class__.__name__
    return "PydanticUndefined" in name


def _format_default(value: Any) -> str:
    """Human-friendly default rendering."""
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
