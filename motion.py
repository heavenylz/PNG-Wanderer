"""Display geometry and animation-free movement helpers.

Pure Python so movement rules can be tested without a GUI or Windows.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    def intersection_area(self, other: "Rect") -> int:
        width = max(0, min(self.x + self.width, other.x + other.width) - max(self.x, other.x))
        height = max(0, min(self.y + self.height, other.y + other.height) - max(self.y, other.y))
        return width * height


def fully_visible(x: float, y: float, width: int, height: int, screens: list[Rect]) -> bool:
    """Return True if the widget fits within the union of display rectangles."""
    if width < 1 or height < 1 or not screens:
        return False
    candidate = Rect(round(x), round(y), width, height)
    # Physical displays don't overlap in desktop virtual-coordinate space.
    return sum(candidate.intersection_area(screen) for screen in screens) >= width * height


def closest_visible(x: float, y: float, width: int, height: int, screens: list[Rect]) -> tuple[int, int]:
    """Snap to the nearest fully visible position on some display."""
    if fully_visible(x, y, width, height, screens):
        return round(x), round(y)
    candidates = []
    for screen in screens:
        # Images larger than a display are clamped to its upper-left; the UI
        # size range is intentionally limited, but tiny displays can occur.
        px = max(screen.x, min(round(x), screen.x + max(0, screen.width - width)))
        py = max(screen.y, min(round(y), screen.y + max(0, screen.height - height)))
        if fully_visible(px, py, width, height, screens):
            candidates.append((px, py))
    if not candidates:
        return round(x), round(y)
    return min(candidates, key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2)


def bounced_step(
    x: float, y: float, dx: float, dy: float, speed: float, dt: float,
    width: int, height: int, screens: list[Rect],
) -> tuple[float, float, float, float]:
    """Try a step, reflecting independently on display-union boundaries."""
    step = max(0.0, speed * dt)
    nx, ny = x + dx * step, y + dy * step
    if fully_visible(nx, ny, width, height, screens):
        return nx, ny, dx, dy
    if not fully_visible(nx, y, width, height, screens):
        dx = -dx
    if not fully_visible(x, ny, width, height, screens):
        dy = -dy
    nx, ny = x + dx * step, y + dy * step
    if fully_visible(nx, ny, width, height, screens):
        return nx, ny, dx, dy
    # Corners of irregular monitor arrangements can require a full reversal.
    dx, dy = -dx, -dy
    nx, ny = x + dx * step, y + dy * step
    if fully_visible(nx, ny, width, height, screens):
        return nx, ny, dx, dy
    # Don't teleport across gaps or change window position if trapped.
    return x, y, dx, dy
