from . import Adapter

import serial
import time

import RPi.GPIO as GPIO


SERIAL_HANDLE_FILE = "/dev/ttyAMA0"


class RPiAdapter(Adapter):

    def __init__(self, reset_pin):
        """
        Initializes a serial port connection from a Raspberry Pi.

        :param reset_pin: Pin that the reset port of the external device
                           is connected to.
        """
        self._gpio_ready = False
        if isinstance(reset_pin, basestring):
            self._reset_pin = int(reset_pin)
        else:
            self._reset_pin = reset_pin
        self._serial_connection = None

    def _assert_ready(self):
        if not self._gpio_ready:
            raise IOError("GPIO not yet initialized")
        elif not self._serial_connection:
            raise IOError("Serial connection not yet initialized")

    def _reset_serial_connection(self):
        self._serial_connection = serial.Serial(
            SERIAL_HANDLE_FILE, 9600, timeout=1)
        self._serial_connection.reset_input_buffer()

    def _set_gpio(self):
        # Setup the reset pin.
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self._reset_pin, GPIO.OUT)
        GPIO.output(self._reset_pin, GPIO.HIGH)
        self._gpio_ready = True

    def initialize(self):

        try:
            self._assert_ready()
        except IOError:
            self._set_gpio()
            self._reset_serial_connection()

    def reset(self):

        self._assert_ready()

        # We can somehow lose this context from time to time.
        # Better reset the port configuration when resetting the device.
        self._set_gpio()

        GPIO.output(self._reset_pin, GPIO.LOW)
        time.sleep(1)  # Long delay to ensure device has reset.
        GPIO.output(self._reset_pin, GPIO.HIGH)
        time.sleep(2)  # Device reboot waiting period.

        self._serial_connection.reset_input_buffer()

    def close(self):
        GPIO.cleanup(channel=self._reset_pin)
        if self._serial_connection:
            self._serial_connection.close()
            self._serial_connection = None
        self._gpio_ready = False

    def read(self, *args, **kwargs):
        self._assert_ready()
        return self._serial_connection.read(*args, **kwargs)

    def write(self, *args, **kwargs):
        self._assert_ready()
        return self._serial_connection.write(*args, **kwargs)

    def flush(self):
        self._assert_ready()
        self._serial_connection.flush()
