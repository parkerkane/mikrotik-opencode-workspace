from __future__ import annotations

from typing import Any

import jq


def apply_jq_filter(payload: Any, jq_filter: str) -> Any:
    try:
        results = jq.compile(jq_filter).input_value(payload).all()
    except Exception as exc:  # pragma: no cover - jq exceptions are implementation-specific
        raise ValueError(f"Invalid jq_filter: {exc}") from exc

    if len(results) == 1:
        return results[0]
    return results
