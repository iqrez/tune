from __future__ import annotations

from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import QSettings, Qt, pyqtSignal
from PyQt6.QtWidgets import QHeaderView, QMenu, QTreeWidget, QTreeWidgetItem


# Honda-first navigation order (SManager-like workflow)
_TREE_SPEC: "OrderedDict[str, OrderedDict[str, List[Tuple[str, str]]]]" = OrderedDict(
    {
        "VTEC / Cam Control": OrderedDict(
            {
                "VTEC": [
                    ("VTEC Solenoid Output", "vtecSolenoidOutput"),
                    ("VTEC Engagement RPM", "vtecEngagementRPM"),
                    ("VTEC Engagement TPS", "vtecEngagementTPS"),
                    ("VTEC Engagement Speed", "vtecEngagementSpeed"),
                    ("Advanced VTEC Window", "vtecWindowAdvanced"),
                ],
                "VVT": [
                    ("VVT Target Tables", "vvtTargetTables"),
                    ("VVT Target Table 1", "vvtTargetTable1"),
                    ("VVT Target Table 2", "vvtTargetTable2"),
                    ("VVT PID Settings", "vvtPidSettings"),
                    ("VVT Offsets", "vvtOffsets"),
                    ("VVT Offset 1", "vvt1Offset"),
                    ("VVT Offset 2", "vvt2Offset"),
                ],
                "Trigger": [
                    ("Trigger / Cam Inputs", "triggerCamInputs"),
                    ("Advanced Trigger", "advancedTrigger"),
                    ("Trigger Gap Override", "triggerGapOverride"),
                    ("Cam Inputs", "camInputs"),
                    ("Trigger Type", "triggerType"),
                    ("Trigger Angle", "triggerAngle"),
                ],
            }
        ),
        "Fuel": OrderedDict(
            {
                "Fuel Maps": [
                    ("VE Map 1", "veTable1"),
                    ("VE Map 2", "veTable2"),
                    ("AFR Target Table 1", "afrTable1"),
                    ("AFR Target Table 2", "afrTable2"),
                ],
                "Injectors": [
                    ("Injector Flow", "injectorFlow"),
                    ("Injector Dead Time", "injectorDeadTime"),
                    ("Injector Lag Voltage Correction", "injectorLagVoltageCorrection"),
                    ("Injector Small Pulse Offset", "injectorSmallPulseOffset"),
                ],
                "Startup": [
                    ("Cranking Fuel", "crankingFuel"),
                    ("Cranking Duration", "crankingDuration"),
                    ("Cranking Timing", "crankingTiming"),
                ],
                "Transient": [
                    ("Acceleration Enrichment", "accelerationEnrichment"),
                    ("Deceleration Enleanment", "decelerationEnleanment"),
                    ("Wall Wetting Coefficient", "wallWettingCoefficient"),
                    ("Wall Wetting Tau", "wallWettingTau"),
                ],
                "Trims": [
                    ("Global Fuel Trim", "globalFuelTrim"),
                    ("Fuel Trim Cyl 1", "perCylinderFuelTrim1"),
                    ("Fuel Trim Cyl 2", "perCylinderFuelTrim2"),
                    ("Fuel Trim Cyl 3", "perCylinderFuelTrim3"),
                    ("Fuel Trim Cyl 4", "perCylinderFuelTrim4"),
                    ("Fuel Trim Cyl 5", "perCylinderFuelTrim5"),
                    ("Fuel Trim Cyl 6", "perCylinderFuelTrim6"),
                    ("Fuel Trim Cyl 7", "perCylinderFuelTrim7"),
                    ("Fuel Trim Cyl 8", "perCylinderFuelTrim8"),
                    ("Lambda 1 Sensor Offset", "lambda1SensorOffset"),
                ],
            }
        ),
        "Ignition": OrderedDict(
            {
                "Ignition Maps": [
                    ("Ignition Map 1", "ignitionTable1"),
                    ("Ignition Map 2", "ignitionTable2"),
                    ("Ignition Advance", "ignitionAdvance"),
                ],
                "Trims": [
                    ("Ignition Trim Cyl 1", "ignitionTrimCyl1"),
                    ("Ignition Trim Cyl 2", "ignitionTrimCyl2"),
                    ("Ignition Trim Cyl 3", "ignitionTrimCyl3"),
                    ("Ignition Trim Cyl 4", "ignitionTrimCyl4"),
                    ("Ignition Trim Cyl 5", "ignitionTrimCyl5"),
                    ("Ignition Trim Cyl 6", "ignitionTrimCyl6"),
                    ("Ignition Trim Cyl 7", "ignitionTrimCyl7"),
                    ("Ignition Trim Cyl 8", "ignitionTrimCyl8"),
                ],
                "Spark Control": [
                    ("Dwell Control", "dwellControl"),
                    ("Spark Dwell", "sparkDwell"),
                    ("Dwell Table", "dwellTable"),
                    ("Knock Control", "knockControl"),
                    ("Knock Retard", "knockRetard"),
                    ("Knock Recovery Rate", "knockRecoveryRate"),
                    ("Knock Threshold", "knockThreshold"),
                    ("Multispark", "multispark"),
                    ("Warmup Timing Correction", "warmupTimingCorrection"),
                ],
                "Coil On Plug (COP)": [
                    ("Coil on Plug Mode", "coilOnPlugMode"),
                    ("Per-Coil Dwell Table", "perCoilDwellTable"),
                    ("Spark Hardware Latency", "sparkHardwareLatency"),
                    ("Fixed Timing Mode", "fixedTimingMode"),
                    ("Ignition Output 1", "ignitionOutput1"),
                    ("Ignition Output 2", "ignitionOutput2"),
                    ("Ignition Output 3", "ignitionOutput3"),
                    ("Ignition Output 4", "ignitionOutput4"),
                    ("Ignition Output 5", "ignitionOutput5"),
                    ("Ignition Output 6", "ignitionOutput6"),
                    ("Ignition Output 7", "ignitionOutput7"),
                    ("Ignition Output 8", "ignitionOutput8"),
                    ("Ignition Output 9", "ignitionOutput9"),
                    ("Ignition Output 10", "ignitionOutput10"),
                    ("Ignition Output 11", "ignitionOutput11"),
                    ("Ignition Output 12", "ignitionOutput12"),
                ],
            }
        ),
        "Boost Control": OrderedDict(
            {
                "Protection": [
                    ("Boost Cut Pressure", "boostCutPressure"),
                    ("Overboost Protection", "overboostProtection"),
                    ("Boost Target Table", "boostTargetTable"),
                    ("Wastegate Duty Table", "wastegateDutyTable"),
                ]
            }
        ),
        "Idle Control": OrderedDict(
            {
                "Idle": [
                    ("Idle RPM Target", "idleRpmTarget"),
                    ("Idle Hardware", "idleHardware"),
                ]
            }
        ),
        "Sensors & Calibration": OrderedDict(
            {
                "Core Sensors": [
                    ("MAP Scaling", "mapScaling"),
                    ("CLT Bias", "cltBias"),
                    ("IAT Bias", "iatBias"),
                    ("TPS Min", "tpsMin"),
                    ("TPS Max", "tpsMax"),
                    ("Speed Sensor", "speedSensor"),
                    ("Fuel Level Sensor", "fuelLevelSensor"),
                    ("Flex Sensor", "flexSensor"),
                ]
            }
        ),
        "Limits & Protection": OrderedDict(
            {
                "Rev Limits": [
                    ("RPM Hard Limit", "rpmHardLimit"),
                    ("Rev Limiter Fuel Cut", "revLimiterFuelCut"),
                    ("Rev Limiter Spark Cut", "revLimiterSparkCut"),
                ]
            }
        ),
        "Outputs & Hardware": OrderedDict(
            {
                "Outputs": [
                    ("Fan On Temperature", "fanOnTemperature"),
                    ("Fan Off Temperature", "fanOffTemperature"),
                    ("A/C Cutoff RPM", "acCutoffRpm"),
                    ("Tach Pulse Per Rev", "tachPulsePerRev"),
                ]
            }
        ),
        "Vehicle & Misc": OrderedDict(
            {
                "Vehicle": [
                    ("Battery Voltage Correction", "batteryVoltageCorrection"),
                    ("Fuel Strategy", "fuelStrategy"),
                    ("Map Sensor", "mapSensor"),
                    ("Speed Sensor", "speedSensor"),
                ]
            }
        ),
        "Advanced / Experimental": OrderedDict(
            {
                "Advanced": [
                    ("Parameter Watch List", "watchList"),
                    ("Software Knock", "softwareKnock"),
                    ("rusEFI Wideband Tools", "rusefiWidebandTools"),
                ]
            }
        ),
    }
)


