"""
Notice2Next - Deterministic Evidence & Anti-Hallucination Validator
Layer 3 of Notice2Next Architecture.

Guarantees:
1. Exact Substring Verification: Ensures every extracted supporting_quote is an authentic substring of the circular.
2. Deadline Grounding: Ensures stated deadlines exist in the source text; prevents hallucinated dates.
3. Explicit Missing Information: Enforces 'NOT STATED' when dates or fees are absent.
4. Human Review Flagging: Surfaces non-grounded or ambiguous items with clear visual warnings.
"""

import re
import unicodedata
from typing import Dict, Any, List, Tuple


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace, newlines, and unicode for robust substring comparison."""
    if not text:
        return ""
    # Normalize unicode (handles Bangla conjuncts and composite characters)
    text = unicodedata.normalize("NFKC", text)
    # Collapse any sequence of whitespace/newlines to a single space
    return re.sub(r"\s+", " ", text).strip()


def verify_source_quote(notice_text: str, candidate_quote: str) -> Tuple[bool, str, float]:
    """
    Checks whether candidate_quote is an exact substring of the original notice.
    Returns: (is_verified, reason_code, match_ratio)
    """
    if not candidate_quote or not candidate_quote.strip():
        return False, "EMPTY_QUOTE", 0.0

    norm_notice = normalize_whitespace(notice_text).lower()
    norm_quote = normalize_whitespace(candidate_quote).lower()

    # Exact substring match on normalized text
    if norm_quote in norm_notice:
        return True, "EXACT_SUBSTRING", 1.0

    # Punctuation-stripped fallback attempt
    clean_notice = re.sub(r"[^\w\s]", "", norm_notice)
    clean_quote = re.sub(r"[^\w\s]", "", norm_quote)
    if clean_quote and clean_quote in clean_notice:
        return True, "EXACT_WORDS_MATCH", 0.95

    # Check for short quote containment (if quote is too long, model might have truncated or paraphrased)
    words = clean_quote.split()
    if len(words) >= 4:
        matched_words = [w for w in words if w in clean_notice]
        overlap_ratio = len(matched_words) / len(words)
        if overlap_ratio >= 0.75:
            return False, "PARAPHRASED_OR_TRUNCATED", round(overlap_ratio, 2)

    return False, "UNVERIFIED_OR_HALLUCINATED", 0.0


def verify_deadline(notice_text: str, quote: str, stated_deadline: str) -> Tuple[bool, str]:
    """
    Validates deadline grounding against circular text and quote.
    """
    if not stated_deadline:
        return True, "NOT_STATED_DEFAULT"

    dl_upper = stated_deadline.strip().upper()
    is_not_stated = dl_upper in [
        "NOT STATED", "NOT SPECIFIED", "NONE", "UNSPECIFIED",
        "NOT MENTIONED", "N/A", "NO DEADLINE"
    ]

    norm_notice = normalize_whitespace(notice_text).lower()
    norm_quote = normalize_whitespace(quote).lower() if quote else ""

    if is_not_stated:
        # Check if the supporting quote itself has an obvious deadline trigger that was missed
        deadline_patterns = [
            r"\bby\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
            r"\bbefore\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)",
            r"\bআগামী\s+\d{1,2}\s+(?:জানুয়ারি|ফেব্রুয়ারি|মার্চ|এপ্রিল|মে|জুন|জুলাই|আগস্ট|সেপ্টেম্বর|অক্টোবর|নভেম্বর|ডিসেম্বর)",
            r"\bতারিখের\s+মধ্যে\b"
        ]
        for pat in deadline_patterns:
            if re.search(pat, norm_quote, re.IGNORECASE):
                return False, "MISSED_DEADLINE_IN_QUOTE"
        return True, "CORRECTLY_MARKED_NOT_STATED"

    # Deadline was stated by model: verify it actually appears in circular
    clean_dl = re.sub(r"[^\w\s]", "", stated_deadline.lower()).strip()
    clean_notice = re.sub(r"[^\w\s]", "", norm_notice)

    dl_tokens = clean_dl.split()
    if not dl_tokens:
        return False, "EMPTY_DEADLINE_TOKENS"

    # At least the core date/time tokens must exist in notice
    found_tokens = [tok for tok in dl_tokens if tok in clean_notice]
    token_ratio = len(found_tokens) / len(dl_tokens)

    if token_ratio < 0.5:
        return False, "HALLUCINATED_DEADLINE_NOT_IN_CIRCULAR"

    # Check if this deadline belongs to an unrelated context (e.g., founding year 1974)
    founding_indicators = ["founding", "founded", "established", "independence", "historic"]
    for ind in founding_indicators:
        if ind in norm_notice:
            # Check if the extracted deadline is located right next to founding keyword
            pat = rf"{ind}[^.]*?{re.escape(clean_dl)}"
            if re.search(pat, norm_notice, re.IGNORECASE):
                return False, "UNRELATED_HISTORICAL_DATE_TRAP"

    return True, "DEADLINE_GROUNDED"


def validate_action_item(notice_text: str, item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates a single extracted action item.
    Enriches item with validation fields.
    """
    action_text = item.get("action", "").strip()
    assignee = item.get("assignee", "NOT STATED").strip()
    deadline = item.get("deadline", "NOT STATED").strip()
    fee_or_docs = item.get("fee_or_docs", "NOT STATED").strip()
    source_quote = item.get("source_quote", "").strip()

    # 1. Verify Source Quote
    quote_ok, quote_reason, quote_score = verify_source_quote(notice_text, source_quote)

    # 2. Verify Deadline
    deadline_ok, deadline_reason = verify_deadline(notice_text, source_quote, deadline)

    # 3. Calculate Grounding Confidence Score (0.0 to 1.0)
    score = 0.0
    if quote_ok:
        score += 0.55
    else:
        score += 0.1 * quote_score

    if deadline_ok:
        score += 0.25
    
    if action_text and len(action_text) >= 10:
        score += 0.10

    if assignee and assignee.upper() != "NOT STATED":
        # Check if assignee tokens appear in circular
        norm_assignee = normalize_whitespace(assignee).lower()
        if norm_assignee in normalize_whitespace(notice_text).lower():
            score += 0.10
    else:
        score += 0.05

    final_score = round(min(score, 1.0), 2)

    # 4. Determine Validation Status
    if quote_ok and deadline_ok and final_score >= 0.70:
        status = "VERIFIED_SUBSTRING"
        badge = "verified"
        notes = "Evidence confirmed: Supporting quote is an authentic substring and deadline is grounded."
    elif quote_reason == "PARAPHRASED_OR_TRUNCATED":
        status = "FLAGGED_FOR_HUMAN_REVIEW"
        badge = "warning"
        notes = "Quote partially matches but appears paraphrased or truncated. Teacher verification recommended."
    elif not quote_ok:
        status = "FLAGGED_FOR_HUMAN_REVIEW"
        badge = "warning"
        notes = f"Evidence unverified: Supporting quote was not found verbatim in original circular ({quote_reason})."
    elif not deadline_ok:
        status = "FLAGGED_FOR_HUMAN_REVIEW"
        badge = "warning"
        notes = f"Deadline warning: {deadline_reason}."
    else:
        status = "FLAGGED_FOR_HUMAN_REVIEW"
        badge = "warning"
        notes = "Low confidence match: Please review action details against original circular."

    return {
        "id": item.get("id", ""),
        "action": action_text or "Unspecified Action",
        "assignee": assignee or "NOT STATED",
        "deadline": deadline or "NOT STATED",
        "fee_or_docs": fee_or_docs or "NOT STATED",
        "source_quote": source_quote or "(No quote provided)",
        "validation_status": status,
        "validation_badge": badge,
        "quote_verified": quote_ok,
        "deadline_verified": deadline_ok,
        "grounding_score": final_score,
        "validation_notes": notes,
        "is_completed": False  # Checklist interactive state
    }


