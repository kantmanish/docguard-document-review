def explanation_faithfulness(flags, explanation_lines):
    """Each explanation line must cite a real flag ID; simple baseline evaluator."""
    ids={f["id"] for f in flags}
    cited=[line for line in explanation_lines if any(fid in line for fid in ids)]
    return {"line_count":len(explanation_lines),"grounded_line_count":len(cited),
            "faithfulness":len(cited)/len(explanation_lines) if explanation_lines else 1.0}
