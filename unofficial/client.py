from secrets import key
import socket
import time, sys, random

p = 21652247421304131782679331804390761485569

def ru(st):
    buf = b''
    while st not in buf:
        c = s.recv(1)
        assert len(c) == 1
        buf += c
    return buf


s = socket.create_connection(('192.168.2.100', 1337))
chall = map(int,ru(b'\n').split())

if len(sys.argv) > 1 and sys.argv[1] == 'fail':
    resp = str(random.randrange(p)).encode('utf-8')
else:
    resp = str(sum(x*y%p for x, y in zip(chall, key))).encode('utf-8')
s.sendall(resp + b'\n')
time.sleep(1)
