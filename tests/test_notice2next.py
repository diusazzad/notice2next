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
    verify_fee_or_docs,
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
    assert val["field_evidence"]["action"]["is_semantically_proven"] is False
    assert val["field_evidence"]["assignee"]["status"] in ["ROLE_FOUND_IN_TEXT", "ROLE_FOUND_IN_QUOTE"]
    assert val["field_evidence"]["deadline"]["status"] == "DEADLINE_GROUNDED_IN_QUOTE"


# 1. Completely matching date and time
def test_verify_deadline_complete_matching_date_and_time():
    """1. Completely matching date and time: must be strictly verified as grounded in quote."""
    notice = "Notice: Science teachers must submit proposals by Thursday, October 29, 2026 at 4:00 PM."
    quote = "Science teachers must submit proposals by Thursday, October 29, 2026 at 4:00 PM."
    ok, reason = verify_deadline(notice, quote, "Thursday, October 29, 2026 at 4:00 PM")
    assert ok is True
    assert reason == "DEADLINE_GROUNDED_IN_QUOTE"

    val = validate_action_item(notice, {
        "action": "Submit proposals",
        "assignee": "Science teachers",
        "deadline": "Thursday, October 29, 2026 at 4:00 PM",
        "source_quote": quote
    })
    assert val["validation_status"] == "VERIFIED_QUOTE_GROUNDED"
    assert "Verbatim Quote Found" in val["validation_badge_text"]


# 2. Only a date matching, but time incorrect
def test_verify_deadline_date_matching_but_time_incorrect_fails():
    """2. Date matches but time is wrong/hallucinated: MUST fail closed (no 50% token pass)."""
    notice = "Notice: Science teachers must submit proposals by Thursday, October 29, 2026 at 4:00 PM."
    quote = "Science teachers must submit proposals by Thursday, October 29, 2026 at 4:00 PM."
    # Model hallucinates 9:00 PM instead of 4:00 PM
    ok, reason = verify_deadline(notice, quote, "Thursday, October 29, 2026 at 9:00 PM")
    assert ok is False
    assert reason == "DEADLINE_TIME_MISMATCH_IN_QUOTE"

    val = validate_action_item(notice, {
        "action": "Submit proposals",
        "assignee": "Science teachers",
        "deadline": "Thursday, October 29, 2026 at 9:00 PM",
        "source_quote": quote
    })
    assert val["validation_status"] == "FLAGGED_FOR_HUMAN_REVIEW"
    assert "Time Mismatch" in val["validation_badge_text"]


# 3. An unrelated date elsewhere in the notice
def test_verify_deadline_unrelated_date_elsewhere_in_notice_fails():
    """3. Unrelated historical date from elsewhere in notice: MUST fail with trap or ungrounded."""
    notice = (
        "Since our school's historic founding on September 15, 1974, excellence has been our mission. "
        "Senior Department Subject Heads are required to submit articles by Tuesday, November 10, 2026 at 3:00 PM."
    )
    quote = "Senior Department Subject Heads are required to submit articles by Tuesday, November 10, 2026 at 3:00 PM."
    # Model traps on founding date
    ok, reason = verify_deadline(notice, quote, "September 15, 1974")
    assert ok is False
    assert reason in ["UNRELATED_HISTORICAL_DATE_TRAP", "DEADLINE_NOT_IN_SUPPORTING_QUOTE"]

    val = validate_action_item(notice, {
        "action": "Submit articles",
        "assignee": "Subject Heads",
        "deadline": "September 15, 1974",
        "source_quote": quote
    })
    assert val["validation_status"] == "FLAGGED_FOR_HUMAN_REVIEW"


# 4. A deadline absent from the supporting quote
def test_verify_deadline_absent_from_supporting_quote_fails():
    """4. Deadline exists in circular paragraph 1, but is absent from this action's quote in paragraph 2."""
    notice = (
        "Paragraph 1: Annual sports day fee is due December 15.\n"
        "Paragraph 2: Homeroom teachers must check and update student attendance ledgers."
    )
    quote = "Homeroom teachers must check and update student attendance ledgers."
    # Model grabs December 15 from paragraph 1
    ok, reason = verify_deadline(notice, quote, "December 15")
    assert ok is False
    assert reason == "DEADLINE_NOT_IN_SUPPORTING_QUOTE"

    val = validate_action_item(notice, {
        "action": "Check and update student attendance ledgers",
        "assignee": "Homeroom teachers",
        "deadline": "December 15",
        "source_quote": quote
    })
    assert val["validation_status"] == "FLAGGED_FOR_HUMAN_REVIEW"
    assert "Date Mismatch" in val["validation_badge_text"]


