import re
PATTERNS=[
 ("PAN",re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",re.I)),
 ("PHONE",re.compile(r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)")),
 ("AADHAAR_LIKE",re.compile(r"(?<!\d)(?:\d[ -]?){12}(?!\d)")),
 ("BANK_ACCOUNT_LIKE",re.compile(r"(?<!\d)\d{9,18}(?!\d)")),
]
def mask_sensitive(text):
    masked=text or ""
    for label,pattern in PATTERNS:
        masked=pattern.sub(f"[REDACTED_{label}]",masked)
    return masked
