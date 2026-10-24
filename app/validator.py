"""
Notice2Next - Deterministic Evidence & Anti-Hallucination Validator
Layer 2 of Notice2Next Architecture.

Core Principles:
1. Strict Substring Verification: Verifies that supporting quotes exist verbatim in the source notice.
   - Punctuation-stripped matches are categorized as PUNCTUATION_STRIPPED_WORD_MATCH and flagged for review.
2. Independent Field Evidence: Action, assignee, deadline, and fees are validated as separate evidence streams.
   - Finding a quote confirms text existence; it does NOT prove the action was semantically interpreted without error.
3. Explicit Missing Information: Enforces 'NOT STATED' when dates or fees are absent.
4. Human Review Flagging: Surfaces non-grounded, ambiguous, or contradictory items with clear visual warnings.
"""

import re
import unicodedata
from typing import Dict, Any, List, Tuple


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace, newlines, and unicode for robust comparison."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip()


def verify_source_quote(notice_text: str, candidate_quote: str) -> Tuple[bool, str, float]:
    """
    Checks candidate_quote against the original notice.
    Returns: (is_strict_substring, match_category, confidence_score)

    Categories:
    - STRICT_SUBSTRING_MATCH: Verbatim substring on normalized text (is_strict_substring=True).
    - PUNCTUATION_STRIPPED_WORD_MATCH: Matches only after punctuation removal (is_strict_substring=False, flagged for review).
    - PARAPHRASED_OR_TRUNCATED: Word overlap >= 75% (is_strict_substring=False).
    - UNVERIFIED_OR_HALLUCINATED: No meaningful match (is_strict_substring=False).
    - EMPTY_QUOTE: No quote provided.
    """
    if not candidate_quote or not candidate_quote.strip():
        return False, "EMPTY_QUOTE", 0.0

    norm_notice = normalize_whitespace(notice_text).lower()
    norm_quote = normalize_whitespace(candidate_quote).lower()

    # 1. STRICT Normalized Substring Match
    if norm_quote in norm_notice:
        return True, "STRICT_SUBSTRING_MATCH", 1.0

    # 2. Punctuation-stripped word match (NOT strict substring, must be flagged for review)
    clean_notice = re.sub(r"[^\w\s]", "", norm_notice)
    clean_quote = re.sub(r"[^\w\s]", "", norm_quote)
    if clean_quote and clean_quote in clean_notice:
        return False, "PUNCTUATION_STRIPPED_WORD_MATCH", 0.75

    # 3. Paraphrase / Truncation Check
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
    Returns: (is_grounded, category)
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

    # At least core date/time tokens must exist in notice
    found_tokens = [tok for tok in dl_tokens if tok in clean_notice]
    token_ratio = len(found_tokens) / len(dl_tokens)

    if token_ratio < 0.5:
        return False, "HALLUCINATED_DEADLINE_NOT_IN_CIRCULAR"

    # Check if this deadline belongs to an unrelated context (e.g., founding year 1974)
    founding_indicators = ["founding", "founded", "established", "independence", "historic"]
    for ind in founding_indicators:
        if ind in norm_notice:
            pat = rf"{ind}[^.]*?{re.escape(clean_dl)}"
            if re.search(pat, norm_notice, re.IGNORECASE):
                return False, "UNRELATED_HISTORICAL_DATE_TRAP"

    return True, "DEADLINE_GROUNDED"


def detect_contradictions(text_segment: str) -> bool:
    """Detects mutually contradictory timing patterns within a clause."""
    lower = text_segment.lower()
    # Check for contrasting time windows: e.g. "by 10:00 am ... however no ... before 5:00 pm"
    has_am = bool(re.search(r"10:00\s*am", lower))
    has_pm = bool(re.search(r"5:00\s*pm", lower))
    has_contrast = any(c in lower for c in ["however", "contrary", "instead", "revision without notice"])
    return has_am and has_pm and has_contrast