# 5. Contradictory timing
def test_verify_deadline_contradictory_timing_fails():
    """5. Contradictory timing (10:00 AM vs 5:00 PM with contrast): MUST be flagged for review."""
    notice = (
        "Uniform inspection slips should be turned in by 10:00 AM tomorrow morning, "
        "however no slips will be accepted before 5:00 PM due to system maintenance. "
        "Details subject to revision without notice."
    )
    quote = "Uniform inspection slips should be turned in by 10:00 AM tomorrow morning, however no slips will be accepted before 5:00 PM."
    ok, reason = verify_deadline(notice, quote, "10:00 AM")
    assert ok is False
    assert reason == "CONTRADICTORY_TIMING_REQUIRES_REVIEW"

    val = validate_action_item(notice, {
        "action": "Turn in inspection slips",
        "assignee": "Staff",
        "deadline": "10:00 AM",
        "source_quote": quote
    })
    assert val["validation_status"] == "FLAGGED_FOR_HUMAN_REVIEW"
    assert "Contradiction Detected" in val["validation_badge_text"]


# 6. Missing deadline incorrectly reported as NOT STATED when the quote contains an explicit deadline
def test_verify_deadline_missed_explicit_date_in_quote_fails():
    """6. Model reports NOT STATED when quote explicitly contains 'by Monday, November 02, 2026 before 12:00 PM'."""
    notice = "Notice: All fees must be deposited by Monday, November 02, 2026 before 12:00 PM."
    quote = "All fees must be deposited by Monday, November 02, 2026 before 12:00 PM."
    # Model incorrectly reports NOT STATED
    ok, reason = verify_deadline(notice, quote, "NOT STATED")
    assert ok is False
    assert reason == "MISSED_DEADLINE_IN_QUOTE"

    val = validate_action_item(notice, {
        "action": "Deposit fees",
        "assignee": "Staff",
        "deadline": "NOT STATED",
        "source_quote": quote
    })
    assert val["validation_status"] == "FLAGGED_FOR_HUMAN_REVIEW"
    assert "Date Missed in Quote" in val["validation_badge_text"]


# 7. Date number ambiguity (P0: Day 3 vs Day 30 regression test)
def test_verify_deadline_date_number_ambiguity_oct_3_vs_30_rejected():
    """P0 Regression: Candidate deadline 'October 3, 2026 at 3:00 PM' against quote 'October 30, 2026 at 3:00 PM' MUST be rejected."""
    notice = "Notice: Science teachers must submit by October 30, 2026 at 3:00 PM."
    quote = "Science teachers must submit by October 30, 2026 at 3:00 PM."
    candidate = "October 3, 2026 at 3:00 PM"
    
    ok, reason = verify_deadline(notice, quote, candidate)
    assert ok is False
    assert reason == "DEADLINE_DATE_COMPONENT_MISMATCH"

    val = validate_action_item(notice, {
        "action": "Submit reports",
        "assignee": "Science teachers",
        "deadline": candidate,
        "source_quote": quote
    })
    assert val["validation_status"] == "FLAGGED_FOR_HUMAN_REVIEW"
    assert "Date Mismatch" in val["validation_badge_text"]


# 8. Partial Assignee Matching (P0: Grade 12 vs Grade 10 regression test)
def test_verify_assignee_partial_match_grade_12_vs_grade_10_flagged():
    """P0 Regression: Candidate assignee 'Grade 12 Science Teachers' against source 'Grade 10 Science Teachers' MUST be flagged for review."""
    notice = "All Grade 10 Science Teachers are hereby instructed to submit project proposals."
    quote = "All Grade 10 Science Teachers are hereby instructed to submit project proposals."
    candidate_assignee = "Grade 12 Science Teachers"

    val = validate_action_item(notice, {
        "action": "Submit project proposals",
        "assignee": candidate_assignee,
        "deadline": "NOT STATED",
        "source_quote": quote
    })
    assert val["validation_status"] == "FLAGGED_FOR_HUMAN_REVIEW"
    assert val["field_evidence"]["assignee"]["status"] == "ROLE_PARTIAL_MATCH"
    assert val["field_evidence"]["assignee"]["is_grounded"] is False
    assert "Role Mismatch" in val["validation_badge_text"]


