import os

from ascender.common.api_docs import DefineAPIDocs
from ascender.core.database import provideDatabase, ORMEnum
from ascender.core.router import provideRouter
from ascender.core.types import IBootstrap

from attp.providers import provideAttp
from attp.server.auth_hmac import HmacAuthStrategy

from routes import routes
from settings import DATABASE_CONNECTION


# ATTP_CONFIG_PATH = os.getenv("ATTP_CONFIG")
ATTP_MAX_PAYLOAD = int(os.getenv("ATTP_MAX_PAYLOAD_SIZE", "10048576"))

auth_strategy = HmacAuthStrategy(
    secret={"env": "ATTP_SHARED_SECRET"},
    allowed_nodes=["main", "peer-1", "peer-2"],
    ttl_seconds=30,
    max_clock_skew=5,
)


appBootstrap: IBootstrap = {
    "providers": [
        {
            "provide": DefineAPIDocs,
            "value": DefineAPIDocs(swagger_url="/docs", redoc_url="/redoc"),
        },
        provideRouter(routes),
        provideDatabase(ORMEnum.SQLALCHEMY, DATABASE_CONNECTION),
        provideAttp(
            auth_strategy=auth_strategy,
            # config_path=ATTP_CONFIG_PATH,
            default_limits={"max_payload_size": ATTP_MAX_PAYLOAD},
        ),
    ]
}
