import json, csv, re
from pathlib import Path
import streamlit as st
from PIL import Image, ImageDraw
from preprocess import load_image, preprocess_image
from ocr import run_ocr, ocr_text
from classify import classify_document
from extract import extract_document
from validators.invoice import validate_invoice
from validators.certificate import validate_certificate
from validators.generic import validate_generic
from risk import score_flags, suggested_next_step
from report import make_pdf_report

ROOT = Path(__file__).parent
st.set_page_config(page_title="DocGuard", page_icon="🛡️", layout="wide")
st.title("🛡️ DocGuard")
st.caption("Multimodal document review assistant · Explainable, human-reviewed decision support")
st.warning("LIMITATIONS: DocGuard does not establish authenticity and is not legal, tax, or financial advice. Always review evidence and make the final decision yourself.")

def draw_ocr_boxes(image, words, evidence_texts=None):
    """Draw OCR words: cyan outlines for OCR locations, yellow fill for evidence matches."""
    canvas = image.convert("RGB").copy()
    draw = ImageDraw.Draw(canvas)
    evidence_tokens = set()
    for snippet in evidence_texts or []:
        evidence_tokens.update(re.findall(r"[\w./:-]+", str(snippet).casefold()))
    for word in words or []:
        box = word.get("bbox")
        if not box:
            continue
        token = str(word.get("text", "")).casefold().strip(".,:;()[]{}")
        coords = (box["x1"], box["y1"], box["x2"], box["y2"])
        if token and token in evidence_tokens:
            draw.rectangle(coords, fill="#ffe066", outline="#b8860b", width=3)
        else:
            draw.rectangle(coords, outline="#39c6d8", width=2)
    return canvas

def build_plain_summary(doc_type, data, flags):
    """Grounded summary assembled from extracted fields and deterministic flags only."""
    passed = sum(f["status"] == "pass" for f in flags)
    warned = sum(f["status"] == "warn" for f in flags)
    failed = sum(f["status"] == "fail" for f in flags)
    lines = [f"Document type: {doc_type.title()}. Checks: {passed} passed, {warned} warnings, {failed} failures."]
    if doc_type == "invoice":
        supplier = (data.get("supplier") or {}).get("name") or "Not extracted"
        number = data.get("invoice_number") or "Not extracted"
        total = data.get("grand_total")
        date_value = data.get("invoice_date") or "Not extracted"
        lines.append(f"Supplier: {supplier}. Invoice number: {number}. Invoice date: {date_value}. Grand total: {total if total is not None else 'Not extracted'} INR.")
    elif doc_type == "certificate":
        lines.append(f"Holder: {data.get('holder_name') or 'Not extracted'}. Issuer: {data.get('issuer') or 'Not extracted'}. Title/course: {data.get('certificate_title') or data.get('course') or 'Not extracted'}. Certificate ID: {data.get('certificate_id') or 'Not extracted'}.")
        lines.append("These checks assess consistency only and do not establish authenticity.")
    else:
        summary = data.get("summary")
        if summary:
            lines.append("Document summary from the current extraction: " + str(summary))
        fields = data.get("key_fields") or []
        if fields:
            lines.append("Key fields: " + "; ".join(f"{x.get('field')}: {x.get('value')}" for x in fields[:8]))
    attention = [f"{f['id']}: {f['message']}" for f in flags if f["status"] != "pass"]
    if attention:
        lines.append("Items needing attention: " + " ".join(attention[:8]))
    else:
        lines.append("No configured rule failures or warnings were raised. Human review is still required.")
    return "\n\n".join(lines)


FIELD_LABELS = {
    "holder_name":"Candidate / holder name","issuer":"Issuing board or institution",
    "certificate_title":"Document type / title","course":"Course / stream",
    "certificate_id":"Certificate / serial ID","issue_date":"Issue date",
    "date_of_birth":"Date of birth","exam_year":"Examination year",
    "roll_number":"Roll number","roll_code":"Roll code","registration_number":"Registration number",
    "total_marks":"Total marks","invoice_number":"Invoice number","invoice_date":"Invoice date",
    "grand_total":"Grand total","subtotal":"Subtotal","cgst":"CGST","sgst":"SGST","igst":"IGST",
    "document_title":"Document title","verification_url":"Verification link",
}
def pretty_field(key):
    return FIELD_LABELS.get(key, key.replace("_"," ").replace("."," · ").title())

