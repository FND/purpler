
import os
import datetime
import sys

import bleach
import httpexceptor
import iso8601
import jinja2
from selector import Selector
from six.moves.urllib.parse import parse_qs

from purpler import store

TEMPLATE_ENV = None


class StoreSet(object):

    def __init__(self, application=None):
        self.application = application

    def __call__(self, environ, start_response):
        # XXX messy
        storage = store.Store(environ.get('PURPLER_DB_URL', 'sqlite:////tmp/purpler'))
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
    store = environ['purpler.store']

    text = store.get(nid)

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
    store = environ['purpler.store']
    context = environ['wsgiorg.routing_args'][1]['context']
    query = parse_qs(environ.get('QUERY_STRING', ''))
    timestamp = query.get('dated', [None])[0]
    # XXX currently IRC only
    if timestamp:
        timestamp = iso8601.parse_date(timestamp)
    else:
        timestamp = datetime.datetime.utcnow()
    # XXX The log does not contain messages from purplerbot itself.
    lines = store.get_by_time_in_context('#%s' % context, timestamp)

    start_response('200 OK', [('content-type', 'text/html; charset=utf-8'),
        ('Cache-Control', 'no-cache, no-store, must-revalidate')])
    return render('irc.html', lines=format_irc_lines(lines), channel=context,
                  timestamp=timestamp)


def logs_list(environ, start_response):
    store = environ['purpler.store']
    logs = store.get_logs()

    start_response('200 OK', [('content-type', 'text/html; charset=utf-8'),
        ('Cache-Control', 'no-cache, no-store, must-revalidate')])
    return render('logs.html', logs=logs)


def load_app():
    app = Selector()
    app.add('/logs/{context:segment}', GET=lines_by_datetime)
    app.add('/logs', GET=logs_list)
    app.add('/{nid:segment}', GET=get_via_nid)
    app = StoreSet(app)
    app = httpexceptor.HTTPExceptor(app)

    return app


application = load_app()
