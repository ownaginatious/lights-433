import serial
import struct
import sys
import time
import codecs

def as_short(x):
    if isinstance(x, str):
        x = ord(x)
    return struct.pack("<H", x)

s = serial.Serial('/dev/ttyACM0', 9600, timeout=10)

time.sleep(2)

def read_signal():

    s.write(b'CLS')
    s.write(b'0')
    s.write(b'1')
    s.flush()

    r = s.read()

    if r == b'B':
        print("> AWAITING DATA")
    else:
        print("BAD CODE RECEIVED %s" % r)
        sys.exit(1)

    s.write(as_short(3))
    s.write(as_short(10000))

    while True:
        r = s.read()
        if r == b'D':
            print("> RADIO TIMEOUT")
            sys.exit(1)
        elif r == b'F':
            print("> DONE")
            sys.exit(0)
        elif r == b'C':
            print("> INCOMING SIGNAL:")
            print("  > PROTOCOL: %d" % struct.unpack('<H', s.read(2)))
            print("  > DELAY: %d" % struct.unpack('<H', s.read(2)))
            size = struct.unpack('<H', s.read(2))[0]
            print("  > SIZE: %d BYTES" % size)
            print("  > DATA: %s" % s.read(size).hex())
        else:
            print(r)
            time.sleep(1000)

def write_signal():

    s.write(b'CLS')
    s.write(b'0')
    s.write(b'2')
    s.flush()

    r = s.read()

    if r == b'B':
        print("> AWAITING DATA")
    else:
        print("BAD CODE RECEIVED %s" % r)
        sys.exit(1)

    s.write(as_short(1))
    s.write(as_short(188))
    s.write(as_short(5))
    s.write(as_short(3))
    s.write(codecs.decode('3c1541', 'hex'))
    #s.write(codecs.decode('331541', 'hex'))

    print(s.read());

write_signal()
