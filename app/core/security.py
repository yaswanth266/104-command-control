import os
import hmac
import hashlib
import base64
import json
import time
from typing import Optional

_MIN_SECRET_LEN = 16
_env_secret = os.environ.get("CCC_SECRET")
_secret_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".secret")

if _env_secret and len(_env_secret) >= _MIN_SECRET_LEN:
    SECRET = _env_secret.encode()
else:
    if os.path.exists(_secret_file):
        with open(_secret_file, "r") as f:
            SECRET = f.read().strip().encode()
    else:
        import secrets
        SECRET = secrets.token_hex(32).encode()
        with open(_secret_file, "w") as f:
            f.write(SECRET.decode())

TOKEN_TTL_SECONDS = int(os.environ.get("CCC_TOKEN_TTL_SECONDS", 12 * 3600))

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
    payload = dict(p)
    payload["iat"] = int(time.time())
    payload["exp"] = payload["iat"] + TOKEN_TTL_SECONDS
    b = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return b + "." + hmac.new(SECRET, b.encode(), hashlib.sha256).hexdigest()[:20]

def parse_token(t: str) -> Optional[dict]:
    try:
        b, s = str(t).split(".")
        if hmac.new(SECRET, b.encode(), hashlib.sha256).hexdigest()[:20] != s:
            return None
        payload = json.loads(base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)))
        if "exp" in payload and time.time() > payload["exp"]:
            return None
        return payload
    except Exception:
        return None
