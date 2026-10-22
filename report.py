from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

LABELS = {
 "holder_name":"Candidate / holder name","issuer":"Issuing board or institution",
 "certificate_title":"Document title","course":"Course / stream","certificate_id":"Certificate / serial ID",
 "issue_date":"Issue date","date_of_birth":"Date of birth","exam_year":"Examination year",
 "roll_number":"Roll number","roll_code":"Roll code","registration_number":"Registration number",
 "total_marks":"Total marks","invoice_number":"Invoice number","invoice_date":"Invoice date",
 "grand_total":"Grand total","subtotal":"Subtotal","cgst":"CGST","sgst":"SGST","igst":"IGST",
 "amount_in_words":"Amount in words","document_title":"Document title","summary":"Summary",
 "supplier.name":"Supplier","supplier.gstin":"Supplier GSTIN","buyer.name":"Buyer / customer",
 "line_items":"Line items","subject_marks":"Subject marks","verification_url":"Verification URL",
 "expiry_date":"Expiry date","start_date":"Course start date","end_date":"Course end date",
 "currency":"Currency","tax_regime":"Tax type","quantity":"Quantity","unit_rate":"Unit rate",
 "line_amount":"Line amount","gst_rate":"GST rate","description":"Description"
}
def pretty_label(key):
    return LABELS.get(key, key.replace("_"," ").replace("."," · ").title())

def make_pdf_report(doc_type, extracted, flags, risk, next_step):
    out=BytesIO()
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name="SmallBody", parent=styles["BodyText"], fontSize=8, leading=10))
    doc=SimpleDocTemplate(out,pagesize=A4,rightMargin=36,leftMargin=36,topMargin=36,bottomMargin=36)
    story=[Paragraph("DocGuard — Document Review",styles["Title"]),
      Paragraph("A plain-language summary to support human review",styles["Heading2"]),
      Paragraph("Important: this report checks extracted information for consistency. It does not prove that a document is authentic and is not legal, tax or financial advice.",styles["BodyText"]),
      Spacer(1,12), Paragraph("At a glance",styles["Heading2"]),
      Paragraph(f"<b>Document type:</b> {escape(doc_type.title())}",styles["BodyText"]),
      Paragraph(f"<b>Review indicator:</b> {escape(str(risk.get('level','Unknown')))} — this is a rule-based indicator, not a probability.",styles["BodyText"]),
      Paragraph(f"<b>Suggested next step:</b> {escape(str(next_step))}",styles["BodyText"]),
      Paragraph(f"<b>Checks:</b> {sum(f.get('status')=='pass' for f in flags)} look consistent; {sum(f.get('status')=='warn' for f in flags)} need review; {sum(f.get('status')=='fail' for f in flags)} detected discrepancies.",styles["BodyText"]),
      Spacer(1,12),Paragraph("Document summary",styles["Heading2"])]
    if doc_type=="certificate":
        summary=f"This document appears to be {extracted.get('certificate_title') or 'a certificate/marksheet'}. Candidate: {extracted.get('holder_name') or 'not clearly extracted'}. Issuer: {extracted.get('issuer') or 'not clearly extracted'}. ID: {extracted.get('certificate_id') or extracted.get('roll_number') or 'not clearly extracted'}. Examination year: {extracted.get('exam_year') or 'not extracted'}. Total marks: {extracted.get('total_marks') or 'not extracted'}."
    elif doc_type=="invoice":
        supplier=(extracted.get("supplier") or {}).get("name") or "not clearly extracted"
        summary=f"This appears to be an invoice from {supplier}. Invoice number: {extracted.get('invoice_number') or 'not extracted'}. Date: {extracted.get('invoice_date') or 'not extracted'}. Subtotal: {extracted.get('subtotal') if extracted.get('subtotal') is not None else 'not extracted'}. Grand total: {extracted.get('grand_total') if extracted.get('grand_total') is not None else 'not extracted'}."
    else:
        summary=str(extracted.get("summary") or "Review the key fields and source text below.")
    story += [Paragraph(escape(summary),styles["BodyText"]),Spacer(1,10),Paragraph("Extracted information",styles["Heading2"])]
    rows=[["Field","Extracted value"]]
    def add(key,value):
        if value is None or value=="" or value==[] or value=={}: return
        if isinstance(value,list):
            if key=="subject_marks":
                val="; ".join(f"{x.get('subject','Subject')}: {x.get('marks_obtained','?')}/{x.get('maximum_marks','?')}" for x in value)
            elif key=="line_items":
                val="; ".join(f"{x.get('description','Item')} (qty {x.get('quantity')}, rate {x.get('unit_rate')}, amount {x.get('line_amount')}, GST {x.get('gst_rate')}%)" for x in value)
            else: val="; ".join(str(v) for v in value)
        elif isinstance(value,dict):
            for k,v in value.items(): add(f"{key}.{k}" if key else k,v)
            return
        else: val=str(value)
        rows.append([Paragraph(escape(pretty_label(key)),styles["SmallBody"]),Paragraph(escape(val)[:1200],styles["SmallBody"])])
    for k,v in extracted.items():
        if k not in {"document_type","registry_result","extraction_note","items_to_check","key_fields","user_provided_name"}:
            add(k,v)
    story.append(Table(rows,colWidths=[150,340],repeatRows=1,style=TableStyle([
      ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e8edf5")),("GRID",(0,0),(-1,-1),.35,colors.grey),
      ("VALIGN",(0,0),(-1,-1),"TOP"),("FONTSIZE",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),5)])))
    if extracted.get("extraction_note"):
        story += [Spacer(1,6),Paragraph("<b>Extraction note:</b> "+escape(str(extracted["extraction_note"])),styles["SmallBody"])]
    story += [Spacer(1,12),Paragraph("Items to review",styles["Heading2"])]
    attention=[f for f in flags if f.get("status") in ("warn","fail")]
    if not attention:
        story.append(Paragraph("No configured warnings or failures were raised. Please still compare the extracted details with the original.",styles["BodyText"]))
    for f in attention:
        story.append(KeepTogether([
          Paragraph(f"<b>{escape(f.get('message','Review item'))}</b>",styles["BodyText"]),
          Paragraph(f"Why: {escape(str(f.get('rule_used','Rule check')))}",styles["SmallBody"]),
          Paragraph(f"Evidence from OCR/extraction: {escape(str(f.get('evidence_text','No snippet available')))}",styles["SmallBody"]),
          Spacer(1,6)]))
    story += [Spacer(1,10),Paragraph("Review status and limitations",styles["Heading2"]),
      Paragraph("DocGuard is decision support. Certificate checks assess consistency only; a registry miss, absent QR code, or missing seal does not by itself prove fraud. Human review and issuer confirmation may be necessary.",styles["BodyText"])]
    doc.build(story)
    return out.getvalue()
