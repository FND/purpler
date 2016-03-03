# Purpleize lines of text on stdin into the db and to stdout.

import sys

from purpler import store

def run():
    try:
        dbname = sys.argv[1] 
    except IndexError:
        dbname = 'foo'

    storage = store.Store('sqlite:////tmp/%s' % dbname)

    with sys.stdin as data:
        for line in data:
            line = line.decode('utf-8').strip()
            guid = storage.put(content=line)
            print('%s\t%s' % (guid, line))
