#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from flask import Flask, jsonify, make_response
from flask_basic_roles import BasicRoleAuth
import RPi.GPIO as GPIO
import time
from .driver import SignalDriver

_RESET_PORT = 3

3\x15A
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
                        users = line.split(':')
                    switches[switch_id] = dict(on_signal=on_signal,
                                               off_signal=off_signal,
                                               pulse_length=pulse_length,
                                               users=users.split(','))
                    raise SwitchAlreadyExistsError(switch_id)
                elif line.startsWith('user:'):
                    _, user_id, password = line.split(':')
                    users[user_id] = password
                    raise UserAlreadyExistsError(user_id)
                else:
                    raise UnknownConfigSetting(line.split(':')[0])

        self.app = Flask(__name__)
        auth = BasicRoleAuth()

        for user_id, password in users:
            auth.add_user(user=user_id, password=password)

        for switch_id, conf in switches.items():

            self.app.route('/switch/%s/<op>')
            auth.require(users=conf.users)

            def switch(op):
                if op.lower() == 'on':
                    self.driver.send_signal(conf.on_signal,
                                            conf.pulse_length, 5)
                    return make_response(
                            jsonify(message='Switch \"%s\" on!' % switch_id),
                            200)
                elif op.lower() == 'off':
                    self.driver.send_signal(conf.off_signal,
                                            conf.pulse_length, 5)
                    return make_response(
                            jsonify(message='Switch \"%s\" off!' % switch_id),
                            200)
                else:
                    return make_response(
                               jsonify(error='no such switch \"%s\" or '
                                             'method "%s"' % (switch_id, op)),
                               404)

    def run(self):
        self.run()

    app = Flask(__name__)
    auth = BasicRoleAuth()