# canonical parameter -> aliases to auto-bind to dynamic INI names
_ALIASES: Dict[str, List[str]] = {
    "veTable1": ["veTable1", "veTable", "ve1"],
    "veTable2": ["veTable2", "veTableSecondary", "veTable", "ve2"],
    "afrTable1": ["afrTable1", "lambdaTable1", "lambdaTable"],
    "afrTable2": ["afrTable2", "lambdaTable2"],
    "injectorFlow": ["injectorFlow", "injector_flow", "injectorFlowRate"],
    "injectorDeadTime": ["injectorDeadTime", "injector_dead_time", "injectorCompensationMode"],
    "injectorLagVoltageCorrection": ["injectorLagVoltageCorrection", "injectorBatteryLag"],
    "injectorSmallPulseOffset": ["injectorSmallPulseOffset", "smallPulseOffset"],
    "crankingFuel": ["crankingFuel"],
    "crankingDuration": ["crankingDuration"],
    "crankingTiming": ["crankingTiming"],
    "accelerationEnrichment": ["accelerationEnrichment", "tpsAccelEnrichmentThreshold"],
    "decelerationEnleanment": ["decelerationEnleanment", "tpsDecelEnleanmentThreshold"],
    "wallWettingCoefficient": ["wallWettingCoefficient", "wwaeBeta"],
    "wallWettingTau": ["wallWettingTau", "wwTau"],
    "globalFuelTrim": ["globalFuelTrim", "stft", "ltft"],
    "lambda1SensorOffset": ["lambda1SensorOffset", "lambdaSensorOffset"],
    "ignitionTable1": ["ignitionTable1", "ignitionTable", "sparkTable1"],
    "ignitionTable2": ["ignitionTable2", "ignitionTable", "sparkTable2"],
    "ignitionAdvance": ["ignitionAdvance", "timingAdvance"],
    "dwellControl": ["dwellControl", "sparkDwell", "dwellTable"],
    "sparkDwell": ["sparkDwell", "dwellMs"],
    "dwellTable": ["dwellTable", "sparkDwellTable"],
    "knockControl": ["knockControl", "knockRetard", "knockThreshold"],
    "knockRetard": ["knockRetard", "maxKnockRetard"],
    "knockRecoveryRate": ["knockRecoveryRate", "knockRetardRateUp"],
    "knockThreshold": ["knockThreshold"],
    "multispark": ["multispark", "multiSpark"],
    "vtecSolenoidOutput": ["vtecSolenoidOutput", "vtecOutput"],
    "vtecEngagementRPM": ["vtecEngagementRPM", "vtecRpm"],
    "vvtTargetTables": ["vvtTargetTables", "vvtTargetTable", "vvtTable"],
    "vvtOffsets": ["vvtOffsets", "vvtOffset", "vvt1Offset", "vvt2Offset"],
    "vvt1Offset": ["vvt1Offset", "vvtOffset1", "vvtOffset"],
    "vvt2Offset": ["vvt2Offset", "vvtOffset2"],
    "triggerType": ["triggerType"],
    "triggerAngle": ["triggerAngle"],
    "triggerGapOverride": ["triggerGapOverride"],
    "mapScaling": ["mapScaling", "mapScale", "mapSensor"],
    "cltBias": ["cltBias"],
    "iatBias": ["iatBias"],
    "tpsMin": ["tpsMin", "tpsMinVoltage"],
    "tpsMax": ["tpsMax", "tpsMaxVoltage"],
    "rpmHardLimit": ["rpmHardLimit", "rpmLimit"],
    "revLimiterFuelCut": ["revLimiterFuelCut"],
    "revLimiterSparkCut": ["revLimiterSparkCut"],
    "boostCutPressure": ["boostCutPressure", "boostCut"],
    "overboostProtection": ["overboostProtection"],
    "idleRpmTarget": ["idleRpmTarget", "idleTargetRpm"],
    "fanOnTemperature": ["fanOnTemperature", "fanOnTemp"],
    "fanOffTemperature": ["fanOffTemperature", "fanOffTemp"],
    "acCutoffRpm": ["acCutoffRpm"],
    "batteryVoltageCorrection": ["batteryVoltageCorrection", "targetVBatt"],
    "tachPulsePerRev": ["tachPulsePerRev"],
    "speedSensor": ["speedSensor", "vss"],
}


