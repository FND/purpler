# A simple irc bot that connects to a channel, logs what people say
# and parses for [t <nid>] to send that back to the channel.

# Based on
# https://github.com/openstack-infra/gerritbot/blob/master/gerritbot/bot.py
# https://github.com/jaraco/irc/blob/master/scripts/testbot.py

import logging
import re
import ssl
import sys
import time

from irc import bot, connection

from purpler import store

TRANSCLUDER = re.compile(r'\[t ([A-Za-z0-9]+)\]')

logging.basicConfig(level=logging.DEBUG)

class PurplerBot(bot.SingleServerIRCBot):
    def __init__(self, dbname, server, port, channels, nickname,
                 password, server_password=None):
        if port == 6697:
            factory = connection.Factory(wrapper=ssl.wrap_socket)
            super(PurplerBot, self).__init__([(server, port, server_password)],
                                             nickname, nickname,
                                             connect_factory=factory)
        else:
            super(PurplerBot, self).__init__([(server, port, server_password)],
                                            nickname, nickname)

        self.channel_list = channels
        self.nickname = nickname
        self.password = password
        self.log = logging.getLogger('purplebot')
        self.storage = store.Store('sqlite:////tmp/%s' % dbname)

    def on_nicknameinuse(self, c, e):
        self.log.info('Nick previously in use, recovering.')
        c.nick(c.get_nickname() + "_")
        c.privmsg("nickserv", "identify %s " % self.password)
        c.privmsg("nickserv", "ghost %s %s" % (self.nickname, self.password))
        c.privmsg("nickserv", "release %s %s" % (self.nickname, self.password))
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

    def on_pubmsg(self, c, e):
        message = e.arguments[0]
        nick = e.source.nick
        self.log.info('Got message %s', message)
        result = TRANSCLUDER.search(message)
        if result:
            self.log.info('saw result %s',result)
            guid = result.group(1)
            self.log.info('saw guid %s', guid)
            outgoing_message = self.storage.get(guid)
            if outgoing_message:
                c.privmsg(e.target, '%s: %s' % (outgoing_message.content, outgoing_message.guid))
        self.storage.put(content='%s: %s' % (nick, message))


def run():
    try:
        dbname = sys.argv[1] 
        server, port = sys.argv[2].split(':')
        channels = [sys.argv[3]]
    except IndexError:
        dbname = 'tiddlyweb'
        server = 'chat.freenode.net'
        port = 6697
        channels = ['#tiddlyweb']

    nickname = 'purplerbot'
    password = 'purplerbot'

    bot = PurplerBot(dbname, server, port, channels, nickname, password)
    bot.start()
