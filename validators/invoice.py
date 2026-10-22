import re
from decimal import Decimal, InvalidOperation
from datetime import date
from .common import flag

GST_RATES = {Decimal("0"), Decimal("5"), Decimal("12"), Decimal("18"), Decimal("28")}
# GST state/UT codes currently allocated for standard domestic GSTINs.
VALID_STATE_CODES = {f"{i:02d}" for i in range(1, 39)} | {"97", "99"}
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")

def dec(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None

def gstin_checksum_valid(gstin: str) -> bool:
    """Validate the GSTIN base-36 check character (last character)."""
    if not gstin or len(gstin) != 15 or not GSTIN_RE.fullmatch(gstin):
        return False
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    total = 0
    factor = 2
    for ch in reversed(gstin[:-1]):
        product = chars.index(ch) * factor
        total += (product // 36) + (product % 36)
        factor = 1 if factor == 2 else 2
    check = (36 - (total % 36)) % 36
    return chars[check] == gstin[-1]

def validate_gstin(gstin):
    g = (gstin or "").strip().upper()
    if not g:
        return [flag("INV_GSTIN_MISSING","warn","medium","Supplier GSTIN was not extracted.","gstin_present","GSTIN missing")]
    if not GSTIN_RE.fullmatch(g):
        return [flag("INV_GSTIN_FORMAT","fail","high","GSTIN does not match the expected 15-character format.","gstin_regex",g)]
    state_ok = g[:2] in VALID_STATE_CODES
    checksum_ok = gstin_checksum_valid(g)
    out = [
      flag("INV_GSTIN_STATE","pass" if state_ok else "fail","low" if state_ok else "high",
           "GSTIN state code is allocated." if state_ok else "GSTIN starts with an unrecognised state code.",
           "gstin_state_code",g[:2]),
      flag("INV_GSTIN_CHECKSUM","pass" if checksum_ok else "fail","low" if checksum_ok else "high",
           "GSTIN checksum is consistent." if checksum_ok else "GSTIN checksum does not match.",
           "gstin_base36_checksum",g)]
    return out

def validate_invoice(data, seen_invoices=None, today=None):
    """Pure rule-based invoice checks. Amounts are parsed using Decimal."""
    seen_invoices = seen_invoices if seen_invoices is not None else set()
    today = today or date.today()
    flags = []
    lines = data.get("line_items") or []
    subtotal = dec(data.get("subtotal"))
    tax_fields = [dec(data.get(k, 0)) or Decimal("0") for k in ("cgst","sgst","igst")]
    tax_total = sum(tax_fields, Decimal("0"))
    total = dec(data.get("grand_total"))
    evidence = f"subtotal={subtotal}; CGST={tax_fields[0]}; SGST={tax_fields[1]}; IGST={tax_fields[2]}; grand_total={total}"

    line_sum = Decimal("0")
    all_lines_numeric = bool(lines)
    for i, line in enumerate(lines, 1):
        qty, rate, amount = dec(line.get("quantity")), dec(line.get("unit_rate")), dec(line.get("line_amount"))
        if qty is None or rate is None or amount is None:
            all_lines_numeric = False
            flags.append(flag(f"INV_LINE_{i}_MISSING","warn","medium",f"Line {i} has missing or unreadable quantity/rate/amount.","line_numeric_fields",str(line)))
            continue
        expected = qty * rate
        ok = abs(expected - amount) <= Decimal("1")
        flags.append(flag(f"INV_LINE_{i}_MATH","pass" if ok else "fail","low" if ok else "high",
            f"Line {i} quantity × rate {'matches' if ok else 'does not match'} line amount.",
            "quantity_times_rate",f"qty={qty}; rate={rate}; amount={amount}"))
        line_sum += amount
    if subtotal is not None and all_lines_numeric:
        ok = abs(line_sum - subtotal) <= Decimal("1")
        flags.append(flag("INV_SUBTOTAL","pass" if ok else "fail","low" if ok else "high",
            "Subtotal matches line amounts." if ok else "Subtotal differs from the sum of line amounts.",
            "subtotal_equals_line_sum",f"line_sum={line_sum}; subtotal={subtotal}"))
    else:
        flags.append(flag("INV_SUBTOTAL","warn","medium","Subtotal could not be checked because fields are missing.","subtotal_equals_line_sum",evidence))

    regime = data.get("tax_regime","UNKNOWN")
    rates = [dec(x.get("gst_rate")) for x in lines]
    if rates and all(r is not None and r in GST_RATES for r in rates):
        flags.append(flag("INV_GST_RATE","pass","low","All extracted GST rates are in the configured allowed set.","gst_rate_allowed",str(rates)))
    else:
        flags.append(flag("INV_GST_RATE","warn","medium","One or more GST rates are missing or outside the configured allowed set.","gst_rate_allowed",str(rates)))

    taxable_values = [dec(x.get("taxable_value", x.get("line_amount"))) for x in lines]
    if regime in {"CGST_SGST","IGST"} and taxable_values and all(v is not None for v in taxable_values) and all(r is not None for r in rates):
        expected_tax = sum((v*r/Decimal("100") for v,r in zip(taxable_values,rates)), Decimal("0"))
        actual_tax = tax_total
        ok = abs(expected_tax-actual_tax) <= Decimal("1")
        flags.append(flag("INV_TAX_TOTAL","pass" if ok else "fail","low" if ok else "high",
            "Tax total is consistent with extracted taxable values and rates." if ok else "Tax total differs from the calculated tax; review tax regime and line rates.",
            "tax_percent_of_taxable_value",f"expected tax={expected_tax}; extracted tax={actual_tax}; regime={regime}"))
    else:
        flags.append(flag("INV_TAX_TOTAL","warn","medium","Tax could not be fully checked because the tax regime or line values are incomplete.","tax_percent_of_taxable_value",evidence))

    if subtotal is not None and total is not None:
        expected_total = subtotal + tax_total
        ok = abs(expected_total-total) <= Decimal("1")
        flags.append(flag("INV_GRAND_TOTAL","pass" if ok else "fail","low" if ok else "critical",
            "Grand total matches subtotal plus tax." if ok else "Grand total does not match subtotal plus extracted tax.",
            "grand_total_equals_subtotal_plus_tax",evidence))
    else:
        flags.append(flag("INV_GRAND_TOTAL","warn","medium","Grand total could not be checked because amounts are missing.","grand_total_equals_subtotal_plus_tax",evidence))

    gstin = data.get("supplier",{}).get("gstin")
    flags.extend(validate_gstin(gstin))
    raw_date = data.get("invoice_date")
    try:
        invoice_date = date.fromisoformat(raw_date)
        date_ok = invoice_date <= today
        flags.append(flag("INV_DATE","pass" if date_ok else "fail","low" if date_ok else "high",
            "Invoice date is valid and not in the future." if date_ok else "Invoice date is in the future.",
            "invoice_date_valid_not_future",str(raw_date)))
    except (TypeError, ValueError):
        flags.append(flag("INV_DATE","fail","high","Invoice date is missing or is not a valid ISO date.","invoice_date_valid_not_future",str(raw_date)))

    inv_no = str(data.get("invoice_number") or "").strip()
    key = (inv_no.casefold(), str(total))
    duplicate = bool(inv_no and key in seen_invoices)
    flags.append(flag("INV_DUPLICATE","fail" if duplicate else "pass","high" if duplicate else "low",
        "Invoice number and amount duplicate a document already checked in this session." if duplicate else "No matching invoice number/amount duplicate was found in the supplied session set.",
        "duplicate_invoice_number_amount",f"invoice_number={inv_no}; total={total}"))
    if inv_no and total is not None:
        seen_invoices.add(key)

    words = (data.get("amount_in_words") or "").strip()
    if words and total is not None:
        # Accurate multilingual number-word comparison needs a number-to-words parser;
        # do not pretend a heuristic text comparison is a deterministic numeric check.
        flags.append(flag("INV_AMOUNT_WORDS","warn","medium","Amount-in-words text is present but numeric agreement needs human review in this prototype.","amount_words_human_review",words))
    else:
        flags.append(flag("INV_AMOUNT_WORDS","warn","medium","Amount-in-words could not be checked automatically.","amount_words_human_review",words or "Amount in words missing"))
    return flags
