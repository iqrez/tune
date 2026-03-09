import requests
import json
import os

def check_tables():
    port = 8000
    port_file = os.path.join("backend", ".port")
    if os.path.exists(port_file):
        with open(port_file, "r") as f:
            port = int(f.read().strip())
    
    url = f"http://localhost:{port}/api/v1"
    print(f"Connecting to {url}")
    
    try:
        # First ensure we are connected (assuming the user has connected)
        # We'll just try to load veTable1
        resp = requests.post(f"{url}/tables/load", json={"table_name": "veTable1"}, timeout=5)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"Table Name: {data.get('table_name')}")
            print(f"Rows: {data.get('rows')}, Cols: {data.get('cols')}")
            print(f"Data length: {len(data.get('data', []))}")
            if data.get('data'):
                 print(f"First row length: {len(data.get('data')[0])}")
            print(f"RPM Axis length: {len(data.get('rpm_axis', []))}")
            print(f"MAP Axis length: {len(data.get('map_axis', []))}")
        else:
            print(f"Error: {resp.text}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    check_tables()