def flat_fields(obj, prefix=""):
    out=[]
    if isinstance(obj,dict):
        for k,v in obj.items():
            if k in {"document_type","registry_result","extraction_note","items_to_check","key_fields","user_provided_name"}: continue
            label=f"{prefix}.{k}" if prefix else k
            if isinstance(v,dict): out.extend(flat_fields(v,label))
            elif isinstance(v,list):
                if k=="subject_marks":
                    for item in v:
                        out.append((pretty_field(k),f"{item.get('subject','Subject')}: {item.get('marks_obtained','?')}/{item.get('maximum_marks','?')}"))
                elif k=="line_items":
                    for i,item in enumerate(v,1):
                        out.append((f"Item {i}",f"{item.get('description','Item')}; quantity {item.get('quantity')}; unit rate {item.get('unit_rate')}; amount {item.get('line_amount')}; GST {item.get('gst_rate')}%"))
            elif v not in (None,""):
                out.append((pretty_field(label),str(v)))
    return out

with st.sidebar:
    st.header("Review settings")
    mode = st.selectbox("Document mode", ["Auto-detect", "Invoice", "Certificate", "Generic"])
    language = st.selectbox("OCR language", ["English", "Hindi + English"])
    privacy = st.toggle("Privacy mode (local processing only)", value=True)
    st.caption("No cloud LLM calls are made in this prototype. Privacy toggle is a reminder/control label, not a guarantee of secure erasure.")
    st.divider()
    st.subheader("Demo samples")
    sample = st.selectbox("Load synthetic sample", ["None", "Sample invoice", "Sample certificate"])
    if st.button("Load sample document", use_container_width=True):
        if sample == "Sample invoice":
            st.session_state["sample_text"] = (
                "INVOICE\nInvoice No: DEMO-001\nInvoice Date: 2026-10-15\n"
                "GSTIN: 09ABCDE1234F1Z5\nQty: 2\nUnit Rate: 100.00\n"
                "Line Amount: 200.00\nGST Rate: 18\nSubtotal: 200.00\n"
                "CGST: 18.00\nSGST: 18.00\nGrand Total: 236.00"
            )
        elif sample == "Sample certificate":
            st.session_state["sample_text"] = (
                "CERTIFICATE OF COMPLETION\nAwarded to: Aarav Kumar\n"
                "Issued by: Example Institute\nCourse: Python Programming\n"
                "Certificate ID: EX-PY-2026-001\nIssue Date: 2026-08-20"
            )
        else:
            st.session_state.pop("sample_text", None)
        st.session_state.pop("ocr_text", None)
        st.rerun()
    st.divider()
    st.caption("For Windows OCR installation, open OCR_SETUP_WINDOWS.md in the project folder.")

st.header("Step 1 — Upload a document")
uploaded = st.file_uploader("Choose a PDF, PNG or JPG", type=["pdf", "png", "jpg", "jpeg"])
text = ""
parse_error = None
image = None
words = []
ocr_error = None
manual_text = st.session_state.get("sample_text", "")

# Uploading a file only stages it. The user explicitly clicks Analyze & validate.
if uploaded is not None:
    st.success(f"Document selected: {uploaded.name} · {uploaded.size / 1024:.1f} KB")
    try:
        image = load_image(uploaded.getvalue(), uploaded.name)
        st.session_state["pending_image"] = image
        st.session_state["pending_filename"] = uploaded.name
    except Exception as exc:
        st.error(f"Could not open this file: {exc}")

if manual_text:
    st.info("A synthetic/manual sample is loaded. Click Analyze & validate to run the review.")

left_btn, right_btn = st.columns([1, 3])
with left_btn:
    analyze_clicked = st.button("🔎 Analyze & validate", type="primary", use_container_width=True)
with right_btn:
    if uploaded is None and not manual_text:
        st.caption("Select a file above, or load a synthetic sample from the sidebar. Analysis starts only when you click the button.")

if analyze_clicked:
    if uploaded is not None:
        try:
            image = load_image(uploaded.getvalue(), uploaded.name)
            clean = preprocess_image(image)
            st.session_state["doc_image"] = image
            words = run_ocr(clean, "eng+hin" if language == "Hindi + English" else "eng")
            text = ocr_text(words)
            st.session_state["ocr_words"] = words
            st.session_state["ocr_text"] = text
            st.session_state.pop("sample_text", None)
            if not text.strip():
                ocr_error = "OCR ran but did not detect readable text."
        except Exception as exc:
            ocr_error = str(exc)
            st.session_state["ocr_text"] = ""
            st.session_state["ocr_words"] = []
    elif manual_text:
        text = manual_text
        words = []
        st.session_state["ocr_text"] = text
        st.session_state["ocr_words"] = []
    else:
        st.warning("Please upload a document or load a synthetic sample first.")

