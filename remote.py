import argparse
import threading
import time
import select
import smbus
import socket
import struct
import sys
import RPi.GPIO as GPIO

from smbpi.ads1115 import ADS1115, MUX_AIN0, MUX_AIN1, MUX_AIN2, MUX_AIN3, PGA_4V,\
    DATA_128, COMP_MODE_TRAD, COMP_POL_LOW, COMP_NON_LAT, COMP_QUE_DISABLE,\
    MODE_SINGLE, OS

# columns
K369 = 23
K147 = 24
K0258 = 25
KSPR = 4
# rows
K321S = 19
K654P = 16
K987R = 26
K0 = 20
# buttons
TRIG0 = 5
TRIG1 = 6

KEY_1 =         1
KEY_2 =         2
KEY_3 =         4
KEY_4 =         8
KEY_5 =      0x10
KEY_6 =      0x20
KEY_7 =      0x40
KEY_8 =      0x80
KEY_9 =     0x100
KEY_0 =     0x200
KEY_HASH =  0x400
KEY_STAR =  0x800
KEY_S =    0x1000
KEY_P =    0x2000
KEY_R =    0x4000

BUT0  =         1
BUT1  =         2
BUTIGNORE = 0x4000
BUTACK =   0x8000

class Remote(threading.Thread):
    def __init__(self, bus, addr=0x48, maxVal=26560, dests=[]): #destAddr=None, destPort=None):
        threading.Thread.__init__(self)
        self.daemon = True
        self.adc = ADS1115(bus, addr)
        self.maxVal = maxVal
        self.dests = dests
        #self.destAddr = destAddr
        #self.destPort = destPort
        self.centerX1 = 500
        self.centerY1 = 500
        self.centerX2 = 500
        self.centerY2 = 500

        # set the columns as output strobes
        GPIO.setup(K369, GPIO.IN)
        GPIO.setup(K147, GPIO.IN)
        GPIO.setup(K0258, GPIO.IN)
        GPIO.setup(KSPR, GPIO.IN)

        # set the rows as inputs
        GPIO.setup(K321S, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(K654P, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(K987R, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(K0, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # set the triggers as inputs
        GPIO.setup(TRIG0, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(TRIG1, GPIO.IN, pull_up_down=GPIO.PUD_UP)        

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

    def pollKeypad(self):
        keys = 0

        # pull K369 low
        GPIO.setup(K369, GPIO.OUT)
        GPIO.output(K369, 0)

        if GPIO.input(K0)==0:
            keys |= KEY_HASH
        if GPIO.input(K321S)==0:
            keys |= KEY_3
        if GPIO.input(K654P)==0:
            keys |= KEY_6
        if GPIO.input(K987R)==0:
            keys |= KEY_9

        # restore K369 to open collector
        GPIO.setup(K369, GPIO.IN)

        # pull K369 low
        GPIO.setup(K147, GPIO.OUT)
        GPIO.output(K147, 0)
    
        if GPIO.input(K0)==0:
            keys |= KEY_STAR
        if GPIO.input(K321S)==0:
            keys |= KEY_1
        if GPIO.input(K654P)==0:
            keys |= KEY_4
        if GPIO.input(K987R)==0:
            keys |= KEY_7

        # restore K147 to open collector
        GPIO.setup(K147, GPIO.IN)

        # pull K369 low
        GPIO.setup(K0258, GPIO.OUT)
        GPIO.output(K0258, 0)

        if GPIO.input(K0)==0:
            keys |= KEY_0
        if GPIO.input(K321S)==0:
            keys |= KEY_2
        if GPIO.input(K654P)==0:
            keys |= KEY_5
        if GPIO.input(K987R)==0:
            keys |= KEY_8

        # restore K369 to open collector
        GPIO.setup(K0258, GPIO.IN)

        # pull KSPR low
        GPIO.setup(KSPR, GPIO.OUT)
        GPIO.output(KSPR, 0)

        if GPIO.input(K321S)==0:
            keys |= KEY_S
        if GPIO.input(K654P)==0:
            keys |= KEY_P
        if GPIO.input(K987R)==0:
            keys |= KEY_R

        # restore KSPR to open collector
        GPIO.setup(KSPR, GPIO.IN)

        return keys

    def pollButtons(self):
        buttons = 0
        if GPIO.input(TRIG0) == 0:
            buttons |= BUT0
        if GPIO.input(TRIG1) == 0:
            buttons |= BUT1
        return buttons

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
            buttons = self.pollButtons()
            keypad = self.pollKeypad()
            if (lastX1 != x1) or (lastY1 != y1) or (lastX2 != x2) or (lastY2 != y2) or (lastButtons != buttons) or (lastKeypad != keypad):
                data = struct.pack("!IIIIIIIIII",
                                   x1, y1, x2, y2,
                                   self.centerX1,
                                   self.centerY1,
                                   self.centerX2,
                                   self.centerY2,
                                   buttons,
                                   keypad)
                lastX1 = x1
                lastY1 = y1
                lastX2 = x2
                lastY2 = y2
                lastButtons = buttons
                lastKeypad = keypad

                for dest in self.dests:
                    self.sock.sendto(data, dest)

                #self.sock.sendto(data, (self.destAddr, self.destPort))

    def test(self):
        while True:
            print "Pots %d %d %d %d Buttons %02X Keypad %02X" % (self.readSample(0), self.readSample(1), self.readSample(2), self.readSample(3), self.pollButtons(), self.pollKeypad())
            time.sleep(0.1)

    def ping(self, count):
        for i in range(0,count):
            data = struct.pack("!IIIIIIIIII",
                               0, 0, 0, 0,
                               0,
                               0,
                               0,
                               0,
                               BUTACK | BUTIGNORE,
                               0)

            for dest in self.dests:
                tStart = time.time()

                self.sock.sendto(data,dest)

                inputs = [self.sock]
                (readable, writable, exceptional) = select.select(inputs, [], [])
                if readable:
                    data, junk = self.sock.recvfrom(1024)
                    print "Ping %d time %d ms" % (i, int((time.time()-tStart) * 1000))
                else:
                    print "Ping %d failed" ^ i


def parse_args():
    parser = argparse.ArgumentParser()

    defs = {"diags": False,
            "daemon": False,
            "port": 1234,
            "ping": 0}

    _help = 'Dump joystick output to stdout (default: %s)' % defs['diags']
    parser.add_argument(
        '-D', '--diags', dest='diags', action='store_true',
        default=defs['diags'],
        help=_help)

    _help = 'Do some pings(default: %d)' % defs['ping']
    parser.add_argument(
        '-P', '--ping', dest='ping', action='store', type=int,
        default=defs['ping'],
        help=_help)        

    _help = 'Daemonize (default: %s)' % defs['daemon']
    parser.add_argument(
        '-d', '--daemon', dest='daemon', action='store_true',
        default=defs['daemon'],
        help=_help)

    _help = 'Destination host:port'
    parser.add_argument(
        '-H', '--host', dest='hosts', action="append", default=[],
        help=_help)

    args = parser.parse_args()

    return args


def main():
    args = parse_args()

    dests = []
    for host in args.hosts:
        parts = host.split(":")
        if len(parts)==1:
            name = parts[0]
            port = 1234
        else:
            name = parts[0]
            port = int(parts[1])
        dests.append( (name, port) )

    print dests

    GPIO.setmode(GPIO.BCM)

    bus = smbus.SMBus(1)
    remote = Remote(bus, dests = dests)

    if args.ping > 0:
        remote.ping(args.ping)

    if args.diags:
        remote.test()

    remote.start()

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
