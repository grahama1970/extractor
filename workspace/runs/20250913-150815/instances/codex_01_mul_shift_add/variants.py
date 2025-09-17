def mul_shift_add(a: int, b: int) -> int:
    """Iterative shift-add (Russian peasant) with sign correction."""
    sign = -1 if (a < 0) ^ (b < 0) else 1
    x, y = abs(a), abs(b)
    res = 0
    while y > 0:
        if y & 1:
            res += x
        x <<= 1
        y >>= 1
    return res * sign
