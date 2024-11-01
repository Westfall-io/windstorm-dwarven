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

import os

# Get environment variables
SQLHOST = os.environ.get("SQLHOST","localhost:5432")
HARBORPATH = os.environ.get("HARBORPATH","core.harbor.domain/")

PGUSER = os.environ.get("PGUSER","postgres")
PGPASSWD = os.environ.get("PGPASSWD","mysecretpassword")
PGDBNAME = os.environ.get("PGDBNAME","pgdb")

KCREALM = os.environ.get("KCREALM","test")
KCADDR = os.environ.get("KCADDR","https://keycloak.digitalforge.app")

import json
import math
from uuid import uuid4 as uuid_gen

from typing import Union, Annotated
from datetime import datetime

import sqlalchemy as db
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

origins = [
    "https://windstorm-api.westfall.io",
    "https://digitalforge.westfall.io",
    "http://localhost",
    "http://localhost:8080",
    "https://windstorm-api.digitalforge.app",
]

from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import true

from pydantic import BaseModel

from database.db_model import Commits, Model_Repo, Models, Elements, \
    Models_Elements, Reqts, Verifications, Actions, Artifacts, \
    Artifacts_Commits, Containers, Container_Commits, Thread_Executions

from views.public import get_commit_view, get_reqts_view, get_verfs_view, \
    get_thread_view, get_threads_view, get_tes_view

def connect():
    db_type = "postgresql"
    user = PGUSER
    passwd = PGPASSWD
    address = SQLHOST
    db_name = PGDBNAME

    address = db_type+"://"+user+":"+passwd+"@"+address+"/"+db_name
    engine = db.create_engine(address)
    conn = engine.connect()

    return conn, engine

def get_harbor(container, session):
    if container is None:
        return None, 'No container was specified, check metadata in model.'

    if not 'app://' == container[:6]:
        return None, 'The action is invalidly defines a container, it should start with app://.'

    container_path = HARBORPATH+container[6:]
    container_result = session \
        .query(Containers.id, Containers.resource_url, Containers.project,
               Containers.image, Containers.tag, Container_Commits.digest,
               Container_Commits.date, Container_Commits.id.label("container_commit_id")) \
        .join(Container_Commits, Containers.id == Container_Commits.containers_id) \
        .filter(Containers.resource_url == container_path) \
        .order_by(db.desc(Container_Commits.date)) \
        .first()

    if container_result is None:
        return None, 'The action is could not find a registered container. Ensure the image/tag ({}) exists and webhooks have fired.'.format(container[6:])

    return container_result, None

def build_action(result, none_msg, output, session):
    if result is None:
        output['total'] = 0
        output['results_per_page'] = 0
        output['results'] = {
            'error': none_msg
        }
        return output

    output['total'] = 1
    output['results_per_page'] = 1

    if not 'git://' == result.artifacts[:6]:
        output['results'] = {
            'error': 'The action is invalidly defines an artifact, it should start with git://.'
        }
        return output

    full_name = result.artifacts[6:]
    ps = full_name.split('/')
    if len(ps) == 2:
        full_name = full_name
        ref = "main"
    elif len(ps) == 3:
        full_name = "/".join([ps[0],ps[1]])
        ref = ps[2]
    else:
        output['results'] = {
            'error': 'The action is invalidly defined. It is not specified in the following format -- git://organization/repository or git://organization/repository/branch'
        }
        return output

    artifact_result = session \
        .query(Artifacts.id, Artifacts.full_name, Artifacts.commit_url,
               Artifacts_Commits.ref, Artifacts_Commits.commit,
               Artifacts_Commits.date) \
        .join(Artifacts_Commits, Artifacts.id == Artifacts_Commits.artifacts_id) \
        .filter(Artifacts.full_name == full_name,
                Artifacts_Commits.ref == ref
        ) \
        .order_by(db.desc(Artifacts_Commits.date)) \
        .first()

    if artifact_result is None:
        output['results'] = {
            'error': 'The action is could not find a registered artifact. Ensure the repo ({}) exists and webhooks have fired.'.format(full_name)
        }
        return output

    container_result, err = get_harbor(result.harbor, session)

    if container_result is None:
        output['results'] = {
            'error': err
        }
        return output

    output['results'] = [{
        'id' : result.id,
        'declaredName': result.declaredName,
        'qualifiedName': result.qualifiedName,
        'verifications_id': result.verifications_id,
        'artifact': {
            'id': artifact_result.id,
            'full_name': artifact_result.full_name,
            'commit_url': artifact_result.commit_url,
            'ref': artifact_result.ref,
            'commit': artifact_result.commit,
            'date':artifact_result.date
        },
        'container': {
            'id': container_result.id,
            'resource_url': container_result.resource_url,
            'project': container_result.project,
            'image': container_result.image,
            'tag': container_result.tag,
            'digest': container_result.digest,
            'date': container_result.date
        },
        'variables': json.loads(result.variables),
        'dependency': result.dependency
    }]
    return output

