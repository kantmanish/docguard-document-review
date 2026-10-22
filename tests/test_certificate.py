from datetime import date
from validators.certificate import validate_certificate
def test_name_mismatch_warns():
    d={"holder_name":"Aarav Kumar","user_provided_name":"Different Person","issuer":"Example Institute",
       "certificate_title":"Certificate of Completion","course":"Python Programming","certificate_id":"EX-PY-2026-001",
       "issue_date":"2026-08-20","start_date":"2026-06-01","end_date":"2026-08-15","qr_present":False}
    flags=validate_certificate(d,registry=[],id_patterns={"Example Institute":r"EX-PY-\d{4}-\d{3}"},today=date(2026,10,1))
    assert next(f for f in flags if f["id"]=="CERT_NAME_MATCH")["status"]=="warn"
def test_registry_match_is_not_authenticity_claim():
    d={"holder_name":"Aarav Kumar","user_provided_name":"Aarav Kumar","issuer":"Example Institute",
       "certificate_title":"Certificate of Completion","course":"Python Programming","certificate_id":"EX-PY-2026-001",
       "issue_date":"2026-08-20","start_date":"2026-06-01","end_date":"2026-08-15","qr_present":True}
    reg=[{"cert_id":"EX-PY-2026-001","name":"Aarav Kumar","course":"Python Programming","date":"2026-08-20"}]
    flags=validate_certificate(d,registry=reg,id_patterns={"Example Institute":r"EX-PY-\d{4}-\d{3}"},today=date(2026,10,1))
    assert next(f for f in flags if f["id"]=="CERT_REGISTRY")["status"]=="pass"
