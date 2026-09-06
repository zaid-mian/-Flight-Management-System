import hmac
import hashlib
import time
import json
import base64
import os
from typing import Dict, Any

# Secret key for signing approval tokens (defaults to secure system secret if not in env)
SECRET_KEY = os.getenv("APPROVAL_TOKEN_SECRET", "flight_agent_hackathon_secure_approval_secret_2026")

def generate_approval_token(booking_id: str, action: str, expires_in_seconds: int = 3600) -> str:
    """Generates a cryptographically signed HMAC-SHA256 approval token."""
    exp = int(time.time()) + expires_in_seconds
    payload = {
        "booking_id": booking_id,
        "action": action,
        "exp": exp
    }
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    signature = hmac.new(SECRET_KEY.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    token_data = {
        "payload": payload,
        "sig": signature
    }
    return base64.urlsafe_b64encode(json.dumps(token_data).encode("utf-8")).decode("utf-8")


def verify_approval_token(token: str, expected_booking_id: str, expected_action: str) -> Dict[str, Any]:
    """Verifies approval token integrity, signature, expiration, and cross-resource matching."""
    try:
        raw_json = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        token_data = json.loads(raw_json)
        
        payload = token_data.get("payload", {})
        signature = token_data.get("sig", "")
        
        # 1. Verify HMAC Signature
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        expected_sig = hmac.new(SECRET_KEY.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
        
        if not hmac.compare_digest(signature, expected_sig):
            return {"valid": False, "reason": "TAMPERED_TOKEN_SIGNATURE_INVALID"}
            
        # 2. Check Expiration
        exp = payload.get("exp", 0)
        if time.time() > exp:
            return {"valid": False, "reason": "APPROVAL_TOKEN_EXPIRED"}
            
        # 3. Check Booking ID Mismatch (Cross-Resource protection)
        if payload.get("booking_id") != expected_booking_id:
            return {"valid": False, "reason": "BOOKING_ID_MISMATCH"}
            
        # 4. Check Action Mismatch
        if payload.get("action") != expected_action:
            return {"valid": False, "reason": "ACTION_MISMATCH"}
            
        return {"valid": True, "payload": payload}
    except Exception as e:
        return {"valid": False, "reason": f"MALFORMED_TOKEN ({type(e).__name__})"}
