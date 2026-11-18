from decimal import Decimal


def to_cents(amount: Decimal) -> int:
    return int((amount * 100).quantize(Decimal("1")))