# 9. Fee and Document Grounding (P0: Hallucinated fee regression test)
def test_verify_fee_or_docs_hallucinated_fee_rejected():
    """P0 Regression: Candidate fee '$15' when circular mentions no fee MUST be flagged for review."""
    notice = "Homeroom teachers must collect excursion permission slips from all students."
    quote = "Homeroom teachers must collect excursion permission slips from all students."
    candidate_fee = "Fee: $15 per student"

    val = validate_action_item(notice, {
        "action": "Collect permission slips",
        "assignee": "Homeroom teachers",
        "deadline": "NOT STATED",
        "fee_or_docs": candidate_fee,
        "source_quote": quote
    })
    assert val["validation_status"] == "FLAGGED_FOR_HUMAN_REVIEW"
    assert val["field_evidence"]["fee_or_docs"]["is_grounded"] is False
    assert "Fee Mismatch" in val["validation_badge_text"]


# 10. Fee Numeric Collision Check (P0 Regression: Number in quote in non-fee context MUST fail)
def test_verify_fee_numeric_amount_without_monetary_context_rejected():
    """P0 Regression: Quote 'There are 15 teachers. No fee is required.' must NOT accept candidate fee '$15 per student'."""
    quote = "There are 15 teachers. No fee is required."
    candidate_fee = "$15 per student"

    ok, reason = verify_fee_or_docs(quote, candidate_fee)
    assert ok is False
    assert reason == "FEE_NOT_IN_SUPPORTING_QUOTE"

    val = validate_action_item(quote, {
        "action": "Staff attendance",
        "assignee": "Teachers",
        "deadline": "NOT STATED",
        "fee_or_docs": candidate_fee,
        "source_quote": quote
    })
    assert val["validation_status"] == "FLAGGED_FOR_HUMAN_REVIEW"
    assert val["field_evidence"]["fee_or_docs"]["status"] == "FEE_NOT_IN_SUPPORTING_QUOTE"
    assert "Fee Mismatch" in val["validation_badge_text"]


# 11. Required Documents Partial Word Match Check (P0 Regression: 'permission slips' vs 'Permission was discussed')
def test_verify_required_docs_partial_word_missing_flagged():
    """P0 Regression: Extracted requirement 'permission slips' must be flagged when quote only mentions 'Permission was discussed.'"""
    quote = "Permission was discussed."
    candidate_doc = "permission slips"

    ok, reason = verify_fee_or_docs(quote, candidate_doc)
    assert ok is False
    assert reason == "DOCS_NOT_IN_SUPPORTING_QUOTE"

    val = validate_action_item(quote, {
        "action": "Review excursion policy",
        "assignee": "NOT STATED",
        "deadline": "NOT STATED",
        "fee_or_docs": candidate_doc,
        "source_quote": quote
    })
    assert val["validation_status"] == "FLAGGED_FOR_HUMAN_REVIEW"
    assert val["field_evidence"]["fee_or_docs"]["status"] == "DOCS_NOT_IN_SUPPORTING_QUOTE"
    assert "Document Mismatch" in val["validation_badge_text"]


# 12. Assignee Clause Scoping Check (P1 Regression: Role from separate clause MUST be flagged)
def test_verify_assignee_role_from_separate_clause_flagged():
    """P1 Regression: Assignee 'Homeroom Teachers' assigned to Science Teachers' quote MUST be flagged as not in supporting quote."""
    notice = (
        "Clause 1: All Grade 10 Science Teachers must submit lab rosters by October 30.\n"
        "Clause 2: Homeroom Teachers must collect attendance slips by November 02."
    )
    quote = "All Grade 10 Science Teachers must submit lab rosters by October 30."
    candidate_assignee = "Homeroom Teachers"

    val = validate_action_item(notice, {
        "action": "Submit lab rosters",
        "assignee": candidate_assignee,
        "deadline": "October 30",
        "source_quote": quote
    })
    assert val["validation_status"] == "FLAGGED_FOR_HUMAN_REVIEW"
    assert val["field_evidence"]["assignee"]["status"] == "ROLE_NOT_IN_SUPPORTING_QUOTE"
    assert val["field_evidence"]["assignee"]["is_grounded"] is False
    assert "Role Mismatch" in val["validation_badge_text"]


