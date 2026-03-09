from __future__ import annotations

import html
from typing import Dict, List, Sequence, Tuple


TREE: List[Tuple[str, List[Tuple[str, List[Tuple[str, str]]]]]] = [
    ("Base Engine & Hardware", [
        ("Base Settings", [
            ("Engine Shape & Constants", "engineShape"),
            ("Trigger Configuration", "triggerConfig"),
            ("Advanced Trigger", "advancedTrigger"),
            ("Trigger Gap Override", "triggerGapOverride"),
            ("Cylinder Banks", "cylinderBanks"),
            ("Outputs", "outputs"),
        ]),
        ("Hardware Setup", [
            ("Ignition Hardware", "ignitionHardware"),
            ("Injection Settings", "injectionSettings"),
            ("Idle hardware", "idleHardware"),
            ("Battery/Alternator", "batteryAlternator"),
        ])
    ]),
    ("Fuel", [
        ("Fuel Mapping", [
            ("VE Table (3D)", "veTable1"),
            ("VE (2D Table Editor)", "veTable2D"),
            ("AFR Target", "afrTarget"),
            ("Injector dead time", "injectorDeadTime"),
            ("Injection Timing", "injectionTiming"),
        ]),
        ("Startup & Enrichment", [
            ("Cranking Settings", "crankingSettings"),
            ("Cranking Fuel Multipliers", "crankingFuelMultiplier"),
            ("Cranking Cycle Base Fuel", "crankingCycleBaseFuel"),
            ("Priming Pulse", "primingPulse"),
            ("After start enrichment", "afterStartEnrichment"),
        ]),
    ]),
    ("Ignition", [
        ("Ignition Mapping", [
            ("Ignition advance", "ignitionAdvance"),
            ("Dwell (Clean view)", "dwellTable"),
            ("Dwell (Settings)", "dwellSettings"),
            ("Multispark", "multispark"),
        ]),
        ("Corrections", [
            ("Ignition IAT correction", "ignitionIatCorrection"),
            ("Warmup timing correction", "warmupTimingCorrection"),
            ("Ignition trim cyl 1..8", "ignitionTrim"),
            ("Ignition adder", "ignitionAdder"),
            ("Software Knock", "softwareKnock"),
            ("Max knock retard", "maxKnockRetard"),
        ]),
    ]),
    ("Idle Control", [
        ("Idle Settings", [
            ("Idle settings", "idleSettings"),
            ("Idle Target RPM", "idleTargetRpm"),
            ("Open Loop Idle position", "openLoopIdle"),
            ("Idle After Start Taper", "idleAfterStartTaper"),
            ("Cranking Air Amount vs CLT", "crankingAirAmount"),
        ])
    ]),
    ("Sensors", [
        ("Core Sensors", [
            ("MAP sensor", "mapSensor"),
            ("MAP sampling", "mapSampling"),
            ("TPS", "tpsSensor"),
            ("IAT Sensor", "iatSensor"),
            ("CLT Sensor", "cltSensor"),
            ("Baro sensor", "baroSensor"),
        ]),
        ("Oxygen Sensors", [
            ("CAN O2 sensors", "canO2Sensors"),
            ("Analog O2 sensor", "analogO2Sensor"),
            ("rusEFI Wideband Tools", "widebandTools"),
        ]),
        ("Auxiliary Sensors", [
            ("MAF sensor", "mafSensor"),
            ("Flex Sensor", "flexSensor"),
            ("Fuel Level Sensor", "fuelLevelSensor"),
            ("Speed sensor", "speedSensor"),
            ("Other Sensor Inputs", "otherSensorInputs"),
            ("Analog Input Settings", "analogInputSettings"),
        ]),
        ("Pressure & Temperature", [
            ("Fuel Pressure Sensor", "fuelPressureSensor"),
            ("Fuel Temp Sensor Settings", "fuelTempSensor"),
            ("Oil Pressure Sensor", "oilPressureSensor"),
            ("Oil Temp Sensor Settings", "oilTempSensor"),
            ("A/C Pressure Sensor", "acPressureSensor"),
            ("Ambient Temp Sensor Settings", "ambientTempSensor"),
            ("Compressor Discharge Temp", "cdtSensor"),
            ("EGT inputs", "egtInputs"),
        ])
    ]),
    ("Limits & Protections", [
        ("Engine Limits", [
            ("Rev limiters", "revLimiters"),
            ("Speed Limit", "speedLimit"),
            ("Overboost protection", "overboostProtection"),
        ]),
        ("Hardware Fallbacks", [
            ("Ignition Key Input", "ignitionKeyInput"),
            ("Low oil pressure protection", "lowOilPressure"),
            ("Sensors Fallback", "sensorsFallback"),
        ])
    ]),
    ("VVT & Extras", [
        ("VVT", [
            ("VVT hardware", "vvtHardware"),
        ]),
        ("Calibration", [
            ("VR 1 Threshold", "vr1Threshold"),
        ])
    ])
]


