"""
Notice2Next - Comprehensive Automated Test Suite
Hacktoberfest 2026 Week 3 Evaluation

Tests:
1. All 6 synthetic evaluation scenarios with strict count and field assertions
2. Strict Substring vs Punctuation-Stripped Word Match differentiation
3. Independent field evidence tracking (action semantic disclaimer, role, deadline)
4. Unrelated historical date trap rejection (1974 founding date)
5. Mocked Google Gemma 2 API execution path (success, timeout, malformed JSON)
6. Exporters (CSV, Markdown) & FastAPI contract
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app
from app.samples import SAMPLE_NOTICES, get_sample_by_id
from app.extractor import (
    extract_action_items,
    extract_with_gemma_api,
    extract_with_deterministic_heuristic
)
from app.validator import (
    verify_source_quote,
    verify_deadline,
    validate_action_item,
    validate_extracted_checklist,
    normalize_whitespace
)
from app.exporter import generate_csv, generate_markdown

client = TestClient(app)


# ==============================================================================
# 1. SIX SYNTHETIC SCENARIO REGRESSION TESTS (Strict Counts & Ground Truth)
# ==============================================================================

def test_case_1_complete_circular_strict():
    """Case 1: Exactly 2 tasks, explicit duties, Oct 29 & Nov 02 deadlines, $15 fee, strict quotes."""
    sample = get_sample_by_id("case_1_complete")
    ext = extract_action_items(sample["text"])
    val = validate_extracted_checklist(sample["text"], ext["raw_items"])

    # Strict count assertion
    assert val["total_items"] == 2
    assert val["verified_count"] == 2
    assert val["flagged_count"] == 0
    assert val["overall_grounding_rate"] == 100.0

    items = val["items"]
    assignees = [it["assignee"] for it in items]
    assert any("Science Teachers" in a for a in assignees)
    assert any("Homeroom Teachers" in a for a in assignees)

    deadlines = [it["deadline"] for it in items]
    assert any("October 29" in d for d in deadlines)
    assert any("November 02" in d for d in deadlines)

    fees = [it["fee_or_docs"] for it in items]
    assert any("$15" in f for f in fees)

    for item in items:
        assert item["quote_verified"] is True
        assert item["validation_status"] == "VERIFIED_QUOTE_GROUNDED"
        assert item["validation_badge_text"] == "✓ Verbatim Quote Found"
        assert item["field_evidence"]["quote"]["is_strict_substring"] is True


def test_case_2_omitted_deadline_strict():
    """Case 2: Exactly 1 task, explicit Homeroom Teachers assignee, deadline strictly NOT STATED."""
    sample = get_sample_by_id("case_2_omitted_deadline")
    ext = extract_action_items(sample["text"])
    val = validate_extracted_checklist(sample["text"], ext["raw_items"])

    assert val["total_items"] == 1
    item = val["items"][0]
    assert item["deadline"] == "NOT STATED"
    assert "homeroom teachers" in item["assignee"].lower()
    assert item["quote_verified"] is True
    assert item["validation_status"] == "VERIFIED_QUOTE_GROUNDED"
    assert item["field_evidence"]["deadline"]["status"] == "CORRECTLY_MARKED_NOT_STATED"


def test_case_3_informational_zero_tasks_strict():
    """Case 3: Exactly 0 actionable tasks for congratulatory/reopening notice."""
    sample = get_sample_by_id("case_3_informational")
    ext = extract_action_items(sample["text"])
    val = validate_extracted_checklist(sample["text"], ext["raw_items"])

    assert val["total_items"] == 0
    assert len(val["items"]) == 0
    assert "Informational Notice" in val["disclaimer"]


def test_case_4_unrelated_date_trap_strict():
    """Case 4: Exactly 1 task; Nov 10 captured; 1974 founding date & March 26 rejected."""
    sample = get_sample_by_id("case_4_unrelated_date")
    ext = extract_action_items(sample["text"])
    val = validate_extracted_checklist(sample["text"], ext["raw_items"])

    assert val["total_items"] == 1
    item = val["items"][0]
    assert "1974" not in item["deadline"]
    assert "March 26" not in item["deadline"]
    assert "November 10" in item["deadline"]
    assert "Subject Heads" in item["assignee"]
    assert item["quote_verified"] is True


def test_case_5_multi_role_bangla_strict():
    """Case 5: Exactly 2 tasks, distinct Bangla duties and deadlines."""
    sample = get_sample_by_id("case_5_multi_role_bangla")
    ext = extract_action_items(sample["text"])
    val = validate_extracted_checklist(sample["text"], ext["raw_items"])

    assert val["total_items"] == 2
    assignees = [it["assignee"] for it in val["items"]]
    assert any("শ্রেণি শিক্ষক" in a for a in assignees)
    assert any("আইসিটি" in a or "ল্যাব" in a for a in assignees)

    deadlines = [it["deadline"] for it in val["items"]]
    assert any("২৮ অক্টোবর" in d for d in deadlines)
    assert any("৩০ অক্টোবর" in d for d in deadlines)


def test_case_6_contradictory_flagged_for_human_review_strict():
    """Case 6: Contradictory times (10:00 AM vs 5:00 PM) MUST be flagged for human review."""
    sample = get_sample_by_id("case_6_contradictory_malformed")
    ext = extract_action_items(sample["text"])
    val = validate_extracted_checklist(sample["text"], ext["raw_items"])

    assert val["total_items"] == 1
    item = val["items"][0]
    assert item["validation_status"] == "FLAGGED_FOR_HUMAN_REVIEW"
    assert "Contradiction Detected" in item["validation_badge_text"]


# ==============================================================================
# 2. EVIDENCE VALIDATOR UNIT TESTS (Strict vs Punctuation vs Hallucination)
# ==============================================================================

def test_verify_source_quote_strict_verbatim():
    """Exact verbatim match returns STRICT_SUBSTRING_MATCH with is_strict=True."""
    notice = "All homeroom teachers must submit the report cards before Friday noon."
    quote = "All homeroom teachers must submit the report cards before Friday noon."
    is_strict, category, score = verify_source_quote(notice, quote)
    assert is_strict is True
    assert category == "STRICT_SUBSTRING_MATCH"
    assert score == 1.0


def test_verify_source_quote_punctuation_stripped_not_strict():
    """Punctuation stripped match returns PUNCTUATION_STRIPPED_WORD_MATCH with is_strict=False."""
    notice = "Grade 10 teachers (special batch) must collect forms."
    # Notice has parentheses, quote strips them
    quote = "Grade 10 teachers special batch must collect forms"
    is_strict, category, score = verify_source_quote(notice, quote)
    assert is_strict is False
    assert category == "PUNCTUATION_STRIPPED_WORD_MATCH"
    assert score == 0.75

    # Ensure validate_action_item flags it for human review!
    validated = validate_action_item(notice, {
        "action": "Collect forms",
        "assignee": "Grade 10 teachers",
        "deadline": "NOT STATED",
        "source_quote": quote
    })
    assert validated["validation_status"] == "FLAGGED_FOR_HUMAN_REVIEW"
    assert "Punctuation Differs" in validated["validation_badge_text"]


def test_verify_source_quote_hallucination_rejected():
    """Invented quote returns UNVERIFIED_OR_HALLUCINATED with is_strict=False."""
    notice = "Oakridge High School sports day will be on Friday."
    hallucinated_quote = "All mathematics teachers must pay 50 dollars immediately."
    is_strict, category, score = verify_source_quote(notice, hallucinated_quote)
    assert is_strict is False
    assert category == "UNVERIFIED_OR_HALLUCINATED"
    assert score == 0.0


def test_independent_field_evidence_generation():
    """Validates that action, assignee, and deadline fields have independent evidence tracking."""
    notice = "Chemistry teachers should review safety goggles by Friday."
    item = {
        "action": "Review safety goggles",
        "assignee": "Chemistry teachers",
        "deadline": "Friday",
        "source_quote": "Chemistry teachers should review safety goggles by Friday."
    }
    val = validate_action_item(notice, item)
    assert "field_evidence" in val
    assert val["field_evidence"]["quote"]["is_strict_substring"] is True
    assert val["field_evidence"]["action"]["is_semantically_proven"] is False  # Honest semantic disclaimer
    assert val["field_evidence"]["assignee"]["status"] == "ROLE_FOUND_IN_TEXT"
    assert val["field_evidence"]["deadline"]["status"] == "DEADLINE_GROUNDED"


# ==============================================================================
# 3. GEMMA 2 INFERENCE PATH & RESILIENCE TESTS (Mocked Calls)
# ==============================================================================

def test_extract_with_gemma_api_success_path():
    """Tests the remote Google Gemma 2 execution path when API returns valid structured JSON."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({
                        "actions": [
                            {
                                "action": "Submit science project synopsis",
                                "assignee": "Science Teachers",
                                "deadline": "October 29, 2026",
                                "fee_or_docs": "Safety Form",
                                "source_quote": "Science Teachers are hereby instructed to submit the final roster"
                            }
                        ]
                    })
                }
            }
        ]
    }

    with patch("app.extractor.BACKBOARD_API_KEY", "mock_valid_key"):
        with patch("requests.post", return_value=mock_response):
            items = extract_with_gemma_api("Sample circular text")
            assert items is not None
            assert len(items) == 1
            assert items[0]["action"] == "Submit science project synopsis"
            assert items[0]["assignee"] == "Science Teachers"


