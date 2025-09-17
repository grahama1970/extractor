def mul_karatsuba(a: int, b: int) -> int:
    """Karatsuba multiplication with tunable bit cutoff.
    CUTOFF_BITS = 128
    """
    sign = -1 if (a < 0) ^ (b < 0) else 1
    x, y = abs(a), abs(b)

    def kar(u: int, v: int) -> int:
        if u == 0 or v == 0:
            return 0
        if u.bit_length() <= CUTOFF_BITS and v.bit_length() <= CUTOFF_BITS:
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