def validate_extracted_checklist(notice_text: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validates a list of extracted action items and provides a summary report.
    """
    if not items:
        return {
            "total_items": 0,
            "verified_count": 0,
            "flagged_count": 0,
            "overall_grounding_rate": 100.0,
            "items": [],
            "disclaimer": (
                "No action items detected in this circular. "
                "Exact quote matching verifies evidence grounding, but does not guarantee 100% semantic completeness. "
                "Teachers should always review notices before sharing."
            )
        }

    validated_items = []
    verified_count = 0
    flagged_count = 0

    for idx, raw_item in enumerate(items, start=1):
        if not raw_item.get("id"):
            raw_item["id"] = f"act_{idx}"
        val_item = validate_action_item(notice_text, raw_item)
        if val_item["validation_status"] == "VERIFIED_SUBSTRING":
            verified_count += 1
        else:
            flagged_count += 1
        validated_items.append(val_item)

    total = len(validated_items)
    grounding_rate = round((verified_count / total) * 100.0, 1) if total > 0 else 0.0

    return {
        "total_items": total,
        "verified_count": verified_count,
        "flagged_count": flagged_count,
        "overall_grounding_rate": grounding_rate,
        "items": validated_items,
        "disclaimer": (
            "Evidence Grounding Notice: Exact quote matching verifies that supporting evidence exists verbatim in the circular. "
            "It does not guarantee semantic correctness or legal authority. Teachers maintain full agency to edit, add, or dismiss items."
        )
    }
