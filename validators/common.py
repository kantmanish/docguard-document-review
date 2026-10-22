from typing import Any
def flag(flag_id: str, status: str, severity: str, message: str, rule_used: str,
         evidence_text: str = "", bbox=None) -> dict[str, Any]:
    return {"id": flag_id, "status": status, "severity": severity, "message": message,
            "rule_used": rule_used, "evidence_text": evidence_text or "No source snippet available.",
            "bbox": bbox}
