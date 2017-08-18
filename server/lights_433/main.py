#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import logging
import os
import sys

import clip

from raven import Client
from raven.contrib.flask import Sentry

from .adapter import get_adapter
from .server import Lights433Server

app = clip.App()

DEFAULT_SWITCH_CONF = "/etc/lights-433/switches.conf"
DEFAULT_SENTRY_CONF = "/etc/lights-433/sentry.conf"


class BadArgumentsError(Exception):
    pass


log = logging.getLogger(__name__)

# Attach loggers to the console.
for l in (__name__, 'sentry.errors'):
    logging.getLogger(l).addHandler(logging.StreamHandler())


@app.main(description='An HTTP server daemon for controlling 433MHz '
                      'light switches')
@clip.arg('adapter', required=True, type=str,
          help='The adapter to use for interfacing with the controller')
@clip.opt('--adapter-args', required=False, default='', type=str,
          help='Comma separated name-value args for the adapter '
               '(e.g. x=1,y=2,...')
@clip.opt('--host', default='127.0.0.1', type=str,
          help='The interface to listen and permit connections on')
@clip.opt('--port', default=8080, type=int,
          help='The port to run the server on')
@clip.opt('--switches', default=DEFAULT_SWITCH_CONF, type=str,
          help='Path to the config file for users and signals')
@clip.opt('--sentry', required=False, default=None, type=str,
          help='Path to the config file containing the Sentry capture URL')
def lights433(host, port, adapter, adapter_args, switches, sentry):

    try:
        adapter_kwargs = {
            k: v
            for pair in adapter_args.split(',') for k, v in pair.split('=')
        }
    except:
        raise BadArgumentsError(adapter_args)

    adapter = get_adapter(adapter)(**adapter_kwargs)

    sentry_client, sentry_url = None, None
    if sentry or os.path.exists(DEFAULT_SENTRY_CONF):
        sentry = sentry if sentry is not None else DEFAULT_SENTRY_CONF
        with open(sentry, 'r') as f:
            sentry_url = f.read().strip()
        if not sentry_url:
            log.error("No sentry URL specified in [%s]" % sentry)
            sys.exit(1)
        else:
            sentry_client = Client(sentry_url)
            log.info("Sentry client configured!")

    try:
        log.info("Loading switch configurations from [%s]" % switches)
        server = Lights433Server(host, port, adapter, switches)
    except:
        if sentry_client:
            sentry_client.captureException()
        raise

    if sentry_client:
        Sentry(dsn=sentry_url).init_app(server.app)
    server.run()


def main():
    try:
        app.run()
    except clip.ClipExit:
        pass


if __name__ == '__main__':
    main()