# label, live-data key, unit
_LIVE_CHANNELS: List[Tuple[str, str, str]] = [
    ("RPM", "rpm", "rpm"),
    ("MAP", "map_kpa", "kPa"),
    ("AFR", "afr", ""),
    ("Boost", "map_kpa", "kPa"),
    ("Duty", "injector_duty", "%"),
    ("Knock", "knock_count", "count"),
    ("ECT", "ect", "C"),
    ("IAT", "iat", "C"),
]


def _slug(text: str) -> str:
    return "".join(ch for ch in (text or "").lower() if ch.isalnum())


def _build_path_lookup() -> Dict[str, Tuple[str, str, str]]:
    out: Dict[str, Tuple[str, str, str]] = {}
    for top, sections in _TREE_SPEC.items():
        for section, leaves in sections.items():
            for label, canonical in leaves:
                out[canonical] = (top, section, label)
    return out


_PATH_BY_CANONICAL = _build_path_lookup()
_TOP_LEVEL_ORDER = ["Live Vehicle Data", *list(_TREE_SPEC.keys())]
_TOP_LEVEL_INDEX = {name.lower(): idx for idx, name in enumerate(_TOP_LEVEL_ORDER)}


class ParameterTreeView(QTreeWidget):
    item_selected = pyqtSignal(str, str)  # category path, param name
    category_selected = pyqtSignal(str)
    context_action = pyqtSignal(str, str)  # action, parameter name

    _ROLE_PARAM_NAME = Qt.ItemDataRole.UserRole
    _ROLE_CATEGORY_PATH = Qt.ItemDataRole.UserRole + 1
    _ROLE_LIVE_KEY = Qt.ItemDataRole.UserRole + 2
    _ROLE_CANONICAL = Qt.ItemDataRole.UserRole + 3
    _ROLE_IS_VIRTUAL = Qt.ItemDataRole.UserRole + 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(2)
        self.setHeaderLabels(["Tuning Tree", "Value"])
        self.setUniformRowHeights(True)
        self.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setWordWrap(False)

        header = self.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.setColumnWidth(1, 110)

        self._settings = QSettings("BaseTuneArchitect", "HondaTree")
        self._live_root: Optional[QTreeWidgetItem] = None
        self._live_items: Dict[str, QTreeWidgetItem] = {}
        self._param_items: Dict[str, QTreeWidgetItem] = {}
        self._preset_marked: set[str] = set()

        self.itemClicked.connect(self.on_item_clicked)
        self.itemExpanded.connect(self._save_expanded_state)
        self.itemCollapsed.connect(self._save_expanded_state)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

        self._add_live_group()

    def _add_live_group(self):
        self._live_root = QTreeWidgetItem(["Live Vehicle Data", "DISCONNECTED"])
        self.addTopLevelItem(self._live_root)
        self._live_root.setExpanded(True)
        self._live_items.clear()

        for label, key, _unit in _LIVE_CHANNELS:
            it = QTreeWidgetItem([label, "--"])
            it.setData(0, self._ROLE_LIVE_KEY, key)
            self._live_root.addChild(it)
            self._live_items[key] = it

    def update_live_data(self, data: Dict[str, Any]):
        if not self._live_root:
            return

        connected = bool((data or {}).get("connected", False))
        self._live_root.setText(1, "LIVE" if connected else "DISCONNECTED")

        for label, key, unit in _LIVE_CHANNELS:
            item = self._live_items.get(key)
            if not item:
                continue
            if not connected:
                item.setText(1, "--")
                continue
            raw = (data or {}).get(key)
            if raw is None:
                item.setText(1, "--")
                continue
            try:
                num = float(raw)
                if key == "rpm" or key == "knock_count":
                    txt = f"{int(num)}"
                elif key in ("afr", "injector_duty"):
                    txt = f"{num:.2f}" if key == "afr" else f"{num:.1f}"
                else:
                    txt = f"{num:.1f}"
                item.setText(1, f"{txt} {unit}".strip())
            except (TypeError, ValueError):
                item.setText(1, str(raw))

    def _resolve_actual_name(self, canonical: str, by_slug: Dict[str, str]) -> Optional[str]:
        candidates = [canonical, *_ALIASES.get(canonical, [])]
        for c in candidates:
            found = by_slug.get(_slug(c))
            if found:
                return found
        return None

    def _value_hint_for_meta(self, meta: Optional[Dict[str, Any]]) -> str:
        if not meta:
            return ""
        kind = (meta.get("kind") or "").lower()
        units = (meta.get("units") or "").strip()
        if kind == "array":
            return "table"
        if kind == "bits":
            return "enum"
        return units

    def _build_path_for_item(self, item: QTreeWidgetItem) -> str:
        parts: List[str] = []
        node = item
        while node and node != self.invisibleRootItem():
            parts.append(node.text(0))
            node = node.parent()
        parts.reverse()
        return " > ".join([p for p in parts if p])

    def _iter_items(self):
        stack = [self.invisibleRootItem()]
        while stack:
            node = stack.pop()
            for i in range(node.childCount()):
                child = node.child(i)
                yield child
                stack.append(child)

    def _save_expanded_state(self, *_args):
        expanded: List[str] = []
        for item in self._iter_items():
            if item.isExpanded():
                path = self._build_path_for_item(item)
                if path and not path.startswith("Live Vehicle Data"):
                    expanded.append(path)
        self._settings.setValue("expanded_paths", expanded)

    def _restore_expanded_state(self):
        expanded = set(self._settings.value("expanded_paths", []) or [])
        if not expanded:
            return
        for item in self._iter_items():
            if self._build_path_for_item(item) in expanded:
                item.setExpanded(True)

    def _canonical_top_level(self, top: str) -> str:
        t = (top or "").strip().lower()
        aliases = {
            "vtec": "VTEC / Cam Control",
            "cam": "VTEC / Cam Control",
            "trigger": "VTEC / Cam Control",
            "fuel": "Fuel",
            "ignition": "Ignition",
            "boost": "Boost Control",
            "idle": "Idle Control",
            "sensor": "Sensors & Calibration",
            "sensors": "Sensors & Calibration",
            "limits": "Limits & Protection",
            "outputs": "Outputs & Hardware",
            "vehicle": "Vehicle & Misc",
            "misc": "Vehicle & Misc",
            "advanced": "Advanced / Experimental",
        }
        for k, v in aliases.items():
            if k in t:
                return v
        return "Vehicle & Misc"

    def _infer_category(self, name: str, kind: str) -> str:
        n = (name or "").lower()
        if any(k in n for k in ("vtec", "vvt", "cam", "trigger")):
            return "VTEC / Cam Control"
        if any(k in n for k in ("fuel", "inject", "afr", "lambda", "ve")):
            return "Fuel"
        if any(k in n for k in ("ign", "spark", "dwell", "knock", "timing", "coil")):
            return "Ignition"
        if any(k in n for k in ("boost", "wastegate")):
            return "Boost Control"
        if any(k in n for k in ("idle", "iac")):
            return "Idle Control"
        if any(k in n for k in ("sensor", "map", "tps", "clt", "iat", "baro", "speed")):
            return "Sensors & Calibration"
        if any(k in n for k in ("limit", "rev", "protect", "cut")):
            return "Limits & Protection"
        if any(k in n for k in ("fan", "relay", "output", "tach", "pump")):
            return "Outputs & Hardware"
        if any(k in n for k in ("vehicle", "battery", "alternator")):
            return "Vehicle & Misc"
        if kind == "array":
            return "Fuel"
        return "Advanced / Experimental"

    def _normalize_path_parts(self, category: str, name: str, kind: str) -> List[str]:
        # If this looks like a known canonical parameter, keep it in Honda-first sections.
        nslug = _slug(name)
        for canonical, aliases in _ALIASES.items():
            if nslug == _slug(canonical) or any(nslug == _slug(a) for a in aliases):
                top, section, _label = _PATH_BY_CANONICAL.get(canonical, ("Vehicle & Misc", "Additional", name))
                return [top, section]

        raw = (category or "").strip()
        if raw:
            parts = [p.strip() for p in raw.split(">") if p.strip()]
            if parts:
                top = self._canonical_top_level(parts[0])
                sec = parts[1].strip() if len(parts) > 1 else "Additional"
                return [top, sec]

        return [self._infer_category(name, kind), "Additional"]

    def _sort_key(self, p: Dict[str, Any]):
        path = self._normalize_path_parts(p.get("category", ""), p.get("name", ""), p.get("kind", ""))
        top_idx = _TOP_LEVEL_INDEX.get(path[0].lower(), 999)
        return (top_idx, path[0], path[1], (p.get("name") or "").lower())

    def load_parameters(self, params_list: List[Dict[str, Any]]):
        self.clear()
        self._add_live_group()
        self._param_items.clear()
        self._preset_marked.clear()

        nodes: Dict[Tuple[str, ...], QTreeWidgetItem] = {}

        def ensure_path(parts: List[str]) -> QTreeWidgetItem:
            parent = self.invisibleRootItem()
            chain: List[str] = []
            for part in parts:
                chain.append(part)
                key = tuple(chain)
                if key not in nodes:
                    item = QTreeWidgetItem([part, ""])
                    item.setData(0, self._ROLE_CATEGORY_PATH, " > ".join(chain))
                    parent.addChild(item)
                    nodes[key] = item
                parent = nodes[key]
            return parent

        sorted_params = sorted(params_list or [], key=self._sort_key)
        by_name = {(p.get("name") or "").strip(): p for p in sorted_params if (p.get("name") or "").strip()}
        by_slug = {_slug(name): name for name in by_name.keys()}
        represented: set[str] = set()

        # Build static Honda-first tree with only supported parameters.
        # Unsupported placeholders are intentionally hidden to keep the tree clean.
        for top, sections in _TREE_SPEC.items():
            for section, leaves in sections.items():
                sec_node: Optional[QTreeWidgetItem] = None
                for label, canonical in leaves:
                    actual = self._resolve_actual_name(canonical, by_slug)
                    if not actual:
                        continue
                    if sec_node is None:
                        sec_node = ensure_path([top, section])

                    meta = by_name.get(actual, {})
                    hint = self._value_hint_for_meta(meta)
                    leaf = QTreeWidgetItem([label, hint])
                    leaf.setData(0, self._ROLE_CATEGORY_PATH, f"{top} > {section}")
                    leaf.setData(0, self._ROLE_CANONICAL, canonical)
                    leaf.setData(0, self._ROLE_IS_VIRTUAL, False)
                    leaf.setData(0, self._ROLE_PARAM_NAME, actual)
                    sec_node.addChild(leaf)

                    self._param_items[actual] = leaf
                    self._param_items[canonical] = leaf
                    represented.add(actual)

        # Add dynamic parameters not represented by blueprint.
        for p in sorted_params:
            name = (p.get("name") or "").strip()
            if not name or name in represented:
                continue
            kind = (p.get("kind") or "").lower()
            parts = self._normalize_path_parts(p.get("category", ""), name, kind)
            node = ensure_path(parts)
            leaf = QTreeWidgetItem([name, self._value_hint_for_meta(p)])
            leaf.setData(0, self._ROLE_PARAM_NAME, name)
            leaf.setData(0, self._ROLE_CANONICAL, name)
            leaf.setData(0, self._ROLE_IS_VIRTUAL, False)
            leaf.setData(0, self._ROLE_CATEGORY_PATH, " > ".join(parts))
            node.addChild(leaf)
            self._param_items[name] = leaf

        # Expand top-level sections.
        for i in range(self.topLevelItemCount()):
            top = self.topLevelItem(i)
            top.setExpanded(top.text(0) in ("Live Vehicle Data", "VTEC / Cam Control", "Fuel", "Ignition"))

        self._restore_expanded_state()

    def clear_preset_marks(self):
        for key in list(self._preset_marked):
            item = self._param_items.get(key)
            if not item:
                continue
            item.setBackground(0, Qt.GlobalColor.transparent)
            item.setBackground(1, Qt.GlobalColor.transparent)
            item.setForeground(0, Qt.GlobalColor.white)
            item.setForeground(1, Qt.GlobalColor.white)
        self._preset_marked.clear()

    def mark_preset_changes(self, names: List[str]):
        self.clear_preset_marks()
        for name in names or []:
            item = self._param_items.get(name)
            if not item:
                # try normalized alias lookup
                slug = _slug(name)
                for k, it in self._param_items.items():
                    if _slug(k) == slug:
                        item = it
                        break
            if not item:
                continue
            item.setBackground(0, Qt.GlobalColor.darkYellow)
            item.setBackground(1, Qt.GlobalColor.darkYellow)
            item.setForeground(0, Qt.GlobalColor.black)
            item.setForeground(1, Qt.GlobalColor.black)
            self._preset_marked.add(name)

    def _on_context_menu(self, pos):
        item = self.itemAt(pos)
        if not item:
            return
        name = item.data(0, self._ROLE_PARAM_NAME)
        if not name:
            return

        menu = QMenu(self)
        actions = [
            ("edit_value", "Edit Value"),
            ("write_to_ecu", "Write to ECU"),
            ("burn_now", "Burn Now"),
            ("copy_value", "Copy Value"),
            ("paste_value", "Paste Value"),
            ("reset_default", "Reset to Default"),
            ("compare_msq", "Compare with .msq"),
            ("add_watch", "Add to Watch List"),
            ("remove_watch", "Remove from Watch List"),
            ("view_3d", "View in 3D"),
            ("help", "Help"),
        ]
        lookup = {}
        for action_id, text in actions:
            lookup[menu.addAction(text)] = action_id

        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen in lookup:
            self.context_action.emit(lookup[chosen], str(name))

    def on_item_clicked(self, item, _column):
        param_name = item.data(0, self._ROLE_PARAM_NAME)
        if param_name:
            category = item.data(0, self._ROLE_CATEGORY_PATH) or ""
            self.item_selected.emit(str(category), str(param_name))
            return

        live_key = item.data(0, self._ROLE_LIVE_KEY)
        if live_key:
            return

        path = self._build_path_for_item(item)
        if path:
            self.category_selected.emit(path)
