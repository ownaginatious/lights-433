#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import codecs
from collections import namedtuple
import logging
import serial
import struct

_PROTOCOL_HEADER = b'CLS'
_PROTOCOL_VERSION = b'0'
_DEFAULT_BAUD = 9600
_DEFAULT_TIMEOUT = 10

# Instructions
_READ_433 = b'1'
_WRITE_433 = b'2'

# Responses
_AWAITING_DATA = b'B'
_INCOMING_DATA = b'C'
_RADIO_TIMEOUT = b'D'
_HELLO = b'E'
_GOODBYE = b'F'
_BAD_HEADER = b'G'
_WRONG_VERSION = b'H'
_HEARTBEAT = b'I'
_UNKNOWN_OP_CODE = b'Z'

# For debugging purposes
_RESPONSE_DEFINITIONS = {
    _AWAITING_DATA: "awaiting additional data",
    _INCOMING_DATA: "there is an incoming radio transmission",
    _RADIO_TIMEOUT: "timed out awaiting radio transmission",
    _HELLO: "protocol hello (beginning handshake)",
    _GOODBYE: "protocol goodbye (terminating communication)",
    _BAD_HEADER: "bad protocol header received",
    _WRONG_VERSION: "bad protocol version received",
    _UNKNOWN_OP_CODE: "unknown request received"
}

Signal = namedtuple('Signal', ['protocol', 'pulse_length', 'message'])

LOG = logging.getLogger(__name__)


class BadResponseError(Exception):
    """
    Represents an either unintelligable or unexpected response from the
    serial device.
    """

    def __init__(self, actual, expected):
        actual_msg = _RESPONSE_DEFINITIONS \
                     .get(actual, "Strange response: %s" % repr(actual))
        expected_msg = _RESPONSE_DEFINITIONS.get(expected, repr(expected))
        message = "[Expected] %s, [Actual] %s" \
                  % (expected_msg, actual_msg)
        super(BadResponseError, self).__init__(message)


class RadioTimeout(Exception):
    """
    Raised in the event of a radio timeout when waiting for an incoming signal.
    """
    pass


class SignalDriver(object):

    def __init__(self, serial_device_file, baud_rate=_DEFAULT_BAUD,
                 timeout=_DEFAULT_TIMEOUT, port_setup=None):
        """
        Connects to a serial interface and initializes a new signal
        driver instance.

        :param serial_device_file: the time to resolve
        :type serial_device_file: str or unicode
        :param baud_rate: the baud rate of the interface
        :type baud_rate: int
        :param timeout: timeout of the interface in seconds
        :type timeout: int
        :param port_setup: a function to do any necessary work in restarting
                           the interface or device (default None)
        :type port_setup: function

        :returns: tuple of days and datetime.time
        """
        self.serial_device_file = serial_device_file
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.conn = None
        self.port_setup = port_setup
        if self.port_setup is not None and \
           not hasattr(self.port_setup, '__call__'):
            raise Exception('Supplied argument for port_setup '
                            'is not a function')
        self.reconnect()

    def reconnect(self):
        """
        Reconnects to the serial interface and resets the device (optional)
        """
        if self.conn:
            try:
                self.conn.close()
            except Exception as e:
                LOG.warn("Exception when terminating connection: %s", str(e))

        self.conn = serial.Serial(self.serial_device_file,
                                  self.baud_rate,
                                  timeout=self.timeout)
        self.conn.flush()

        if self.port_setup:
            self.port_setup()

    def _assert_response(self, expected, actual=None):
        """
        Asserts that the next response matches the expected response and
        raises an exception otherwise.

        :param expected: the expected response
        :type expected: byte
        :param actual: the actual response (read from interface if unspecified)
        :type actual: byte

        :returns: none; raises error on assertion failure
        """
        if not actual:
            actual = self.conn.read()
        if actual != expected:
            raise BadResponseError(actual, expected)

    def _read_2byte_int(self):
        """
        Reads a two-byte integer from the serial interface
        (i.e. short on most desktop systems)

        :returns: int
        """
        return struct.unpack('<H', self.conn.read(2))

    def _write_as_2bytes(self, x):
        """
        Writes a number/character to the serial interface as 2-bytes
        (i.e. short on most desktop systems)

        :param x: the number to write
        :type x: int or byte
        """
        if isinstance(x, str):
            x = ord(x)
        self.conn.write(struct.pack("<H", x))

    def _perform_handshake(self):
        """
        Performs the handshake with the serial device to initializes
        accepting incoming commands.
        """
        self.conn.write(_PROTOCOL_HEADER)
        self.conn.write(_PROTOCOL_VERSION)
        self.conn.flush()
        self._assert_response(_HELLO)

    def send_signal(self, message, pulse_length, repetitions=1, protocol=1):
        """
        Instructs the serial device to broadcast a 433MHz signal with the
        specified properties.

        :param message: the message to send
        :type message: str or unicode
        :param pulse_length: pulse length of the message in microseconds
        :type pulse_length: int
        :param repetitions: number of times to broadcase the signal (default 1)
        :type repetitions: int
        :param protocol: the protocol version to use (default 1)
        :type protocol: int
        """
        self._perform_handshake()
        self.conn.write(_WRITE_433)
        self.conn.flush()
        self._assert_response(_AWAITING_DATA)

        # Send the message definition payload.
        self._write_as_2bytes(protocol)
        self._write_as_2bytes(pulse_length)
        self._write_as_2bytes(repetitions)
        if isinstance(message, unicode):
            message = codecs.decode(message, 'hex')
        self._write_as_2bytes(len(message))
        self.conn.write(message)
        self._assert_response(_GOODBYE)

    def read_signals(self, message_num, radio_timeout=10000):
        """
        Reads a specified number of captured 433MHz broadcasts within a certain
        timeout.

        :param message_num: the number of messages to capture
        :type message_num: int
        :param radio_timeout: the number of milliseconds to wait before timeout
        :type radio_timeout: int

        :returns: generator of Signal
        """
        self._perform_handshake()
        self.conn.write(_READ_433)
        self.conn.flush()
        self._assert_response(_AWAITING_DATA)

        # Send desired spec.
        self._write_as_2bytes(message_num)
        self._write_as_2bytes(radio_timeout)

        # Begin reading message data.
        for _ in range(message_num):
            while True:
                resp = self.conn.read()
                if resp == _HEARTBEAT:
                    continue
                if resp == _RADIO_TIMEOUT:
                    raise RadioTimeout(radio_timeout)
                self._assert_response(_INCOMING_DATA, actual=resp)
                break
            protocol = self._read_2byte_int()[0]
            delay = self._read_2byte_int()[0]
            size = self._read_2byte_int()[0]
            message = self.conn.read(size)
            yield Signal(protocol, delay, codecs.encode(message, 'hex'))
        self._assert_response(_GOODBYE)
