from datetime import date
from validators.invoice import validate_invoice, validate_gstin, gstin_checksum_valid
def test_gstin_bad_format_fails():
    assert validate_gstin("NOT-A-GSTIN")[0]["status"]=="fail"
def test_grand_total_mismatch_detected():
    d={"supplier":{"gstin":None},"invoice_number":"I-1","invoice_date":"2026-01-01",
       "line_items":[{"quantity":2,"unit_rate":100,"line_amount":200,"taxable_value":200,"gst_rate":18}],
       "subtotal":200,"cgst":18,"sgst":18,"igst":0,"grand_total":250,"tax_regime":"CGST_SGST"}
    flags=validate_invoice(d,today=date(2026,10,1))
    assert next(f for f in flags if f["id"]=="INV_GRAND_TOTAL")["status"]=="fail"
def test_correct_total_passes():
    d={"supplier":{"gstin":None},"invoice_number":"I-2","invoice_date":"2026-01-01",
       "line_items":[{"quantity":2,"unit_rate":100,"line_amount":200,"taxable_value":200,"gst_rate":18}],
       "subtotal":200,"cgst":18,"sgst":18,"igst":0,"grand_total":236,"tax_regime":"CGST_SGST"}
    flags=validate_invoice(d,today=date(2026,10,1))
    assert next(f for f in flags if f["id"]=="INV_GRAND_TOTAL")["status"]=="pass"