# 13. Monetary Fee Amount Boundary Check (P0 Regression: $15 candidate vs $150 quote, and budget allocation vs no fee)
def test_verify_fee_amount_boundary_and_disclaimer():
    """P0 Regression: A candidate $15 fee must not be accepted from a $150 amount or a $15 budget allocation when no fee is stated."""
    # Test 13A: $15 fee vs $150 quote -> fail closed
    quote_150 = "A transport fee of $150 is required."
    ok, reason = verify_fee_or_docs(quote_150, "$15 fee")
    assert ok is False
    assert reason == "FEE_NOT_IN_SUPPORTING_QUOTE"

    val_150 = validate_action_item(quote_150, {
        "action": "Pay transport cost",
        "assignee": "NOT STATED",
        "deadline": "NOT STATED",
        "fee_or_docs": "$15 fee",
        "source_quote": quote_150
    })
    assert val_150["validation_status"] == "FLAGGED_FOR_HUMAN_REVIEW"
    assert val_150["field_evidence"]["fee_or_docs"]["status"] == "FEE_NOT_IN_SUPPORTING_QUOTE"

    # Test 13B: $15 fee vs $15 quote -> amount supported
    quote_15 = "A transport fee of $15 is required."
    ok_15, reason_15 = verify_fee_or_docs(quote_15, "$15 fee")
    assert ok_15 is True
    assert reason_15 == "FEE_DOCS_GROUNDED_IN_QUOTE"

    # Test 13C: $15 fee vs $15 budget allocation with explicit no fee disclaimer -> flag for review
    quote_budget = "A budget allocation of $15 was recorded; no fee is required."
    ok_b, reason_b = verify_fee_or_docs(quote_budget, "$15 fee")
    assert ok_b is False
    assert reason_b == "FEE_NOT_IN_SUPPORTING_QUOTE"

    val_budget = validate_action_item(quote_budget, {
        "action": "Record project budget",
        "assignee": "NOT STATED",
        "deadline": "NOT STATED",
        "fee_or_docs": "$15 fee",
        "source_quote": quote_budget
    })
    assert val_budget["validation_status"] == "FLAGGED_FOR_HUMAN_REVIEW"
    assert val_budget["field_evidence"]["fee_or_docs"]["status"] == "FEE_NOT_IN_SUPPORTING_QUOTE"


# 14. Assignee Token Word-Boundary Check (P0 Regression: Grade 1 vs Grade 10)
def test_verify_assignee_grade_1_vs_grade_10_flagged():
    """P0 Regression: Grade 1 Science Teachers must not be accepted when quote states Grade 10 Science Teachers."""
    notice = "Grade 10 Science Teachers must submit lab rosters."
    quote = "Grade 10 Science Teachers must submit lab rosters."
    candidate_assignee = "Grade 1 Science Teachers"

    val = validate_action_item(notice, {
        "action": "Submit lab rosters",
        "assignee": candidate_assignee,
        "deadline": "NOT STATED",
        "source_quote": quote
    })
    assert val["validation_status"] == "FLAGGED_FOR_HUMAN_REVIEW"
    assert val["field_evidence"]["assignee"]["status"] == "ROLE_PARTIAL_MATCH"
    assert val["field_evidence"]["assignee"]["is_grounded"] is False
    assert "Role Mismatch" in val["validation_badge_text"]


# 15. Required Document Form Stripping Check (P0 Regression: 'Permission form' vs 'Permission was discussed')
def test_verify_required_doc_permission_form_vs_permission_discussed():
    """P0 Regression: Candidate document 'Permission form' must be rejected when quote only mentions 'Permission was discussed'."""
    quote = "Permission was discussed during the meeting."
    candidate_doc = "Permission form"

    ok, reason = verify_fee_or_docs(quote, candidate_doc)
    assert ok is False
    assert reason == "DOCS_NOT_IN_SUPPORTING_QUOTE"

    val = validate_action_item(quote, {
        "action": "Submit permission form",
        "assignee": "NOT STATED",
        "deadline": "NOT STATED",
        "fee_or_docs": candidate_doc,
        "source_quote": quote
    })
    assert val["validation_status"] == "FLAGGED_FOR_HUMAN_REVIEW"
    assert val["field_evidence"]["fee_or_docs"]["status"] == "DOCS_NOT_IN_SUPPORTING_QUOTE"
    assert "Document Mismatch" in val["validation_badge_text"]


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


# ==============================================================================
# 5. URL & PDF INGESTION TESTS (Browserbase & SSRF Safeguards)
# ==============================================================================

