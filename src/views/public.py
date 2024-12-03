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

minio_access_key = os.environ.get("MINIOACCESSKEY")
minio_secret_key = os.environ.get("MINIOSECRETKEY")

import math
import json

import ssl
from urllib.parse import urlparse
import socket

def get_certificate(url: str) -> str:
    """Download certificate from remote server.

    Args:
        url (str): url to get certificate from

    Returns:
        str: certificate string in PEM format
    """
    parsed_url = urlparse(url)

    hostname = parsed_url.hostname
    port = int(parsed_url.port or 443)
    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    sock = context.wrap_socket(conn, server_hostname=hostname)
    sock.connect((hostname, port))
    return ssl.DER_cert_to_PEM_cert(sock.getpeercert(True))

with open('minio.pem', 'w') as f:
    f.write(get_certificate('https://storage.digitalforge.app'))

import urllib3

httpClient = urllib3.ProxyManager(
    'https://storage.digitalforge.app/',
    timeout=urllib3.Timeout.DEFAULT_TIMEOUT,
    cert_reqs='CERT_NONE',
    assert_hostname=False,
    #ca_certs='minio.pem'
)

httpClient = urllib3.PoolManager(
                cert_reqs='CERT_REQUIRED',
                ca_certs='minio.pem')

from datetime import timedelta

import sqlalchemy as db

from minio import Minio
from minio.error import S3Error
from minio.commonconfig import GOVERNANCE, Tags
from minio.retention import Retention

#client = Minio(
#        "storage-minio.artifacts:9000",
#        access_key="CcgP5DINKOfemEXcjYyL",
#        secret_key="YS62HYwroWYozFGoWyeZjYsmGwFLEULu047lquE6",
#        secure=False,
#    )

client = Minio(
    "storage.digitalforge.app",
    access_key=minio_access_key,
    secret_key=minio_secret_key,
    secure=True,
    http_client=httpClient
)

from database.db_model import Commits, Model_Repo, Models, Elements, \
    Models_Elements, Reqts, Verifications, Actions, Artifacts, \
    Artifacts_Commits, Containers, Container_Commits, Thread_Executions

def get_commit_view(session, branch, size, page):

    model = session \
        .query(Model_Repo) \
        .first()

    if model is None:
        default_branch = None
    else:
        default_branch = model.default_branch
        if branch is None:
            branch = model.default_branch

    if branch is None:
        commits_cnt = 0
        commits =[]
        m_db = None
        m_fn = None
    else:
        commits_cnt = session \
            .query(Commits.id) \
            .filter(Commits.ref==branch) \
            .count()

        commits = session \
            .query(Commits) \
            .filter(Commits.ref==branch) \
            .order_by(Commits.ref, db.desc(Commits.date)) \
            .limit(size) \
            .offset((page-1)*size)

        m_db = model.default_branch
        m_fn = model.full_name

    output = {}
    output['total'] = commits_cnt
    output['pages'] = math.ceil(commits_cnt/size)
    output['page'] = page
    output['results_per_page'] = size
    output['default_branch'] = m_db
    output['model_path'] = m_fn
    output['results'] = []

    for commit in commits:
        c = {
            'id': commit.id,
            'commit': commit.commit,
            'processed': commit.processed,
            'date': commit.date
        }
        output['results'].append(c)

    return output

