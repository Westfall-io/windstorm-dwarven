from typing import Union

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
