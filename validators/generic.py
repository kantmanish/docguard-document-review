from .common import flag
def validate_generic(data):
    flags=[]
    for i,item in enumerate(data.get("items_to_check",[]),1):
        snippet=item.get("source_text","")
        flags.append(flag(f"GEN_REVIEW_{i}","warn","low",item.get("description","Review this item."),
                          "source_grounded_generic_review",snippet))
    if not flags:
        flags.append(flag("GEN_NO_ISSUES","pass","low","No review items were generated; still review the source document.","generic_review_items","No items to check were identified."))
    return flags
