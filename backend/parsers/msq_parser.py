import xml.etree.ElementTree as ET
import os
from datetime import datetime
from typing import Dict, List, Optional
import io

# We import CalibrationSnapshot for type hinting, but we must do it carefully
# to avoid circular imports if this is called from the schemas file.
# However, usually schemas are at the top.
try:
    from ..app.schemas import CalibrationSnapshot
except (ImportError, ValueError):
    # Fallback for standalone testing
    CalibrationSnapshot = None

class MsqParser:
    """
    Robust rusEFI MSQ parser and exporter.
    Correctly extracts tables (VE, Ignition, Boost) and their axes.
    Generates valid .msq files for TunerStudio/rusEFI.
    """
    def __init__(self, filepath_or_content: str | bytes):
        self.root = None
        if isinstance(filepath_or_content, bytes):
            self.root = ET.fromstring(filepath_or_content)
        elif isinstance(filepath_or_content, str):
            if os.path.exists(filepath_or_content):
                tree = ET.parse(filepath_or_content)
                self.root = tree.getroot()
            else:
                # Assume it might be an XML string
                try:
                    self.root = ET.fromstring(filepath_or_content)
                except ET.ParseError:
                    self.root = None
        else:
            self.root = None

    def get_constant_by_name(self, name: str) -> Optional[str]:
        if self.root is None:
            return None
        # Handle both old and new rusEFI MSQ formats:
        # 1. Direct children of a page: //page/constant[@name='...']
        # 2. Nested or flattened: .//constant[@name='...']
        constant = self.root.find(f".//constant[@name='{name}']")
        if constant is not None:
            return constant.text
        return None

    def parse_array(self, text: str) -> List[float]:
        if not text:
            return []
        # Handle multi-line, tabs, and extra whitespace
        return [float(v) for v in text.replace("\n", " ").replace("\t", " ").split() if v.strip()]

    def extract_table(self, table_name: str, x_axis_name: str, y_axis_name: str) -> dict:
        """
        Locates a TunerStudio MSQ table and extracts its 
        Z values along with X and Y bins.
        """
        result = {
            "name": table_name,
            "x_axis": self.parse_array(self.get_constant_by_name(x_axis_name) or ""),
            "y_axis": self.parse_array(self.get_constant_by_name(y_axis_name) or ""),
            "z_values": []
        }
        
        raw_z = self.parse_array(self.get_constant_by_name(table_name) or "")
        if raw_z and result["x_axis"]:
            x_len = len(result["x_axis"])
            result["z_values"] = [raw_z[i:i + x_len] for i in range(0, len(raw_z), x_len)]
        else:
            result["z_values"] = raw_z
            
        return result

    def extract_calibration(self) -> Optional['CalibrationSnapshot']:
        """Extracts the core tuning tables into a CalibrationSnapshot."""
        if CalibrationSnapshot is None:
            return None
            
        # 1. Extract Axes
        rpm_axis = self.parse_array(self.get_constant_by_name("rpmBins1") or "")
        map_axis = self.parse_array(self.get_constant_by_name("mapBins1") or "")
        
        # 2. Extract Tables
        ve_raw = self.parse_array(self.get_constant_by_name("veTable1") or "")
        ign_raw = self.parse_array(self.get_constant_by_name("ignitionTable1") or "")
        boost_raw = self.parse_array(self.get_constant_by_name("boostTable1") or "")

        x_len = len(rpm_axis) if rpm_axis else 16
        
        def reshape(raw: List[float], x_len: int):
            if not raw or x_len == 0: return [[0.0]*16 for _ in range(16)]
            return [raw[i:i + x_len] for i in range(0, len(raw), x_len)]

        return CalibrationSnapshot(
            axes={
                "rpm": rpm_axis if rpm_axis else [500 + i*500 for i in range(16)],
                "map_kpa": map_axis if map_axis else [30 + i*15 for i in range(16)]
            },
            fuel_table=reshape(ve_raw, x_len),
            ignition_table=reshape(ign_raw, x_len),
            boost_table=reshape(boost_raw, x_len),
            metadata={"source": "msq_import"}
        )

    def export_msq(self, snapshot: 'CalibrationSnapshot', output_path: str) -> None:
        """
        Takes a CalibrationSnapshot and generates a valid rusEFI .msq XML file.
        """
        root = ET.Element("tunersq")
        page = ET.SubElement(root, "page")
        
        def add_const(name: str, values: List):
            const = ET.SubElement(page, "constant", name=name)
            if values and isinstance(values[0], list): # 2D Table
                flat = [item for sublist in values for item in sublist]
                const.text = "\n" + " ".join(f"{v:.2f}" for v in flat) + "\n"
            else: # 1D Axis
                const.text = "\n" + " ".join(f"{v:.2f}" for v in values) + "\n"

        add_const("rpmBins1", snapshot.axes["rpm"])
        add_const("mapBins1", snapshot.axes["map_kpa"])
        add_const("veTable1", snapshot.fuel_table)
        add_const("ignitionTable1", snapshot.ignition_table)
        add_const("boostTable1", snapshot.boost_table)
        
        ET.SubElement(root, "bibliography", author="AI BaseTune Architect", date=str(datetime.now()) if 'datetime' in globals() else "")
        
        tree = ET.ElementTree(root)
        with open(output_path, "wb") as f:
            tree.write(f, encoding='utf-8', xml_declaration=True)
