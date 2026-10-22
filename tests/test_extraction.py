from classify import classify_document
from extract import extract_document

def test_marksheet_auto_detects_as_certificate():
    text = "BIHAR SCHOOL EXAMINATION BOARD\nMARKS STATEMENT\nRoll Number: 23010370\nName: MANISH KANT"
    assert classify_document(text) == "certificate"

def test_marksheet_extracts_common_fields():
    text = """BIHAR SCHOOL EXAMINATION BOARD
MARKS STATEMENT
Name: MANISH KANT
Roll Code: 22001
Roll Number: 23010370
Registration No: R-220010364-21
Annual Examination: 2023
Faculty: SCIENCE"""
    data = extract_document(text, "certificate")
    assert data["holder_name"] == "MANISH KANT"
    assert data["roll_code"] == "22001"
    assert data["roll_number"] == "23010370"
    assert data["exam_year"] == "2023"