def get_artifact_from_uri(uri, session):
    # Input is git://Westfall/python-sample
    if uri is None:
        return None, 'No artifact uri was specified, check metadata in model.'

    if not 'git://' == uri[:6]:
        return None, 'The action is invalidly defines a container, it should start with app://.'

    artifact_path = uri[6:]

    artifact_result = session \
        .query(Artifacts.id, Artifacts.full_name, Artifacts.commit_url,
               Artifacts_Commits.ref, Artifacts_Commits.commit,
               Artifacts_Commits.date, Artifacts_Commits.id.label("artifact_commit_id")) \
        .join(Artifacts_Commits, Artifacts.id == Artifacts_Commits.artifacts_id) \
        .filter(Artifacts.full_name == artifact_path) \
        .order_by(db.desc(Artifacts.id)) \
        .first()

    if artifact_result is None:
        return None, 'The action could not find a registered artifact. Ensure the git repo ({}) exists and webhooks have fired.'.format(uri[6:])

    return artifact_result, None

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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _, engine = connect()
    session = Session(engine)

    ## Commit Table
    @app.get("/models/commits", tags=["models"])
    def read_commits(size: Union[int, None] = 10):
        if db.inspect(engine).has_table("commits"):
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
                    'processed': commit.processed,
                    'date': (commit.date).isoformat()
                })
            return output
        else:
            return {'error_message': 'Table does not exist.'}

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
                'processed': commit.processed,
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

    @app.get("/models/verifications/{verification_id}", tags=["models"])
    def get_verification(verification_id: int):
        verification = session \
            .query(Verifications) \
            .filter(Verifications.id == verification_id) \
            .first()

        output = {}
        output['pages'] = 1
        output['page'] = 1

        if verification is not None:
            output['total'] = 1
            output['results_per_page'] = 1
            output['results'] = [{
                'commit_id': verification.commit_id,
                'element_id': verification.element_id,
                'requirement_id': verification.requirement_id,
                'verified': verification.verified,
                'attempted': verification.attempted,
            }]
        else:
            output['total'] = 0
            output['results_per_page'] = 0
            output['results'] = []

        return output

    @app.put("/models/verifications/{verification_id}", tags=["models"], dependencies=[Depends(valid_access_token)])
    def verify(verification_id: int, verify: bool):
        verification = session \
            .query(Verifications) \
            .filter(Verifications.id == verification_id) \
            .first()

        if verification is not None:
            result = session \
                .query(Verifications) \
                .filter(Verifications.id == verification_id) \
                .update({'verified': verify})
            session.commit()

            return verify
        else:
            return {'error': 'verification not found'}

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

    @app.get("/models/threads/thread/{thread_id}", tags=["models"])
    def read_thread(thread_id: int, validate: Union[bool, None]=False):

        if validate:
            result = session \
                .query(Actions.id, Actions.declaredName, Actions.qualifiedName,
                       Actions.harbor, Actions.artifacts, Actions.variables,
                       Actions.dependency, Actions.verifications_id) \
                .join(Verifications, Verifications.id == Actions.verifications_id) \
                .filter(Actions.id == thread_id,
                        Actions.valid == true()
                ) \
                .first()
        else:
            result = session \
                .query(Actions.id, Actions.declaredName, Actions.qualifiedName,
                       Actions.harbor, Actions.artifacts, Actions.variables,
                       Actions.dependency, Actions.verifications_id) \
                .join(Verifications, Verifications.id == Actions.verifications_id) \
                .filter(Actions.id == thread_id) \
                .first()

        output = {}
        output['pages'] = 1
        output['page'] = 1
        output['validated'] = validate

        output = build_action(result, 'The action/thread has invalid/missing tool metadata.', output, session)
        return output

    @app.get("/models/threads/dependency/{thread_id}", tags=["models"])
    def find_dependency(thread_id: int, validate: Union[bool, None]=False):
        # Only one response, for right now.
        if validate:
            result = session \
                .query(Actions.id, Actions.declaredName, Actions.qualifiedName,
                       Actions.harbor, Actions.artifacts, Actions.variables,
                       Actions.dependency, Actions.verifications_id) \
                .filter(Actions.dependency == thread_id,
                        Actions.valid == true(),
                ) \
                .first()
        else:
            result = session \
                .query(Actions.id, Actions.declaredName, Actions.qualifiedName,
                       Actions.harbor, Actions.artifacts, Actions.variables,
                       Actions.dependency, Actions.verifications_id) \
                .filter(Actions.dependency == thread_id,
                ) \
                .first()

        output = {}
        output['pages'] = 1
        output['page'] = 1
        output['valid_only'] = validate

        output = build_action(result, 'There are no valid dependencies.', output, session)
        return output

    @app.get("/models/threads/all/main", tags=["models"])
    def read_threads(
        size: Union[int, None] = 10,
        page: Union[int, None] = 1,
        valid_only: Union[bool, None] = True):
        output = {}

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

        if valid_only:
            total = session \
                .query(Actions.id) \
                .join(Verifications) \
                .filter(Verifications.id == Actions.verifications_id,
                        Verifications.commit_id==commit.id,
                        Actions.valid == true()
                ) \
                .count()
        else:
            total = session \
                .query(Actions.id) \
                .join(Verifications) \
                .filter(Verifications.id == Actions.verifications_id,
                    Verifications.commit_id==commit.id
                ) \
                .count()

        output['total'] = total
        output['pages'] = math.ceil(total/size)
        output['page'] = page
        output['valid_only'] = valid_only
        output['results_per_page'] = size
        output['results'] = []

        if valid_only:
            results = session \
                .query(Actions) \
                .join(Verifications) \
                .filter(Verifications.id == Actions.verifications_id,
                    Verifications.commit_id==commit.id,
                    Actions.valid == true()
                ) \
                .order_by(db.desc(Actions.id)) \
                .limit(size) \
                .offset((page-1)*size)
        else:
            results = session \
                .query(Actions) \
                .join(Verifications) \
                .filter(Verifications.id == Actions.verifications_id,
                        Verifications.commit_id==commit.id
                ) \
                .order_by(db.desc(Actions.id)) \
                .limit(size) \
                .offset((page-1)*size)

        for action in results:
            output['results'].append({
                'id': action.id,
                'qualifiedName': action.qualifiedName,
                'declaredName': action.declaredName,
                'harbor': action.harbor,
                'artifacts': action.artifacts,
                'variables': action.variables,
                'valid': action.valid
            })
        return output

    @app.get("/models/threads/branch_search/{ref:path}", tags=["models"])
    def find_model_threads(ref : str, validate: bool=True, updated: bool=False):
        '''
        This endpoint is to find all threads that match this ref id.

        This is useful for windstorm-mage to query to match all models that match
        the given branch.

        '''
        output = {}

        if updated:
            # Compare the head to the previous commit to filter actions that
            # don't need to be executed.
            results = session \
                .query(Commits.id, Commits.commit) \
                .filter(Commits.ref == ref,
                        Commits.processed==True) \
                .distinct(Commits.ref) \
                .order_by(Commits.ref,db.desc(Commits.date)) \
                .limit(2)

            main_commit = None
            prev_commit = None
            for result in results:
                if main_commit is None:
                    main_commit = result
                else:
                    prev_commit = result
        else:
            # Pass all actions
            main_commit = session \
                .query(Commits.id, Commits.commit) \
                .filter(Commits.ref == ref,
                        Commits.processed==True) \
                .distinct(Commits.ref) \
                .order_by(Commits.ref,db.desc(Commits.date)) \
                .first()
            prev_commit = None

        if main_commit is not None:
            # Grab all actions that match:
            # 1. This commit
            # 2. The action is valid (i.e. it also has a harbor)
            if validate:
                results = session \
                    .query(Actions) \
                    .filter(Actions.commit_id==main_commit.id,
                        Actions.valid == true()
                    ) \
                    .all()
            else:
                results = session \
                    .query(Actions) \
                    .filter(Actions.commit_id==main_commit.id,
                    ) \
                    .all()

            if prev_commit is None:
                total = results
            else:
                total = []
                for result in results:
                    prev_result = session \
                        .query(Actions) \
                        .filter(Actions.commit_id==prev_commit.id,
                                Actions.qualifiedName==result.qualifiedName
                        ) \
                        .first()
                    if result.harbor == prev_result.harbor and \
                        result.artifacts == prev_result.artifacts and \
                        result.variables == prev_result.variables:
                        # No changes, no need to rerun this one
                        pass
                    else:
                        total.append(result)
                # End for result
            #

        else:
            # Create an empty list to store a response
            total = []

        total2 = []
        ids = {}
        for thread in total:
            container, _ = get_harbor(thread.harbor, session)
            if container is None and validate:
                # Skip this thread
                continue
            artifacts, _ = get_artifact_from_uri(thread.artifacts, session)
            if artifacts is None and validate:
                # Skip this thread
                continue

            total2.append(thread)

            if container is None:
                c_id = None
                cc_id = None
                c_digest = None
            else:
                c_id = container.id
                cc_id = container.container_commit_id
                c_digest = container.digest

            if artifacts is None:
                a_id = None
                ac_id = None
                a_hash = None
            else:
                a_id = artifacts.id
                ac_id = artifacts.artifact_commit_id
                a_hash = artifacts.commit

            ids[thread.id] = {
                'container_id': c_id,
                'container_commit_id': cc_id,
                'container_digest': c_digest,
                'artifact_id': a_id,
                'artifact_commit_id': ac_id,
                'artifact_hash': a_hash
            }

        output['results'] = []

        # Put data into dictionary rather than list.
        for action in total2:
            output['results'].append({
                'id': action.id,
                'qualifiedName': action.qualifiedName,
                'dependency': action.dependency,
                'model_commit_id': main_commit.id,
                'model_commit_hash': main_commit.commit,
                'container_id': ids[action.id]['container_id'],
                'container_commit_id': ids[action.id]['container_commit_id'],
                'container_digest': ids[action.id]['container_digest'],
                'artifact_id': ids[action.id]['artifact_id'],
                'artifact_commit_id': ids[action.id]['artifact_commit_id'],
                'artifact_commit_hash': ids[action.id]['artifact_hash'],
            })

        # Create summary data
        output['total'] = len(output['results'])
        output['pages'] = 1
        output['page'] = 1
        output['results_per_page'] = len(output['results'])

        return output

    @app.get("/models/threads/artifact_search/{artifact_id}", tags=["models"])
    def find_artifact_threads(
        artifact_id : int,
        validate: bool = True,
        ):
        '''
        This endpoint is to find all threads that match this artifact id.

        This is useful for windstorm-mage to query to match all models that match
        the given artifact.

        '''
        output = {}

        # Grab the artifact full name
        artifacts = session \
            .query(Artifacts.id, Artifacts.full_name, Artifacts_Commits.commit,
                   Artifacts_Commits.id.label('artifact_commits_id')) \
            .join(Artifacts_Commits, Artifacts.id == Artifacts_Commits.artifacts_id) \
            .filter(Artifacts.id == artifact_id) \
            .first()

        if artifacts is None:
            # Couldn't find this artifact.
            total = []
        else:
            # The matching uri comes from the gitea full_name key:
            # Ex. "full_name": "Westfall/sysml_workflow"
            uri = 'git://'+artifacts.full_name

            # Grab all of the model commit heads (i.e. all the branches), limited
            # to the latest date
            results = session \
                .query(Commits.id) \
                .filter(Commits.processed==True) \
                .distinct(Commits.ref) \
                .order_by(Commits.ref,db.desc(Commits.date)) \
                .all()

            # Create an empty list to store a response
            total = []
            for commit in results:
                # Search all possible ref heads

                # Grab all actions that match:
                # 1. This commit
                # 2. This uri as the artifact
                # 3. The action is valid (i.e. it also has a harbor)
                r = session \
                    .query(Actions.id, Actions.qualifiedName,
                           Actions.dependency, Actions.harbor,
                           Verifications.commit_id) \
                    .join(Verifications) \
                    .filter(Verifications.id == Actions.verifications_id,
                        Verifications.commit_id==commit.id,
                        Actions.artifacts == uri,
                        Actions.valid == true()
                    ) \
                    .all()

                for result in r:
                    total.append(result)

        output['results'] = []

        # Put data into dictionary rather than list.
        for action in total:

            main_commit = session \
                .query(Commits.id, Commits.commit) \
                .filter(Commits.id==action.commit_id) \
                .first()

            container, _ = get_harbor(action.harbor, session)
            if container is None:
                c_id = None
                cc_id = None
                c_digest = None
            else:
                c_id = container.id
                cc_id = container.container_commit_id
                c_digest = container.digest

            if validate and c_id is not None:
                output['results'].append({
                    'id': action.id,
                    'qualifiedName': action.qualifiedName,
                    'dependency': action.dependency,
                    'model_commit_id': main_commit.id,
                    'model_commit_hash': main_commit.commit,
                    'container_id': c_id,
                    'container_commit_id': cc_id,
                    'container_digest': c_digest,
                    'artifact_id': artifacts.id,
                    'artifact_commit_id': artifacts.artifact_commits_id,
                    'artifact_commit_hash': artifacts.commit,
                })
            elif not validate:
                output['results'].append({
                    'id': action.id,
                    'qualifiedName': action.qualifiedName,
                    'dependency': action.dependency,
                    'model_commit_id': main_commit.id,
                    'model_commit_hash': main_commit.commit,
                    'container_id': c_id,
                    'container_commit_id': cc_id,
                    'container_digest': c_digest,
                    'artifact_id': artifacts.id,
                    'artifact_commit_id': artifacts.artifact_commits_id,
                    'artifact_commit_hash': artifacts.commit,
                })
            else:
                # Skip if validate and c_id is None
                pass

        # Create summary data
        output['total'] = len(output['results'])
        output['pages'] = 1
        output['page'] = 1
        output['results_per_page'] = len(output['results'])

        return output

    @app.get("/models/threads/container_search/{container_id}", tags=["models"])
    def find_container_threads(
        container_id : int,
        validate : bool = True,
        ):
        '''
        This endpoint is to find all threads that match this container id.

        This is useful for windstorm-mage to query to match all models that match
        the given container.

        '''
        output = {}

        # Grab the container
        containers = session \
            .query(Containers.id, Containers.resource_url, Containers.project,
                   Containers.image, Containers.tag, Container_Commits.digest,
                   Container_Commits.date, Container_Commits.id.label("container_commit_id")) \
            .join(Container_Commits, Containers.id == Container_Commits.containers_id) \
            .filter(Containers.id == container_id) \
            .first()

        if containers is None:
            results = []
        else:
            # If container's tag is latest, we can leave off
            if containers.tag == 'latest':
                uri = 'app://'+containers.project+'/'+containers.image
            else:
                uri = 'app://'+containers.project+'/'+containers.image+":"+containers.tag

            # Grab all of the model commit heads (i.e. all the branches), limited
            # to the latest date
            results = session \
                .query(Commits.id) \
                .filter(Commits.processed==True) \
                .distinct(Commits.ref) \
                .order_by(Commits.ref,db.desc(Commits.date)) \
                .all()

        # Create an empty list to store a response
        total = []
        for commit in results:
            # Search all possible ref heads

            # Grab all actions that match:
            # 1. This commit
            # 2. This uri as the container
            # 3. The action is valid (i.e. it also has a artifact)
            r = session \
                .query(Actions.id, Actions.qualifiedName, Actions.dependency,
                       Actions.artifacts, Verifications.commit_id) \
                .join(Verifications) \
                .filter(Verifications.id == Actions.verifications_id,
                    Verifications.commit_id==commit.id,
                    Actions.harbor == uri,
                    Actions.valid == true()
                ) \
                .all()

            for result in r:
                total.append(result)

        output['results'] = []

        # Put data into dictionary rather than list.
        for action in total:
            main_commit = session \
                .query(Commits.id, Commits.commit) \
                .filter(Commits.id==action.commit_id) \
                .first()

            artifacts, _ = get_artifact_from_uri(action.artifacts, session)
            if artifacts is None:
                a_id = None
                ac_id = None
                a_hash = None
            else:
                a_id = artifacts.id
                ac_id = artifacts.artifact_commit_id
                a_hash = artifacts.commit

            if validate and a_id is not None:
                output['results'].append({
                    'id': action.id,
                    'qualifiedName': action.qualifiedName,
                    'dependency': action.dependency,
                    'model_commit_id': main_commit.id,
                    'model_commit_hash': main_commit.commit,
                    'container_id': containers.id,
                    'container_commit_id': containers.container_commit_id,
                    'container_digest': containers.digest,
                    'artifact_id': a_id,
                    'artifact_commit_id': ac_id,
                    'artifact_commit_hash': a_hash,
                })
            elif not validate:
                output['results'].append({
                    'id': action.id,
                    'qualifiedName': action.qualifiedName,
                    'dependency': action.dependency,
                    'model_commit_id': main_commit.id,
                    'model_commit_hash': main_commit.commit,
                    'container_id': container_id,
                    'container_commit_id': containers.container_commit_id,
                    'container_digest': containers.digest,
                    'artifact_id': a_id,
                    'artifact_commit_id': ac_id,
                    'artifact_commit_hash': a_hash,
                })
            else:
                # Skip if validate and c_id is None
                pass

        # Create summary data
        output['total'] = len(output['results'])
        output['pages'] = 1
        output['page'] = 1
        output['results_per_page'] = len(output['results'])

        return output

    # Get all artifacts in the repo, but only the first of this url and ref.
    @app.get("/artifacts", tags=["artifacts"])
    def read_artifacts(size: Union[int, None] = 10):
        output = []
        results = session \
            .query(Artifacts, Artifacts_Commits) \
            .join(Artifacts_Commits) \
            .filter(Artifacts.id == Artifacts_Commits.artifacts_id and
                (
                    Artifacts_Commits.ref == 'main' or
                    Artifacts_Commits.ref == 'master'
                )
            ) \
            .order_by(db.desc(Artifacts_Commits.date)) \
            .limit(size)

        for result in results:
            artifact = result[0]
            commit = result[1]
            output.append({
                'id': artifact.id,
                'full_name': artifact.full_name,
                'commit_url': artifact.commit_url,
                'ref': commit.ref,
                'commit': commit.commit,
                'date_updated': commit.date
            })
        return output

    @app.get("/artifacts/count", tags=["artifacts"])
    def count_artifacts(size: Union[int, None] = 10):
        output = []
        results = session \
            .query(Artifacts, Artifacts_Commits) \
            .join(Artifacts_Commits) \
            .filter(Artifacts.id == Artifacts_Commits.artifacts_id and
                (
                    Artifacts_Commits.ref == 'main' or
                    Artifacts_Commits.ref == 'master'
                )
            ) \
            .order_by(db.desc(Artifacts_Commits.date)) \
            .all()

        output = {
            'size': len(results),
            'pages': math.ceil(len(results)/size)
        }
        return output

    # Get all refs for this artifact.
    @app.get("/artifacts/{artifact_id}/refs", tags=["artifacts"])
    def read_artifact_refs(artifact_id: int, size: Union[int, None] = 10):
        output = []
        results = session \
            .query(Artifacts, Artifacts_Commits) \
            .join(Artifacts_Commits) \
            .filter(Artifacts.id == Artifacts_Commits.artifacts_id and
                (
                    Artifacts.id == artifact_id
                )
            ) \
            .order_by(db.desc(Artifacts_Commits.date)) \
            .limit(size)

        for result in results:
            artifact = result[0]
            commit = result[1]
            output.append({
                'id': artifact.id,
                'full_name': artifact.full_name,
                'commit_url': artifact.commit_url,
                'ref': commit.ref,
                'commit': commit.commit,
                'date_updated': commit.date
            })
        return output

    # Get all refs for this artifact.
    @app.get("/artifacts/{artifact_id}/main", tags=["artifacts"])
    def read_artifact_refs(artifact_id: int, size: Union[int, None] = 10):
        output = []
        result = session \
            .query(Artifacts, Artifacts_Commits) \
            .join(Artifacts_Commits) \
            .filter(Artifacts.id == Artifacts_Commits.artifacts_id and
                Artifacts.id == artifact_id and
                (
                    Artifacts_Commits.ref == 'main' or
                    Artifacts_Commits.ref == 'master'
                )
            ) \
            .order_by(db.desc(Artifacts_Commits.date)) \
            .first()

        if result is not None:
            artifact = result[0]
            commit = result[1]
            output = {
                'id': artifact.id,
                'full_name': artifact.full_name,
                'commit_url': artifact.commit_url,
                'ref': commit.ref,
                'commit': commit.commit,
                'date_updated': commit.date
            }
        return output

    # Get the artifact associated
    @app.get("/artifacts/{artifact_id}/refs/{ref_name}/commits", tags=["artifacts"])
    def read_commits(artifact_id: int, ref_name: str, size: Union[int, None] = 10):
        output = []
        results = session \
            .query(Artifacts_Commits) \
            .filter(Artifacts_Commits.artifacts_id == artifact_id and
                Artifacts_Commits.ref == ref_name
            ) \
            .order_by(db.desc(Artifacts_Commits.date)) \
            .limit(size)
        for commit in results:
            output.append({
                'id': commit.id,
                'commit': commit.commit,
                'date': (commit.date).isoformat()
            })
        return output

