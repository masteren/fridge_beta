import base64
import json
import os
from typing import Any, Dict, List, Optional

import openai
from openai import OpenAI


class OpenAIVisionError(Exception):
    pass


class MissingAPIKeyError(OpenAIVisionError):
    pass


class NonJsonResponseError(OpenAIVisionError):
    pass


class VisionTimeoutError(OpenAIVisionError):
    pass


def _normalize_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def recognize_ingredients_from_bytes(
    image_bytes: bytes,
    mime_type: str,
    model: str = "gpt-4.1-mini",
    timeout_seconds: int = 30,
) -> List[Dict[str, Any]]:
    if not os.environ.get("OPENAI_API_KEY"):
        raise MissingAPIKeyError("OPENAI_API_KEY is not set.")

    client = OpenAI(timeout=timeout_seconds)
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64}"

    try:
        response = client.responses.create(
            model=model,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "ingredients_schema",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "ingredients": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "quantity": {"type": ["number", "null"]},
                                        "confidence": {"type": ["number", "null"]},
                                        "unit": {"type": ["string", "null"]},
                                    },
                                    "required": ["name", "quantity", "confidence", "unit"],
                                    "additionalProperties": False,
                                },
                            }
                        },
                        "required": ["ingredients"],
                        "additionalProperties": False,
                    },
                }
            },
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "画像内の食材を識別してください。"
                            ),
                        },
                        {"type": "input_image", "image_url": data_url},
                    ],
                }
            ],
        )
    except Exception as exc:
        if exc.__class__.__name__ in ("APITimeoutError", "TimeoutError"):
            raise VisionTimeoutError(f"OpenAI request timed out: {exc}") from exc
        raise OpenAIVisionError(f"OpenAI request failed: {exc.__class__.__name__}: {exc}") from exc

    raw_text = (response.output_text or "").strip()
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise NonJsonResponseError("Model did not return valid JSON.") from exc

    if not isinstance(payload, dict):
        raise NonJsonResponseError("JSON root is not an object.")
    items = payload.get("ingredients")
    if not isinstance(items, list):
        raise NonJsonResponseError("Missing 'ingredients' array.")

    results: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        quantity = _normalize_number(item.get("quantity"))
        confidence = _normalize_number(item.get("confidence"))

        entry: Dict[str, Any] = {"name": name}
        if quantity is not None:
            entry["quantity"] = quantity
        if confidence is not None:
            entry["confidence"] = confidence
        results.append(entry)

    return results
