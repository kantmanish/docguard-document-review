def score_flags(flags):
    """Deterministic risk indicator; not a probability and not an authenticity score."""
    weights={"low":1,"medium":3,"high":7,"critical":10}
    score=sum(weights.get(f.get("severity","low"),1) for f in flags if f.get("status")=="fail")
    score+=sum(1 for f in flags if f.get("status")=="warn")
    level="Low" if score<5 else ("Medium" if score<12 else "High")
    return {"score":score,"level":level,"disclaimer":"Rule-weighted review indicator; not a probability or authenticity determination."}
def suggested_next_step(doc_type, flags):
    failures=[f for f in flags if f.get("status")=="fail"]
    warnings=[f for f in flags if f.get("status")=="warn"]
    if doc_type=="invoice":
        if failures:return "Hold payment"
        if warnings:return "Ask supplier to correct or clarify"
        return "Pay as is (after human review)"
    if doc_type=="certificate":
        if failures:return "Verify with issuer"
        if warnings:return "Request additional proof"
        return "Accept (after human review)"
    return "Review identified items" if failures or warnings else "Confirm extracted details and review"
