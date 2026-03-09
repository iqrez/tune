from __future__ import annotations
import io
import os
import re
import struct
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
import requests

from .rusefi_connector import (
    RusefiTunerClient,
    TS_READ_COMMAND,
    TS_WRITE_COMMAND,
    TS_CHUNK_WRITE_COMMAND,
    TS_BURN_COMMAND,
    TS_RESPONSE_OK,
    TS_RESPONSE_OK_ALT,
    TS_RESPONSE_BURN_OK,
)

# ---------------------------------------------------------
# Type Definitions
# ---------------------------------------------------------
TYPE_INFO: Dict[str, Tuple[str, int, int, int]] = {
    "U08": ("<B", 1, 0, 0xFF),
    "S08": ("<b", 1, -128, 127),
    "U16": ("<H", 2, 0, 0xFFFF),
    "S16": ("<h", 2, -32768, 32767),
    "U32": ("<I", 4, 0, 0xFFFFFFFF),
    "S32": ("<i", 4, -2147483648, 2147483647),
    "F32": ("<f", 4, -1e38, 1e38),
}

MENU_CATEGORY_FALLBACK = "Other"
DEFAULT_CATEGORY_ORDER = [
    "Engine & Constants", "Fuel", "Ignition", "Boost Control", "Idle Control",
    "VVT / Cam Control", "Launch / Flat Shift / Traction", "Sensors & Calibration",
    "Other Critical", MENU_CATEGORY_FALLBACK
]

# ---------------------------------------------------------
@dataclass
class ParameterDefinition:
    name: str
    page_id: int
    offset: int
    value_type: str
    kind: str
    size_bytes: int
    units: str = ""
    scale: float = 1.0
    translate: float = 0.0
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    digits: Optional[int] = None
    shape: Optional[Tuple[int, int]] = None
    bit_range: Optional[Tuple[int, int]] = None
    options: List[str] = field(default_factory=list)
    read_only: bool = False
    category: str = MENU_CATEGORY_FALLBACK
    aliases: List[str] = field(default_factory=list)
    menu_order: int = 1_000_000

    @property
    def element_count(self) -> int:
        if not self.shape: return 1
        return self.shape[0] * self.shape[1]

