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


def mul_karatsuba(a: int, b: int) -> int:
    sign = -1 if (a < 0) ^ (b < 0) else 1
    x, y = abs(a), abs(b)

    def kar(u: int, v: int) -> int:
        if u == 0 or v == 0:
            return 0
        if u.bit_length() <= 64 and v.bit_length() <= 64:
            return u * v
        n = max(u.bit_length(), v.bit_length())
        m = n // 2
        uh, ul = u >> m, u & ((1 << m) - 1)
        vh, vl = v >> m, v & ((1 << m) - 1)
        z0 = kar(ul, vl)
        z2 = kar(uh, vh)
        z1 = kar(ul + uh, vl + vh) - z2 - z0
        return (z2 << (2 * m)) + (z1 << m) + z0

    return sign * kar(x, y)


def mul_chunked(a: int, b: int) -> int:
    sign = -1 if (a < 0) ^ (b < 0) else 1
    x, y = abs(a), abs(b)
    if x == 0 or y == 0:
        return 0
    BASE_EXP = 4
    base = 10 ** BASE_EXP
    ax, ay = [], []
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
    res = 0
    for d in reversed(out):
        res = res * base + d
    return res * sign

