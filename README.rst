
What and Why
============

Purpler is the beginning of a suite of tools that manage content to
apply purple numbers, starting with a logging IRC bot that enables
transclusion. See a `blog posting
<https://anticdent.org/purple-irc-bot.html>`_ for more details.

There are further plans. IRC logging is just the first part.

Use
===

Purpler consists of two services:

* A WSGI application that presents logs of content:
  ``purpler.wsgi``.
* An IRC bot script that listens on configured channels:
  ``purpler-bot``.

The WSGI application requires a database url to run. Provide this by
create a file ``purpler.db_url`` in the working directory of the
WSGI application containing something like::

    mysql+pymysql://localhost/purpler?charset=utf8mb4

The IRC bot takes a complex set of configuration on the command
line (run ``purpler-bot --help``). To avoid this complexity it is
possible to read configuration from a file. Here's one way to
start it::

    nohup purpler-bot @purplerbot.conf --db-url=`cat purpler.db_url` &

``purplerbot.conf`` contains entries like::

    --no-log=#someprivatechannel
    -c #openstack-nova
    -c #openstack-sdks
    -c #openstack-telemetry
    -c #openstack-dev
    -c #someprivatechannel

Install
=======

Install purpler in the usual pip way::

    pip install -U purpler

Also install a database driver that will work with sqlalchemy.

Web App
-------

Configure a WSGI server to run the wsgi application. Here's an
example using mod_wsgi (you should modify this for your own
requirements with regard to logging, auth, etc.)::

    <VirtualHost *:80>
    ServerName p.anticdent.org
    AllowEncodedSlashes On

    WSGIDaemonProcess purpler user=cdent processes=2 threads=20 stack-size=524288 display-name=%{GROUP} maximum-requests=500
    WSGIProcessGroup purpler

    WSGIScriptAlias / /some/path/to/purpler/wsgi.py
    </VirtualHost>

The templates used for presenting the logs exist within the purpler
package. If you want custom templates set the ``PURPLER_TEMPLATE_PATH``
environment variable to a path to find overrides. CSS is inlined from a
style.css template.

The Bot
-------

See above for an example of how to start up ``purpler-bot``. That's
just one of many ways. Other options include systemd service,
supervisord or an initscript.

Code
====

On `GitHub <https://github.com/cdent/purpler>`_.

Caveats
-------

This could charitably be described as a weekend hack so there
has been limited testing of the code with proper testing.

License
-------

Apache License, Version 2.0
