import hmac
import hashlib
import json
import base64
import time
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from fastapi import Request
from pydantic import BaseModel

logger = logging.getLogger("api.auth")

try:
    import jwt as pyjwt
except ImportError:
    pyjwt = None


class UserPrincipal(BaseModel):
    id: str
    email: str
    name: str
    role: Optional[str] = None


class AuthProvider(ABC):
    @abstractmethod
    async def authenticate(self, request: Request) -> Optional[UserPrincipal]:
        """
        Authenticate the request and return a UserPrincipal, or None if authentication fails.
        """
        pass


class HeaderAuthProvider(AuthProvider):
    async def authenticate(self, request: Request) -> Optional[UserPrincipal]:
        """
        A simple replaceable provider that extracts user info from headers.
        Useful for local dev, testing, or gateway-delegated auth.
        """
        user_id = request.headers.get("X-User-ID")
        email = request.headers.get("X-User-Email")
        name = request.headers.get("X-User-Name", "Default User")

        if not email:
            # Fall back to Authorization header format if present (e.g. Bearer test_user@org.com)
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                raw_token = auth_header[7:].strip()
                # If token looks like a simple email
                if "@" in raw_token and not raw_token.startswith("ey"):
                    email = raw_token
                    if not user_id:
                        user_id = f"usr_{email.replace('@', '_').replace('.', '_')}"
                else:
                    return None
            else:
                return None

        if not user_id:
            user_id = f"usr_{email.replace('@', '_').replace('.', '_')}"

        return UserPrincipal(id=user_id, email=email, name=name)


class JWTAuthProvider(AuthProvider):
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm

    def create_token(self, payload: Dict[str, Any], expires_in: int = 3600) -> str:
        """
        Utility method to generate a signed JWT token.
        """
        payload_copy = payload.copy()
        payload_copy["exp"] = int(time.time()) + expires_in
        if pyjwt:
            return pyjwt.encode(payload_copy, self.secret_key, algorithm=self.algorithm)
        
        # Standard library HMAC-SHA256 JWT builder fallback
        header = {"alg": "HS256", "typ": "JWT"}
        header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload_copy).encode()).decode().rstrip("=")
        sig_input = f"{header_b64}.{payload_b64}".encode()
        signature = hmac.new(self.secret_key.encode(), sig_input, hashlib.sha256).digest()
        sig_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")
        return f"{header_b64}.{payload_b64}.{sig_b64}"

    async def authenticate(self, request: Request) -> Optional[UserPrincipal]:
        """
        Verifies Bearer JWT token from Authorization header.
        """
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header[7:].strip()
        if not token:
            return None

        payload = None
        if pyjwt:
            try:
                payload = pyjwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            except Exception as e:
                logger.warning(f"PyJWT decode failed: {e}")
                return None
        else:
            # Native HMAC-SHA256 signature and claim verification
            parts = token.split(".")
            if len(parts) != 3:
                return None
            header_b64, payload_b64, sig_b64 = parts
            
            # Recompute signature
            def b64_decode(data: str) -> bytes:
                padded = data + "=" * (4 - len(data) % 4)
                return base64.urlsafe_b64decode(padded.encode())

            try:
                sig_input = f"{header_b64}.{payload_b64}".encode()
                expected_sig = hmac.new(self.secret_key.encode(), sig_input, hashlib.sha256).digest()
                actual_sig = b64_decode(sig_b64)
                if not hmac.compare_digest(expected_sig, actual_sig):
                    logger.warning("JWT signature verification failed")
                    return None
                
                payload = json.loads(b64_decode(payload_b64).decode())
            except Exception as e:
                logger.warning(f"Native JWT decode failed: {e}")
                return None

        if not payload:
            return None

        # Verify expiration
        exp = payload.get("exp")
        if exp and time.time() > float(exp):
            logger.warning("JWT token has expired")
            return None

        user_id = payload.get("sub") or payload.get("user_id") or payload.get("id")
        email = payload.get("email")
        name = payload.get("name", "Authenticated User")
        role = payload.get("role")

        if not user_id or not email:
            return None

        return UserPrincipal(id=str(user_id), email=str(email), name=str(name), role=role)

