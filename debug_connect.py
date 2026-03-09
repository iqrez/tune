import urllib.request
import json

payload = json.dumps({
    "connection_type": "serial",
    "serial_port": None,
    "host": None,
    "port": None
}).encode('utf-8')

req = urllib.request.Request(
    'http://127.0.0.1:8000/api/v1/rusefi/connect',
    data=payload,
    headers={'Content-Type': 'application/json'}
)

try:
    with urllib.request.urlopen(req) as response:
        print("Status:", response.status)
        print("Response:", response.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code)
    print("Response:", e.read().decode('utf-8'))
except Exception as e:
    print("Error:", e)
