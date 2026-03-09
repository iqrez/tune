import html
from typing import Any, Dict, List


CATEGORY_ORDER = [
    "Engine & Constants",
    "Fuel",
    "Ignition",
    "Boost Control",
    "Idle Control",
    "VVT / Cam Control",
    "Launch / Flat Shift / Traction",
    "Sensors & Calibration",
    "Other Critical",
    "Other",
]


def default_full_tuning_state() -> Dict[str, Any]:
    return {
        "ini_path": "",
        "ini_source": "unknown",
        "query": "",
        "category": "",
        "parameters": [],
        "selected_name": "",
        "selected_meta": {},
        "selected_value": None,
        "dirty_pages": [],
        "status": "Load parameter registry to begin.",
    }


def _param_kind_label(param: Dict[str, Any]) -> str:
    if param.get("is_table"):
        return "table"
    if param.get("is_scalar"):
        return "scalar"
    return str(param.get("kind", "param"))


def build_parameter_tree_html(
    parameters: List[Dict[str, Any]],
    selected_name: str = "",
) -> str:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for p in parameters:
        grouped.setdefault(p.get("category", "Other"), []).append(p)

    sections: List[str] = []
    for category in CATEGORY_ORDER + sorted([k for k in grouped.keys() if k not in CATEGORY_ORDER]):
        items = grouped.get(category, [])
        if not items:
            continue
        items = sorted(items, key=lambda x: str(x.get("name", "")).lower())
        rows: List[str] = []
        for p in items:
            name = str(p.get("name", ""))
            title = str(p.get("table_title") or "")
            selected = " style='background:#1e293b;border-color:#fb923c;'" if name == selected_name else ""
            label = html.escape(name if not title else f"{name} ({title})")
            kind = html.escape(_param_kind_label(p))
            units = html.escape(str(p.get("units") or ""))
            rows.append(
                f"<div class='ft-item'{selected}>"
                f"<span class='ft-name'>{label}</span>"
                f"<span class='ft-kind'>{kind}</span>"
                f"<span class='ft-units'>{units}</span>"
                f"</div>"
            )
        sections.append(
            f"<div class='ft-group'>"
            f"<div class='ft-header'>{html.escape(category)} <span>({len(items)})</span></div>"
            f"{''.join(rows)}"
            f"</div>"
        )

    if not sections:
        sections.append("<div class='ft-empty'>No parameters matched your filter.</div>")

    return (
        "<style>"
        ".ft-group{margin-bottom:10px;border:1px solid #334155;border-radius:8px;overflow:hidden;}"
        ".ft-header{background:#0f172a;color:#e2e8f0;padding:8px 10px;font-weight:700;display:flex;justify-content:space-between;}"
        ".ft-item{display:grid;grid-template-columns:1fr 80px 80px;gap:8px;padding:6px 10px;border-top:1px solid #1e293b;background:#020617;color:#cbd5e1;}"
        ".ft-item:nth-child(even){background:#0b1220;}"
        ".ft-name{font-family:Consolas,monospace;font-size:12px;}"
        ".ft-kind,.ft-units{font-size:11px;color:#94a3b8;text-align:right;}"
        ".ft-empty{padding:12px;border:1px dashed #475569;border-radius:8px;color:#94a3b8;}"
        "</style>"
        + "".join(sections)
    )


def parameter_details_markdown(meta: Dict[str, Any], value: Any) -> str:
    if not meta:
        return "No parameter selected."
    name = meta.get("name", "")
    kind = _param_kind_label(meta)
    units = meta.get("units", "")
    rng = f"{meta.get('min_value')} .. {meta.get('max_value')}"
    page = meta.get("page_number")
    offset = meta.get("offset")
    source = f"page {page} @ {offset}"
    if isinstance(value, list):
        if value and isinstance(value[0], list):
            rows = len(value)
            cols = len(value[0]) if rows else 0
            val_txt = f"{rows}x{cols} matrix"
        else:
            val_txt = f"array[{len(value)}]"
    else:
        val_txt = str(value)
    return (
        f"**{name}**\n\n"
        f"- kind: `{kind}`\n"
        f"- location: `{source}`\n"
        f"- units: `{units}`\n"
        f"- limits: `{rng}`\n"
        f"- value: `{val_txt}`"
    )


def write_result_text(result: Dict[str, Any]) -> str:
    if not isinstance(result, dict):
        return "Write completed."
    if "written" in result or "errors" in result:
        w = len(result.get("written", []))
        e = len(result.get("errors", []))
        return f"Write batch completed: {w} succeeded, {e} failed."
    status = result.get("status", "ok")
    name = result.get("name", "")
    if name:
        return f"Write {status}: {name}"
    return f"Write {status}"


def burn_result_text(result: Dict[str, Any]) -> str:
    if not isinstance(result, dict):
        return "Burn completed."
    status = result.get("status", "ok")
    pages = result.get("burned_pages", [])
    if pages:
        return f"Burn {status}: pages {pages}"
    return f"Burn {status}: no pages"
