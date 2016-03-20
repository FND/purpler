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

import re

from purpler import base62


def test_base62():
    # FIXME: this sometimes fails. Uniqueness is not really
    # guaranteed across a vast swath of uuid generations.
    # We can protect against that in storage.
    guid1 = base62.guid()
    guid2 = base62.guid()
    assert guid1 != guid2

    assert re.match('^[a-zA-Z0-9]+$', guid1)
    assert re.match('^[a-zA-Z0-9]+$', guid2)
