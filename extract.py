"""Conservative local extraction for invoices, certificates and common Indian marksheets."""
import re
from datetime import datetime

def _clean(value):
    return re.sub(r"\s+", " ", value).strip(" \t:;-|") if value else None

def _find(pattern, text, flags=re.I|re.M):
    m = re.search(pattern, text, flags)
    return _clean(m.group(1)) if m else None

def _amount(pattern, text):
    value = _find(pattern, text)
    if not value:
        return None
    try:
        return float(value.replace(",", "").replace("₹", "").strip())
    except ValueError:
        return None

def _date(value):
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
                "%d/%m/%y", "%d-%m-%y", "%d.%m.%y", "%B %d, %Y", "%d %B %Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return value

def extract_document(text, doc_type):
    t = text or ""
    if doc_type == "invoice":
        gst = re.search(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b", t.upper())
        no = _find(r"(?:invoice\s*(?:no|number|#)?|bill\s*(?:no|number))\s*[:#\-]?\s*([A-Z0-9/-]+)", t)
        dt = _find(r"(?:invoice\s*date|bill\s*date|date)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}[./-]\d{1,2}[./-]\d{2,4})", t)
        subtotal = _amount(r"subtotal\s*[:₹]?\s*([\d,]+(?:\.\d{1,2})?)", t)
        cgst = _amount(r"cgst\s*[:₹]?\s*([\d,]+(?:\.\d{1,2})?)", t) or 0.0
        sgst = _amount(r"sgst\s*[:₹]?\s*([\d,]+(?:\.\d{1,2})?)", t) or 0.0
        igst = _amount(r"igst\s*[:₹]?\s*([\d,]+(?:\.\d{1,2})?)", t) or 0.0
        total = _amount(r"(?:grand\s*total|total\s*amount|amount\s*due|net\s*amount|total)\s*[:₹]?\s*([\d,]+(?:\.\d{1,2})?)", t)
        rate = _amount(r"(?:gst\s*rate|tax\s*rate)\s*[:%]?\s*([\d.]+)", t)
        qty = _amount(r"qty(?:uantity)?\s*[:x]?\s*([\d.]+)", t)
        unit = _amount(r"(?:unit\s*rate|rate)\s*[:₹]?\s*([\d.]+)", t)
        line = _amount(r"(?:line\s*amount|amount)\s*[:₹]?\s*([\d,]+(?:\.\d{1,2})?)", t)
        supplier = _find(r"(?:supplier|seller|from)\s*[:\-]\s*([^\n]+)", t)
        buyer = _find(r"(?:buyer|bill\s*to|customer)\s*[:\-]\s*([^\n]+)", t)
        return {"document_type":"invoice","supplier":{"name":supplier,"gstin":gst.group(0) if gst else None,"address":None},
            "buyer":{"name":buyer,"gstin":None},"invoice_number":no,"invoice_date":_date(dt),
            "currency":"INR","line_items":[{"description":_find(r"(?:item|description|product)\s*[:\-]\s*([^\n]+)",t) or "Extracted line item",
            "quantity":qty,"unit_rate":unit,"line_amount":line,"taxable_value":line,"gst_rate":rate}] if any(x is not None for x in (qty,unit,line,rate)) else [],
            "subtotal":subtotal,"cgst":cgst,"sgst":sgst,"igst":igst,"grand_total":total,
            "amount_in_words":_find(r"(?:amount in words|in words)\s*[:\-]\s*([^\n]+)",t),
            "tax_regime":"IGST" if igst and not (cgst or sgst) else ("CGST_SGST" if cgst or sgst else "UNKNOWN")}

    if doc_type == "certificate":
        holder = _find(r"(?:awarded to|holder(?:'s)? name|candidate(?:'s)? name|student(?:'s)? name|name of candidate|name)\s*[:\-]?\s*([A-Za-z][A-Za-z .'-]{2,})", t)
        # Marksheets often have OCR text in "Mother's Name / Father's Name" rows; stop at next known label.
        if holder:
            holder = re.split(r"\s+(?:father|mother|roll|registration|date of birth|dob|school|college)\b", holder, flags=re.I)[0].strip()
        issuer = _find(r"(?:issued by|issuer|institute|university|board|examination board)\s*[:\-]?\s*([^\n]+)", t)
        title = _find(r"(certificate of [A-Za-z ]+|degree certificate|marksheet|marks statement|statement of marks|matriculation|intermediate)", t)
        course = _find(r"(?:course|program|programme|stream|faculty)\s*[:\-]?\s*([^\n]+)", t)
        cert_id = _find(r"(?:certificate id|certificate no|cert id|registration no\.?|registration number|serial no\.?|serial number)\s*[:#\-]?\s*([A-Z0-9/-]+)", t)
        roll_number = _find(r"roll\s*(?:number|no\.?)\s*[:#\-]?\s*([A-Z0-9/-]+)", t)
        roll_code = _find(r"roll\s*code\s*[:#\-]?\s*([A-Z0-9/-]+)", t)
        reg_no = _find(r"(?:registration\s*(?:no\.?|number))\s*[:#\-]?\s*([A-Z0-9/-]+)", t)
        issue = _find(r"(?:issue date|date of issue|issued on|date)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}[./-]\d{1,2}[./-]\d{2,4})", t)
        dob = _find(r"(?:date of birth|dob)\s*[:\-]?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})", t)
        exam_year = _find(r"(?:annual examination|examination year|exam year)\s*[:\-]?\s*(20\d{2}|19\d{2})", t)
        # Keep this heuristic deliberately simple: OCR text can merge columns, so marks need review.
        marks = []
        for m in re.finditer(r"(?im)^\s*([A-Za-z][A-Za-z &()/.-]{2,30})\s{2,}(\d{1,3})\s{2,}(\d{1,3})\s*$", t):
            marks.append({"subject":_clean(m.group(1)), "marks_obtained":int(m.group(2)), "maximum_marks":int(m.group(3))})
        total = _find(r"(?:total marks|grand total|total)\s*[:\-]?\s*(\d{1,4}(?:\s*/\s*\d{1,4})?)", t)
        verification_url = _find(r"(https?://[^\s]+)", t)
        return {"document_type":"certificate","document_subtype":"marksheet_or_certificate",
            "holder_name":holder,"issuer":issuer,"certificate_title":title or ("Marks Statement" if any(k in t.lower() for k in ["marks statement","examination board","roll number"]) else None),
            "course":course,"certificate_id":cert_id,"issue_date":_date(issue),"start_date":None,"end_date":None,"expiry_date":None,
            "date_of_birth":_date(dob),"exam_year":exam_year,"roll_number":roll_number,"roll_code":roll_code,"registration_number":reg_no,
            "total_marks":total,"subject_marks":marks,"verification_url":verification_url,
            "qr_present":bool(re.search(r"(?:qr code|verify online|verification)",t,re.I)),
            "signature_or_seal_region_present":bool(re.search(r"(?:signature|principal|seal|controller of examination)",t,re.I)),
            "user_provided_name":"","registry_result":{"status":"not_checked","matched_fields":[],"mismatched_fields":[]},
            "extraction_note":"Fields are inferred from OCR text and may need correction, especially for marksheets with complex tables."}

    # Generic mode: present useful entities found verbatim in the OCR text.
    key_fields=[]
    patterns=[
        ("Names",r"(?im)^\s*(?:name|candidate(?:'s)? name|student name)\s*[:\-]\s*([^\n]+)"),
        ("Dates",r"(?im)^\s*(?:date|issue date|due date|deadline|date of birth)\s*[:\-]\s*([^\n]+)"),
        ("Amounts",r"(?im)^\s*(?:amount|total|fee|payment|balance)\s*[:₹]\s*([^\n]+)"),
        ("Reference numbers",r"(?im)^\s*(?:reference|ref|application|registration|roll|notice)\s*(?:no|number|id)?\s*[:#\-]\s*([^\n]+)")
    ]
    for label, pattern in patterns:
        for value in re.findall(pattern,t):
            key_fields.append({"field":label,"value":_clean(value),"source_text":_clean(value)})
    title = next((line.strip() for line in t.splitlines() if line.strip()),None)
    attention=[]
    for line in t.splitlines():
        if re.search(r"\b(?:due|deadline|submit|required|verify|payment|action required|warning|notice)\b",line,re.I):
            attention.append({"description":"Review this item: "+_clean(line),"source_text":_clean(line),"reason":"Keyword-based review cue"})
    if not attention and t.strip():
        attention=[{"description":"Review the extracted document and confirm important details manually.","source_text":t[:350],"reason":"General review reminder"}]
    return {"document_type":"generic","document_title":title,"summary":"A summary is assembled from detected text and key fields; verify against the source document.",
        "key_fields":key_fields,"items_to_check":attention}
