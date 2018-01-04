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
"""A simple logging and transcluding irc bot

Connects to a channel, logs what people say and parses for
[t <nid>] to send that back to the channel.

Based on
https://github.com/openstack-infra/gerritbot/blob/master/gerritbot/bot.py
https://github.com/jaraco/irc/blob/master/scripts/testbot.py
"""

import argparse
import logging
import re
import ssl
import time

from irc import bot
from irc import connection
from sqlalchemy import exc

from purpler import store

COMMANDS = {
    'log': 'show_log',
    'logs': 'show_logs',
    'help': 'show_help',
    'hist': 'show_history',
    'spy': 'show_mentions',
}
COMMANDER = re.compile('^p!(%s)(.*)?$' % '|'.join(COMMANDS.keys()))
TRANSCLUDER = re.compile(r'\[t ([A-Za-z0-9]+)\]')

logging.basicConfig(level=logging.DEBUG)


class PurplerBot(bot.SingleServerIRCBot):
    def __init__(self, db_url, server, port, channels, nickname,
                 password, darkchannels, server_password=None, web_url=None):
        if port == 6697:
            factory = connection.Factory(wrapper=ssl.wrap_socket)
            super(PurplerBot, self).__init__([(server, port, server_password)],
                                             nickname, nickname,
                                             connect_factory=factory)
        else:
            super(PurplerBot, self).__init__([(server, port, server_password)],
                                             nickname, nickname)

        self.channel_list = channels
        self.darkchannels = darkchannels
        self.nickname = nickname
        self.password = password
        self.web_url = web_url
        self.log = logging.getLogger(__name__)
        self.storage = store.Store(db_url)

    def on_nicknameinuse(self, c, e):
        self.log.info('Nick previously in use, recovering.')
        c.nick(c.get_nickname() + "_")
        c.privmsg("nickserv", "identify %s " % self.password)
        c.privmsg("nickserv", "ghost %s %s" % (self.nickname, self.password))
        c.privmsg("nickserv", "release %s %s"
                  % (self.nickname, self.password))
        time.sleep(1)
        c.nick(self.nickname)
        self.log.info('Nick previously in use, recovered.')

    def on_welcome(self, c, e):
        self.log.info('Identifying with IRC server.')
        c.privmsg("nickserv", "identify %s " % self.password)
        self.log.info('Identified with IRC server.')
        for channel in self.channel_list:
            c.join(channel)
            self.log.info('Joined channel %s' % channel)
            time.sleep(0.5)

    def show_help(self, c, e, arg=None):
        nick = e.source.nick
        c.privmsg(nick,
                  'p!log to get the URL of the log of the current channel')
        c.privmsg(nick, 'p!logs to get the URL of all available logs')
        c.privmsg(nick, 'p!hist up to last 10 messages in the recent past')
        c.privmsg(nick, 'p!spy last 10 mentions (fuzzy) in the recent past')
        c.privmsg(nick, 'The bot listens in channels and on private messages')

    def parse_arg(self, arg, url):
        self.log.debug('saw arg "%s" and url "%s"', arg, url)
        count = 10
        arg = arg.strip()
        args = arg.split(None, 1)
        self.log.debug('args is %s', args)
        for arg in args:
            if arg.isdigit():
                count = arg
            else:
                url = arg
                if not url.startswith('#'):
                    url = '#%s' % url
        self.log.debug('set url and count: %s, %s', url, count)
        return url, count

    def show_history(self, c, e, arg=None):
        nick = e.source.nick
        url = e.target
        count = 10
        if arg:
            url, count = self.parse_arg(arg, url)
        lines = self.storage.get_by_time_in_context(url=url, count=count)
        line = None
        for line in lines:
            c.privmsg(nick, '%s: %s [n %s]'
                      % (line.when, line.content, line.guid))
        if line and self.web_url:
            c.privmsg(nick, 'last message: %s/%s'
                      % (self.web_url, line.guid))
        self.show_log(c, e, arg)

    def show_mentions(self, c, e, arg=None):
        nick = e.source.nick
        url = e.target
        count = 10
        if arg:
            url, count = self.parse_arg(arg, url)
        self.log.debug('looking for url, count, nick: %s, %s, %s', url, count, nick)
        lines = self.storage.get_by_time_in_context(url=url, count=count,
                                                    containing=nick)
        line = None
        for line in lines:
            c.privmsg(nick, '%s: %s [n %s]' %
                      (line.when, line.content, line.guid))
        if line and self.web_url:
            c.privmsg(nick, 'last mention: %s/%s'
                      % (self.web_url, line.guid))
        self.show_log(c, e, arg)

    def show_log(self, c, e, arg=None):
        nick = e.source.nick
        channel = e.target.replace('#', '')
        if arg:
            channel, count = self.parse_arg(arg, channel)
            channel = channel.replace('#', '')
        if self.web_url:
            c.privmsg(nick, 'log at %s/logs/%s' % (self.web_url, channel))
        else:
            c.privmsg(nick, 'There is no web log')

    def show_logs(self, c, e, arg=None):
        nick = e.source.nick
        # XXX static url
        if self.web_url:
            c.privmsg(nick, 'logs at %s/logs' % self.web_url)
        else:
            c.privmsg(nick, 'There is no web log')

    def on_action(self, c, e):
        nick = e.source.nick
        message = e.arguments[0]
        self._log(e, message, nick, action=True)

    def _handle_command(self, c, e):
        nick = e.source.nick
        message = e.arguments[0]

        command = COMMANDER.search(message)
        if command:
            func = command.group(1)
            arg = command.group(2)
            return getattr(self, COMMANDS[func])(c, e, arg)

    def on_privmsg(self, c, e):
        self._handle_command(c, e)

    def on_pubmsg(self, c, e):
        # XXX at the moment we don't see messages that we send so
        # the outgoing message is not logged. Not sure if the fix
        # for that is to see them or just log them.
        nick = e.source.nick
        message = e.arguments[0]

        self._handle_command(c, e)

        results = TRANSCLUDER.finditer(message)
        if results:
            for result in results:
                guid = result.group(1)
                self.log.debug('saw guid %s', guid)
                outgoing_message = self.storage.get(guid)
                if outgoing_message:
                    out_nick, the_message = outgoing_message.content.split(':', 1)
                    c.privmsg(e.target, '<%s> %s [%s] [n %s]' % (
                        out_nick.strip(), the_message.strip(),
                        outgoing_message.when,
                        outgoing_message.guid))
        self._log(e, message, nick)

    def _log(self, e, message, nick, action=False):
        if e.target not in self.darkchannels:
            self.log.debug('Got message %s', message)
            if action:
                message = '/me %s' % message
            count = 0
            while count < 10:
                try:
                    guid = self.storage.put(
                        url=e.target, content='%s: %s' % (nick, message))
                    self.log.debug('Logged guid: %s', guid)
                    return
                except exc.IntegrityError:
                    count = count + 1
            self.log.debug('guid conflict after ten tries')


