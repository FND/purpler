
import os
import datetime
import logging
import sys

import bleach
import httpexceptor
import iso8601
import jinja2
from selector import Selector
from six.moves.urllib.parse import parse_qs

from purpler import store

TEMPLATE_ENV = None
LOGGER = logging.getLogger(__name__)
logging.basicConfig()
logging.getLogger(__name__).setLevel(logging.DEBUG)


class StoreSet(object):

    def __init__(self, application=None):
        # XXX Need real config, doing this for now for expediency.
        with open('/home/cdent/src/purpler/db_url') as dbfile:
            self.dbname = dbfile.read().strip()
        self.application = application

    def __call__(self, environ, start_response):
        storage = store.Store(self.dbname)
        environ['purpler.store'] = storage
        return self.application(environ, start_response)


def render(template_file, **kwargs):
    global TEMPLATE_ENV
    if not TEMPLATE_ENV:
        TEMPLATE_ENV = jinja2.Environment(
            loader=jinja2.FileSystemLoader('/home/cdent/src/purpler', encoding='utf-8'))  # FIXME
    template = TEMPLATE_ENV.get_template(template_file)
    # FIXME: would prefer generate here but encoding
    return [template.render(**kwargs).encode('utf-8')]


# need to make up my mind on nid or guid
def get_via_nid(environ, start_response):
    nid = environ['wsgiorg.routing_args'][1]['nid']
    storage = environ['purpler.store']

    LOGGER.warn('asking for nid: %s', nid)
    text = storage.get(nid)
    LOGGER.warn('nid got text: %s', text)

    if text:
        # XXX this only works for irc contexts
        if '#' in text.url:
            context = text.url.replace('#', '')
            # XXX: If accept headers are for something other than html we
            # should not redirect.
            raise httpexceptor.HTTP302('/logs/%s?dated=%s#%s' % (context, text.when, text.guid))
    else:
        raise httpexceptor.HTTP404('we got nothing for you mate')
    

def format_irc_lines(lines):
    for line in lines:
        content = line.content
        nick, content = content.split(':', 1)
        content = bleach.linkify(content)
        content = dict(nick=nick, message=content)
        yield dict(when=line.when, guid=line.guid, content=content)


def lines_by_datetime(environ, start_response):
    storage = environ['purpler.store']
    context = environ['wsgiorg.routing_args'][1]['context']
    query = parse_qs(environ.get('QUERY_STRING', ''))
    timestamp = query.get('dated', [None])[0]
    # XXX currently IRC only
    if timestamp:
        timestamp = iso8601.parse_date(timestamp)
    else:
        timestamp = datetime.datetime.utcnow()
        raise httpexceptor.HTTP302('/logs/%s?dated=%s#bottom' % (context, timestamp))
    # XXX The log does not contain messages from purplerbot itself.
    lines = storage.get_by_time_in_context('#%s' % context, timestamp)
    earlier = timestamp - datetime.timedelta(minutes=60)
    later = timestamp + datetime.timedelta(minutes=60)

    start_response('200 OK', [('content-type', 'text/html; charset=utf-8'),
        ('Cache-Control', 'no-cache')])
    return render('irc.html', lines=format_irc_lines(lines), channel=context,
                  timestamp=timestamp, earlier=earlier.replace(tzinfo=None),
                  later=later.replace(tzinfo=None))


def logs_list(environ, start_response):
    storage = environ['purpler.store']
    logs = storage.get_logs()

    start_response('200 OK', [('content-type', 'text/html; charset=utf-8'),
        ('Cache-Control', 'no-cache')])
    return render('logs.html', logs=logs)


def get_root(environ,start_resonse):
    raise httpexceptor.HTTP302('/logs')


def load_app():
    app = Selector()
    app.add('/logs/{context:segment}', GET=lines_by_datetime)
    app.add('/logs[/]', GET=logs_list)
    app.add('/{nid:segment}', GET=get_via_nid)
    app.add('/', GET=get_root)
    app = StoreSet(app)
    app = httpexceptor.HTTPExceptor(app)

    return app


application = load_app()
