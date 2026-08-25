import os
import hmac
import hashlib
import base64
import json
from typing import Optional

SECRET = os.environ.get("CCC_SECRET", "ccc-dev-secret-change-me").encode()

def hash_pw(pw: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", str(pw).encode(), salt, 120000)
    return "pbkdf2$120000$%s$%s" % (salt.hex(), dk.hex())

def verify_pw(pw: str, stored: str) -> bool:
    try:
        _, it, salt, h = str(stored).split("$")
        return hmac.compare_digest(
            hashlib.pbkdf2_hmac("sha256", str(pw).encode(), bytes.fromhex(salt), int(it)).hex(),
            h
        )
    except Exception:
        return False

def mktoken(p: dict) -> str:
    b = base64.urlsafe_b64encode(json.dumps(p).encode()).decode().rstrip("=")
    return b + "." + hmac.new(SECRET, b.encode(), hashlib.sha256).hexdigest()[:20]

def parse_token(t: str) -> Optional[dict]:
    try:
        b, s = str(t).split(".")
        if hmac.new(SECRET, b.encode(), hashlib.sha256).hexdigest()[:20] != s:
            return None
        return json.loads(base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)))
    except Exception:
        return None
