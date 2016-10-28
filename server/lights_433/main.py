#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import logging

import clip

from raven import Client
from raven.contrib.flask import Sentry

from .server import Lights433Server

app = clip.App()

DEFAULT_SWITCH_CONF = "/etc/lights-433/switches.conf"
DEFAULT_SENTRY_CONF = "/etc/lights-433/sentry.conf"

log = logging.getLogger(__name__)

# Attach loggers to the console.
for l in (__name__, 'sentry.errors'):
    logging.getLogger(l).addHandler(logging.StreamHandler())


@app.main(description='An HTTP server daemon for controlling 433MHz '
                      'light switches')
@clip.arg('serial', required=True, help='The port to the serial device '
                                        'that generates the signals')
@clip.opt('--host', default='127.0.0.1', type=str,
          help='The interface to listen and permit connections on')
@clip.opt('--port', default=8080, type=int,
          help='The port to run the server on')
@clip.opt('--baud', required=False, default=9600, type=int,
          help='Baud rate of the serial interface')
@clip.opt('--timeout', default=1, type=int,
          help='The timeout of the serial interface')
@clip.opt('--switches', default=DEFAULT_SWITCH_CONF, type=str,
          help='Path to the config file for users and signals')
@clip.opt('--sentry', default=DEFAULT_SENTRY_CONF, type=str,
          help='Path to the config file containing the Sentry capture URL')
@clip.flag('--resettable',
           help='Enables device resetting over pin 3 (assumed RPi)')
def lights433(host, port, resettable, serial, baud, timeout, switches, sentry):

    if sentry:
        with open(sentry, 'r') as f:
            sentry_url = f.read().strip()
        if not sentry_url and sentry == DEFAULT_SENTRY_CONF:
            log.warn("No sentry URL specified in [%s]" % DEFAULT_SENTRY_CONF)
        else:
            sentry_client = Client(sentry_url)
            log.info("Sentry client configured!")

    try:
        log.info("Loading switch configurations from [%s]"
                 % DEFAULT_SWITCH_CONF)

        server = Lights433Server(host, port, serial, baud, timeout,
                                 switches, resettable)
    except:
        if sentry_client:
            sentry_client.captureException()
        raise

    if sentry:
        Sentry(dsn=sentry_url).init_app(server.app)
    server.run()


def main():
    try:
        app.run()
    except clip.ClipExit:
        pass

if __name__ == '__main__':
    main()
