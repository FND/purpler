"""
Store bits of text and their guids and timestamps.
"""

from sqlalchemy.engine import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.functions import now
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.schema import Table, Column, UniqueConstraint
from sqlalchemy.types import String, UnicodeText, DateTime

from purpler import base62

Base = declarative_base()
Session = scoped_session(sessionmaker())


class Text(Base):
     __tablename__ = 'text'

     guid = Column(String(12), primary_key=True, nullable=False)
     url = Column(String(255), nullable=True, index=True)
     content = Column(UnicodeText, nullable=True)
     when = Column(DateTime(timezone=True), server_default=now())


class Store(object):

    mapped = False

    def __init__(self, dburi):
        engine = create_engine(dburi)
        Base.metadata.bind = engine
        Session.configure(bind=engine)
        self.session = Session()

        if not Store.mapped:
            Base.metadata.create_all(engine)
            Store.mapped = True

    def get(self, guid):
        text = self.session.query(Text).filter_by(guid=guid).first()
        return text

    def put(self, content=None):
        try:
            guid = base62.guid()
            text = Text(guid=guid, content=content)
            self.session.add(text)
            self.session.commit()
        except:
            self.session.rollback()
            raise
        return guid