def test_url_safety_ssrf_blocking():
    """Verifies that validate_url_safety blocks localhost, private subnets, and non-HTTP protocols."""
    from app.browser_fetcher import validate_url_safety

    assert validate_url_safety("http://localhost:8000")[0] is False
    assert validate_url_safety("http://127.0.0.1/admin")[0] is False
    assert validate_url_safety("http://192.168.1.1/secret")[0] is False
    assert validate_url_safety("http://10.0.0.1/private")[0] is False
    assert validate_url_safety("ftp://nu.ac.bd/notice.pdf")[0] is False
    assert validate_url_safety("file:///etc/passwd")[0] is False

    # Valid public university URLs
    assert validate_url_safety("https://www.nu.ac.bd/uploads/notices/notice_2121.pdf")[0] is True
    assert validate_url_safety("https://bou.ac.bd/NoticeBoard/Examination")[0] is True


def test_api_fetch_notice_url_ssrf_rejected():
    """Tests that the API rejects SSRF attacks with HTTP 400."""
    res = client.post("/api/fetch-notice-url", json={"url": "http://127.0.0.1:8000/internal"})
    assert res.status_code == 400
    assert "SSRF prevention" in res.json()["detail"]


# ==============================================================================
# 6. ELEVENLABS AUDIO BRIEFING GENERATION TESTS
# ==============================================================================

def test_elevenlabs_spoken_briefing_generation():
    """Tests the natural language briefing text generator."""
    from app.audio import generate_spoken_briefing_text

    items = [
        {
            "action": "Submit lab rosters",
            "assignee": "Science Teachers",
            "deadline": "October 30, 2026",
            "fee_or_docs": "Safety Form",
            "validation_status": "VERIFIED_QUOTE_GROUNDED"
        }
    ]
    briefing = generate_spoken_briefing_text(items)
    assert "1 next action item detected" in briefing
    assert "Science Teachers must submit lab rosters" in briefing
    assert "October 30, 2026" in briefing
    assert "Safety Form" in briefing


def test_api_speak_briefing_endpoint():
    """Tests the /api/speak-briefing endpoint with automatic Web Speech fallback."""
    payload = {
        "items": [
            {
                "action": "Submit science project synopsis",
                "assignee": "Grade 10 Teachers",
                "deadline": "November 02, 2026",
                "fee_or_docs": "$15 fee",
                "validation_status": "VERIFIED_QUOTE_GROUNDED"
            }
        ],
        "summary": "Annual science fair circular"
    }
    res = client.post("/api/speak-briefing", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "briefing_text" in data
    assert "Grade 10 Teachers" in data["briefing_text"]
    assert "November 02, 2026" in data["briefing_text"]
    assert "engine" in data


# ==============================================================================
# 7. OCR CLEANUP & VERIFIED SAMPLE NOTICE TESTS
# ==============================================================================

def test_clean_ocr_text_deterministic():
    """Tests that hyphenated broken lines and fragmented sentences are repaired."""
    from app.extractor import clean_ocr_text_deterministic

    raw_noisy_ocr = (
        "It is hereby notified that all Grade 9 sci-\n"
        "ence teachers must submit final student ro-\n"
        "sters by October 29 at 4 : 00 PM.\n"
        "Please collect transport fee of $ 15 per student."
    )
    cleaned = clean_ocr_text_deterministic(raw_noisy_ocr)
    assert "science teachers" in cleaned
    assert "student rosters" in cleaned
    assert "4:00 PM" in cleaned
    assert "$15" in cleaned


def test_api_clean_ocr_text_endpoint():
    """Tests the /api/clean-ocr-text endpoint."""
    raw_ocr = "Homeroom teachers must submit forms by Friday 3 : 00 PM."
    res = client.post("/api/clean-ocr-text", json={"raw_text": raw_ocr})
    assert res.status_code == 200
    data = res.json()
    assert "cleaned_text" in data
    assert "3:00 PM" in data["cleaned_text"]
    assert "engine" in data


def test_api_sample_public_notice_endpoint():
    """Tests the /api/sample-public-notice endpoint returns valid HTML circular."""
    res = client.get("/api/sample-public-notice")
    assert res.status_code == 200
    assert "BOARD OF INTERMEDIATE & SECONDARY EDUCATION" in res.text
    assert "November 03, 2026" in res.text
    assert "$25 per candidate" in res.text