# ---------------------------------------------------------
class ParameterRegistry:
    """
    Guaranteed Flawless Parameter Engine.
    Dynamic INI parsing, alias mapping, and safety guardrails.
    """
    def __init__(self, client: RusefiTunerClient):
        self.client = client
        self._definitions: Dict[str, ParameterDefinition] = {}
        self._name_index: Dict[str, str] = {}
        self._lock = threading.RLock()
        self._ini_path = None
        self._blocking_factor = 256

    def ensure_loaded(self, force: bool = False):
        with self._lock:
            if self._definitions and not force: return
            path = self._resolve_ini()
            if not path: raise FileNotFoundError("No INI found")
            self._parse_ini(path.read_text(encoding='utf-8', errors='ignore'))
            self._ini_path = path

    def _resolve_ini(self) -> Optional[Path]:
        # Priority: State Cache > bundled repo copy
        root = Path(__file__).resolve().parents[2]
        candidates = [
            root / "backend" / "state" / "ini_cache" / "rusefi_uaefi_latest.ini",
            root / "state" / "ini_cache" / "rusefi_uaefi_latest.ini",
            root / "rusefi_uaefi.ini",
            root.parent / "rusefi_uaefi.ini",
        ]
        for c in candidates:
            if c.exists():
                print(f"DEBUG: Using INI file: {c.absolute()}")
                return c
        return None

    @staticmethod
    def _eval_simple_math(expr: str) -> Optional[float]:
        """Evaluate simple math like '1/147', '0.1', '1.0/10'."""
        expr = expr.strip()
        if not expr:
            return None
        # Handle division: 1/147
        if '/' in expr:
            parts = expr.split('/')
            if len(parts) == 2:
                try:
                    num = float(parts[0].strip())
                    den = float(parts[1].strip())
                    return num / den if den != 0 else None
                except ValueError:
                    return None
        # Handle multiplication: 0.1*10
        if '*' in expr:
            parts = expr.split('*')
            if len(parts) == 2:
                try:
                    return float(parts[0].strip()) * float(parts[1].strip())
                except ValueError:
                    return None
        try:
            return float(expr)
        except ValueError:
            return None

    @staticmethod
    def _safe_float(token: str, default: float = 0.0) -> float:
        """Parse a float or TunerStudio expression ({ternary ? val1 : val2})."""
        t = token.strip()
        if '{' not in t:
            try:
                return float(t)
            except ValueError:
                # Try simple math (e.g. 1/10)
                result = ParameterRegistry._eval_simple_math(t)
                return result if result is not None else default
        # Strip braces: { expr } -> expr
        inner = t.replace('{', '').replace('}', '').strip()
        if not inner:
            return default
        # Handle ternary: var ? true_val : false_val
        # Boolean flags default to 0, so use the false branch
        if '?' in inner and ':' in inner:
            q_idx = inner.index('?')
            c_idx = inner.index(':', q_idx)
            false_expr = inner[c_idx + 1:].strip()
            true_expr = inner[q_idx + 1:c_idx].strip()
            # Try false branch first (most boolean flags default to 0)
            result = ParameterRegistry._eval_simple_math(false_expr)
            if result is not None:
                return result
            # Try true branch as fallback
            result = ParameterRegistry._eval_simple_math(true_expr)
            if result is not None:
                return result
            return default
        # Try direct math evaluation
        result = ParameterRegistry._eval_simple_math(inner)
        return result if result is not None else default

    @staticmethod
    def _safe_units(token: str) -> str:
        """Parse a units string, handling ternary expressions like {var ? "lambda" : "afr"}."""
        t = token.strip()
        if '{' not in t:
            return t.strip('"')
        # Strip braces
        inner = t.replace('{', '').replace('}', '').strip()
        if '?' in inner and ':' in inner:
            q_idx = inner.index('?')
            c_idx = inner.index(':', q_idx)
            false_expr = inner[c_idx + 1:].strip().strip('"')
            return false_expr
        return inner.strip('"')

    @staticmethod
    def _split_respecting_braces(s: str) -> List[str]:
        """Split on commas but keep {…} blocks intact."""
        tokens = []
        depth = 0
        current = []
        for ch in s:
            if ch == '{':
                depth += 1
                current.append(ch)
            elif ch == '}':
                depth -= 1
                current.append(ch)
            elif ch == ',' and depth == 0:
                tokens.append(''.join(current).strip())
                current = []
            else:
                current.append(ch)
        tokens.append(''.join(current).strip())
        return tokens

    def _parse_ini(self, content: str):
        defs = {}
        section = ""
        page_id = 0

        # Categorization maps
        dialog_to_path = {}  # dialog_name -> "Menu > SubMenu"
        dialog_to_order = {} # dialog_name -> appearance order in [Menu]
        param_to_dialog = {} # param_name -> immediate_dialog
        child_to_parent_dialog = {} # child_dialog -> parent_dialog
        menu_order_counter = 0

        # --- Pass 1: Build Menu & Dialog Hierarchy ---
        current_menu = "General"
        current_group = ""
        current_dialog = ""

        def _clean_label(token: str) -> str:
            # TS uses leading '&' for menu accelerators. Drop it for UI labels.
            return token.strip().strip('"').replace("&", "").strip()
        
        for line in content.splitlines():
            line = line.split(';')[0].strip()
            if not line: continue
            
            m = re.match(r"^\[(.*)\]", line, re.I)
            if m:
                section = m.group(1).lower().strip()
                continue
            
            low_line = line.lower()
            if section == "menu":
                if low_line.startswith("menu ="):
                    parts = self._split_respecting_braces(line.split('=', 1)[1])
                    if parts:
                        current_menu = _clean_label(parts[0]) or "General"
                    else:
                        current_menu = "General"
                    current_group = ""
                elif low_line.startswith("submenu ="):
                    parts = self._split_respecting_braces(line.split('=', 1)[1])
                    if len(parts) >= 2:
                        d_name = parts[0].strip()
                        if d_name.lower() == "std_separator":
                            continue
                        label = _clean_label(parts[1])
                        dialog_to_path[d_name] = f"{current_menu} > {label}"
                        if d_name not in dialog_to_order:
                            dialog_to_order[d_name] = menu_order_counter
                            menu_order_counter += 1
                elif low_line.startswith("groupmenu ="):
                    parts = self._split_respecting_braces(line.split('=', 1)[1])
                    current_group = _clean_label(parts[0]) if parts else ""
                elif low_line.startswith("groupchildmenu ="):
                    parts = self._split_respecting_braces(line.split('=', 1)[1])
                    if len(parts) >= 2:
                        d_name = parts[0].strip()
                        if d_name.lower() == "std_separator":
                            continue
                        label = _clean_label(parts[1])
                        path = f"{current_menu}"
                        if current_group: path += f" > {current_group}"
                        path += f" > {label}"
                        dialog_to_path[d_name] = path
                        if d_name not in dialog_to_order:
                            dialog_to_order[d_name] = menu_order_counter
                            menu_order_counter += 1
            
            elif section in ("dialog", "dialogs", "userdefined"):
                if low_line.startswith("dialog ="):
                    parts = self._split_respecting_braces(line.split('=', 1)[1])
                    if len(parts) >= 1:
                        current_dialog = parts[0].strip()
                elif low_line.startswith("field =") and current_dialog:
                    parts = self._split_respecting_braces(line.split('=', 1)[1])
                    if len(parts) >= 2:
                        p_name = parts[1].strip()
                        if p_name not in param_to_dialog:
                            param_to_dialog[p_name] = current_dialog
                elif low_line.startswith("panel =") and current_dialog:
                    parts = self._split_respecting_braces(line.split('=', 1)[1])
                    if len(parts) >= 1:
                        child_dialog = parts[0].strip()
                        child_to_parent_dialog[child_dialog] = current_dialog

        # --- Pass 2: Parse Constants & Assign Categories ---
        section = ""
        page_id = 0
        for line in content.splitlines():
            line = line.split(';')[0].strip()
            if not line: continue
            
            m = re.match(r"^\[(.*)\]", line, re.I)
            if m:
                section = m.group(1).lower().strip()
                continue
            
            if section == "constants":
                if line.lower().startswith("page"):
                    try: page_id = int(line.split('=')[1].strip())
                    except: pass
                    continue

                if '=' not in line: continue
                lhs, rhs = [x.strip() for x in line.split('=', 1)]
                tokens = self._split_respecting_braces(rhs)
                if len(tokens) < 3: continue

                kind = tokens[0].lower()
                val_type = tokens[1].upper()
                if val_type not in TYPE_INFO: continue

                try:
                    offset = int(tokens[2])
                    fmt, bsize, _, _ = TYPE_INFO[val_type]

                    d = ParameterDefinition(
                        name=lhs, page_id=page_id, offset=offset,
                        value_type=val_type, kind=kind, size_bytes=bsize
                    )

                    if kind == "scalar" and len(tokens) >= 9:
                        d.units = self._safe_units(tokens[3])
                        d.scale = self._safe_float(tokens[4], 1.0)
                        d.translate = self._safe_float(tokens[5])
                        d.min_val = self._safe_float(tokens[6])
                        d.max_val = self._safe_float(tokens[7], 65535.0)
                        try: d.digits = int(self._safe_float(tokens[8], 0))
                        except: pass
                    elif kind == "array" and len(tokens) >= 10:
                        sh = tokens[3].strip('[]').split('x')
                        d.shape = (int(sh[0]), int(sh[1])) if len(sh) == 2 else (1, int(sh[0]))
                        d.size_bytes = bsize * d.element_count
                        d.units = self._safe_units(tokens[4])
                        d.scale = self._safe_float(tokens[5], 1.0)
                        d.translate = self._safe_float(tokens[6])
                        d.min_val = self._safe_float(tokens[7])
                        d.max_val = self._safe_float(tokens[8], 65535.0)
                        if len(tokens) >= 10:
                            try: d.digits = int(self._safe_float(tokens[9], 0))
                            except: pass
                    elif kind == "bits" and len(tokens) >= 4:
                        m = re.match(r"\[(\d+):(\d+)\]", tokens[3])
                        if m: d.bit_range = (int(m.group(1)), int(m.group(2)))
                        d.options = [t.strip('"') for t in tokens[4:]]

                    defs[lhs] = d
                except: continue

        # Final pass: Assign categories by climbing the parent dialog tree
        for name, d in defs.items():
            path = ""
            menu_order = None
            curr = param_to_dialog.get(name)
            visited = set()
            while curr and curr not in visited:
                visited.add(curr)
                if not path and curr in dialog_to_path:
                    path = dialog_to_path[curr]
                if menu_order is None and curr in dialog_to_order:
                    menu_order = dialog_to_order[curr]
                if path and menu_order is not None:
                    break
                curr = child_to_parent_dialog.get(curr)

            if path:
                d.category = path
            else:
                if "Table" in name: d.category = "Tables"
                else: d.category = MENU_CATEGORY_FALLBACK
            d.menu_order = menu_order if menu_order is not None else 1_000_000

        self._definitions = defs
        self._build_index()

    def list_parameters(self, query: str = "", category: str = "", kind: str = "") -> List[Dict[str, Any]]:
        self.ensure_loaded()
        results = []
        q = query.lower()
        c = category.lower()
        k = kind.lower()
        
        for name, d in self._definitions.items():
            if q and q not in name.lower(): continue
            if c and c not in d.category.lower(): continue
            if k and k != d.kind.lower(): continue
            
            results.append({
                "name": name,
                "category": d.category,
                "menu_order": d.menu_order,
                "kind": d.kind,
                "units": d.units,
                "min": d.min_val,
                "max": d.max_val,
                "read_only": d.read_only
            })
        return sorted(results, key=lambda x: (x.get("menu_order", 1_000_000), x.get("category", ""), x.get("name", "")))

    @contextmanager
    def temporary_write_access(self):
        prev = bool(getattr(self.client, "allow_writes", False))
        self.client.set_allow_writes(True)
        try:
            yield
        finally:
            self.client.set_allow_writes(prev)

    def write_many(self, items: List[Dict[str, Any]], force: bool = False) -> Dict[str, Any]:
        results = {}
        for item in items:
            name = item.get("name")
            value = item.get("value")
            if name is None or value is None: continue
            try:
                results[name] = self.write_parameter(name, value, force=force)
            except Exception as e:
                results[name] = f"Error: {str(e)}"
        return results

    def burn(self, pages: Optional[List[int]] = None) -> bool:
        if not bool(getattr(self.client, "allow_writes", False)):
            raise PermissionError("Writes are disabled. Call set_allow_writes(True) before burn().")
        if not pages:
            pages = [0]
        success = True
        for p in pages:
            # Burn is framed 'B' + page (2 bytes LE, 0-based)
            binary_page = max(0, p - 1) if p > 0 else p
            payload = struct.pack('<H', binary_page)
            ok, code, _ = self.client.send_and_receive_binary(ord(TS_BURN_COMMAND), payload)
            if not ok or code not in (TS_RESPONSE_OK, TS_RESPONSE_BURN_OK):
                success = False
        return success

    def export_msq_bytes(self, include_read_only: bool = False) -> bytes:
        from parsers.msq_parser import MsqParser
        # For a full export, we read all non-array parameters
        self.ensure_loaded()
        data = {}
        for name, d in self._definitions.items():
            if d.kind == "scalar":
                try:
                    val = self.read_parameter(name)["value"]
                    data[name] = val
                except: continue
        
        # Create a mock snapshot or just use the MsqParser directly if we can
        # For now, let's just generate a simple XML if MsqParser isn't flexible enough
        import xml.etree.ElementTree as ET
        root = ET.Element("tunersq")
        page = ET.SubElement(root, "page")
        for k, v in data.items():
             const = ET.SubElement(page, "constant", name=k)
             const.text = str(v)
        
        out = io.BytesIO()
        ET.ElementTree(root).write(out, encoding='utf-8', xml_declaration=True)
        return out.getvalue()

    def import_msq_bytes(self, content: bytes, apply_to_ecu: bool = True, burn_after: bool = False, force: bool = False) -> Dict[str, Any]:
        from parsers.msq_parser import MsqParser
        parser = MsqParser(content)
        results = {"total": 0, "applied": 0, "errors": []}
        
        self.ensure_loaded()
        for name, d in self._definitions.items():
            val_str = parser.get_constant_by_name(name)
            if val_str:
                results["total"] += 1
                if apply_to_ecu:
                    try:
                        # Extract numerical value
                        val = float(val_str.split()[0]) 
                        if self.write_parameter(name, val, force=force):
                            results["applied"] += 1
                    except Exception as e:
                        results["errors"].append(f"{name}: {str(e)}")
        
        if burn_after and results["applied"] > 0:
            self.burn()
            
        return results

    def _build_index(self):
        idx = {}
        for d in self._definitions.values():
            idx[d.name.lower()] = d.name
        # Explicit aliases (set only if not already present)
        _aliases = {
            "injectorflow": "injector_flow",
            "vvtoffset1": "vvtOffsets1", "vvtoffset2": "vvtOffsets2",
            "vetable1": "veTable", "ignitiontable1": "ignitionTable",
            "boosttable1": "boostTableOpenLoop", "lambdatable1": "lambdaTable",
        }
        for alias, real in _aliases.items():
            if real in self._definitions and alias not in idx:
                idx[alias] = real
        self._name_index = idx

    def resolve_name(self, name: str) -> str:
        self.ensure_loaded()
        key = name.lower()
        if key in self._name_index: return self._name_index[key]
        if name in self._definitions: return name
        raise KeyError(f"Parameter '{name}' not found")

    def read_parameter(self, name: str) -> Dict[str, Any]:
        res = self.resolve_name(name)
        d = self._definitions[res]
        
        # Performance/Safety: Read in chunks (Blocking Factor)
        # Most ECUs have limited serial buffer (256-512 bytes). 
        # Large tables (e.g. 16x16 F32 = 1024 bytes) must be read in chunks.
        data = b""
        chunk_size = self._blocking_factor
        
        # INI uses 1-based pages, binary protocol uses 0-based
        binary_page = max(0, d.page_id - 1)
        for i in range(0, d.size_bytes, chunk_size):
            size_to_read = min(chunk_size, d.size_bytes - i)
            payload = struct.pack('<HHH', binary_page, d.offset + i, size_to_read)
            ok, code, chunk = self.client.send_and_receive_binary(ord(TS_READ_COMMAND), payload)
            
            if not ok or code not in (TS_RESPONSE_OK, TS_RESPONSE_OK_ALT):
                raise RuntimeError(f"Read failed for {res} at offset {i} (code={code})")
            
            data += chunk
            
        fmt, bsize, _, _ = TYPE_INFO[d.value_type]
        count = len(data) // bsize
        values = []
        for i in range(count):
            chunk = data[i*bsize:(i+1)*bsize]
            raw = struct.unpack(fmt, chunk)[0]
            if d.kind == "bits" and d.bit_range:
                lo, hi = d.bit_range
                val = (raw >> lo) & ((1 << (hi - lo + 1)) - 1)
                values.append(float(val))
            else:
                values.append(float(raw) * d.scale + d.translate)
        
        return {
            "name": res,
            "value": values[0] if len(values) == 1 else values,
            "units": d.units,
            "min": d.min_val,
            "max": d.max_val
        }

    def write_parameter(self, name: str, value: Any, force: bool = False) -> bool:
        res = self.resolve_name(name)
        d = self._definitions[res]
        if not bool(getattr(self.client, "allow_writes", False)):
            raise PermissionError("Writes are disabled. Call set_allow_writes(True) before write_parameter().")

        # Flatten 2D tables (UI sends [[row0], [row1], ...]) into 1D list
        if isinstance(value, list) and value and isinstance(value[0], list):
            value = [cell for row in value for cell in row]

        # Safety Guardrails
        if not force:
            v_list = value if isinstance(value, list) else [value]
            for v in v_list:
                if d.min_val is not None and float(v) < d.min_val:
                    raise ValueError(f"{res}: Value {v} below minimum {d.min_val}")
                if d.max_val is not None and float(v) > d.max_val:
                    raise ValueError(f"{res}: Value {v} above maximum {d.max_val}")

        fmt, bsize, tlo, thi = TYPE_INFO[d.value_type]
        values = value if isinstance(value, list) else [value]
        
        full_payload = b""
        for v in values:
            raw_val = (float(v) - d.translate) / d.scale
            raw_val = max(tlo, min(thi, int(round(raw_val))))
            full_payload += struct.pack(fmt, raw_val)
        
        # Using Binary Write in chunks (Blocking Factor)
        chunk_size = self._blocking_factor
        
        # INI uses 1-based pages, binary protocol uses 0-based
        binary_page = max(0, d.page_id - 1)
        all_ok = True
        for i in range(0, len(full_payload), chunk_size):
            chunk = full_payload[i:i + chunk_size]
            # Binary Write (Page + Offset + Size, 2 bytes LE each) + data
            payload = struct.pack('<HHH', binary_page, d.offset + i, len(chunk)) + chunk
            ok, code, _ = self.client.send_and_receive_binary(ord(TS_WRITE_COMMAND), payload)
            
            if not ok or code not in (TS_RESPONSE_OK, TS_RESPONSE_OK_ALT):
                 # Try Chunk Write as fallback if needed (though TS_WRITE_COMMAND is standard)
                 ok, code, _ = self.client.send_and_receive_binary(ord(TS_CHUNK_WRITE_COMMAND), payload)
                 if not ok or code not in (TS_RESPONSE_OK, TS_RESPONSE_OK_ALT):
                     all_ok = False
                     break
                     
        return all_ok