################################################################################
# Containers
################################################################################
    @app.get("/containers", tags=["containers"])
    def read_containers(
        size: Union[int, None] = 10,
        page: Union[int, None] = 1,
        ):
        output = {}
        total = session \
            .query(Containers.id) \
            .join(Container_Commits, Container_Commits.containers_id == Containers.id) \
            .distinct(Containers.resource_url) \
            .order_by(Containers.resource_url, db.desc(Container_Commits.date)) \
            .count()

        results = session \
            .query(
                Containers.id, Containers.resource_url, Containers.host,
                Containers.project, Containers.image, Containers.tag,
                Container_Commits.digest, Container_Commits.date,
            ) \
            .join(Container_Commits, Container_Commits.containers_id == Containers.id) \
            .distinct(Containers.resource_url) \
            .order_by(Containers.resource_url, db.desc(Container_Commits.date)) \
            .limit(size)

        output['total'] = total
        output['pages'] = math.ceil(total/size)
        output['page'] = page
        output['results_per_page'] = size
        output['results'] = []

        for container in results:
            output['results'].append({
                'id': container.id,
                'resource_url': container.resource_url,
                'host': container.host,
                'project': container.project,
                'image': container.image,
                'tag': container.tag,
                'digest': container.digest,
                'date': (container.date).isoformat()
            })
        return output

    ############################################################################
    # These are specific API calls for web front end.

    ## Dashboard Page
    @app.get("/views/count_models/", tags=["views"])
    def view_model_count():
        output = {}
        models = session \
            .query(Model_Repo) \
            .count()
        output['models'] = models
        return output

    @app.get("/views/count_requirements/", tags=["views"])
    def view_requirements_count():
        output = {}
        model = session \
            .query(Model_Repo.default_branch) \
            .first()

        if model is None:
            output['requirements'] = 0
            return output

        head_commit = session \
            .query(Commits.id) \
            .filter(Commits.ref==model.default_branch,
                    Commits.processed==True) \
            .order_by(Commits.ref, db.desc(Commits.date)) \
            .first()

        if head_commit is None:
            output['requirements'] = 0
            return output

        reqts_count = session \
            .query(Reqts.id) \
            .filter(Reqts.commit_id == head_commit.id) \
            .order_by(Reqts.id) \
            .count()
        output['requirements'] = reqts_count
        return output

    @app.get("/views/count_threads/", tags=["views"])
    def view_thread_count():
        output = {}
        model = session \
            .query(Model_Repo.default_branch) \
            .first()

        if model is None:
            output['threads'] = 0
            return output

        head_commit = session \
            .query(Commits.id) \
            .filter(Commits.ref==model.default_branch,
                    Commits.processed==True) \
            .order_by(Commits.ref, db.desc(Commits.date)) \
            .first()

        if head_commit is None:
            output['threads'] = 0
            return output

        acts_count = session \
            .query(Actions.id) \
            .filter(Actions.commit_id == head_commit.id) \
            .order_by(Actions.id) \
            .count()
        output['threads'] = acts_count
        return output

    ## Commit Page
    @app.get("/views/model_commits/", tags=["views"])
    def view_model_commits(size: Union[int, None] = 10, page: Union[int, None] = 1):
        return get_commit_view(session, None, size, page)

    @app.get("/views/model_commits/{branch}", tags=["views"])
    def view_model_commits(branch:str, size: Union[int, None] = 10, page: Union[int, None] = 1):
        return get_commit_view(session, branch, size, page)

    @app.get("/views/model_branches/", tags=["views"])
    def view_model_branches(size: Union[int, None] = 10, page: Union[int, None] = 1):

        model = session \
            .query(Model_Repo) \
            .first()

        if model is None:
            return {'error': 'No models have been pushed to windstorm db.'}

        refs_cnt = session \
            .query(Commits.id) \
            .distinct(Commits.ref) \
            .order_by(Commits.ref,db.desc(Commits.date)) \
            .count()

        refs = session \
            .query(Commits) \
            .distinct(Commits.ref) \
            .order_by(Commits.ref, db.desc(Commits.date)) \
            .limit(size) \
            .offset((page-1)*size)

        output = {}
        output['total'] = refs_cnt
        output['pages'] = math.ceil(refs_cnt/size)
        output['page'] = page
        output['results_per_page'] = size
        output['default_branch'] = model.default_branch
        output['model_path'] = model.full_name
        output['results'] = []

        for ref in refs:
            r = {
                'id': ref.id,
                'branch': ref.ref,
                'commit': ref.commit,
                'date': ref.date
            }
            output['results'].append(r)

        return output

    ## Artifacts
    @app.get("/views/artifacts/", tags=["views"])
    def view_artifacts(size: Union[int, None] = 10, page: Union[int, None] = 1):

        artifacts_cnt = session \
            .query(Artifacts.id) \
            .count()

        results = session \
            .query(Artifacts, Artifacts_Commits) \
            .join(Artifacts_Commits, Artifacts.id == Artifacts_Commits.artifacts_id) \
            .order_by(db.desc(Artifacts_Commits.date)) \
            .limit(size) \
            .offset((page-1)*size)

        output = {}
        output['total'] = artifacts_cnt
        output['pages'] = math.ceil(artifacts_cnt/size)
        output['page'] = page
        output['results_per_page'] = size
        output['results'] = []

        for result in results:
            artifact = result[0]
            commit = result[1]
            output['results'].append({
                'id': artifact.id,
                'full_name': artifact.full_name,
                'commit_url': artifact.commit_url,
                'default_branch': artifact.default_branch,
                'ref': commit.ref,
                'commit': commit.commit,
                'date_updated': commit.date
            })
        return output

    ## Artifacts
    @app.get("/views/containers/", tags=["views"])
    def view_containers(size: Union[int, None] = 10, page: Union[int, None] = 1):

        containers_cnt = session \
            .query(Containers.id) \
            .distinct(Containers.project, Containers.image) \
            .count()

        results = session \
            .query(Containers, Container_Commits) \
            .join(Container_Commits, Containers.id == Container_Commits.containers_id) \
            .distinct(Containers.project, Containers.image) \
            .order_by(Containers.project, Containers.image, db.desc(Container_Commits.date)) \
            .limit(size) \
            .offset((page-1)*size)

        output = {}
        output['total'] = containers_cnt
        output['pages'] = math.ceil(containers_cnt/size)
        output['page'] = page
        output['results_per_page'] = size
        output['results'] = []

        for result in results:
            container = result[0]
            commit = result[1]
            output['results'].append({
                'id': container.id,
                'project': container.project,
                'project_id': container.project_id,
                'image': container.image,
                'image_id': container.image_id,
                'tag': container.tag,
                'date_updated': commit.date
            })
        return output

    ## Requirements Page
    @app.get("/views/requirements/", tags=["views"])
    def view_reqts_main(size: Union[int, None] = 10, page: Union[int, None] = 1):
        return get_reqts_view(session, None, size, page)

    @app.get("/views/requirements/{ref}", tags=["views"])
    def view_reqts(ref: str, size: Union[int, None] = 10, page: Union[int, None] = 1):
        return get_reqts_view(session, ref, size, page)

    ## Requirement Page
    @app.get("/views/requirement/{requirement_id}", tags=["views"])
    def view_reqt(requirement_id: int, size: Union[int, None] = 10, page: Union[int, None] = 1):
        reqt = session \
            .query(Reqts) \
            .filter(Reqts.id == requirement_id) \
            .first()

        reqt_e = session \
            .query(Elements) \
            .filter(Elements.id==reqt.element_id) \
            .first()

        payload = json.loads(reqt_e.element_text)

        vs_tot = session \
            .query(Verifications) \
            .filter(Verifications.requirement_id==reqt.id) \
            .count()

        output = {
            'id': reqt.id,
            'shortName': reqt.shortName,
            'declaredName': reqt.declaredName,
            'qualifiedName': reqt.qualifiedName,
            'text': "".join(payload['payload']['text']).replace('\n',''),
        }

        verifications = {}
        verifications['total'] = vs_tot
        verifications['pages'] = math.ceil(vs_tot/size)
        verifications['page'] = page
        verifications['results_per_page'] = size
        verifications['results'] = []

        if vs_tot > 0:
            vs = session \
                .query(Verifications) \
                .filter(Verifications.requirement_id==reqt.id) \
                .order_by(Verifications.id) \
                .limit(size) \
                .offset((page-1)*size)

            for v in vs:
                v_e = session \
                    .query(Elements) \
                    .filter(Elements.id==v.element_id) \
                    .first()

                payload_v = json.loads(v_e.element_text)

                actions = session \
                    .query(Actions.id) \
                    .filter(Actions.verifications_id==v.id) \
                    .count()

                this_v = {
                    'id': v.id,
                    'qualifiedName': payload_v['payload']['qualifiedName'],
                    'declaredName': payload_v['payload']['declaredName'],
                    'verified': v.verified,
                    'attempted': v.attempted,
                    'linkedActions': actions
                }
                verifications['results'].append(this_v)

        output['verifications'] = verifications

        return output

    ## Verification Page
    @app.get("/views/verification/{verification_id}", tags=["views"])
    def view_v(verification_id: int, size: Union[int, None] = 10, page: Union[int, None] = 1):
        v = session \
            .query(Verifications) \
            .filter(Verifications.id == verification_id) \
            .first()

        r = session \
            .query(Reqts) \
            .filter(Reqts.id == v.requirement_id) \
            .first()

        if r is not None:
            rid = r.id
            rname = r.declaredName
            rqname = r.qualifiedName
        else:
            rid = None
            rname = None
            rqname = None


        requirement = {
            'id': rid,
            'declaredName': rname,
            'qualifiedName': rqname
        }

        v_e = session \
            .query(Elements) \
            .filter(Elements.id==v.element_id) \
            .first()

        payload = json.loads(v_e.element_text)

        as_tot = session \
            .query(Actions) \
            .filter(Actions.verifications_id==v.id) \
            .count()

        output = {
            'id': v.id,
            'qualifiedName': payload['payload']['qualifiedName'],
            'declaredName': payload['payload']['declaredName'],
            'requirement': requirement
        }

        actions = {}
        actions['total'] = as_tot
        actions['pages'] = math.ceil(as_tot/size)
        actions['page'] = page
        actions['results_per_page'] = size
        actions['results'] = []

        if as_tot > 0:
            acts = session \
                .query(Actions) \
                .filter(Actions.verifications_id==v.id) \
                .order_by(Actions.id) \
                .limit(size) \
                .offset((page-1)*size)

            for a in acts:
                a_e = session \
                    .query(Elements) \
                    .filter(Elements.id==a.element_id) \
                    .first()

                payload_a = json.loads(v_e.element_text)

                container_result, _ = get_harbor(a.harbor, session)
                if container_result is not None:
                    addr = 'https://'+container_result.resource_url
                    cvalid = True
                else:
                    addr = ''
                    cvalid = False

                this_a = {
                    'id': a.id,
                    'qualifiedName': a.qualifiedName,
                    'declaredName': a.declaredName,
                    'container': addr,
                    'container_valid': cvalid,
                    'artifacts': a.artifacts,
                    'artifacts_valid': True,
                    'valid': a.valid,
                }
                actions['results'].append(this_a)

        output['actions'] = actions

        return output

    @app.get("/views/verifications/", tags=["views"])
    def view_verfs_main(size: Union[int, None] = 10, page: Union[int, None] = 1):
        return get_verfs_view(session, None, size, page)

    @app.get("/views/verifications/{ref}", tags=["views"])
    def view_verfs(ref: str, size: Union[int, None] = 10, page: Union[int, None] = 1):
        return get_verfs_view(session, ref, size, page)

    @app.get("/views/thread/{thread_id}", tags=["views"])
    def view_action(thread_id: int, size: Union[int, None] = 10, page: Union[int, None] = 1):
        return get_thread_view(session, thread_id, size, page)

    @app.get("/views/threads/", tags=["views"])
    def view_actions_main(size: Union[int, None] = 10, page: Union[int, None] = 1):
        return get_threads_view(session, None, size, page)

    @app.get("/views/threads/{ref}", tags=["views"])
    def view_actions(ref: str, size: Union[int, None] = 10, page: Union[int, None] = 1):
        return get_threads_view(session, ref, size, page)

    @app.get("/views/thread_executions/", tags=["views"])
    def view_tes(size: Union[int, None] = 10, page: Union[int, None] = 1):
        return get_tes_view(session, size, page)

    class Status(BaseModel):
        status: str

    @app.put("/auth/update_thread/{thread_id}", tags=["auth"], dependencies=[Depends(valid_access_token)])
    def update_te(thread_id: int, status: Status):
        if status.status == 'windrunner_1':
            # No input files
            st = status.status
        elif status.status == 'windrunner_2':
            # Now input files
            st = status.status
        elif status.status == 'windchest_1':
            # Run is done
            st = status.status
        elif status.status == 'windchest_2':
            # Complete
            st = status.status
        else:
            st = "unknown"

        result = session \
            .query(Thread_Executions.id, Thread_Executions.state) \
            .filter(Thread_Executions.id == thread_id) \
            .first()

        if result is not None:
            result = session \
                .query(Thread_Executions) \
                .filter(Thread_Executions.id == thread_id) \
                .update({'state': st,
                         'date_updated': datetime.utcnow()
                })

            session.commit()
            result = session \
                .query(Thread_Executions.id, Thread_Executions.name,
                       Thread_Executions.state) \
                .filter(Thread_Executions.id == thread_id) \
                .first()
            return {'id':result.id, 'name': result.name, 'state': result.state}
        else:
            return {'error': 'Not found'}

    @app.put("/auth/add_thread/{action_id}", tags=["auth"], dependencies=[Depends(valid_access_token)])
    def auth_add_thread(action_id: int):
        action = session \
            .query(Actions) \
            .filter(Actions.id==action_id) \
            .first()

        if action is None:
            return {'error': 'No thread found with this id.'}

        container, _ = get_harbor(action.harbor, session)
        if container is not None:
            cc_id = container.container_commit_id
        else:
            return {'error': 'No container found'}

        artifacts, _ = get_artifact_from_uri(action.artifacts, session)
        if artifacts is not None:
            ac_id = artifacts.artifact_commit_id
        else:
            return {'error': 'No artifact found'}

        dtn = datetime.now()
        te = Thread_Executions(
            name = str(uuid_gen()),
            action_id = action.id,
            model_commit_id = action.commit_id,
            container_commit_id = cc_id,
            artifact_commit_id = ac_id,
            source = 'storm', # Only matters if going to mage, but we're not.
            state = 'windstorm',
            date_created = dtn,
            date_updated = dtn,
        )
        session.add(te)
        session.commit()
        session.refresh(te)

        a = build_action(action, '', {}, session)['results'][0]
        return {'thread': a, 'thread_execution_id': te.id}

    return app

if __name__ == "__main__":
    main()
