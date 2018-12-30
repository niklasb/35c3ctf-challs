import os, math, sys, binascii
from secrets import key, flag
from hashlib import sha256
from Crypto.Cipher import AES

p = 21652247421304131782679331804390761485569
bits = 128
N = 40

def rand():
    return int.from_bytes(os.urandom(bits // 8), 'little')

def keygen():
    return [rand() for _ in range(N)]

if __name__ == '__main__':
    # key = keygen()   # generated once & stored in secrets.py
    challenge = keygen()
    print(' '.join(map(str, challenge)))
    response = int(input())
    if response != sum(x*y%p for x, y in zip(challenge, key)):
        print('ACCESS DENIED')
        exit(1)

    print('ACCESS GRANTED')
    cipher = AES.new(
            sha256(' '.join(map(str, key)).encode('utf-8')).digest(),
            AES.MODE_CFB,
            b'\0'*16)
    print(binascii.hexlify(cipher.encrypt(flag)).decode('utf-8'))