def get_reqts_view(session, branch, size, page, filter_empty):
    model = session \
        .query(Model_Repo) \
        .first()

    if model is None:
        default_branch = None
    else:
        default_branch = model.default_branch
        if branch is None:
            branch = model.default_branch

    if branch is None:
        head_commit = None
    else:
        head_commit = session \
            .query(Commits) \
            .filter(Commits.ref==branch,
                    Commits.processed==True) \
            .order_by(Commits.ref, db.desc(Commits.date)) \
            .first()

    if head_commit is None:
        reqts_count = 0
        reqts = []
        hc_commit = None
        hc_date = None
    else:
        reqts_count = session \
            .query(Reqts.id) \
            .filter(Reqts.commit_id == head_commit.id) \
            .order_by(Reqts.id) \
            .count()

        reqts = session \
            .query(Reqts) \
            .filter(Reqts.commit_id == head_commit.id) \
            .order_by(Reqts.id) \
            .limit(size) \
            .offset((page-1)*size)

        hc_commit = head_commit.commit
        hc_date = head_commit.date

    output = {}
    output['total'] = reqts_count
    output['pages'] = math.ceil(reqts_count/size)
    output['page'] = page
    output['results_per_page'] = size
    output['default_branch'] = default_branch
    output['commit'] = hc_commit
    output['commit_date'] = hc_date
    output['results'] = []

    for reqt in reqts:
        this_r = {
            'id': reqt.id,
            'shortName': reqt.shortName,
            'declaredName': reqt.declaredName,
            'qualifiedName': reqt.qualifiedName,
        }

        vs_tot = session \
            .query(Verifications) \
            .filter(Verifications.requirement_id==reqt.id) \
            .count()

        this_r['linkedVerifications'] = vs_tot

        if vs_tot == 0:
            this_r['verified'] = False
        else:
            vs = session \
                .query(Verifications.verified) \
                .filter(Verifications.requirement_id==reqt.id) \
                .all()

            for v in vs:
                if not v.verified:
                    this_r['verified'] = False
                    break
            else:
                this_r['verified'] = True
        if not filter_empty or vs_tot > 0:
            # vs_tot == 0 && filter_empty == True => False
            # vs_tot == 1 && filter_empty == True => True
            # vs_tot == 1 && filter_empty == False => True
            # vs_tot == 0 && filter_empty == False => True
            output['results'].append(this_r)
    return output

def get_verfs_view(session, branch, size, page):
    model = session \
        .query(Model_Repo) \
        .first()

    if model is None:
        default_branch = None
    else:
        default_branch = model.default_branch
        if branch is None:
            branch = model.default_branch

    if branch is None:
        head_commit = None
    else:
        head_commit = session \
            .query(Commits) \
            .filter(Commits.ref==branch,
                    Commits.processed==True) \
            .order_by(Commits.ref, db.desc(Commits.date)) \
            .first()

    if head_commit is None:
        vs_count = 0
        vs = []
        hc_commit = None
        hc_date = None
    else:
        vs_count = session \
            .query(Verifications.id) \
            .filter(Verifications.commit_id == head_commit.id) \
            .order_by(Verifications.id) \
            .count()

        vs = session \
            .query(Verifications) \
            .filter(Verifications.commit_id == head_commit.id) \
            .order_by(Verifications.id) \
            .limit(size) \
            .offset((page-1)*size)

        hc_commit = head_commit.commit
        hc_date = head_commit.date

    output = {}
    output['total'] = vs_count
    output['pages'] = math.ceil(vs_count/size)
    output['page'] = page
    output['results_per_page'] = size
    output['default_branch'] = default_branch
    output['commit'] = hc_commit
    output['commit_date'] = hc_date
    output['results'] = []

    for v in vs:
        v_e = session \
            .query(Elements) \
            .filter(Elements.id==v.element_id) \
            .first()

        payload_v = json.loads(v_e.element_text)

        this_v = {
            'id': v.id,
            'qualifiedName': payload_v['payload']['qualifiedName'],
            'declaredName': payload_v['payload']['declaredName'],
            'verified': v.verified,
            'attempted': v.attempted
        }

        as_tot = session \
            .query(Actions) \
            .filter(Actions.verifications_id==v.id) \
            .count()

        this_v['linkedActions'] = as_tot

        output['results'].append(this_v)
    return output