def flatten_targets() -> List[str]:
    out: List[str] = []
    for _, sections in TREE:
        for _, items in sections:
            for _, target in items:
                out.append(target)
    return out


def build_tree_html(search: str, selected: str, available: Sequence[str], input_id: str, trigger_id: str) -> str:
    q = (search or "").strip().lower()
    avail = set(available or [])
    cards: List[str] = []

    for group, sections in TREE:
        sec_html: List[str] = []
        for section_title, items in sections:
            item_html: List[str] = []
            for label, target in items:
                hay = f"{group} {section_title} {label} {target}".lower()
                if q and q not in hay:
                    continue
                on = "1" # Temporarily force all UI items to be active for dialog viewing
                selected_cls = " selected" if selected == target else ""
                disabled_cls = "" if on == "1" else " disabled"
                tooltip = f'Select {target}'
                item_html.append(
                    f"<button class='pt-item{selected_cls}{disabled_cls}' data-target='{html.escape(target)}' data-avail='{on}' title='{html.escape(tooltip)}'>"
                    f"{html.escape(label)}</button>"
                )
            if item_html:
                sec_html.append(
                    f"<details class='pt-sub' open><summary>{html.escape(section_title)}</summary>"
                    f"{''.join(item_html)}</details>"
                )
        if sec_html:
            cards.append(
                f"<details class='pt-group' open><summary>{html.escape(group)}</summary>{''.join(sec_html)}</details>"
            )

    if not cards:
        cards.append("<div class='pt-empty'>No matching parameters.</div>")

    script = f"""
<script>
(function() {{
  const root = document.getElementById('parameter-tree-root');
  if (!root || root.dataset.bound === '1') return;
  root.dataset.bound = '1';
  root.addEventListener('click', function(ev) {{
    const btn = ev.target.closest('.pt-item');
    if (!btn) return;
    if (btn.getAttribute('data-avail') !== '1') return;
    const target = btn.getAttribute('data-target') || '';
    const input = document.querySelector('#{input_id} textarea, #{input_id} input') || document.getElementById('{input_id}');
    const trigger = document.querySelector('#{trigger_id} button') || document.getElementById('{trigger_id}');
    if (!input || !trigger) {{
      console.error("Could not find tree proxy inputs:", '{input_id}', '{trigger_id}');
      return;
    }}
    input.value = target;
    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
    trigger.click();
  }});
}})();
</script>
"""

    return (
        "<style>"
        "#parameter-tree-root{padding:4px;}"
        ".pt-group,.pt-sub{background:#101010;border:1px solid #2b2b2b;border-radius:8px;margin-bottom:8px;padding:6px;}"
        ".pt-group>summary,.pt-sub>summary{cursor:pointer;color:#E0E0E0;font-size:14px;font-weight:700;}"
        ".pt-sub>summary{font-size:13px;color:#C8C8C8;font-weight:600;}"
        ".pt-item{display:block;width:100%;text-align:left;margin:4px 0;padding:6px 8px;background:#1A1A1A;border:1px solid #333;border-radius:6px;color:#E0E0E0;font-size:12px;}"
        ".pt-item:hover{filter:brightness(1.08);border:2px solid #FF6600;}"
        ".pt-item.selected{border:2px solid #00CCFF;background:#15232A;}"
        ".pt-item.disabled{opacity:0.35;cursor:not-allowed;}"
        ".pt-empty{padding:10px;color:#888;font-size:12px;border:1px dashed #333;border-radius:8px;}"
        "</style>"
        f"<div id='parameter-tree-root'>{''.join(cards)}</div>{script}"
    )
