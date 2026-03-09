from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import plotly.graph_objects as go
from plotly.subplots import make_subplots


GAUGE_SPECS: List[Dict[str, Any]] = [
    {"key": "rpm", "label": "RPM", "unit": "rpm", "min": 0, "max": 8000, "warn": 6500, "danger": 7000},
    {"key": "map_kpa", "label": "MAP", "unit": "kPa", "min": 0, "max": 300, "warn": 220, "danger": 260},
    {"key": "afr", "label": "AFR", "unit": "", "min": 10, "max": 20, "warn": 17, "danger": 18.5},
    {"key": "boost_kpa", "label": "Boost", "unit": "kPa", "min": 0, "max": 300, "warn": 220, "danger": 260},
    {"key": "injector_duty", "label": "Injector Duty", "unit": "%", "min": 0, "max": 100, "warn": 80, "danger": 90},
    {"key": "knock_count", "label": "Knock Count", "unit": "", "min": 0, "max": 30, "warn": 4, "danger": 8},
    {"key": "ect", "label": "ECT", "unit": "C", "min": 0, "max": 150, "warn": 105, "danger": 120},
    {"key": "iat", "label": "IAT", "unit": "C", "min": 0, "max": 100, "warn": 60, "danger": 80},
]


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _status(value: float, warn: float, danger: float) -> str:
    if value >= danger:
        return "danger"
    if value >= warn:
        return "caution"
    return "safe"


def _live_defaults(live: Dict[str, Any]) -> Dict[str, float]:
    rpm = _f(live.get("rpm", 0.0))
    map_kpa = _f(live.get("map_kpa", 0.0))
    return {
        "rpm": rpm,
        "map_kpa": map_kpa,
        "afr": _f(live.get("afr", 0.0)),
        "boost_kpa": max(0.0, map_kpa - 100.0),
        "injector_duty": _f(live.get("injector_duty", 0.0)),
        "knock_count": _f(live.get("knock_count", 0.0)),
        "ect": _f(live.get("ect", 0.0)),
        "iat": _f(live.get("iat", 0.0)),
    }


def build_live_gauges_figure(live: Dict[str, Any] | None = None) -> go.Figure:
    data = _live_defaults(live or {})
    stamp = datetime.now().strftime("%H:%M:%S")

    fig = make_subplots(
        rows=4,
        cols=2,
        specs=[[{"type": "indicator"}, {"type": "indicator"}] for _ in range(4)],
        horizontal_spacing=0.12,
        vertical_spacing=0.08,
    )

    for idx, spec in enumerate(GAUGE_SPECS):
        row = (idx // 2) + 1
        col = (idx % 2) + 1
        v = data.get(spec["key"], 0.0)
        zone = _status(v, spec["warn"], spec["danger"])
        suffix = f" {spec['unit']}" if spec["unit"] else ""
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=v,
                title={"text": spec["label"], "font": {"size": 13, "color": "#E0E0E0"}},
                number={"font": {"size": 24, "color": "#FFFFFF"}, "suffix": suffix},
                gauge={
                    "axis": {"range": [spec["min"], spec["max"]], "tickcolor": "#888888"},
                    "bar": {"color": "#00CCFF"},
                    "bgcolor": "#1A1A1A",
                    "bordercolor": "#333333",
                    "steps": [
                        {"range": [spec["min"], spec["warn"]], "color": "#176B3A"},
                        {"range": [spec["warn"], spec["danger"]], "color": "#8A6E00"},
                        {"range": [spec["danger"], spec["max"]], "color": "#8A2020"},
                    ],
                },
                customdata=[f"{spec['label']}: {v:.1f}{suffix} ({zone}) @ {stamp}"],
            ),
            row=row,
            col=col,
        )

    fig.update_layout(
        height=640,
        margin={"l": 6, "r": 6, "t": 8, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#E0E0E0"},
        transition={"duration": 200, "easing": "cubic-in-out"},
    )
    return fig
