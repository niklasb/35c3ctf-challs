import pkappa
import os, math, sys, binascii
from hashlib import sha256
from Crypto.Cipher import AES
from lll import small_lgs2, vector, matrix, Integers, ZZ
from secrets import key

N = 40
p = 21652247421304131782679331804390761485569
Zp = Integers(p)

os.system('rm -rf ./tmp')
pkappa.extract_pcap('surveillance.pcap', 'tmp')
pcap = pkappa.PcapDir('tmp/192.168.2.100_1337')

challs = []
answers = []

for s in pcap.all:
    server = pcap.get_server_stream(s)
    if 'GRANTED' in server:
        chall = map(int, server.split('\n')[0].split())
        flagenc = server.split('\n')[2].decode('hex')
        assert len(chall) == N
        resp = int(pcap.get_client_stream(s).strip())
        challs.append(chall)
        answers.append(resp)
    else:
        print "Invalid", s

assert len(challs) == N-1
A = matrix(challs)
c = vector(ZZ,answers)
x = small_lgs2(A, c, p)
assert list(x) == list(key)


cipher = AES.new(
        key=sha256(' '.join(map(str, x)).encode('utf-8')).digest(),
        mode=AES.MODE_CFB,
        IV=b'\0'*16)
print(cipher.decrypt(flagenc))
