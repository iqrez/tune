import requests
import json
try:
    resp = requests.get("http://localhost:8001/api/v1/parameters/list")
    print("STATUS:", resp.status_code)
    data = resp.json()
    params = data.get("parameters", [])
    names = [p.get("name") for p in params]
    print("TOTAL PARAMS:", len(names))
    print("SAMPLE PARAMS:", names[:50])
except Exception as e:
    print("ERR:", e)
