def explain_flags(flags, language="English"):
    """Explanation is assembled only from deterministic flags; no LLM is trusted to invent findings."""
    groups={"pass":[],"warn":[],"fail":[]}
    for f in flags: groups.setdefault(f["status"],[]).append(f)
    return groups
