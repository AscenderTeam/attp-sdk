import hashlib
import hmac
import os
import secrets
import time
from typing import Any, Mapping

from attp.shared.secrets import resolve_secret_if_ref, parse_secret_ref, SecretRef


class ConnectionAuthenticator:
    def __init__(
        self, 
        conn_uri: str, 
        namespace: str,
        authorization: Any | None = None,
        data: Any | None = None
    ) -> None:
        self.authorization = authorization
        self.conn_uri = conn_uri
        self.namespace = namespace
        self.data = data
        self.AUTH_TIMEOUT = float(os.getenv("ATTP_CLIENT_CONNECTION_TIMEOUT", 10))
    
    async def authenticate(self):
        """
        Method is invoked when authentication process starts.
        Usually server requires protocol authentication, and the connection authenticator signs the 
        """
        return resolve_secret_if_ref(self.authorization)
    
    async def send_hello(self):
        """
        Method is invoked only after authentication, to send the `data` given on `__init__` to the remote peer.
        This method is mandatory for handshake part, for future authentications, it 
        """
        return self.data


class HmacConnectionAuthenticator(ConnectionAuthenticator):
    def __init__(
        self,
        conn_uri: str,
        namespace: str,
        *,
        secret: str | SecretRef | Mapping[str, Any],
        node_id: str | None = None,
        key_id: str | None = None,
        ttl_seconds: int = 30,
        max_clock_skew: int = 5,
    ) -> None:
        super().__init__(conn_uri, namespace, authorization=None, data=None)
        self._secret_ref = parse_secret_ref(secret)
        if self._secret_ref is None:
            raise TypeError("secret must be a string or secret reference.")

        self.node_id = node_id or os.getenv("ATTP_NODE_ID") or "node"
        self.key_id = key_id
        self.ttl_seconds = ttl_seconds
        self.max_clock_skew = max_clock_skew
        self.AUTH_TIMEOUT = float(
            os.getenv("ATTP_CLIENT_CONNECTION_TIMEOUT", ttl_seconds + max_clock_skew + 5)
        )

    def _sign(self, ts: int, nonce: str) -> str:
        secret = self._secret_ref.resolve() # type: ignore
        message = f"{self.namespace}:{self.node_id}:{ts}:{nonce}".encode("utf-8")
        return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

    async def authenticate(self):
        ts = int(time.time())
        nonce = secrets.token_hex(16)
        sig = self._sign(ts, nonce)

        payload = {
            "alg": "HS256",
            "ts": ts,
            "nonce": nonce,
            "sig": sig,
            "node_id": self.node_id,
        }
        if self.key_id:
            payload["kid"] = self.key_id
        return payload
