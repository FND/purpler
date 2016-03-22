# Licensed under the Apache License, Version 2.0 (the "License"); you
# may not use this file except in compliance with the License. You may
# obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied. See the License for the specific language governing
# permissions and limitations under the License.
"""
Store bits of text and their guids and timestamps.
"""

import datetime
import logging

from sqlalchemy.engine import create_engine
from sqlalchemy import event
from sqlalchemy.exc import DisconnectionError
from sqlalchemy.ext import declarative
from sqlalchemy import orm
from sqlalchemy.schema import Column
from sqlalchemy.sql.expression import and_, not_
from sqlalchemy.sql.functions import now
from sqlalchemy.types import String, UnicodeText, DateTime

from purpler import base62

Base = declarative.declarative_base()
Session = orm.scoped_session(orm.sessionmaker())


LOGGER = logging.getLogger(__name__)
# logging.basicConfig()
# logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
# logging.getLogger('sqlalchemy.pool').setLevel(logging.DEBUG)

ENGINE = None
MAPPED = False


def on_checkout(dbapi_con, con_record, con_proxy):
    """Ensure MySQL connections checked out of the pool are alive.

    Borrowed from:
    http://groups.google.com/group/sqlalchemy/msg/a4ce563d802c929f
    """
    try:
        try:
            dbapi_con.ping(False)
        except TypeError:
            dbapi_con.ping()
    except dbapi_con.OperationalError as ex:
        if ex.args[0] in (2006, 2013, 2014, 2045, 2055):
            LOGGER.debug('got mysql server has gone away: %s', ex)
            # caught by pool, which will retry with a new connection
            raise DisconnectionError()
        else:
            raise


class Text(Base):
    __tablename__ = 'text'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8mb4',
    }

    guid = Column(String(12), primary_key=True, nullable=False)
    url = Column(String(255), nullable=True, index=True)
    content = Column(UnicodeText, nullable=True)
    when = Column(DateTime(timezone=True), index=True,
                  server_default=now())


class Store(object):

    def __init__(self, dburi):
        global ENGINE, MAPPED
        if not ENGINE:
            if 'mysql' in dburi:
                engine = create_engine(dburi,
                                       pool_recycle=3600,
                                       pool_size=20,
                                       max_overflow=-1,
                                       pool_timeout=2)
                event.listen(engine, 'checkout', on_checkout)
            else:
                engine = create_engine(dburi)
            Base.metadata.bind = engine
            Session.configure(bind=engine)
            ENGINE = engine
        self.session = Session()

        if not MAPPED:
            Base.metadata.create_all(engine)
            MAPPED = True

    def get(self, guid):
        try:
            text = self.session.query(Text).filter_by(guid=guid).first()
        except Exception:
            self.session.rollback()
            raise
        finally:
            self.session.close()
        return text

    def get_by_guid_in_context(self, guid):
        try:
            text = self.get(guid)
            if text:
                one_hour = datetime.timedelta(minutes=60)
                timeless = text.when - one_hour
                timemore = text.when + one_hour
                query = self.session.query(Text).filter(
                    Text.url == text.url, Text.when >= timeless,
                    Text.when <= timemore).order_by(Text.when)
                for line in query.all():
                    yield line
            else:
                yield
        except Exception:
            self.session.rollback()
        finally:
            self.session.close()

    def get_ten_behind_date(self, url, time):
        try:
            query = (self.session.query(Text).filter(
                     Text.url == url,
                     Text.when <= time)
                     .order_by(Text.when.desc())
                     .limit(10))
            result = query.all()
        except Exception:
            self.session.rollback()
        finally:
            self.session.close()
        return result[-1].when

    def get_by_time_in_context(self, url, time=None, count=None,
                               containing=None, rlimit=1):
        one_hour = datetime.timedelta(minutes=60)
        results = []
        if time:
            timeless = time - one_hour
            timemore = time + one_hour
            query = self.session.query(Text).filter(
                Text.url == url, Text.when >= timeless,
                Text.when <= timemore)
        else:
            query = self.session.query(Text).filter(
                Text.url == url)
        try:
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
        except Exception:
            self.session.rollback()
            raise
        finally:
            self.session.close()
        # If we don't get any results go back in time up to 12 hours
        if time and not results and rlimit < 12:
            rlimit = rlimit + 1
            return self.get_by_time_in_context(url, time=timeless,
                                               count=count,
                                               containing=containing,
                                               rlimit=rlimit)
        return results

    def get_logs(self):
        # XXX irc specific (again)
        try:
            query = (self.session.query(Text).group_by(Text.url)
                     .order_by(Text.url))
            for line in query.all():
                yield line
        except Exception:
            self.session.rollback()
            raise
        finally:
            self.session.close()

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
        except Exception:
            self.session.rollback()
            raise
        finally:
            self.session.close()
        return guid
