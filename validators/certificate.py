from datetime import date
from rapidfuzz.fuzz import ratio
from .common import flag

def validate_certificate(data, registry=None, id_patterns=None, seen_ids=None, today=None, threshold=85):
    registry = registry or []
    id_patterns = id_patterns or {}
    seen_ids = seen_ids if seen_ids is not None else set()
    today = today or date.today()
    flags=[]
    required = ["holder_name","issuer","certificate_title","issue_date","certificate_id"]
    for field in required:
        value = data.get(field)
        ok = bool(str(value or "").strip())
        flags.append(flag(f"CERT_REQUIRED_{field.upper()}","pass" if ok else "fail","low" if ok else "high",
            f"Required field '{field}' is present." if ok else f"Required field '{field}' is missing.",
            "required_certificate_fields",f"{field}={value}"))
    issuer = str(data.get("issuer") or "")
    cert_id = str(data.get("certificate_id") or "")
    pattern = id_patterns.get(issuer)
    if pattern and cert_id:
        import re
        ok = bool(re.fullmatch(pattern,cert_id))
        flags.append(flag("CERT_ID_FORMAT","pass" if ok else "fail","low" if ok else "high",
            "Certificate ID matches issuer's configured pattern." if ok else "Certificate ID does not match issuer's configured pattern.",
            "issuer_specific_certificate_id_regex",cert_id))
    else:
        flags.append(flag("CERT_ID_FORMAT","warn","medium","No issuer-specific ID pattern is configured; format was not verified.","issuer_specific_certificate_id_regex",f"issuer={issuer}; id={cert_id}"))
    def parse(field):
        try: return date.fromisoformat(data.get(field)) if data.get(field) else None
        except (TypeError,ValueError): return None
    issue,start,end,expiry = [parse(x) for x in ("issue_date","start_date","end_date","expiry_date")]
    if not issue:
        flags.append(flag("CERT_ISSUE_DATE","fail","high","Issue date is missing or invalid.","issue_date_valid",str(data.get("issue_date"))))
    else:
        ok=issue<=today
        flags.append(flag("CERT_ISSUE_DATE","pass" if ok else "fail","low" if ok else "high",
            "Issue date is valid and not in the future." if ok else "Issue date is in the future.","issue_date_valid_not_future",str(issue)))
    if start and end and issue:
        ok=start<end<issue
        flags.append(flag("CERT_DATE_ORDER","pass" if ok else "fail","low" if ok else "high",
            "Start, end and issue dates are in logical order." if ok else "Expected start date < end date < issue date.",
            "start_before_end_before_issue",f"start={start}; end={end}; issue={issue}"))
    elif data.get("start_date") or data.get("end_date"):
        flags.append(flag("CERT_DATE_ORDER","warn","medium","Course date order could not be checked because one or more dates are missing or invalid.","start_before_end_before_issue",f"start={data.get('start_date')}; end={data.get('end_date')}; issue={data.get('issue_date')}"))
    if expiry:
        ok=expiry>=today
        flags.append(flag("CERT_EXPIRY","pass" if ok else "warn","low" if ok else "medium",
            "Expiry date has not passed." if ok else "Expiry date has passed; check issuer requirements.","expiry_not_passed",str(expiry)))
    name = str(data.get("holder_name") or "")
    user_name = str(data.get("user_provided_name") or "")
    if name and user_name:
        score=ratio(name.casefold().strip(),user_name.casefold().strip())
        ok=score>=threshold
        flags.append(flag("CERT_NAME_MATCH","pass" if ok else "warn","low" if ok else "medium",
            f"Certificate name similarity is {score:.0f}/100." + ("" if ok else " Request additional proof or review spelling."),
            "fuzzy_name_similarity",f"certificate_name={name}; entered_name={user_name}; similarity={score:.1f}/100"))
    else:
        flags.append(flag("CERT_NAME_MATCH","warn","medium","Name consistency could not be checked because one name is missing.","fuzzy_name_similarity",f"certificate_name={name}; entered_name={user_name}"))
    if cert_id and cert_id in seen_ids:
        flags.append(flag("CERT_DUPLICATE_ID","warn","medium","Certificate ID has already appeared in this session.","duplicate_certificate_id",cert_id))
    else:
        flags.append(flag("CERT_DUPLICATE_ID","pass","low","No duplicate certificate ID was found in the supplied session set.","duplicate_certificate_id",cert_id))
    if cert_id: seen_ids.add(cert_id)
    match = next((r for r in registry if str(r.get("cert_id",""))==cert_id),None)
    if not match:
        flags.append(flag("CERT_REGISTRY","warn","medium","Certificate ID was not found in the local simulated registry; this is not proof of invalidity.","local_issuer_registry",cert_id or "No certificate ID"))
    else:
        compared={"name":(name,match.get("name","")),"course":(str(data.get("course") or ""),match.get("course","")),"date":(str(data.get("issue_date") or ""),match.get("date",""))}
        mismatches=[k for k,(a,b) in compared.items() if a.strip().casefold()!=str(b).strip().casefold()]
        status="warn" if mismatches else "pass"
        flags.append(flag("CERT_REGISTRY",status,"medium" if mismatches else "low",
            "Registry entry has partial mismatches: "+", ".join(mismatches) if mismatches else "Extracted fields match the local simulated registry entry.",
            "local_issuer_registry",f"registry_entry={match}; mismatched_fields={mismatches}"))
    flags.append(flag("CERT_QR_PRESENCE","pass" if data.get("qr_present") else "warn","low" if data.get("qr_present") else "medium",
        "QR code was detected." if data.get("qr_present") else "No QR code was detected; some legitimate certificates do not use QR codes.",
        "qr_presence_heuristic",str(data.get("verification_url") or "QR/URL not detected")))
    flags.append(flag("CERT_SEAL_HEURISTIC","pass" if data.get("signature_or_seal_region_present") else "warn","low" if data.get("signature_or_seal_region_present") else "medium",
        "A possible signature/seal region was detected." if data.get("signature_or_seal_region_present") else "No obvious signature/seal region was detected; this visual heuristic is not proof.",
        "signature_seal_region_heuristic","Visual heuristic only"))
    return flags
