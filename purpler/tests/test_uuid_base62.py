
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
