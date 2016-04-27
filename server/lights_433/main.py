#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals
from .server import Lights433Server
import clip

app = clip.App()


@app.main(description='An HTTP server daemon for controlling 433MHz '
                      'light switches')
@clip.opt('-h', '--host', default='127.0.0.1', type=str,
          help='The interface to listen and permit connections on')
@clip.opt('-p', '--port', default=8080, type=int,
          help='The port to run the server on')
@clip.opt('-g', '--gpio', required=False,
          help='The device for controlling GPIO (if necessary)')
@clip.arg('serial', required=True, help='The port to the serial device '
                                        'that generates the signals')
@clip.opt('-b', '--baud', required=False, default=9600, type=int,
          help='Baud rate of the serial interface')
@clip.opt('-t', '--timeout', required=False, default=1, type=int,
          help='The timeout of the serial interface')
@clip.arg('spec', required=True, help='Path to the spec file for users '
                                      'and signals')
def lights433(host, port, gpio, serial, baud, timeout, spec):
    server = Lights433Server(host, port, serial, baud, timeout, spec, gpio)
    server.start()


def main():
    try:
        app.run()
    except clip.ClipExit:
        pass

if __name__ == '__main__':
    main()
