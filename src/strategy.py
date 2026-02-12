from typing import Any

from pydantic import validate_call
from attp.client.authenticator import ConnectionAuthenticator
from attp.server.abc.auth_strategy import AuthStrategy


class TestStrategy(AuthStrategy):
    def __init__(self, token: str) -> None:
        super().__init__()
        self.token = token
        self.AUTH_TIMEOUT = 10
    
    @validate_call(config={"arbitrary_types_allowed": True})
    async def authenticate(self, namespace: str, frame: str) -> bool:
        # Frame is token.
        return frame == self.token



class TestConnector(ConnectionAuthenticator):
    async def authenticate(self):
        return 