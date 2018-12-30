#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pyparsing import (Literal, Word, Group, ZeroOrMore, Forward,
        alphas, alphanums, Regex, Suppress)
import os, tempfile, re
from subprocess import Popen, PIPE

ROOT = os.path.dirname(os.path.abspath(__file__))
HSK_TEMPLATE = ROOT + '/EvmCompiler.hs'

class Parser():
    def __init__(self):
        number = Regex(r'\d+')
        ident = Word(alphas, alphanums + "_'")

        plus, minus, mult, mod = map(Literal, '+-*%')
        lpar, rpar = map(Suppress, '()')
        addop = plus | minus
        multop = mult | mod
        expr = Forward()
        atom = (number
                | Literal('getBalance') + lpar + expr + rpar
                | Literal('setBalance') + lpar + expr + Literal(',') + expr + rpar
                | Literal('boundscheck') + lpar + expr + Literal(',') + expr + Literal(',') + expr + rpar
                | ident
                ).setParseAction(self.push) | Group(lpar + expr + rpar)
        term = atom + ZeroOrMore((multop + atom).setParseAction(self.push))
        expr << term + ZeroOrMore((addop + term).setParseAction(self.push))

        self.statement = (ident + Literal('=') + expr).setParseAction(self.setLhs) | expr

        self.curVar = 0
        self.out = []

    def addLine(self, line):
        self.exprStack = []
        self.lhs = None
        self.statement.parseString(line, parseAll=True)
        self.build(self.lhs and 'var_%s' % self.lhs)

    def addFile(self, code):
        lines = [line for line in code.splitlines()
                    if line.strip() and not line.strip().startswith('#')]
        for l in lines:
            l = l.strip()
            if not l or l.startswith('#'):
                continue
            self.addLine(l)

    def push(self, strg, loc, toks):
        self.exprStack.append(toks[0])

    def setLhs(self, strg, loc, toks):
        self.lhs = toks[0]

    def tmpVar(self):
        self.curVar += 1
        return 'tmp_%d' % self.curVar

    def build(self, var=None):
        opsym = {
            '+': '➕',
            '*': '∗',
            '-': '–',
            '%': '÷',
        }

        op = self.exprStack.pop()
        var = var or self.tmpVar()
        if op in '+-*%':
            op2 = self.build()
            op1 = self.build()
            hsk = r'%s %s %s' % (op1, opsym[op], op2)
        elif op == 'getBalance':
            arg1 = self.build()
            hsk = 'getBalance %s' % arg1
        elif op == 'setBalance':
            arg2 = self.build()
            arg1 = self.build()
            hsk = 'setBalance %s %s' % (arg1, arg2)
        elif op == 'boundscheck':
            arg3 = self.build()
            arg2 = self.build()
            arg1 = self.build()
            hsk = 'boundscheck %s %s %s' % (arg1, arg2, arg3)
        elif op[0].isalpha():
            return 'var_%s' % op
        else:
            hsk = 'singleton (Proxy ∷ Proxy %s)' % op
        self.out.append('%s ≻≻≈ \%s ->' % (hsk, var))
        return var

    def finalize(self):
        self.out.append('ret ()')

    def get(self):
        return self.out

class HskTypeError(Exception):
    pass

def script_to_hsk(code):
    p = Parser()
    try:
        p.addFile(code)
    except:
        raise SyntaxError()
    p.finalize()
    builder = '\n  ' + '\n  '.join(p.get())
    with open(HSK_TEMPLATE, encoding='utf-8') as f:
        hsk = f.read()
    hsk = re.sub(
            r'(-- <GENERATED CODE>)(?:.|\n)*(-- </GENERATED CODE>)',
            lambda m: '%s\ncode = (%s)\n%s' % (m.group(1), builder, m.group(2)),
            hsk)
    return hsk

def run_hsk(hsk, timeout):
    with tempfile.NamedTemporaryFile(suffix='.hs') as f:
        f.write(hsk.encode('utf-8'))
        f.flush()
        proc = Popen(['runhaskell', f.name, 'compile'],
                    stdin=PIPE, stdout=PIPE, stderr=PIPE)
        evmcode, err = proc.communicate(timeout=timeout)
        if proc.returncode != 0:
            raise HskTypeError()
        return evmcode

def compile_script(code, timeout=60):
    return run_hsk(script_to_hsk(code), timeout)


def test():
    good = [
        'getBalance(100)',
        'getBalance(getBalance(100)%5 + 100)',
        '1%(getBalance(100)%100+1)',
        'getBalance(100)%10000+10000-10000',
        str(2**256-1),

        '''
        MAX_BALANCE = 1000000000
        from = 100
        to = 101
        amount = 1337

        bal_from = boundscheck(getBalance(from), amount, MAX_BALANCE)
        bal_to = boundscheck(getBalance(to), 0, MAX_BALANCE - amount)
        setBalance(from, bal_from - amount)
        setBalance(to, bal_to + amount)
        ''',

        '''
        MAX_BALANCE = 1000000000
        acc = 100
        amount = 1337

        bal = boundscheck(getBalance(acc), 0, MAX_BALANCE - amount)
        setBalance(acc, bal + amount)
        '''
    ]
    bad = [
        'getBalance(99)',
        'getBalance(100)+1',
        'getBalance(100)+1-1',
        '0-1',
        '0+1-2',
        'getBalance(100)%10+1-2',
        'getBalance(getBalance(100))',
        'getBalance(getBalance(100)%6 + 100)',
        'getBalance(getBalance(100)%5 + 99)',
        '1%(getBalance(100)%100)',
        str(2**256),
        '%d+1' % (2**256-1),
    ]

    print('======== GOOD ========')
    for scr in good:
        print(scr)
        print()
        compile_script(scr, timeout=20)

    print('======== BAD ========')
    for scr in bad:
        print(scr)
        print()
        try:
            compile_script(scr, timeout=200)
            assert 0, 'Should have thrown but succeeded'
        except HskTypeError:
            pass


if __name__ == '__main__':
    import sys
    if sys.argv[1] == 'TEST':
        test()
    else:
        hsk = script_to_hsk(open(sys.argv[1]).read())
        print(hsk)
        print(repr(run_hsk(hsk, timeout=1000)))
