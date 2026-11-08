"""Server-sent event decoding: raw stream bytes to the JSON objects carried in `data` fields."""

import json
import re


def _invalid_constant(value):
    raise ValueError("Response contains a non-JSON number")


def sse_events(raw: bytes) -> list[dict]:
    """Decode a complete SSE body. `[DONE]` markers are dropped; every other event must be a JSON object."""
    events, data = [], []

    def dispatch():
        if data:
            payload = "\n".join(data)
            data.clear()
            if payload.strip() == "[DONE]":
                return
            event = json.loads(payload, parse_constant=_invalid_constant)
            if not isinstance(event, dict):
                raise ValueError("SSE event must be a JSON object")
            events.append(event)

    for line in re.split(r"\r\n|\r|\n", raw.decode("utf-8")):
        if not line:
            dispatch()
        elif line.startswith("data:"):
            value = line[5:]
            data.append(value[1:] if value.startswith(" ") else value)
    dispatch()
    return events