# Keep analyzed text available across Streamlit reruns (e.g. editing fields / downloading).
if not text and uploaded is None and not analyze_clicked:
    text = st.session_state.get("ocr_text", "")
words = words or st.session_state.get("ocr_words", [])
image = image or st.session_state.get("doc_image")

if uploaded is not None and analyze_clicked and ocr_error:
    st.error("OCR is not ready: " + ocr_error)
    st.info("Your file can be opened, but automatic text extraction needs EasyOCR installed. Use the manual text fallback below while you install it.")
    with st.expander("OCR setup commands", expanded=True):
        st.markdown("""
        **Install the local EasyOCR engine (no Tesseract executable required):**
        ```powershell
        python -m pip install -r requirements-easyocr.txt
        ```
        EasyOCR installs large PyTorch dependencies and may download model weights on first run. Restart Streamlit after installation.

        If installation fails, use the manual text fallback below to demonstrate the rule-based checks.
        """)
    st.warning("Temporary workaround: paste the document text below. Check it against the original before relying on results.")
    manual = st.text_area("Manual text input (fallback)", value=st.session_state.get("manual_text_fallback", ""),
                          height=160, placeholder="Paste document text here.")
    st.session_state["manual_text_fallback"] = manual
    if st.button("Analyze pasted text", type="secondary"):
        if manual.strip():
            st.session_state["ocr_text"] = manual
            st.session_state["sample_text"] = manual
            st.session_state["ocr_words"] = []
            st.rerun()
        else:
            st.warning("Paste some text first.")

