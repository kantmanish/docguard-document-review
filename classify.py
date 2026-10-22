def classify_document(text: str, requested_mode="Auto-detect") -> str:
    if requested_mode in {"Invoice", "Certificate", "Generic"}:
        return requested_mode.lower()
    t = (text or "").lower()
    invoice_terms = ["invoice", "gstin", "subtotal", "grand total", "cgst", "sgst", "igst", "bill to", "tax invoice"]
    certificate_terms = ["certificate", "certified", "course", "awarded to", "degree", "marksheet",
                         "marks statement", "examination board", "roll number", "roll code", "registration no",
                         "annual examination", "intermediate", "matriculation", "candidate's name", "candidate name"]
    invoice_score = sum(k in t for k in invoice_terms)
    cert_score = sum(k in t for k in certificate_terms)
    # Marksheets often do not contain the literal word "certificate".
    if any(k in t for k in ["marks statement", "examination board", "roll number", "roll code", "matriculation", "intermediate"]):
        cert_score += 3
    if invoice_score >= 2 and invoice_score >= cert_score:
        return "invoice"
    if cert_score >= 2:
        return "certificate"
    return "generic"
