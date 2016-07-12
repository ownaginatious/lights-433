#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from functools import wraps, partial
import logging
from threading import Lock
from flask import Flask, jsonify, make_response
from flask_basic_roles import BasicRoleAuth
import time
from .driver import SignalDriver


log = logging.getLogger(__name__)

_RESET_PORT = 3


class UnknownConfigSettingError(Exception):
    pass


class UserAlreadyExistsError(Exception):
    pass


class SwitchAlreadyExistsError(Exception):
    pass


def sentry_capture(client=None):
    def wrapper(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except:
                if client:
                    client.captureException()
                raise


class Lights433Server(object):

    def __init__(self, host, port, serial, baud, timeout, switch_conf,
                 resettable=False, sentry=None):

        if resettable:

            # It is assumed this is always a Raspberry Pi for now.
            import RPi.GPIO as GPIO

            GPIO.setmode(GPIO.BCM)
            GPIO.setup(_RESET_PORT, GPIO.OUT)
            GPIO.output(_RESET_PORT, GPIO.HIGH)

            def _reset_function():
                GPIO.output(_RESET_PORT, GPIO.LOW)
                time.sleep(1)  # Long delay to ensure device has reset.
                GPIO.output(_RESET_PORT, GPIO.HIGH)
                time.sleep(2)  # Device reboot waiting period.

            reset_function = _reset_function

        self.serial_lock = Lock()
        self.host = host
        self.port = port
        self.driver = sentry_capture(sentry)(
            SignalDriver(serial,
                         baud_rate=baud, timeout=timeout,
                         port_setup=locals().get('reset_function', None))
        )

        users = {}
        switches = {}
        with open(switch_conf, 'r') as f:
            for line in f:
                if line.startswith('switch:'):
                    _, switch_id, on_signal, off_signal, pulse_length, \
                        allowed = line.strip().split(':')
                    if switch_id in switches:
                        raise SwitchAlreadyExistsError(switch_id)
                    switches[switch_id] = dict(on_signal=unicode(on_signal),
                                               off_signal=unicode(off_signal),
                                               pulse_length=int(pulse_length),
                                               users=allowed.split(','))
                    log.info("Loaded switch [%s]..." % switch_id)

                elif line.startswith('user:'):
                    _, user_id, password = line.strip().split(':')
                    if user_id in users:
                        raise UserAlreadyExistsError(user_id)
                    users[user_id] = password
                else:
                    raise UnknownConfigSettingError(line.split(':')[0])

        self.app = Flask(__name__)
        auth = BasicRoleAuth()

        for user_id, password in users.items():
            auth.add_user(user=user_id, password=password)

        @sentry_capture(sentry)
        def switch(op, switch_id, conf):
            with self.serial_lock:
                op = op.lower()
                if op not in ('on', 'off'):
                    return make_response(jsonify(
                               error='no such switch \"%s\" or method "%s"'
                                     % (switch_id, op)), 404)
                f = partial(self.driver.send_signal,
                            conf['%s_signal' % op], conf['pulse_length'], 5)
                try:
                    f()
                except:
                    self.driver.reconnect()  # Reboot the transmitter
                    f()
                return make_response(jsonify(
                           message='%s switched %s!' % (switch_id, op)), 200)
        for switch_id, conf in switches.items():
            switch_func = (lambda x, y:
                           lambda op: switch(op, x, y))(switch_id, conf)
            switch_func.__name__ = str(switch_id)

            self.app.route('/switch/%s/<op>' % switch_id)(
                auth.require(users=conf['users'])(switch_func)
            )

    def run(self):
        self.app.run(host=self.host, port=self.port)