if text.strip() and (analyze_clicked or uploaded is None):
    st.success(f"Text ready for review · {len(text.split())} words detected/entered")
    detected = classify_document(text, mode)
    st.header("Step 2 — Document overview")
    extracted = extract_document(text, detected)
    summary_text = build_plain_summary(detected, extracted, [])
    st.info(summary_text)
    field_rows = flat_fields(extracted)
    if field_rows:
        st.subheader("What DocGuard could read")
        st.dataframe([{"Information":label,"Extracted value":value} for label,value in field_rows],
                     use_container_width=True, hide_index=True)
    if detected == "certificate":
        st.caption("For marksheets, OCR may mix columns or confuse marks. Compare each extracted value with the original.")
    left, right = st.columns([1, 1])
    with left:
        display_image = image or st.session_state.get("doc_image")
        current_words = words or st.session_state.get("ocr_words", [])
        if display_image is not None:
            st.image(draw_ocr_boxes(display_image, current_words), caption="OCR word boxes: cyan = recognized words; yellow = words matching source evidence snippets (when available).", use_container_width=True)
        with st.expander("Show source OCR text"):
            st.text_area("OCR text", value=text, height=180, disabled=True)
        if current_words:
            with st.expander("Word-level OCR confidence"):
                st.dataframe([{"text": w["text"], "confidence": round(float(w["confidence"]), 3), "bbox": w["bbox"]} for w in current_words],
                             use_container_width=True, hide_index=True)
    with right:
        st.write(f"**Detected document mode:** {detected.title()}")
        st.caption("Check the extracted details against the source. Use the advanced editor only if you need to correct a field.")
        if detected == "certificate":
            extracted["user_provided_name"] = st.text_input(
                "Candidate name entered by reviewer", value=extracted.get("user_provided_name") or "",
                help="Optional: enter the name supplied by the candidate to compare it with the document.")
        with st.expander("Advanced: edit extracted data (JSON)"):
            edited = st.text_area("Editable extracted fields", value=json.dumps(extracted, indent=2, ensure_ascii=False), height=300)
        if "edited" in locals():
            try:
                extracted = json.loads(edited)
                parse_error = None
            except json.JSONDecodeError as exc:
                parse_error = str(exc)
                st.error(f"Please fix the JSON format: {exc}")
        else:
            parse_error = None

    if not parse_error:
        st.header("Step 3 — Rule-based checks")
        if detected == "invoice":
            flags = validate_invoice(extracted, seen_invoices=st.session_state.setdefault("seen_invoices", set()))
        elif detected == "certificate":
            registry = []
            registry_path = ROOT / "data" / "issuer_registry.csv"
            if registry_path.exists():
                with registry_path.open(encoding="utf-8-sig", newline="") as f:
                    registry = list(csv.DictReader(f))
            patterns = {"Example Institute": r"EX-PY-\d{4}-\d{3}"}
            flags = validate_certificate(extracted, registry=registry, id_patterns=patterns,
                                         seen_ids=st.session_state.setdefault("seen_cert_ids", set()))
        else:
            flags = validate_generic(extracted)

        groups = {"pass": [], "warn": [], "fail": []}
        for item in flags:
            groups.setdefault(item["status"], []).append(item)
        tabs = st.tabs([f"Pass ({len(groups['pass'])})", f"Warnings ({len(groups['warn'])})", f"Failures ({len(groups['fail'])})"])
        for tab, key in zip(tabs, ["pass", "warn", "fail"]):
            with tab:
                if not groups[key]:
                    st.info("No checks in this group.")
                for item in groups[key]:
                    with st.expander(f"{'Looks consistent' if key == 'pass' else ('Please review' if key == 'warn' else 'Possible mismatch')} · {item['message']}"):
                        st.caption("Check reference: " + item["id"])
                        st.write(item["message"])
                        st.caption("How it was checked: " + item["rule_used"])
                        st.write("**Source evidence**")
                        st.code(item["evidence_text"])
                        if item.get("bbox"):
                            st.json(item["bbox"])

        st.header("Step 4 — Suggested next step")
        risk = score_flags(flags)
        next_step = suggested_next_step(detected, flags)
        c1, c2, c3 = st.columns(3)
        c1.metric("Review risk", risk["level"])
        c2.metric("Rule score", risk["score"])
        c3.write("**Suggested next step**")
        c3.write(next_step)
        st.caption(risk["disclaimer"])
        st.write("**Plain-language summary**")
        st.write(build_plain_summary(detected, extracted, flags))
        if detected == "certificate":
            st.caption("Certificate/marksheet results describe consistency in the available text. They do not establish whether the document is genuine.")
        if detected == "invoice":
            st.caption("Invoice checks help identify arithmetic and field inconsistencies. They do not authorize payment automatically.")
        with st.expander("Evidence highlighting guide"):
            st.markdown("**Yellow** boxes mark OCR words that match text cited by checks. **Cyan** boxes show other recognized words. This is text matching for navigation, not proof that a document is correct.")
        st.write("**Items needing attention**")
        attention_items = [item for item in flags if item["status"] != "pass"]
        if not attention_items:
            st.success("No configured warnings or failures were raised. Human review is still required.")
        for item in attention_items:
            with st.expander(f"{item['status'].upper()} · {item['id']}"):
                st.write(item["message"])
                st.caption("Rule: " + item["rule_used"])
                st.write("**Evidence text**")
                st.code(item["evidence_text"])
        evidence_texts = [item["evidence_text"] for item in attention_items if item.get("evidence_text")]
        if display_image is not None and current_words and evidence_texts:
            st.subheader("Evidence view")
            st.image(draw_ocr_boxes(display_image, current_words, evidence_texts),
                     caption="Yellow boxes identify OCR words matching evidence snippets for warnings/failures.", use_container_width=True)

        st.header("Step 5 — Export and audit")
        pdf = make_pdf_report(detected, extracted, flags, risk, next_step)
        st.download_button("Download review report (PDF)", data=pdf, file_name="docguard_review_report.pdf",
                           mime="application/pdf", type="primary")
        st.download_button("Download extracted JSON", data=json.dumps(extracted, indent=2, ensure_ascii=False),
                           file_name="docguard_extracted.json", mime="application/json")
        st.download_button("Download validation flags (JSON)", data=json.dumps(flags, indent=2, ensure_ascii=False),
                           file_name="docguard_flags.json", mime="application/json")
        with st.expander("All validation flags (JSON)"):
            st.json(flags)
else:
    st.info("Upload a document or load a synthetic sample from the sidebar. If OCR is unavailable, use the manual text fallback shown after upload.")

st.divider()
st.caption("Privacy note: this app makes no cloud LLM calls and does not intentionally save uploaded files. Session memory and process memory cannot be guaranteed to be securely erased. Use synthetic or consented documents only.")
