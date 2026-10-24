"""
Notice2Next - Comprehensive Automated Test Suite
Hacktoberfest 2026 Week 3 Evaluation

Tests:
- All 6 synthetic evaluation cases (Complete, Missing Deadline, Informational, Date Trap, Bangla Multi-Role, Contradictory)
- Exact Substring Quote Matching & Anti-Hallucination Guardrails
- Deadline Grounding vs Unrelated Historical Date Trap
- CSV & Markdown Exporter Integrity
- FastAPI Contract & Error Responses
"""

import pytest
import json
from fastapi.testclient import TestClient

from main import app
from app.samples import SAMPLE_NOTICES, get_sample_by_id
from app.extractor import extract_action_items, extract_with_deterministic_heuristic
from app.validator import (
    verify_source_quote,
    verify_deadline,
    validate_action_item,
    validate_extracted_checklist,
    normalize_whitespace
)
from app.exporter import generate_csv, generate_markdown

client = TestClient(app)


# ==========================================
# 1. SIX SYNTHETIC SCENARIO EVALUATION TESTS
# ==========================================

def test_case_1_complete_circular():
    """Case 1: Standard circular with complete duties, explicit deadlines, and fees."""
    sample = get_sample_by_id("case_1_complete")
    ext = extract_action_items(sample["text"])
    val = validate_extracted_checklist(sample["text"], ext["raw_items"])

    assert val["total_items"] >= 2
    assert val["verified_count"] >= 2
    assert val["overall_grounding_rate"] == 100.0

    # Verify Science Teachers duty
    actions_text = " ".join([it["action"] for it in val["items"]])
    assert "Science Teachers" in [it["assignee"] for it in val["items"]][0] or "Science Teachers" in [it["assignee"] for it in val["items"]][1]
    
    # Verify quotes are exact substrings
    for item in val["items"]:
        assert item["quote_verified"] is True
        assert item["validation_status"] == "VERIFIED_SUBSTRING"


def test_case_2_omitted_deadline():
    """Case 2: Action is stated, but deadline is absent. Must yield NOT STATED."""
    sample = get_sample_by_id("case_2_omitted_deadline")
    ext = extract_action_items(sample["text"])
    val = validate_extracted_checklist(sample["text"], ext["raw_items"])

    assert val["total_items"] >= 1
    item = val["items"][0]
    assert item["deadline"] == "NOT STATED"
    assert item["quote_verified"] is True
    assert "homeroom teachers" in item["assignee"].lower()


def test_case_3_informational_zero_actions():
    """Case 3: Purely informational advisory with congratulations. Must yield 0 tasks."""
    sample = get_sample_by_id("case_3_informational")
    ext = extract_action_items(sample["text"])
    val = validate_extracted_checklist(sample["text"], ext["raw_items"])

    assert val["total_items"] == 0
    assert len(val["items"]) == 0
    assert "No action items detected" in val["disclaimer"]


def test_case_4_unrelated_date_trap():
    """Case 4: Contains historical founding date (1974) and holiday (March 26). Target deadline is Nov 10."""
    sample = get_sample_by_id("case_4_unrelated_date")
    ext = extract_action_items(sample["text"])
    val = validate_extracted_checklist(sample["text"], ext["raw_items"])

    assert val["total_items"] >= 1
    item = val["items"][0]
    # Ensure founding year 1974 is not falsely captured as deadline
    assert "1974" not in item["deadline"]
    assert "March 26" not in item["deadline"]
    assert "November 10" in item["deadline"]


def test_case_5_multi_role_bangla():
    """Case 5: Multi-role Bangla circular with distinct roles and dates."""
    sample = get_sample_by_id("case_5_multi_role_bangla")
    ext = extract_action_items(sample["text"])
    val = validate_extracted_checklist(sample["text"], ext["raw_items"])

    assert val["total_items"] >= 2
    assignees = [it["assignee"] for it in val["items"]]
    assert any("শ্রেণি শিক্ষক" in a for a in assignees)
    assert any("আইসিটি" in a or "ল্যাব" in a for a in assignees)


def test_case_6_contradictory_notice():
    """Case 6: Contradictory instructions requiring human review."""
    sample = get_sample_by_id("case_6_contradictory_malformed")
    ext = extract_action_items(sample["text"])
    val = validate_extracted_checklist(sample["text"], ext["raw_items"])

    assert val["total_items"] >= 1


# ==========================================
# 2. EVIDENCE VALIDATOR UNIT TESTS
# ==========================================

