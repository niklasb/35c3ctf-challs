'''
[1] https://cr.yp.to/bib/2001/nguyen.ps
[2] https://www.math.cmu.edu/~af1p/Texfiles/RECONTRUNC.pdf
'''
from sage.all import (
    next_prime, matrix, vector, inverse_mod, is_prime,
    Integers, ZZ, RR
    )
from random import randint, randrange, seed
from IPython import embed

FAST = True

if FAST:
    ALGOS = ('fpLLL:wrapper',)
    DELTAS =(0.99,)
else:
    ALGOS = ('NTL:LLL', 'fpLLL:wrapper')
    DELTAS =(0.75, 0.9, 0.99, 0.999)

def lll_params():
    for algo in ALGOS:
        for delta in DELTAS:
            yield (algo, delta, lambda x: x.LLL(algorithm=algo, delta=delta))

def lll(L):
    for algo, delta, f in lll_params():
        for row in f(L).rows():
            yield row

def normalize(x):
    return x if next(c for c in x if c != 0) >= 0 else -x

def svp(L):
    res = None
    for x in lll(L):
        if x == 0: continue
        if res is None or x.norm() < res.norm():
            res = x
    return normalize(res)

def integer_lgs(A, b, smith=None):
    # https://groups.google.com/forum/#!topic/sage-support/mSEvNtJlvgs
    if not smith:
        smith = A.smith_form()
    D, U, V = smith
    # assert D == U*A*V
    c = U * b
    d = D.diagonal()
    y = vector(ZZ, D.ncols())
    for i in range(len(d), D.nrows()):
        assert not c[i], 'no integers solution'
    for i in range(len(d)):
        if d[i] == 0:
            assert not c[i], 'no integer solution'
            y[i] = 0
        else:
            q = c[i] / d[i]
            assert q in ZZ, 'no integer solution'
            y[i] = q
    # assert D*y == c
    return V * y

def in_lattice(L, x):
    try:
        integer_lgs(L.transpose(), x)
        return True
    except AssertionError:
        return False

def cvp_embed(L, v, b=None):
    if not b:
        b = max(max(row) for row in L.rows())

    L2 = matrix([list(row) + [0] for row in L] + [list(v) + [b]])
    res = None
    for x in lll(matrix(L2)):
        if x[-1] > 0: x = -x
        if x[-1] == -b:
            u = vector(x[:-1]) + v
            assert in_lattice(L, u)
            if res is None or (v - u).norm() < (v - res).norm():
                res = u
    return res

def cvp_babai(L, v):
    # https://cims.nyu.edu/~regev/teaching/lattices_fall_2004/ln/cvp.pdf
    # http://mslc.ctf.su/wp/plaidctf-2016-sexec-crypto-300/
    res = None
    for _, _, f in lll_params():
        B = f(L)
        G,_ = B.gram_schmidt()
        b = v
        for i in reversed(range(G.nrows())):
            c = ((b * G[i]) / (G[i] * G[i])).round()
            b -= B[i]*c
        if res is None or (v - b).norm() < res.norm():
            res = v - b
    return res

def cvp(L, v):
    res = cvp_embed(L, v)
    res2 = cvp_babai(L, v)
    if res is None or (res2 - v).norm() < (res - v).norm():
        res = res2
    return res

def mod_right_kernel(A, mod):
    # from https://ask.sagemath.org/question/33890/how-to-find-kernel-of-a-matrix-in-mathbbzn/
    # too slow though
    Zn = ZZ**A.ncols()
    M = Zn/(mod*Zn)
    phi = M.hom([M(a) for a in A] + [M(0) for _ in range(A.ncols()-A.nrows())])
    return matrix([M(b) for b in phi.kernel().gens()])

def kernel_lattice(A, mod=None):
    ''' Lattice of vectors x with Ax = 0 (potentially mod m) '''
    A = matrix(ZZ if mod is None else Integers(mod), A)
    L = [vector(ZZ, row) for row in A.right_kernel().basis()]
    if mod is not None:
        cols = len(L[0])
        for i in range(cols):
            L.append([0]*i + [mod] + [0]*(cols-i-1))
    return matrix(L)

def small_lgs(A, c=None, mod=None):
    '''
    Find short x with Ax = c (mod m).

    If m is None, solve over integers.

    If c is None, it is treated as the zero vector and the algorithm will try
    to produce a non-zero solution.

    From section 3.4 in [1]. This works by computing the lattice orthogonal to A,
    i.e. the lattice of vectors x with Ax = 0. This is not easy modulo a composite.
    '''
    A = matrix(ZZ, A)
    L = kernel_lattice(A, mod)
    if c == 0 or c is None:
        return svp(L)
    y = integer_lgs(A, c)
    return y - cvp(L, y)

def small_lgs2(A, c, mod, sol=None):
    '''
    Find short x with Ax = c (mod m).

    This is more generic because it also works for composite m, but it does
    not work for c = 0. The difference is that we don't have to compute the
    orthogonal lattice of A.

    TODO: For c = 0, we can brute force a k with small ||k|| and solve for
    c = k*mod instead.

    See [2] (p. 264-268) and https://crypto.stackexchange.com/questions/37836/
    '''
    m, n = A.dimensions()
    A = list(A)
    for i in range(n):
        A.append([0]*i + [mod] + [0]*(n-i-1))
    A = matrix(ZZ, A)
    L = A.LLL(delta=0.999999)

    for i in range(m):
        assert L[i] == 0
    L = L[m:]
    if c == 0 or c == None:
        # Brutal heuristic here, see TODO above. We are only trying one single k
        # here, namely (0, ..., 0, 1)
        x = normalize(integer_lgs(L, vector([0]*(n-1) + [mod])))
        for t in x:
            assert 0 <= x < mod
        return x

    # compute Y such that Y*A == L
    Y = []
    smith = A.transpose().smith_form()
    for i in range(L.nrows()):
        y = integer_lgs(None, L[i], smith)
        # assert At*y == L[i]
        Y.append(y)
    Y = matrix(ZZ, Y)
    # assert Y*A == L

    c = Y*vector(list(c)+[0]*n)%mod
    for i in range(len(c)):
        if c[i] * 2 >= mod:
            c[i] -= mod
        assert abs(c[i]) * 2 < mod
    return integer_lgs(Y*A, c)

def truncated_lgs(A, y, mod):
    '''
    Find short x with A(y + x) = 0 (mod m).

    This is essentially a special case of small_lgs2, might be faster?

    See [2] (p. 264-268) and https://crypto.stackexchange.com/questions/37836/
    '''

    ## This will also work usually, but might be slower
    # c = -A*y%mod
    # return y + small_lgs2(A, c, mod)

    n = A.ncols()
    A = list(matrix(ZZ, A))
    for i in range(n):
        A.append([0]*i + [mod] + [0]*(n-i-1))

    L = matrix(ZZ, A).LLL()
    W1 = L*vector(ZZ, y)
    W2 = vector([int(round(RR(w)/mod))*mod - w for w in W1])
    return L.solve_right(W2) + y


if __name__ == "__main__":
    test = 0
    while True:
        print '  Testing heterogenous LGS mod composite'
        # from secrets import key
        # p = 2**126
        # p = 2**135
        p = 21652247421304131782679331804390761485569
        assert not is_prime(p)
        Zp = Integers(p)

        n = 40 # num vars
        m = n-1 # num equations

        x = vector([randrange(lo) for _ in range(n)])
        A = matrix([[randrange(lo) for _ in range(n)] for _ in range(m)])
        c = vector(ZZ,matrix(Zp,A)*x)
        assert x == small_lgs2(A, c, p)
