"""Standard built-in tools for basic math, string transforms, JSON queries, and hashes."""

import hashlib
import json
import math
from typing import Any, Dict
from ..core.models import ToolDefinition, ToolParameter, ToolType, utc_now


def calc_handler(args: Dict[str, Any]) -> str:
    expr = args.get("expression", "")
    # Safe eval limited to math constants and basic operations
    allowed_names = {
        k: v for k, v in math.__dict__.items() if not k.startswith("__")
    }
    allowed_names["abs"] = abs
    allowed_names["round"] = round
    # Simple parse check
    code = compile(expr, "<string>", "eval")
    for name in code.co_names:
        if name not in allowed_names:
            raise ValueError(f"Use of '{name}' not allowed in calculator")
    result = eval(code, {"__builtins__": {}}, allowed_names)
    return str(result)


def string_transform_handler(args: Dict[str, Any]) -> str:
    text = args.get("text", "")
    op = args.get("operation", "upper").lower()
    if op == "upper":
        return text.upper()
    elif op == "lower":
        return text.lower()
    elif op == "reverse":
        return text[::-1]
    elif op == "word_count":
        return str(len(text.split()))
    elif op == "length":
        return str(len(text))
    return text


def json_query_handler(args: Dict[str, Any]) -> Any:
    raw = args.get("json_str", "{}")
    key = args.get("key", "")
    parsed = json.loads(raw)
    return parsed.get(key)


def hash_generator_handler(args: Dict[str, Any]) -> str:
    text = args.get("text", "")
    algo = args.get("algorithm", "sha256").lower()
    if algo == "sha256":
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    elif algo == "md5":
        return hashlib.md5(text.encode("utf-8")).hexdigest()
    elif algo == "sha1":
        return hashlib.sha1(text.encode("utf-8")).hexdigest()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def timestamp_handler(args: Dict[str, Any]) -> str:
    return utc_now().isoformat()


BUILTIN_TOOL_DEFS = [
    ToolDefinition(
        name="calculator",
        description="Safely evaluate mathematical expressions like '2 * pi * 5' or 'sqrt(144)'",
        tool_type=ToolType.BUILTIN,
        parameters=[
            ToolParameter(name="expression", type="string", description="Mathematical expression to evaluate", required=True)
        ],
    ),
    ToolDefinition(
        name="string_transform",
        description="Perform transformations on text: upper, lower, reverse, word_count, length",
        tool_type=ToolType.BUILTIN,
        parameters=[
            ToolParameter(name="text", type="string", description="Input string to transform", required=True),
            ToolParameter(name="operation", type="string", description="Operation: upper, lower, reverse, word_count, length", required=False, default="upper"),
        ],
    ),
    ToolDefinition(
        name="json_query",
        description="Extract a value from a JSON string using a key",
        tool_type=ToolType.BUILTIN,
        parameters=[
            ToolParameter(name="json_str", type="string", description="JSON string payload", required=True),
            ToolParameter(name="key", type="string", description="Key to retrieve", required=True),
        ],
    ),
    ToolDefinition(
        name="hash_generator",
        description="Generate cryptographic hash (sha256, sha1, md5) of input text",
        tool_type=ToolType.BUILTIN,
        parameters=[
            ToolParameter(name="text", type="string", description="Text to hash", required=True),
            ToolParameter(name="algorithm", type="string", description="Algorithm: sha256, md5, sha1", required=False, default="sha256"),
        ],
    ),
    ToolDefinition(
        name="current_timestamp",
        description="Returns the current ISO 8601 UTC timestamp",
        tool_type=ToolType.BUILTIN,
        parameters=[],
    ),
]

BUILTIN_HANDLERS = {
    "calculator": calc_handler,
    "string_transform": string_transform_handler,
    "json_query": json_query_handler,
    "hash_generator": hash_generator_handler,
    "current_timestamp": timestamp_handler,
}
