"""
Store bits of text and their guids and timestamps.
"""

import datetime
import logging

from sqlalchemy import event
from sqlalchemy.engine import create_engine
from sqlalchemy.exc import DisconnectionError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.expression import and_, not_
from sqlalchemy.sql.functions import now
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.schema import Table, Column, UniqueConstraint
from sqlalchemy.types import String, UnicodeText, DateTime

from purpler import base62

Base = declarative_base()
Session = scoped_session(sessionmaker())


LOGGER = logging.getLogger(__name__)
# logging.basicConfig()
# logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
# logging.getLogger('sqlalchemy.pool').setLevel(logging.DEBUG)


def on_checkout(dbapi_con, con_record, con_proxy):
    """
    Ensures that MySQL connections checked out of the pool are alive.
    Borrowed from:
    http://groups.google.com/group/sqlalchemy/msg/a4ce563d802c929f
    """
    try:
        try:
            dbapi_con.ping(False)
        except TypeError:
            dbapi_con.ping()
    except dbapi_con.OperationalError, ex:
        if ex.args[0] in (2006, 2013, 2014, 2045, 2055):
            LOGGER.debug('got mysql server has gone away: %s', ex)
            # caught by pool, which will retry with a new connection
            raise DisconnectionError()
        else:
            raise


class Text(Base):
     __tablename__ = 'text'

     guid = Column(String(12), primary_key=True, nullable=False)
     url = Column(String(255), nullable=True, index=True)
     content = Column(UnicodeText, nullable=True)
     when = Column(DateTime(timezone=True), index=True,
                   server_default=now())


class Store(object):

    mapped = False

    def __init__(self, dburi):
        engine = create_engine(dburi)
        Base.metadata.bind = engine

        if not Store.mapped:
            Session.configure(bind=engine)
            Base.metadata.create_all(engine)
            Store.mapped = True
            event.listen(engine, 'checkout', on_checkout)

        self.session = Session()

    def get(self, guid):
        text = self.session.query(Text).filter_by(guid=guid).first()
        return text

    def get_by_guid_in_context(self, guid):
        text = self.get(guid)
        if text:
            one_hour = datetime.timedelta(minutes=60)
            timeless = text.when - one_hour
            timemore = text.when + one_hour
            query = self.session.query(Text).filter(
                Text.url == text.url, Text.when >= timeless,
                Text.when <= timemore).order_by(Text.when)
            return query.all()
        else:
            return []

    def get_by_time_in_context(self, url, time=None, count=None,
                               containing=None, rlimit=1):
        one_hour = datetime.timedelta(minutes=60)
        if time:
            timeless = time - one_hour
            timemore = time + one_hour
        else:
            now = datetime.datetime.utcnow()
            timeless = now - one_hour
            timemore = now + one_hour
        query = self.session.query(Text).filter(
            Text.url == url, Text.when >= timeless,
            Text.when <= timemore)
        if containing:
            # XXX hack to avoid finding nick at that start of text
            intro = containing + ':%'
            containing = '%' + containing + '%'
            query = query.filter(and_(not_(Text.content.like(intro))),
                                 Text.content.like(containing))
        if count:
            query = (query.order_by(Text.when.desc()).
                     limit(count).from_self().order_by(Text.when))
        else:
            query = query.order_by(Text.when)
        results = query.all()
        # If we don't get any results go back in time up to 12 hours
        if not results and rlimit < 12:
            rlimit = rlimit +1
            return self.get_by_time_in_context(url, time=timeless, count=count,
                                               containing=containing, rlimit=rlimit)
        return results


    def get_logs(self):
        # XXX irc specific (again)
        query = self.session.query(Text).group_by(Text.url).order_by(Text.url)
        return query.all()


    def put(self, guid=None, url=None, content=None):
        # If something with the provided guid already exists, we'll
        # raise an error and the caller is expected to try again. I
        # considered doing that looping in here but it upsets the
        # mechanics of things that are providing their own guids.
        try:
            if not guid:
                guid = base62.guid()
            text = Text(guid=guid, url=url, content=content)
            self.session.add(text)
            self.session.commit()
        except:
            self.session.rollback()
            raise
        return guid
