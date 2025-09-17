def mul_chunked(a: int, b: int) -> int:
    """Chunked schoolbook multiplication with tunable base exponent.
    BASE_EXP = 6  # base = 10**BASE_EXP
    """
    sign = -1 if (a < 0) ^ (b < 0) else 1
    x, y = abs(a), abs(b)
    if x == 0 or y == 0:
        return 0
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