def get_thread_view(session, thread_id, size, page):
    # Get thread executions
    action = session \
        .query(Actions) \
        .filter(Actions.id==thread_id) \
        .first()

    verf = session \
        .query(Verifications) \
        .filter(Verifications.id==action.verifications_id) \
        .first()

    v_e = session \
        .query(Elements) \
        .filter(Elements.id==verf.element_id) \
        .first()

    payload_v = json.loads(v_e.element_text)

    # Filter by qualified name rather than action_id
    tes_count = session \
        .query(Thread_Executions.id) \
        .join(Actions, Actions.id==Thread_Executions.action_id) \
        .filter(Actions.qualifiedName==action.qualifiedName) \
        .count()

    tes = session \
        .query(Thread_Executions.id, Thread_Executions.name,
               Thread_Executions.state, Thread_Executions.source,
               Thread_Executions.date_created, Thread_Executions.date_updated) \
        .join(Actions, Actions.id==Thread_Executions.action_id) \
        .filter(Actions.qualifiedName==action.qualifiedName) \
        .order_by(db.desc(Thread_Executions.date_updated)) \
        .limit(size) \
        .offset((page-1)*size)

    output = {}
    output['total'] = tes_count
    output['pages'] = math.ceil(tes_count/size)
    output['page'] = page
    output['results_per_page'] = size
    output['results'] = []
    output['verification'] = {
        'id': action.verifications_id,
        'qualifiedName': payload_v['payload']['qualifiedName'],
        'declaredName': payload_v['payload']['declaredName'],
    }

    for te in tes:
        if 'windrunner_2' == te.state or 'windchest' in te.state:
            bucket = action.qualifiedName.lower().strip().replace('_', '-'). \
                replace("'", "").replace('"', "").replace("\\","").replace("/",""). \
                replace("::", ".")
            if len(bucket) > 63:
                bucket = bucket[:63]
            elif len(bucket) < 3:
                bucket = bucket+'-bucket'

            found = client.bucket_exists(bucket)
            if found:
                # Bucket exists
                if 'windchest_2' == te.state:
                    # Input and output files exist
                    url1 = client.get_presigned_url(
                        "GET",
                        bucket,
                        'input'+te.name+'.zip',
                        expires=timedelta(hours=2),
                    )
                    url2 = client.get_presigned_url(
                        "GET",
                        bucket,
                        'output'+te.name+'.zip',
                        expires=timedelta(hours=2),
                    )
                else:
                    # Only input files have been made
                    url1 = client.get_presigned_url(
                        "GET",
                        bucket,
                        'input'+te.name+'.zip',
                        expires=timedelta(hours=2),
                    )
                    url2 = None
            else:
                print('Bucket not found!')
                url1 = None
                url2 = None
        else:
            print('Files not ready!')
            url1 = None
            url2 = None

        output['results'].append({
            'id': te.id,
            'name': te.name,
            'state': te.state,
            'source': te.source,
            'date_created': te.date_created,
            'date_updated': te.date_updated,
            'inputs': url1,
            'outputs': url2,
        })
    return output

def get_threads_view(session, branch, size, page):
    model = session \
        .query(Model_Repo) \
        .first()

    if model is None:
        default_branch = None
    else:
        default_branch = model.default_branch
        if branch is None:
            branch = model.default_branch

    if branch is None:
        head_commit = None
    else:
        head_commit = session \
            .query(Commits) \
            .filter(Commits.ref==branch,
                    Commits.processed==True) \
            .order_by(Commits.ref, db.desc(Commits.date)) \
            .first()

    if head_commit is None:
        as_count = 0
        actions = []
        hc_commit = None
        hc_date = None
    else:
        as_count = session \
            .query(Actions.id) \
            .filter(Actions.commit_id == head_commit.id) \
            .order_by(Actions.id) \
            .count()

        actions = session \
            .query(Actions) \
            .filter(Actions.commit_id == head_commit.id) \
            .order_by(Actions.id) \
            .limit(size) \
            .offset((page-1)*size)

        hc_commit = head_commit.commit
        hc_date = head_commit.date

    output = {}
    output['total'] = as_count
    output['pages'] = math.ceil(as_count/size)
    output['page'] = page
    output['results_per_page'] = size
    output['default_branch'] = default_branch
    output['commit'] = hc_commit
    output['commit_date'] = hc_date
    output['results'] = []

    for action in actions:
        this_a = {
            'id': action.id,
            'qualifiedName': action.qualifiedName,
            'declaredName': action.declaredName,
            'container': action.harbor,
            'artifact': action.artifacts,
            'variables': action.variables,
            'valid': action.valid,
        }

        output['results'].append(this_a)
    return output

