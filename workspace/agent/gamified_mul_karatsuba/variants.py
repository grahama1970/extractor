from __future__ import annotations

# Approach 1: Shift-add ("Russian peasant")
def mul_shift_add(a: int, b: int) -> int:
    sign = -1 if (a < 0) ^ (b < 0) else 1
    x, y = abs(a), abs(b)
    res = 0
    while y > 0:
        if y & 1:
            res += x
        x <<= 1
        y >>= 1
    return res * sign


# Approach 2: Karatsuba (recursive) with cutoff
def _karatsuba(x: int, y: int, cutoff: int = 64) -> int:
    if x == 0 or y == 0:
        return 0
    # small numbers: use builtin
    if x.bit_length() <= cutoff and y.bit_length() <= cutoff:
        return x * y
    # split the numbers
    n = max(x.bit_length(), y.bit_length())
    m = n // 2
    high_x, low_x = x >> m, x & ((1 << m) - 1)
    high_y, low_y = y >> m, y & ((1 << m) - 1)

    z0 = _karatsuba(low_x, low_y, cutoff)
    z2 = _karatsuba(high_x, high_y, cutoff)
    z1 = _karatsuba(low_x + high_x, low_y + high_y, cutoff) - z2 - z0

    return (z2 << (2 * m)) + (z1 << m) + z0


def mul_karatsuba(a: int, b: int) -> int:
    sign = -1 if (a < 0) ^ (b < 0) else 1
    return sign * _karatsuba(abs(a), abs(b))


# Approach 3: Chunked schoolbook (base 10**4) for illustration
def mul_chunked(a: int, b: int) -> int:
    sign = -1 if (a < 0) ^ (b < 0) else 1
    x, y = abs(a), abs(b)
    base = 10 ** 4
    ax = []
    ay = []
    if x == 0 or y == 0:
        return 0
    while x:
        ax.append(x % base)
        x //= base
    while y:
        ay.append(y % base)
        y //= base

    n, m = len(ax), len(ay)
    out = [0] * (n + m)
    for i in range(n):
        carry = 0
        for j in range(m):
            s = out[i + j] + ax[i] * ay[j] + carry
            out[i + j] = s % base
            carry = s // base
        k = i + m
        while carry:
            s = out[k] + carry
            out[k] = s % base
            carry = s // base
            k += 1

    # reconstruct integer
    res = 0
    for d in reversed(out):
        res = res * base + d
    return res * sign

