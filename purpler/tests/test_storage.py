
import datetime
import py.test
from sqlalchemy.orm import exc

from purpler import store

def setup_module(module):
    module.storage = store.Store('sqlite:///')
    store.Base.metadata.drop_all()
    store.Base.metadata.create_all()


def test_table_stores():

    guid = storage.put(content='i am some text')
    text = storage.get(guid)

    assert text.content == 'i am some text'
    assert text.guid == guid
    assert text.url == None
    assert isinstance(text.when, datetime.datetime)

    py.test.raises(exc.FlushError,
                   'storage.put(guid=guid, content="i am some text")')
