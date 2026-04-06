# Copyright 2026 Timo Reunanen <timo@reunanen.eu>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