def run():
    parser = argparse.ArgumentParser(description='Run the irc bot',
                                     fromfile_prefix_chars='@')
    parser.add_argument(
        '--db-url',
        dest='db_url',
        default='sqlite:////tmp/purpler',
        help='A db_url that describes where stuff will be stored'
    )
    parser.add_argument(
        '--irc-server',
        dest='server',
        default='chat.freenode.net:6697',
        help='IRC host:port'
    )
    parser.add_argument(
        '--nickname',
        dest='nickname',
        default='purplerbot',
        help='Nickname for the bot'
    )
    parser.add_argument(
        '--password',
        dest='password',
        default='purpler',
        help='Password for the bot'
    )
    parser.add_argument(
        '-c', '--channel',
        nargs='?', default=None,
        dest='channels',
        action='append',
        help='With each use add a channel on which the bot should listen. '
             'Use # in channel name.'
    )
    parser.add_argument(
        '-n', '--no-log',
        nargs='?', default=[],
        dest='darkchannels',
        action='append',
        help='Channels in the channel list that should not log. '
             'Use # in channel name.'
    )
    parser.add_argument(
        '-w', '--web-url',
        dest='web_url',
        default=None,
        help='URL of the web interface'
    )
    args = parser.parse_args()

    server, port = args.server.split(':', 1)
    port = int(port)

    bot = PurplerBot(args.db_url, server, port, args.channels,
                     args.nickname, args.password, args.darkchannels,
                     web_url=args.web_url)
    while True:
        try:
            bot.start()
        except UnicodeDecodeError:
            pass
