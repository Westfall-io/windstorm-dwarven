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

from datetime import datetime

import sqlalchemy as db
from sqlalchemy.orm import DeclarativeBase, Mapped, \
    mapped_column, MappedAsDataclass, relationship

class Base(MappedAsDataclass, DeclarativeBase):
    """subclasses will be converted to dataclasses"""

class Commits(Base):
    __tablename__ = "commits"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    ref: Mapped[str] = mapped_column(db.String(255))
    commit: Mapped[str] = mapped_column(db.String(255))
    processed: Mapped[bool] = mapped_column(db.Boolean())
    date: Mapped[datetime] = mapped_column(default=None)

class Model_Repo(Base):
    __tablename__ = "model_repo"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    default_branch: Mapped[str] = mapped_column(db.String(255))
    full_name: Mapped[str] = mapped_column(db.String())

class Models(Base):
    __tablename__ = "models"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    commit_id: Mapped[int] = mapped_column(db.ForeignKey("commits.id"))
    nb_id: Mapped[str] = mapped_column(db.String(36))
    execution_order: Mapped[int] = mapped_column(db.Integer())
    model_text: Mapped[str] = mapped_column(db.String())
    model_hash: Mapped[str] = mapped_column(db.String(16))
    path_text: Mapped[str] = mapped_column(db.String(255))
    path_hash: Mapped[str] = mapped_column(db.String(16))
    element_name: Mapped[str] = mapped_column(db.String(255))

    def set_id(self, id):
        self.id = id
        return self

class Elements(Base):
     __tablename__ = "elements"
     id: Mapped[int] = mapped_column(init=False, primary_key=True)
     commit_id: Mapped[int] = mapped_column(db.ForeignKey("commits.id"))
     element_id: Mapped[str] = mapped_column(db.String(36))
     element_text: Mapped[str] = mapped_column(db.String())
     element_name: Mapped[str] = mapped_column(db.String(255))

     def set_id(self, id):
         self.id = id
         return self

class Models_Elements(Base):
    __tablename__ = "models_elements"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    model_id: Mapped[int] = mapped_column(db.ForeignKey("models.id"))
    element_id: Mapped[int] = mapped_column(db.ForeignKey("elements.id"))
    commit_id: Mapped[int] = mapped_column(db.ForeignKey("commits.id"))

class Reqts(Base):
    __tablename__ = "requirements"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    commit_id: Mapped[int] = mapped_column(db.ForeignKey("commits.id"))
    declaredName: Mapped[str] = mapped_column(db.String(255))
    shortName: Mapped[str] = mapped_column(db.String(255))
    qualifiedName: Mapped[str] = mapped_column(db.String(255))
    element_id: Mapped[int] = mapped_column(db.ForeignKey("elements.id"))

class Verifications(Base):
    __tablename__ = "verifications"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    commit_id: Mapped[int] = mapped_column(db.ForeignKey("commits.id"))
    element_id: Mapped[int] = mapped_column(db.ForeignKey("elements.id"))
    requirement_id: Mapped[int] = mapped_column(db.ForeignKey("requirements.id"))
    verified: Mapped[bool] = mapped_column(db.Boolean())
    attempted: Mapped[bool] = mapped_column(db.Boolean())

class Actions(Base):
    __tablename__ = "actions"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    commit_id: Mapped[int] = mapped_column(db.ForeignKey("commits.id"))
    element_id: Mapped[int] = mapped_column(db.ForeignKey("elements.id"))
    verifications_id: Mapped[int] = mapped_column(db.ForeignKey("verifications.id"))
    shortName: Mapped[str] = mapped_column(db.String(255))
    declaredName: Mapped[str] = mapped_column(db.String(255))
    qualifiedName: Mapped[str] = mapped_column(db.String())
    harbor: Mapped[str] = mapped_column(db.String())
    artifacts: Mapped[str] = mapped_column(db.String())
    variables: Mapped[str] = mapped_column(db.String())
    valid: Mapped[bool] = mapped_column(db.Boolean())
    dependency: Mapped[int] = mapped_column(db.Integer())

class Artifacts(Base):
    __tablename__ = "artifacts"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    full_name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    commit_url: Mapped[str] = mapped_column(db.String(), nullable=False)
    default_branch: Mapped[str] = mapped_column(db.String(255))

class Artifacts_Commits(Base):
    __tablename__ = "artifact_commits"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    artifacts_id: Mapped[int] = mapped_column(db.ForeignKey("artifacts.id"))
    ref: Mapped[str] = mapped_column(db.String(255))
    commit: Mapped[str] = mapped_column(db.String(255))
    date: Mapped[datetime] = mapped_column(default=None)

class Containers(Base):
    __tablename__ = "containers"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    resource_url: Mapped[str] = mapped_column(db.String(255))
    host: Mapped[str] = mapped_column(db.String(255))
    project: Mapped[str] = mapped_column(db.String(255))
    project_id: Mapped[int] = mapped_column(db.Integer())
    image: Mapped[str] = mapped_column(db.String(255))
    image_id: Mapped[int] = mapped_column(db.Integer())
    tag: Mapped[str] = mapped_column(db.String(255))

class Container_Commits(Base):
    __tablename__ = "container_commits"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    containers_id: Mapped[int] = mapped_column(db.ForeignKey("containers.id"))
    digest: Mapped[str] = mapped_column(db.String(64))
    date: Mapped[datetime] = mapped_column(default=None)

class Thread_Executions(Base):
    __tablename__ = "thread_executions"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    name: Mapped[str] = mapped_column(db.String(255))
    action_id: Mapped[int] = mapped_column(db.ForeignKey(Actions.id))
    model_commit_id: Mapped[int] = mapped_column(db.ForeignKey(Commits.id))
    container_commit_id: Mapped[int] = mapped_column(db.ForeignKey(Container_Commits.id))
    artifact_commit_id: Mapped[int] = mapped_column(db.ForeignKey(Artifacts_Commits.id))
    source: Mapped[str] = mapped_column(db.String(255))
    state: Mapped[str] = mapped_column(db.String(255))
    date_created: Mapped[datetime] = mapped_column(default=None)
    date_updated: Mapped[datetime] = mapped_column(default=None)
