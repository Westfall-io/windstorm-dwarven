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
    date: Mapped[datetime] = mapped_column(default=None)

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

class Actions(Base):
    __tablename__ = "actions"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    element_id: Mapped[int] = mapped_column(db.ForeignKey("elements.id"))
    verifications_id: Mapped[int] = mapped_column(db.ForeignKey("verifications.id"))
    declaredName: Mapped[str] = mapped_column(db.String(255))
    qualifiedName: Mapped[str] = mapped_column(db.String())
    harbor: Mapped[str] = mapped_column(db.String())
    artifacts: Mapped[str] = mapped_column(db.String())
    variables: Mapped[str] = mapped_column(db.String())

#class Verifications_Actions(Base):
#    __tablename__ = "verifications_actions"
#    id: Mapped[int] = mapped_column(init=False, primary_key=True)
#    verifications_id: Mapped[int] = mapped_column(db.ForeignKey("verifications.id"))
#    actions_id: Mapped[int] = mapped_column(db.ForeignKey("actions.id"))

class Artifacts(Base):
    __tablename__ = "artifacts"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    full_name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    commit_url: Mapped[str] = mapped_column(db.String(), nullable=False)

class Artifacts_Commits(Base):
    __tablename__ = "artifact_commits"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    artifacts_id: Mapped[int] = mapped_column(db.ForeignKey("artifacts.id"))
    ref: Mapped[str] = mapped_column(db.String(255))
    commit: Mapped[str] = mapped_column(db.String(255))
    date: Mapped[datetime] = mapped_column(default=None)