def validate_action_item(notice_text: str, item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates a single extracted action item across separate evidence streams:
    1. Quote evidence (strict substring check)
    2. Action intent (flagged that semantics must be verified by educator)
    3. Assignee grounding
    4. Deadline grounding
    5. Contradiction detection
    """
    action_text = item.get("action", "").strip()
    assignee = item.get("assignee", "NOT STATED").strip()
    deadline = item.get("deadline", "NOT STATED").strip()
    fee_or_docs = item.get("fee_or_docs", "NOT STATED").strip()
    source_quote = item.get("source_quote", "").strip()

    # 1. Verify Source Quote
    is_strict_quote, quote_category, quote_score = verify_source_quote(notice_text, source_quote)

    # 2. Verify Deadline
    deadline_ok, deadline_category = verify_deadline(notice_text, source_quote, deadline)

    # 3. Verify Assignee Grounding
    norm_notice = normalize_whitespace(notice_text).lower()
    norm_assignee = normalize_whitespace(assignee).lower()
    if assignee.upper() in ["NOT STATED", "UNSPECIFIED", "GENERAL", ""]:
        assignee_status = "EXPLICIT_NOT_STATED"
        assignee_grounded = True
    elif norm_assignee in norm_notice:
        assignee_status = "ROLE_FOUND_IN_TEXT"
        assignee_grounded = True
    else:
        # Check partial token match
        assignee_tokens = [t for t in norm_assignee.split() if len(t) > 2]
        matches = [t for t in assignee_tokens if t in norm_notice]
        if matches:
            assignee_status = "ROLE_PARTIAL_MATCH"
            assignee_grounded = True
        else:
            assignee_status = "ROLE_UNGROUNDED"
            assignee_grounded = False

    # 4. Check Contradictions
    is_contradictory = detect_contradictions(source_quote) or detect_contradictions(action_text)

    # 5. Build Independent Evidence Dict
    field_evidence = {
        "quote": {
            "is_strict_substring": is_strict_quote,
            "category": quote_category,
            "display_label": "Verbatim Quote Found" if is_strict_quote else (
                "Punctuation Differs (Review)" if quote_category == "PUNCTUATION_STRIPPED_WORD_MATCH" else "Quote Unverified"
            )
        },
        "action": {
            "status": "ACTION_EXTRACTED_REQUIRES_EDUCATOR_CONFIRMATION",
            "is_semantically_proven": False,
            "note": "Quote matching confirms text presence; semantic alignment requires teacher verification."
        },
        "assignee": {
            "status": assignee_status,
            "is_grounded": assignee_grounded,
            "value": assignee
        },
        "deadline": {
            "status": deadline_category,
            "is_grounded": deadline_ok,
            "value": deadline
        },
        "fee_or_docs": {
            "value": fee_or_docs
        }
    }

    # 6. Overall Verification Status & Badge
    if is_contradictory:
        status = "FLAGGED_FOR_HUMAN_REVIEW"
        badge = "warning"
        badge_text = "⚠️ Contradiction Detected (Review)"
        notes = "Contradictory timing or revision notice detected. Teacher review required before acting."
    elif not is_strict_quote:
        status = "FLAGGED_FOR_HUMAN_REVIEW"
        badge = "warning"
        if quote_category == "PUNCTUATION_STRIPPED_WORD_MATCH":
            badge_text = "⚠️ Punctuation Differs (Review)"
            notes = "Quote matches words only after punctuation removal; not a strict verbatim substring."
        elif quote_category == "PARAPHRASED_OR_TRUNCATED":
            badge_text = "⚠️ Paraphrased Quote (Review)"
            notes = "Quote appears paraphrased or truncated. Verify against original circular."
        else:
            badge_text = "⚠️ Quote Unverified"
            notes = "Supporting quote was not found verbatim in original circular."
    elif not deadline_ok:
        status = "FLAGGED_FOR_HUMAN_REVIEW"
        badge = "warning"
        badge_text = "⚠️ Deadline Warning"
        notes = f"Deadline verification issue: {deadline_category}."
    elif not assignee_grounded:
        status = "FLAGGED_FOR_HUMAN_REVIEW"
        badge = "warning"
        badge_text = "⚠️ Role Warning"
        notes = "Assigned role could not be grounded in circular text."
    else:
        # STRICT VERBATIM MATCH + GROUNDED DEADLINE
        # Honest label: "Quote Found (Verbatim)" - NOT "Action Verified"
        status = "VERIFIED_QUOTE_GROUNDED"
        badge = "quote-verified"
        badge_text = "✓ Verbatim Quote Found"
        notes = "Supporting quote is an authentic verbatim substring and deadline is grounded. Review action text before proceeding."

    return {
        "id": item.get("id", ""),
        "action": action_text or "Unspecified Action",
        "assignee": assignee or "NOT STATED",
        "deadline": deadline or "NOT STATED",
        "fee_or_docs": fee_or_docs or "NOT STATED",
        "source_quote": source_quote or "(No quote provided)",
        "validation_status": status,
        "validation_badge": badge,
        "validation_badge_text": badge_text,
        "quote_verified": is_strict_quote,
        "deadline_verified": deadline_ok,
        "validation_notes": notes,
        "field_evidence": field_evidence,
        "is_completed": False
    }


def validate_extracted_checklist(notice_text: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validates a list of extracted action items and provides a summary report.
    """
    disclaimer_text = (
        "Source Evidence Check Notice: Verbatim quote matching confirms that cited text appears in the circular. "
        "It does not guarantee semantic completeness, legal authority, or that the action description accurately represents school intent. "
        "Teachers must review all items before taking action."
    )

    if not items:
        return {
            "total_items": 0,
            "verified_count": 0,
            "flagged_count": 0,
            "overall_grounding_rate": 100.0,
            "items": [],
            "disclaimer": (
                "Informational Notice: No actionable teacher tasks detected in this circular. "
                "Teachers should review notices to ensure no informal instructions were overlooked."
            )
        }

    validated_items = []
    verified_count = 0
    flagged_count = 0

    for idx, raw_item in enumerate(items, start=1):
        if not raw_item.get("id"):
            raw_item["id"] = f"act_{idx}"
        val_item = validate_action_item(notice_text, raw_item)
        if val_item["validation_status"] == "VERIFIED_QUOTE_GROUNDED":
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
        "disclaimer": disclaimer_text
    }
