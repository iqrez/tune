import xml.etree.ElementTree as ET
import json
import os

class MsqParser:
    def __init__(self, filepath: str):
        self.filepath = filepath
        try:
            self.tree = ET.parse(filepath)
            self.root = self.tree.getroot()
        except ET.ParseError as e:
            print(f"Failed to parse MSQ XML: {e}")
            self.root = None

    def extract_table(self, table_name: str, x_axis_name: str, y_axis_name: str) -> dict:
        """
        Locates a TunerStudio MSQ table (e.g., 'veTable1') and extracts its 
        Z values along with X (RPM) and Y (MAP) bins.
        """
        if self.root is None:
            return {}

        result = {
            "name": table_name,
            "x_axis": [],
            "y_axis": [],
            "z_values": []
        }

        # TunerStudio .msq stores arrays in <page> or <constant> nodes usually.
        # This is a simplified extraction looking for common TS patterns.
        # In a real TS MSQ, it's typically <constant name="veTable1" ...> 
        # For this prototype we will simulate the extraction if nodes are missing 
        # or parse them if they match the standard format.
        
        # Look for standard <constant> tags
        for constant in self.root.findall(".//constant"):
            name = constant.get("name")
            if name == x_axis_name:
                result["x_axis"] = [float(v) for v in constant.text.split()]
            elif name == y_axis_name:
                result["y_axis"] = [float(v) for v in constant.text.split()]
            elif name == table_name:
                # Z values are usually serialized row by row
                raw_z = [float(v) for v in constant.text.split()]
                
                # Reshape into 2D array if we have the axes
                if len(result["x_axis"]) > 0 and len(result["y_axis"]) > 0:
                    x_len = len(result["x_axis"])
                    reshaped = [raw_z[i:i + x_len] for i in range(0, len(raw_z), x_len)]
                    result["z_values"] = reshaped
                else:
                    result["z_values"] = raw_z
                    
        return result

if __name__ == "__main__":
    # Test stub
    parser = MsqParser("test.msq")
    ve = parser.extract_table("veTable1", "rpmBins1", "mapBins1")
    print(json.dumps(ve, indent=2))