def test_verify_source_quote_exact_match():
    notice = "All homeroom teachers must submit the report cards before Friday noon."
    quote = "All homeroom teachers must submit the report cards before Friday noon."
    ok, reason, score = verify_source_quote(notice, quote)
    assert ok is True
    assert reason == "EXACT_SUBSTRING"
    assert score == 1.0


def test_verify_source_quote_whitespace_variance():
    notice = "Notice:\n  Grade 10 teachers\tshall collect permission forms."
    quote = "Grade 10 teachers shall collect permission forms."
    ok, reason, score = verify_source_quote(notice, quote)
    assert ok is True
    assert score >= 0.95


def test_verify_source_quote_hallucination_rejected():
    notice = "Oakridge High School sports day will be on Friday."
    hallucinated_quote = "All mathematics teachers must pay 50 dollars immediately."
    ok, reason, score = verify_source_quote(notice, hallucinated_quote)
    assert ok is False
    assert reason == "UNVERIFIED_OR_HALLUCINATED"
    assert score == 0.0


def test_verify_deadline_correctly_marked_not_stated():
    notice = "Teachers should update their emergency contact books."
    quote = "Teachers should update their emergency contact books."
    ok, reason = verify_deadline(notice, quote, "NOT STATED")
    assert ok is True
    assert reason == "CORRECTLY_MARKED_NOT_STATED"


def test_verify_deadline_missed_date_flagged():
    notice = "Please submit the final ledger by Monday, November 02, 2026."
    quote = "Please submit the final ledger by Monday, November 02, 2026."
    ok, reason = verify_deadline(notice, quote, "NOT STATED")
    # Quote had a date, but model called it NOT STATED
    assert ok is False
    assert reason == "MISSED_DEADLINE_IN_QUOTE"


def test_verify_deadline_hallucinated_date():
    notice = "School picnic on Saturday."
    quote = "School picnic on Saturday."
    ok, reason = verify_deadline(notice, quote, "2029-12-31 at 11:59 PM")
    assert ok is False
    assert reason == "HALLUCINATED_DEADLINE_NOT_IN_CIRCULAR"


# ==========================================
# 3. EXPORTER TESTS
# ==========================================

def test_csv_export_structure():
    items = [
        {
            "id": "act_1",
            "action": "Collect field trip fees",
            "assignee": "Grade 8 Homeroom Teachers",
            "deadline": "November 02, 2026",
            "fee_or_docs": "$15 per student",
            "source_quote": "Homeroom Teachers of Grade 8 are requested to collect...",
            "validation_status": "VERIFIED_SUBSTRING",
            "grounding_score": 0.95,
            "is_completed": False
        }
    ]
    csv_str = generate_csv(items)
    assert "Status,Action Item,Responsible Group,Deadline" in csv_str
    assert "Collect field trip fees" in csv_str
    assert "Grade 8 Homeroom Teachers" in csv_str
    assert "November 02, 2026" in csv_str


def test_markdown_export_structure():
    items = [
        {
            "action": "Submit science project synopsis",
            "assignee": "Science Teachers",
            "deadline": "October 29, 2026",
            "fee_or_docs": "Safety Form",
            "source_quote": "submit the final roster of student project proposals",
            "is_completed": True
        }
    ]
    md = generate_markdown(items, "Oakridge Notice Checklist")
    assert "# 📋 Oakridge Notice Checklist" in md
    assert "[x]" in md
    assert "Submit science project synopsis" in md
    assert "Science Teachers" in md


# ==========================================
# 4. FASTAPI API INTEGRATION TESTS
# ==========================================

def test_api_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["service"] == "notice2next"
    assert "live_gemma_configured" in data


def test_api_samples_endpoint():
    res = client.get("/api/samples")
    assert res.status_code == 200
    data = res.json()
    assert "samples" in data
    assert len(data["samples"]) == 6


def test_api_extract_valid_notice():
    payload = {
        "text": (
            "CIRCULAR: All Art Teachers are instructed to deposit student painting portfolios "
            "to Room 304 by Wednesday, November 04, 2026 before 3:00 PM."
        ),
        "verify_quotes": True
    }
    res = client.post("/api/extract", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "engine" in data
    assert "summary" in data
    assert "items" in data
    assert len(data["items"]) >= 1
    assert data["items"][0]["quote_verified"] is True


def test_api_extract_empty_fails():
    res = client.post("/api/extract", json={"text": "   "})
    assert res.status_code == 422  # Pydantic validation error (min_length=10)


def test_api_benchmark_endpoint():
    res = client.get("/api/benchmark")
    assert res.status_code == 200
    data = res.json()
    assert data["total_test_cases"] == 6
    assert data["pass_rate_percentage"] == 100.0
    assert len(data["test_results"]) == 6
