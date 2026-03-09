import hmac
import hashlib
import json
import base64
import os

# In a real app, this would be generated once and stored in the OS keychain (e.g. DPAPI)
# For this milestone, we'll store it in a local hidden file
SECRET_KEY_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '.secret.key')

def get_or_create_key() -> bytes:
    if os.path.exists(SECRET_KEY_PATH):
        with open(SECRET_KEY_PATH, 'rb') as f:
            return f.read()
    else:
        new_key = os.urandom(32)
        with open(SECRET_KEY_PATH, 'wb') as f:
            f.write(new_key)
        return new_key

SECRET_KEY = get_or_create_key()

def sign_payload(payload_dict: dict) -> str:
    """
    Creates an HMAC-SHA256 signature for a dictionary payload.
    The dictionary is serialized to a canonical JSON string (sorted keys).
    """
    # Canonicalize the JSON so it's deterministic
    canonical_json = json.dumps(payload_dict, sort_keys=True, separators=(',', ':'))
    
    mac = hmac.new(SECRET_KEY, msg=canonical_json.encode('utf-8'), digestmod=hashlib.sha256)
    return base64.b64encode(mac.digest()).decode('utf-8')

def verify_signature(payload_dict: dict, signature: str) -> bool:
    """
    Verifies that the provided signature matches the payload.
    """
    expected_signature = sign_payload(payload_dict)
    return hmac.compare_digest(expected_signature, signature)
