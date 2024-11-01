# Copyright (c) 2023-2024 Westfall Inc.
#
# This file is part of Windstorm-Dwarven.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, and can be found in the file NOTICE inside this
# git repository.
#
# This program is distributed in the hope that it will be useful
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

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

import sqlalchemy as db
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import true
from sqlalchemy.exc import OperationalError

def connect():
    db_type = "postgresql"
    user = PGUSER
    passwd = PGPASSWD
    address = SQLHOST
    db_name = PGDBNAME

    address = db_type+"://"+user+":"+passwd+"@"+address+"/"+db_name
    engine = db.create_engine(address)
    print(passwd)
    conn = engine.connect()

    return conn, engine

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

    _, engine = connect()
    session = Session(engine)

    @app.get("/")
    def read_root():
        return {"Hello": "World2"}


    @app.get("/private", dependencies=[Depends(valid_access_token)])
    def get_private():
        return {"message": "Ce endpoint est privé"}

    return app
