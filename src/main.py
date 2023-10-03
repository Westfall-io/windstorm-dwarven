import os

SQLDEF = "localhost:5432"
SQLHOST = os.environ.get("SQLHOST",SQLDEF)

import json
from typing import Union

import sqlalchemy as db
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .models import Commits, Models, Elements, Models_Elements, \
    Reqts, Verifications, Actions, Artifacts

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
]

app = FastAPI(openapi_tags=tags_metadata)

def connect():
    db_type = "postgresql"
    user = "postgres"
    passwd = "mysecretpassword"
    address = SQLHOST
    db_name = "sysml2"

    address = db_type+"://"+user+":"+passwd+"@"+address+"/"+db_name
    engine = db.create_engine(address)
    conn = engine.connect()

    return conn, engine

_, engine = connect()
with Session(engine) as session:

    ## Commit Table
    # /models/commits - Get list of all commits
    # /models/commits/{id} - Get specific commit
    # /models/refs - Get list of all branches
    # /models/refs/{ref} - Get list of all commits on branch
    ## Model Table
    # Internal Only
    ## Element Table
    # Internal Only
    ## Requirements Table
    # /models/requirements/main - Get all requirements on main
    # /models/requirements/requirement/{reqt_id} - Get specific requirement
    ## Verifications Table
    ## TODO: Fix multiple objects getting the same id.
    # /models/verifications/main - Get all verifications on main
    # /models/verifications/verification/{verifications_id} - Get specific verification
    ## Threads/Actions Table
    # /models/threads/main - Get all threads on main
    # /models/threads/thread/{thread_id} - Get specific thread
    ## Artifacts Table



    ## Commit Table
    @app.get("/models/commits", tags=["models"])
    def read_commits(size: Union[int, None] = 10):
        output = []
        results = session \
            .query(Commits) \
            .order_by(db.desc(Commits.date)) \
            .limit(size)
        for commit in results:
            output.append({
                'id': commit.id,
                'ref': commit.ref,
                'commit': commit.commit,
                'date': (commit.date).isoformat()
            })
        return output

    @app.get("/models/commits/{commit_id}", tags=["models"])
    def read_commit_id(commit_id: int):
        result = session \
            .query(Commits) \
            .filter(Commits.id==commit_id) \
            .first()

        if result is None:
            return JSONResponse(status_code=404, content={"message": "Item not found"})
        else:
            output = {
                'id': result.id,
                'ref': result.ref,
                'commit': result.commit,
                'date': (result.date).isoformat()
            }
            return output


    @app.get("/models/refs", tags=["models"])
    def read_refs(size: Union[int, None] = 10):
        output = []
        results = session \
            .query(Commits) \
            .distinct(Commits.ref) \
            .order_by(Commits.ref,db.desc(Commits.date)) \
            .limit(size)
        for commit in results:
            output.append({
                'id': commit.id,
                'ref': commit.ref,
                'commit': commit.commit,
                'date': (commit.date).isoformat()
            })
        return output

    @app.get("/models/refs/{ref:path}", tags=["models"])
    def read_ref(ref : str, size: Union[int, None] = 10):
        output = []
        results = session \
            .query(Commits) \
            .filter(Commits.ref==ref) \
            .order_by(Commits.ref,db.desc(Commits.date)) \
            .limit(size)
        for commit in results:
            output.append({
                'id': commit.id,
                'ref': commit.ref,
                'commit': commit.commit,
                'date': (commit.date).isoformat()
            })
        return output
    ## END Commit Table

    ## Requirements Table
    @app.get("/models/requirements/main", tags=["models"])
    def read_reqts(include_element: bool = False, size: Union[int, None] = 10):
        ''' Always uses main ref '''

        # Find the commit id for the latest
        MAIN_HEAD = 'master'
        commit = session \
            .query(Commits) \
            .filter(Commits.ref==MAIN_HEAD) \
            .order_by(db.desc(Commits.date)) \
            .first()
        if commit is None:
            MAIN_HEAD = 'main'
            commit = session \
                .query(Commits) \
                .filter(Commits.ref==MAIN_HEAD) \
                .order_by(db.desc(Commits.date)) \
                .first()
        if commit is None:
            return JSONResponse(status_code=404, content={"message": "Item not found"})

        output = []
        results = session \
            .query(Reqts) \
            .filter(Reqts.commit_id==commit.id) \
            .order_by(db.desc(Reqts.id)) \
            .limit(size)
        for reqt in results:

            reqt_e = session \
                .query(Elements) \
                .filter(Elements.id==reqt.element_id) \
                .first()
            payload = json.loads(reqt_e.element_text)

            if include_element:
                payload_out = payload
            else:
                payload_out = {}
            if not 'shortName' in payload['payload']:
                payload['payload']['shortName'] = ''

            output.append({
                'id': reqt.id,
                'commit_id': reqt.commit_id,
                'shortName': reqt.shortName,
                'qualifiedName': reqt.qualifiedName,
                'declaredName': reqt.declaredName,
                'text': payload['payload']['text'],
                'payload': payload_out,
            })
        return output

    @app.get("/models/requirements/requirement/{requirement_id}", tags=["models"])
    def read_reqt(requirement_id: int, include_element: bool = False):
        result = session \
            .query(Reqts) \
            .filter(Reqts.id==requirement_id) \
            .first()

        reqt_e = session \
            .query(Elements) \
            .filter(Elements.id==result.element_id) \
            .first()

        payload = json.loads(reqt_e.element_text)
        if include_element:
            payload_out = payload
        else:
            payload_out = {}

        output = {
            'id': result.id,
            'commit_id': result.commit_id,
            'shortName': result.shortName,
            'qualifiedName': result.qualifiedName,
            'declaredName': result.declaredName,
            'text': payload['payload']['text'],
            'payload': payload_out,
        }
        return output

    @app.get("/models/verifications", tags=["models"])
    def read_verifications(include_element: bool = False, size: Union[int, None] = 10):
        output = []
        results = session \
            .query(Verifications) \
            .order_by(db.desc(Verifications.id)) \
            .limit(size)

        for verify in results:
            verify_e = session \
                .query(Elements) \
                .filter(Elements.id==verify.element_id) \
                .first()

            reqt = session \
                .query(Reqts) \
                .filter(Reqts.id==verify.requirement_id) \
                .first()

            payload = json.loads(verify_e.element_text)
            if include_element:
                payload_out = payload
            else:
                payload_out = {}

            output.append({
                'id': verify.id,
                'commit_id': verify.commit_id,
                'reqt_id': verify.requirement_id,
                'reqt_shortName': reqt.shortName,
                'reqt_qualifiedName': reqt.qualifiedName,
                'reqt_declaredName': reqt.declaredName,
                'payload': payload_out,
            })
        return output

    @app.get("/models/verifications/main", tags=["models"])
    def read_verifications(include_element: bool = False, size: Union[int, None] = 10):
        # Find the commit id for the latest
        MAIN_HEAD = 'master'
        commit = session \
            .query(Commits) \
            .filter(Commits.ref==MAIN_HEAD) \
            .order_by(db.desc(Commits.date)) \
            .first()
        if commit is None:
            MAIN_HEAD = 'main'
            commit = session \
                .query(Commits) \
                .filter(Commits.ref==MAIN_HEAD) \
                .order_by(db.desc(Commits.date)) \
                .first()
        if commit is None:
            return JSONResponse(status_code=404, content={"message": "Item not found"})

        output = []
        results = session \
            .query(Verifications) \
            .filter(Verifications.commit_id==commit.id) \
            .order_by(db.desc(Verifications.id)) \
            .limit(size)

        for verify in results:
            verify_e = session \
                .query(Elements) \
                .filter(Elements.id==verify.element_id) \
                .first()

            reqt = session \
                .query(Reqts) \
                .filter(Reqts.id==verify.requirement_id) \
                .first()

            payload = json.loads(verify_e.element_text)
            if include_element:
                payload_out = payload
            else:
                payload_out = {}

            output.append({
                'id': verify.id,
                'commit_id': verify.commit_id,
                'reqt_id': verify.requirement_id,
                'reqt_shortName': reqt.shortName,
                'reqt_qualifiedName': reqt.qualifiedName,
                'reqt_declaredName': reqt.declaredName,
                'payload': payload_out,
            })
        return output

    @app.get("/models/threads", tags=["models"])
    def read_threads(include_element: bool = False, size: Union[int, None] = 10):
        output = []
        results = session \
            .query(Reqts) \
            .order_by(db.desc(Reqts.id)) \
            .limit(size)
        for reqt in results:
            reqt_e = session \
                .query(Elements) \
                .filter(Elements.id==reqt.element_id) \
                .first()
            payload = json.loads(reqt_e.element_text)
            if include_element:
                payload_out = payload
            else:
                payload_out = {}
            output.append({
                'id': reqt.id,
                'qualifiedName': reqt.name,
                'declaredName': payload['payload']['declaredName'],
                'text': payload['payload']['text'],
                'payload': payload_out,
            })
        return output

    # Get all artifacts in the repo, but only the first of this url and ref.
    @app.get("/artifacts", tags=["artifacts"])
    def read_artifacts(size: Union[int, None] = 10):
        output = []
        results = session \
            .query(Artifacts) \
            .distinct(Artifacts.commit_url, Artifacts.ref) \
            .order_by(Artifacts.commit_url, Artifacts.ref, db.desc(Artifacts.date)) \
            .limit(size)
        #if len(results) == 0:
        #    return JSONResponse(status_code=404, content={"message": "Item not found"})
        for commit in results:
            output.append({
                'id': commit.id,
                'full_name': commit.full_name,
                'commit_url': commit.commit_url,
                'ref': commit.ref,
                'commit': commit.commit,
                'date': (commit.date).isoformat()
            })
        return output

    # Get the commits associated with the main
    @app.get("/artifacts/main/commits", tags=["artifacts"])
    def read_commits(size: Union[int, None] = 10):
        output = []
        results = session \
            .query(Artifacts) \
            .order_by(db.desc(Artifacts.date)) \
            .limit(size)
        for commit in results:
            output.append({
                'id': commit.id,
                'full_name': commit.full_name,
                'commit_url': commit.commit_url,
                'ref': commit.ref,
                'commit': commit.commit,
                'date': (commit.date).isoformat()
            })
        return output

    # Get the artifact associated
    @app.get("/artifacts/ref/{ref_id}/commits", tags=["artifacts"])
    def read_commits(size: Union[int, None] = 10):
        output = []
        results = session \
            .query(Artifacts) \
            .order_by(db.desc(Artifacts.date)) \
            .limit(size)
        for commit in results:
            output.append({
                'id': commit.id,
                'full_name': commit.full_name,
                'commit_url': commit.commit_url,
                'ref': commit.ref,
                'commit': commit.commit,
                'date': (commit.date).isoformat()
            })
        return output

    @app.get("/containers", tags=["containers"])
    def read_commits(size: Union[int, None] = 10):
        output = []
        results = session \
            .query(Artifacts) \
            .order_by(db.desc(Artifacts.date)) \
            .limit(size)
        for commit in results:
            output.append({
                'id': commit.id,
                'full_name': commit.full_name,
                'commit_url': commit.commit_url,
                'ref': commit.ref,
                'commit': commit.commit,
                'date': (commit.date).isoformat()
            })
        return output
