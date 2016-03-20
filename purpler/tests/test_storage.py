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

import datetime
import py.test
from sqlalchemy import exc

from purpler import store


def setup_module(module):
    module.storage = store.Store('sqlite:///')
    store.Base.metadata.drop_all()
    store.Base.metadata.create_all()


def test_table_stores():
    guid = storage.put(content=u'i am some text')  # noqa
    text = storage.get(guid)  # noqa

    assert text.content == 'i am some text'
    assert text.guid == guid
    assert text.url is None
    assert isinstance(text.when, datetime.datetime)

    py.test.raises(exc.IntegrityError,
                   'storage.put(guid=guid, content=u"i am some text")')
