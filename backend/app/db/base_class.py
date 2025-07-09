from typing import Any
from sqlalchemy.orm import as_declarative, declared_attr

@as_declarative()
class Base:
    """
    Base class for all SQLAlchemy models.
    """
    id: Any
    __name__: str

    # to BDD
    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower()

    def as_dict(self):
       """
       Returns a dictionary representation of the model.
       """
       return {c.name: getattr(self, c.name) for c in self.__table__.columns}