def get_tes_view(session, size, page):
    tes_cnt = session \
        .query(Thread_Executions.id) \
        .order_by(db.desc(Thread_Executions.date_updated)) \
        .count()

    tes = session \
        .query(Thread_Executions) \
        .order_by(db.desc(Thread_Executions.date_updated)) \
        .limit(size) \
        .offset((page-1)*size)

    output = {}
    output['total'] = tes_cnt
    output['pages'] = math.ceil(tes_cnt/size)
    output['page'] = page
    output['results_per_page'] = size
    output['results'] = []

    for thread in tes:
        container = session \
            .query(Container_Commits.digest, Containers.project,
                   Containers.image, Containers.tag) \
            .join(Containers, Containers.id == Container_Commits.containers_id) \
            .filter(Container_Commits.id==thread.container_commit_id) \
            .first()

        artifact = session \
            .query(Artifacts_Commits.commit, Artifacts.full_name) \
            .join(Artifacts, Artifacts.id == Artifacts_Commits.artifacts_id) \
            .filter(Artifacts_Commits.id==thread.artifact_commit_id) \
            .first()

        model = session \
            .query(Commits.ref, Commits.commit) \
            .filter(Commits.id==thread.model_commit_id) \
            .first()

        action = session \
            .query(Actions.qualifiedName, Actions.declaredName) \
            .filter(Actions.id==thread.action_id) \
            .first()

        if 'windrunner_2' == thread.state or 'windchest' in thread.state:
            bucket = action.qualifiedName.lower().strip().replace('_', '-'). \
                replace("'", "").replace('"', "").replace("\\","").replace("/",""). \
                replace("::", ".")
            if len(bucket) > 63:
                bucket = bucket[:63]
            elif len(bucket) < 3:
                bucket = bucket+'-bucket'

            found = client.bucket_exists(bucket)
            if found:
                # Bucket exists
                if 'windchest_2' == thread.state:
                    # Input and output files exist
                    url1 = client.get_presigned_url(
                        "GET",
                        bucket,
                        'input'+thread.name+'.zip',
                        expires=timedelta(hours=2),
                    )
                    url2 = client.get_presigned_url(
                        "GET",
                        bucket,
                        'output'+thread.name+'.zip',
                        expires=timedelta(hours=2),
                    )
                else:
                    # Only input files have been made
                    url1 = client.get_presigned_url(
                        "GET",
                        bucket,
                        'input'+thread.name+'.zip',
                        expires=timedelta(hours=2),
                    )
                    url2 = None
            else:
                url1 = None
                url2 = None
        else:
            url1 = None
            url2 = None

        def replace_url(url):
            if url is None:
                return url

            return url.replace('http://storage-minio.artifacts:9000', 'https://storage.digitalforge.app')

        output['results'].append({
            'id': thread.id,
            'name': thread.name,
            "thread": {
                "id": thread.action_id,
                "declaredName": action.declaredName,
                "qualifiedName": action.qualifiedName
            },
            "model": {
                "branch": model.ref,
                "commit": model.commit,
            },
            "container": {
                "project": container.project,
                "image": container.image,
                "tag": container.tag,
                "digest": container.digest
            },
            "artifact": {
                "full_name": artifact.full_name,
                "commit": artifact.commit,
            },
            "bucket": {
                "input": replace_url(url1),
                "output": replace_url(url2)
            },
            "source": thread.source,
            "state": thread.state,
            "date_created": thread.date_created,
            "date_updated": thread.date_updated,
        })
    return output
