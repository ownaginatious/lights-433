#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from functools import partial
import logging
from threading import Lock

from flask import Flask, jsonify, make_response
from flask_basic_roles import BasicRoleAuth

from .alexa import AlexaServer
from .driver import SignalDriver, DeviceCommError


log = logging.getLogger(__name__)


class UnknownConfigSettingError(Exception):
    pass


class UserAlreadyExistsError(Exception):
    pass


class SwitchAlreadyExistsError(Exception):
    pass


class Lights433Server(object):

    def __init__(self, host, port, adapter, switch_conf):

        self.driver_lock = Lock()
        self.host = host
        self.port = port
        self.switches = {}

        self.driver = SignalDriver(adapter)
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
        self._setup_users(users, auth)
        self._setup_switches(switches, auth)
        self.alexa = AlexaServer(self)

    def _setup_users(self, users, auth):
        for user_id, password in users.items():
            auth.add_user(user=user_id, password=password)

    def _setup_switches(self, switches, auth):
        def switch(op, switch_id, conf):
            with self.driver_lock:
                op = op.lower()
                if op not in ('on', 'off'):
                    return make_response(
                        jsonify(error='no such switch \"%s\" or '
                                      'method "%s"' % (switch_id, op)),
                        404)
                f = partial(self.driver.send_signal,
                            conf['%s_signal' % op],
                            conf['pulse_length'], 5)
                try:
                    f()
                except DeviceCommError:
                    self.driver.reconnect()  # Reboot the transmitter
                    f()
                return make_response(
                    jsonify(message='%s switched %s!' % (switch_id, op)),
                    200)

        for switch_id, conf in switches.items():
            switch_func = (lambda x, y:
                           lambda op: switch(op, x, y))(switch_id, conf)
            switch_func.__name__ = str(switch_id)
            self.switches[switch_id] = switch_func
            self.app.route('/switch/%s/<op>' % switch_id)(
                auth.require(users=conf['users'])(switch_func)
            )

    def run(self):
        self.app.run(host=self.host, port=self.port)
