import ast
from typing import Any


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return {}
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none", "~"}:
        return None
    try:
        return ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return value.strip("\"'")


def _minimal_safe_load(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        key, separator, raw_value = line.strip().partition(":")
        if not separator:
            raise ValueError(f"unsupported YAML line: {raw_line}")
        while stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        value = _parse_scalar(raw_value)
        parent[key] = value
        if isinstance(value, dict):
            stack.append((indent, value))
    return root


def safe_load(text: str) -> Any:
    try:
        import yaml
    except ModuleNotFoundError:
        return _minimal_safe_load(text)
    return yaml.safe_load(text)
