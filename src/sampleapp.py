from env import *

from typing import Union, Annotated

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2AuthorizationCodeBearer

from jwt import PyJWKClient
import jwt

oauth_2_scheme = OAuth2AuthorizationCodeBearer(
    tokenUrl=KCADDR+"/"+KCREALM+"/protocol/openid-connect/token",
    authorizationUrl=KCADDR+"/"+KCREALM+"/protocol/openid-connect/auth",
    refreshUrl=KCADDR+"/"+KCREALM+"/protocol/openid-connect/token",
)

async def valid_access_token(
    access_token: Annotated[str, Depends(oauth_2_scheme)]
):
    url = KCADDR+"/"+KCREALM+"/protocol/openid-connect/certs"
    optional_custom_headers = {"User-agent": "custom-user-agent"}
    jwks_client = PyJWKClient(url, headers=optional_custom_headers)

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(access_token)
        data = jwt.decode(
            access_token,
            signing_key.key,
            algorithms=["RS256"],
            audience="api",
            options={"verify_exp": True},
        )
        return data
    except jwt.exceptions.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Not authenticated")

def main():
    tags_metadata = [
        {
            "name": "artifacts",
            "description": "Get details about git-config repos.",
        },
        {
            "name": "containers",
            "description": "Get details about registered containers.",
        },
        {
            "name": "models",
            "description": "Get details about models.",
        },
        {
            "name": "views",
            "description": "View data for the front-end.",
        },
        {
            "name": "auth",
            "description": "Future authenticated requests.",
        }
    ]

    app = FastAPI(openapi_tags=tags_metadata)

    origins = [
        "https://windstorm-api.westfall.io",
        "https://digitalforge.westfall.io",
        "http://localhost",
        "http://localhost:8080",
        "https://windstorm-api.digitalforge.app",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    def read_root():
        return {"Hello": "World2"}


    @app.get("/items/{item_id}")
    def read_item(item_id: int, q: Union[str, None] = None):
        return {"item_id": item_id, "q": q}

    return app