def test_extract_with_gemma_api_timeout_fallback():
    """Tests that network timeout falls back gracefully without raising an unhandled exception."""
    import requests
    with patch("app.extractor.BACKBOARD_API_KEY", "mock_valid_key"):
        with patch("requests.post", side_effect=requests.Timeout("Connection timed out")):
            result = extract_action_items("CIRCULAR: Homeroom teachers must update allergy cards.")
            assert result is not None
            assert result["live_model_called"] is False
            assert "Deterministic Heuristic" in result["engine"]
            assert len(result["raw_items"]) >= 1


def test_extract_with_gemma_api_malformed_json_fallback():
    """Tests that malformed non-JSON model output falls back to deterministic heuristic."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "I cannot parse this notice in JSON format."}}]
    }

    with patch("app.extractor.BACKBOARD_API_KEY", "mock_valid_key"):
        with patch("requests.post", return_value=mock_response):
            result = extract_action_items("CIRCULAR: Homeroom teachers must update allergy cards.")
            assert result["live_model_called"] is False
            assert "Deterministic Heuristic" in result["engine"]


# ==============================================================================
# 4. EXPORTERS & FASTAPI BENCHMARK ENDPOINT TESTS
# ==============================================================================

def test_csv_export_format():
    items = [
        {
            "action": "Collect garden slips",
            "assignee": "Homeroom Teachers",
            "deadline": "November 02, 2026",
            "fee_or_docs": "$15",
            "source_quote": "Homeroom Teachers of Grade 8 are requested to collect...",
            "validation_status": "VERIFIED_QUOTE_GROUNDED",
            "grounding_score": 1.0,
            "is_completed": False
        }
    ]
    csv_str = generate_csv(items)
    assert "Action Item,Responsible Group,Deadline" in csv_str
    assert "Collect garden slips" in csv_str
    assert "$15" in csv_str


def test_api_benchmark_endpoint_strict_pass():
    """Verifies that the /api/benchmark endpoint runs and evaluates all 6 scenarios with exact checks."""
    res = client.get("/api/benchmark")
    assert res.status_code == 200
    data = res.json()
    assert data["total_test_cases"] == 6
    assert data["passed_cases"] == 6
    assert data["pass_rate_percentage"] == 100.0
    assert "transparency_statement" in data
    assert "engine_evaluated" in data


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

