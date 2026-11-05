"""Validated, backwards-compatible local-only settings persistence."""

from __future__ import annotations

import json
import math
import os
import uuid
from pathlib import Path

VERSION = "0.4.0-beta.1"
DEFAULT_SIZE = 160
DEFAULT_SPEED = 90
MODES = ("Wander", "Bounce", "Follow cursor")


def clamp_int(value: object, low: int, high: int, fallback: int) -> int:
    try:
        number = int(value)
        if isinstance(value, bool):
            return fallback
        return max(low, min(number, high))
    except (TypeError, ValueError, OverflowError):
        return fallback


def normalize_companion(raw: object) -> dict | None:
    if not isinstance(raw, dict):
        return None
    path = raw.get("png_path", raw.get("path"))
    if not isinstance(path, str) or not path.strip():
        return None
    pos = raw.get("position")
    if not (
        isinstance(pos, list)
        and len(pos) == 2
        and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                and math.isfinite(v) and abs(v) <= 1_000_000 for v in pos)
    ):
        pos = None
    mode = raw.get("mode", "Wander")
    if mode not in MODES:
        mode = "Wander"
    uid = raw.get("id")
    if not isinstance(uid, str) or not uid:
        uid = uuid.uuid4().hex
    return {
        "id": uid,
        "png_path": path,
        "size": clamp_int(raw.get("size"), 48, 512, DEFAULT_SIZE),
        "speed": clamp_int(raw.get("speed"), 10, 300, DEFAULT_SPEED),
        "mode": mode,
        "paused": raw.get("paused") is True,
        "animation_paused": raw.get("animation_paused") is True,
        "monitor": raw.get("monitor") if isinstance(raw.get("monitor"), str) else "",
        "click_through": raw.get("click_through") is True,
        "position": pos,
    }


def normalize_config(raw: object) -> dict:
    if not isinstance(raw, dict):
        return {"companions": []}
    if isinstance(raw.get("companions"), list):
        source = raw["companions"][:24]  # Avoid pathological settings files.
    elif "png_path" in raw:  # v0.1 single-companion config migration
        source = [raw]
    else:
        source = []
    seen = set()
    companions = []
    for value in source:
        companion = normalize_companion(value)
        if companion is None:
            continue
        if companion["id"] in seen:
            companion["id"] = uuid.uuid4().hex
        seen.add(companion["id"])
        companions.append(companion)
    return {"companions": companions}


def read_config(path: Path) -> dict:
    try:
        return normalize_config(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"companions": []}


def write_config(path: Path, value: dict) -> None:
    """Atomic replacement keeps the previous file intact on interrupted writes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(normalize_config(value), indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
