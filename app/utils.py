from __future__ import annotations
import re
from decimal import Decimal, InvalidOperation
from datetime import datetime

AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

def clean_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text.translate(AR_DIGITS)


def normalize_number(value) -> Decimal:
    text = clean_text(value).replace(",", "")
    if text == "":
        return Decimal("0.00")
    try:
        return Decimal(text).quantize(Decimal("0.01"))
    except InvalidOperation:
        nums = re.findall(r"\d+(?:\.\d+)?", text)
        if not nums:
            return Decimal("0.00")
        return Decimal(nums[0]).quantize(Decimal("0.01"))


def money_for_txt(value) -> str:
    """Format like sample: 0000000450,00"""
    amount = normalize_number(value)
    cents = int(amount * 100)
    whole = cents // 100
    frac = cents % 100
    return f"{whole:010d},{frac:02d}"


def money_plain(value) -> str:
    amount = normalize_number(value)
    if amount == amount.to_integral():
        return str(int(amount))
    return f"{amount:.2f}"


def validate_iban(iban: str) -> bool:
    iban = clean_text(iban).replace(" ", "").upper()
    return iban.startswith("SA") and len(iban) == 24 and iban[2:].isdigit()


def validate_sa_id(value: str) -> bool:
    text = clean_text(value)
    return len(text) == 10 and text.isdigit()


def make_file_reference(dt: datetime | None = None) -> str:
    dt = dt or datetime.now()
    return dt.strftime("%Y%m%d%H%M%S")


def make_transaction_ref(index: int, dt: datetime | None = None) -> str:
    dt = dt or datetime.now()
    return dt.strftime("%y%m%d") + f"{index:010d}"


def date_yyyymmdd(date_obj) -> str:
    if hasattr(date_obj, "strftime"):
        return date_obj.strftime("%Y%m%d")
    text = clean_text(date_obj)
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y%m%d")
        except Exception:
            pass
    return datetime.now().strftime("%Y%m%d")
