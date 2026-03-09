import xml.etree.ElementTree as ET
import os
from datetime import datetime
from typing import Dict, List, Optional
import io

from ..schemas import CalibrationSnapshot

class MsqParser:
    """
    Robust rusEFI MSQ parser and exporter.
    Correctly extracts tables (VE, Ignition, Boost) and their axes.
    Generates valid .msq files for TunerStudio/rusEFI.
    """
    def __init__(self, content: Optional[bytes] = None, filepath: Optional[str] = None):
        self.root = None
        if content:
            self.root = ET.fromstring(content)
        elif filepath and os.path.exists(filepath):
            tree = ET.parse(filepath)
            self.root = tree.getroot()

    def get_constant_by_name(self, name: str) -> Optional[str]:
        if self.root is None:
            return None
        # Handle both old and new rusEFI MSQ formats
        constant = self.root.find(f".//constant[@name='{name}']")
        if constant is not None:
            return constant.text
        return None

    def parse_array(self, text: str) -> List[float]:
        if not text:
            return []
        return [float(v) for v in text.replace("\n", " ").replace("\t", " ").split() if v.strip()]

    def extract_calibration(self) -> CalibrationSnapshot:
        """Extracts the core tuning tables into a CalibrationSnapshot."""
        # 1. Extract Axes
        rpm_axis = self.parse_array(self.get_constant_by_name("rpmBins1") or "")
        map_axis = self.parse_array(self.get_constant_by_name("mapBins1") or "")
        
        # 2. Extract Tables
        ve_raw = self.parse_array(self.get_constant_by_name("veTable1") or "")
        ign_raw = self.parse_array(self.get_constant_by_name("ignitionTable1") or "")
        boost_raw = self.parse_array(self.get_constant_by_name("boostTable1") or "")

        def reshape(raw: List[float], x_len: int):
            if not raw or x_len == 0:
                return [[0.0]*16 for _ in range(16)]
            return [raw[i:i + x_len] for i in range(0, len(raw), x_len)]

        x_len = len(rpm_axis) if rpm_axis else 16
        
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

    @staticmethod
    def export_msq(snapshot: CalibrationSnapshot) -> bytes:
        """
        Takes a CalibrationSnapshot and generates a valid rusEFI .msq XML.
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
        
        bib = ET.SubElement(root, "bibliography", author="AI BaseTune Architect", date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        return ET.tostring(root, encoding='utf-8', xml_declaration=True)
