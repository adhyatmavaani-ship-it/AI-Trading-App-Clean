from __future__ import annotations

from typing import Any


class RenderProfileEngine:
    """Chooses mobile-safe rendering quality from live pressure signals."""

    def profile(
        self,
        *,
        overlay_count: int,
        heatmap_zones: int,
        dom_levels: int,
        fps: float = 60.0,
        low_power_requested: bool = False,
    ) -> dict[str, Any]:
        pressure = min((overlay_count * 0.012) + (heatmap_zones * 0.028) + (dom_levels * 0.010), 1.0)
        if low_power_requested or (0 < fps < 45) or pressure >= 0.78:
            mode = "LOW_POWER"
            target_fps = 30
            max_overlays = 18
            max_dom_levels = 8
        elif pressure >= 0.48:
            mode = "BALANCED"
            target_fps = 45
            max_overlays = 28
            max_dom_levels = 12
        else:
            mode = "PRO"
            target_fps = 60
            max_overlays = 40
            max_dom_levels = 16
        return {
            "mode": mode,
            "target_fps": target_fps,
            "pressure": round(pressure * 100, 2),
            "max_overlays": max_overlays,
            "max_dom_levels": max_dom_levels,
            "shader_quality": "reduced" if mode == "LOW_POWER" else "full",
            "thermal_safe": mode != "PRO",
        }
