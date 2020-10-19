import argparse
import threading
import time
import smbus
import socket
import struct
import sys

from smbpi.ads1115 import ADS1115, MUX_AIN0, MUX_AIN1, MUX_AIN2, MUX_AIN3, PGA_4V,\
    DATA_128, COMP_MODE_TRAD, COMP_POL_LOW, COMP_NON_LAT, COMP_QUE_DISABLE,\
    MODE_SINGLE, OS


class Remote(threading.Thread):
    def __init__(self, bus, addr=0x48, maxVal=26560, destAddr=None, destPort=None):
        threading.Thread.__init__(self)
        self.daemon = True
        self.adc = ADS1115(bus, addr)
        self.maxVal = maxVal
        self.destAddr = destAddr
        self.destPort = destPort
        self.centerX1 = 500
        self.centerY1 = 500
        self.centerX2 = 500
        self.centerY2 = 500

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def readSample(self, chan):
        if (chan == 1):
            ain = MUX_AIN1
        elif (chan == 2):
            ain = MUX_AIN2
        elif (chan == 3):
            ain = MUX_AIN3
        else:
            ain = MUX_AIN0

        self.adc.write_config(ain | PGA_4V | MODE_SINGLE | OS | DATA_128 | COMP_MODE_TRAD | COMP_POL_LOW | COMP_NON_LAT | COMP_QUE_DISABLE)
        self.adc.wait_samp()
        v = self.adc.read_conversion()

        if (v > self.maxVal):
            v = self.maxVal

        # normalize to (0,0) is upper-left, range of 0-1000
        v = float(self.maxVal-v)/float(self.maxVal) * 1000.0

        return int(v)

    def run(self):
        lastX1 = None
        lastX2 = None
        lastY1 = None
        lastY2 = None
        lastButtons = None
        lastKeypad = None
        while True:
            x1 = self.readSample(0)
            y1 = self.readSample(1)
            x2 = self.readSample(2)
            y2 = self.readSample(3)
            buttons = 0
            keypad = 0
            if (lastX1 != x1) or (lastY1 != y1) or (lastX2 != x2) or (lastY2 != y2) or (lastButtons != buttons) or (lastKeypad != keypad):
                data = struct.pack("!IIIIIIIIII",
                                   x1, y1, x2, y2,
                                   self.centerX1,
                                   self.centerY1,
                                   self.centerX2,
                                   self.centerY2,
                                   buttons, keypad)
                lastX1 = x1
                lastY1 = y1
                lastX2 = x2
                lastY2 = y2
                lastButtons = buttons
                lastKeypad = keypad

                self.sock.sendto(data, (self.destAddr, self.destPort))

    def test(self):
        while True:
            print "%d %d %d %d" % (self.readSample(0), self.readSample(1), self.readSample(2), self.readSample(3))
            time.sleep(0.1)


def parse_args():
    parser = argparse.ArgumentParser()

    defs = {"diags": False,
            "daemon": False,
            "host": None,
            "port": 1234}

    _help = 'Dump joystick output to stdout (default: %s)' % defs['diags']
    parser.add_argument(
        '-D', '--diags', dest='diags', action='store_true',
        default=defs['diags'],
        help=_help)

    _help = 'Daemonize (default: %s)' % defs['daemon']
    parser.add_argument(
        '-d', '--daemon', dest='daemon', action='store_true',
        default=defs['daemon'],
        help=_help)

    _help = 'Destination host (default: %s)' % defs['host']
    parser.add_argument(
        '-H', '--host', dest='host', action='store', type=str,
        default=defs['host'],
        help=_help)

    _help = 'Destination port (default: %d)' % defs['port']
    parser.add_argument(
        '-p', '--port', dest='port', action='store', type=int,
        default=defs['port'],
        help=_help)          

    args = parser.parse_args()

    return args


def main():
    args = parse_args()

    bus = smbus.SMBus(1)
    remote = Remote(bus, destAddr=args.host, destPort=args.port)

    if args.diags:
        remote.test()

    remote.start()

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
