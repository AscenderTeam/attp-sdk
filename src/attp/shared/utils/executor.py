import inspect
from typing import Any, get_args, get_origin

from pydantic import BaseModel, TypeAdapter

from attp_core.rs_api import PyAttpMessage

from attp.types.frame import AttpFrameDTO


async def execute_validated(callback: Any, payload: Any, *, frame: PyAttpMessage | None = None):
    """Thx GPT-5 for the call validator!"""
    sig = inspect.signature(callback)
    params = list(sig.parameters.values())

    # Drop "self" / "cls" if present in signature
    if params and params[0].name in ("self", "cls"):
        params = params[1:]
        sig = sig.replace(parameters=params)

    def _payload_as_dict(value: Any) -> dict[str, Any] | None:
        if value is None:
            return None
        if isinstance(value, dict):
            return value
        if isinstance(value, (AttpFrameDTO, BaseModel)):
            if hasattr(value, "model_dump"):
                return value.model_dump(mode="python")  # type: ignore[attr-defined]
            return value.__dict__
        return None

    payload_dict = _payload_as_dict(payload)
    payload_maps: list[dict[str, Any]] = []
    if payload_dict:
        payload_maps.append(payload_dict)
        for key in ("data", "payload", "body", "params"):
            nested = payload_dict.get(key)
            if isinstance(nested, dict):
                payload_maps.append(nested)
    elif hasattr(payload, "data") and isinstance(getattr(payload, "data"), dict):
        payload_maps.append(getattr(payload, "data"))

    def wants_frame(param: inspect.Parameter) -> bool:
        if frame is None:
            return False

        ann = param.annotation
        if ann is PyAttpMessage:
            return True

        origin = get_origin(ann)
        if origin is not None and PyAttpMessage in get_args(ann):
            return True

        return ann is inspect._empty and param.name in ("message", "frame")

    # --- Case 1: single-param message frame ---
    if len(params) == 1:
        param = params[0]
        if wants_frame(param):
            if inspect.iscoroutinefunction(callback):
                return await callback(frame)
            return callback(frame)

        # --- Case 2: single-param model ---
        ann = param.annotation

        if ann is not inspect._empty and (issubclass_safe(ann, AttpFrameDTO) or issubclass_safe(ann, BaseModel)):
            if inspect.isclass(ann) and isinstance(payload, ann):
                model = payload
            else:
                source = payload_dict
                if payload_dict and payload_maps:
                    field_names = ()
                    if hasattr(ann, "model_fields"):
                        field_names = ann.model_fields.keys()  # type: ignore[attr-defined]
                    elif hasattr(ann, "__fields__"):
                        field_names = ann.__fields__.keys()  # type: ignore[attr-defined]
                    if field_names and not any(name in payload_dict for name in field_names):
                        source = payload_maps[1] if len(payload_maps) > 1 else payload_dict
                model = ann.model_validate(source) if hasattr(ann, "model_validate") else ann(**(source or {}))
            if inspect.iscoroutinefunction(callback):
                return await callback(model)
            return callback(model)

    # --- Case 3: normal kwargs mapping ---
    bound_args = {}
    for name, param in sig.parameters.items():
        if wants_frame(param):
            bound_args[name] = frame
            continue

        value = None
        found = False
        for mapping in payload_maps:
            if name in mapping:
                value = mapping[name]
                found = True
                break

        if not found:
            if param.default is inspect.Parameter.empty:
                raise TypeError(f"Missing required argument: {name}")
            value = param.default
        else:
            if param.annotation is not inspect._empty and (issubclass_safe(param.annotation, AttpFrameDTO) or issubclass_safe(param.annotation, BaseModel)):
                if inspect.isclass(param.annotation) and isinstance(value, param.annotation):
                    bound_args[name] = value
                    continue
                if isinstance(value, dict):
                    value = param.annotation.model_validate(value) if hasattr(param.annotation, "model_validate") else param.annotation(**value)
                bound_args[name] = value
                continue

        if param.annotation is not inspect._empty:
            adapter = TypeAdapter(param.annotation)
            value = adapter.validate_python(value)

        bound_args[name] = value

    if inspect.iscoroutinefunction(callback):
        return await callback(**bound_args)
    return callback(**bound_args)


def issubclass_safe(obj: Any, cls: type) -> bool:
    try:
        return inspect.isclass(obj) and issubclass(obj, cls)
    except Exception:
        return False
