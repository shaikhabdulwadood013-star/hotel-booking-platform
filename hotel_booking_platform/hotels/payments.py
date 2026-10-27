"""Payment gateway abstraction.

This is a MOCK gateway so the project runs without API keys.
  - Test card that succeeds: 4242 4242 4242 4242
  - Test card that is declined: 4000 0000 0000 0002

To go live, replace charge()/refund() with Stripe, Razorpay, etc. (use their hosted
checkout or tokenised cards so raw card numbers never touch your server).
"""
import uuid
from dataclasses import dataclass


@dataclass
class ChargeResult:
    success: bool
    transaction_id: str = ""
    message: str = ""


def luhn_ok(number: str) -> bool:
    if not number.isdigit() or not 13 <= len(number) <= 19:
        return False
    total = 0
    for i, ch in enumerate(reversed(number)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def charge(amount, card_number: str, expiry: str, cvc: str) -> ChargeResult:
    digits = card_number.replace(" ", "")
    if not luhn_ok(digits):
        return ChargeResult(False, message="Invalid card number.")
    if digits.endswith("0002"):
        return ChargeResult(False, message="Your card was declined.")
    return ChargeResult(True, transaction_id=f"MOCK-{uuid.uuid4().hex[:12].upper()}")


def refund(transaction_id: str) -> bool:
    return True
