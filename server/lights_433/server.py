#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from flask import Flask, jsonify, make_response
from flask_basic_roles import BasicRoleAuth
import RPi.GPIO as GPIO
import time
from .driver import SignalDriver

_RESET_PORT = 3


class UnknownConfigSettingError(Exception):
    pass


class UserAlreadyExistsError(Exception):
    pass


class SwitchAlreadyExistsError(Exception):
    pass


class Lights433Server(object):

    def __init__(self, host, port, serial, baud, timeout, spec, gpio=None):

        if gpio:
            # It is assumed this is a Raspberry Pi.
            # We will setup port 3.
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(_RESET_PORT, GPIO.OUT)
            GPIO.output(_RESET_PORT, GPIO.HIGH)

            def _reset_port():
                GPIO.output(_RESET_PORT, GPIO.LOW)
                time.sleep(2)
                GPIO.output(_RESET_PORT, GPIO.HIGH)

            gpio = _reset_port

        self.host = host
        self.port = port
        self.driver = SignalDriver(serial,
                                   baud_rate=baud, timeout=timeout,
                                   port_setup=gpio if gpio else lambda: None)
        users = {}
        switches = {}
        with open(spec, 'r') as f:
            for line in f:
                if line.startswith('switch:'):
                    _, switch_id, on_signal, off_signal, pulse_length, \
                        allowed = line.split(':')
                    if switch_id in switches:
                        raise SwitchAlreadyExistsError(switch_id)
                    switches[switch_id] = dict(on_signal=unicode(on_signal),
                                               off_signal=unicode(off_signal),
                                               pulse_length=pulse_length,
                                               users=allowed.split(','))

                elif line.startswith('user:'):
                    _, user_id, password = line.split(':')
                    if user_id in users:
                        raise UserAlreadyExistsError(user_id)
                    users[user_id] = password
                else:
                    raise UnknownConfigSetting(line.split(':')[0])

        self.app = Flask(__name__, host=host, port=port)
        auth = BasicRoleAuth()

        for user_id, password in users.items():
            auth.add_user(user=user_id, password=password)

        for switch_id, conf in switches.items():

            self.app.route('/switch/%s/<op>')
            auth.require(users=conf['users'])

            def switch(op):
                if op.lower() == 'on':
                    self.driver.send_signal(conf['on_signal'],
                                            conf['pulse_length'], 5)
                    return make_response(
                            jsonify(message='Switch \"%s\" on!' % switch_id),
                            200)
                elif op.lower() == 'off':
                    self.driver.send_signal(conf['off_signal'],
                                            conf['pulse_length'], 5)
                    return make_response(
                            jsonify(message='Switch \"%s\" off!' % switch_id),
                            200)
                else:
                    return make_response(
                               jsonify(error='no such switch \"%s\" or '
                                             'method "%s"' % (switch_id, op)),
                               404)

    def run(self):
        self.app.run()
