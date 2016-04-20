import codecs
from collections import namedtuple
import logging
import serial
import struct
import time

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
    def __init__(self, actual, expected):
        actual_msg = _RESPONSE_DEFINITIONS \
                     .get(actual, "Strange response: %s" % repr(actual))
        expected_msg = _RESPONSE_DEFINITIONS.get(expected, repr(expected))
        message = "[Expected] %s, [Actual] %s" \
                  % (expected_msg, actual_msg)
        super(BadResponseError, self).__init__(message)


class RadioTimeout(Exception):
    pass


class SignalDriver(object):

    def __init__(self, serial_device_file, baud_rate=_DEFAULT_BAUD,
                 timeout=_DEFAULT_TIMEOUT):

        self.serial_device_file = serial_device_file
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.conn = None
        self.reconnect()

    def reconnect(self):
        if self.conn:
            try:
                self.conn.close()
            except Exception as e:
                LOG.warn("Exception when terminating connection: %s", str(e))

        self.conn = serial.Serial(self.serial_device_file,
                                  self.baud_rate,
                                  timeout=self.timeout)

        # Time for the ATMega328P to complete boot in the event of a
        # serial-triggered reset.
        time.sleep(3)

    def _assert_response(self, expected, actual=None):
        if not actual:
            actual = self.conn.read()
        if actual != expected:
            raise BadResponseError(actual, expected)

    def _read_2byte_int(self):
        return struct.unpack('<H', self.conn.read(2))

    def _write_as_2bytes(self, x):
        if isinstance(x, str):
            x = ord(x)
        self.conn.write(struct.pack("<H", x))

    def _perform_handshake(self):
        self.conn.write(_PROTOCOL_HEADER)
        self.conn.write(_PROTOCOL_VERSION)
        self.conn.flush()
        self._assert_response(_HELLO)

    def send_signal(self, message, pulse_length, repetitions=1, protocol=1):
        self._perform_handshake()
        self.conn.write(_WRITE_433)
        self.conn.flush()
        self._assert_response(_AWAITING_DATA)

        # Send the message definition payload.
        self._write_as_2bytes(protocol)
        self._write_as_2bytes(pulse_length)
        self._write_as_2bytes(repetitions)
        self._write_as_2bytes(len(message))
        if isinstance(message, bytes):
            self.conn.write(message)
        else:
            self.conn.write(codecs.decode(message, 'hex'))
        self._assert_response(_GOODBYE)

    def read_signals(self, message_num, radio_timeout=10000):
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
            yield Signal(protocol, delay, message)
        self._assert_response(_GOODBYE)
