"""Generate 20 synthetic invoice PDFs and 20 synthetic certificate PDFs plus ground_truth.json."""
from pathlib import Path
from datetime import date, timedelta
import json, random, csv
from faker import Faker
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"data"/"synthetic"
fake=Faker("en_IN")
random.seed(42); Faker.seed(42)

def draw_pdf(path, title, lines):
    path.parent.mkdir(parents=True,exist_ok=True)
    c=canvas.Canvas(str(path),pagesize=A4)
    w,h=A4; y=h-65
    c.setFillColor(colors.HexColor("#17365D")); c.setFont("Helvetica-Bold",19); c.drawString(48,y,title)
    y-=35; c.setFillColor(colors.black); c.setFont("Helvetica",10)
    for line in lines:
        if y<55: c.showPage(); y=h-55; c.setFont("Helvetica",10)
        c.drawString(48,y,str(line)[:115]); y-=21
    c.save()

def make_invoice(i):
    inv=f"SYN-{i:04d}"
    qty=random.randint(1,8); rate=random.choice([100,250,499,800,1200])
    line=qty*rate; gst=random.choice([0,5,12,18,28])
    tax=round(line*gst/100,2); bad=i%4==0
    subtotal=line
    cgst=round(tax/2,2); sgst=round(tax-cgst,2); igst=0
    total=subtotal+tax+(13 if bad else 0)
    gstin="09ABCDE1234F1Z5" if i%5 else "00ABCDE1234F1Z5"
    invdate=(date(2026,9,1)+timedelta(days=i)).isoformat()
    lines=[f"Supplier: {fake.company()}",f"Invoice No: {inv}",f"Invoice Date: {invdate}",
      f"GSTIN: {gstin}",f"Item: {fake.word().title()}",
      f"Qty: {qty}",f"Unit Rate: {rate:.2f}",f"Line Amount: {line:.2f}",
      f"GST Rate: {gst}",f"Subtotal: {subtotal:.2f}",f"CGST: {cgst:.2f}",
      f"SGST: {sgst:.2f}",f"IGST: {igst:.2f}",f"Grand Total: {total:.2f}"]
    path=OUT/"invoices"/f"invoice_{i:02d}.pdf"
    draw_pdf(path,"TAX INVOICE",lines)
    return {"file":str(path.relative_to(ROOT)),"document_type":"invoice",
      "invoice_number":inv,"quantity":qty,"unit_rate":rate,"line_amount":line,
      "gst_rate":gst,"subtotal":subtotal,"cgst":cgst,"sgst":sgst,"igst":igst,
      "grand_total":total,"injected_error":"grand_total_plus_13" if bad else ("invalid_state_code" if i%5==0 else None),
      "expected_total":subtotal+tax}

def make_certificate(i):
    name=fake.name()
    cert=f"EX-PY-2026-{i:03d}"
    course=random.choice(["Python Programming","Data Science","Machine Learning"])
    issue=(date(2026,6,1)+timedelta(days=i)).isoformat()
    actual_name=("Different Candidate" if i%4==0 else name)
    cert_id=(f"BAD-ID-{i}" if i%5==0 else cert)
    lines=["CERTIFICATE OF COMPLETION",f"Awarded to: {actual_name}","Issued by: Example Institute",
      f"Course: {course}",f"Certificate ID: {cert_id}",f"Issue Date: {issue}",
      "This document is synthetic and created for software testing only."]
    path=OUT/"certificates"/f"certificate_{i:02d}.pdf"
    draw_pdf(path,"CERTIFICATE OF COMPLETION",lines)
    return {"file":str(path.relative_to(ROOT)),"document_type":"certificate",
      "holder_name":actual_name,"expected_name":name,"issuer":"Example Institute",
      "course":course,"certificate_id":cert_id,"issue_date":issue,
      "injected_error":"name_mismatch" if i%4==0 else ("id_not_in_registry" if i%5==0 else None)}

def main():
    (OUT/"invoices").mkdir(parents=True,exist_ok=True)
    (OUT/"certificates").mkdir(parents=True,exist_ok=True)
    invoices=[make_invoice(i) for i in range(1,21)]
    certificates=[make_certificate(i) for i in range(1,21)]
    with (ROOT/"data"/"issuer_registry.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=["cert_id","name","course","date"]); writer.writeheader()
        for item in certificates:
            if item["injected_error"]!="id_not_in_registry":
                writer.writerow({"cert_id":item["certificate_id"],"name":item["expected_name"],"course":item["course"],"date":item["issue_date"]})
    (OUT/"ground_truth.json").write_text(json.dumps({"invoices":invoices,"certificates":certificates},indent=2),encoding="utf-8")
    print(f"Generated {len(invoices)} invoices and {len(certificates)} certificates under {OUT}")
if __name__=="__main__": main()
