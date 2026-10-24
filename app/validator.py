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
    Validates that a stated deadline is grounded in the RELEVANT supporting quote.
    A deadline cannot merely appear somewhere else in the document; it must be supported
    by the specific action clause/quote.
    
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

    # Contradiction & Ambiguity Check: Flag if circular has conflicting timing
    if detect_contradictions(norm_quote) or detect_contradictions(norm_notice):
        return False, "CONTRADICTORY_TIMING_REQUIRES_REVIEW"

    clean_dl = re.sub(r"[^\w\s]", "", stated_deadline.lower()).strip()
    clean_quote = re.sub(r"[^\w\s]", "", norm_quote)
    clean_notice = re.sub(r"[^\w\s]", "", norm_notice)

    if is_not_stated:
        # Check if the supporting quote itself has an obvious deadline trigger that was missed
        deadline_patterns = [
            r"\bby\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
            r"\bbefore\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)",
            r"\bby\s+[a-z]+\s+\d{1,2}",
            r"\bআগামী\s+\d{1,2}\s+(?:জানুয়ারি|ফেব্রুয়ারি|মার্চ|এপ্রিল|মে|জুন|জুলাই|আগস্ট|সেপ্টেম্বর|অক্টোবর|নভেম্বর|ডিসেম্বর)",
            r"\bতারিখের\s+মধ্যে\b"
        ]
        for pat in deadline_patterns:
            if re.search(pat, norm_quote, re.IGNORECASE):
                return False, "MISSED_DEADLINE_IN_QUOTE"
        return True, "CORRECTLY_MARKED_NOT_STATED"

    dl_tokens = clean_dl.split()
    if not dl_tokens:
        return False, "EMPTY_DEADLINE_TOKENS"

    # 1. Historical Date Trap Check: If deadline matches founding or anniversary dates
    founding_indicators = ["founding", "founded", "established", "independence", "historic", "golden jubilee"]
    for ind in founding_indicators:
        if ind in norm_notice:
            pat = rf"{ind}[^.]*?{re.escape(clean_dl)}"
            if re.search(pat, norm_notice, re.IGNORECASE):
                return False, "UNRELATED_HISTORICAL_DATE_TRAP"

    # 2. STRICT SUPPORTING QUOTE GROUNDING: Verify deadline tokens appear IN THIS ACTION'S QUOTE
    quote_tokens_found = [tok for tok in dl_tokens if tok in clean_quote]
    quote_token_ratio = len(quote_tokens_found) / len(dl_tokens)

    if quote_token_ratio >= 0.5:
        return True, "DEADLINE_GROUNDED_IN_QUOTE"

    # 3. Check if deadline exists in the notice overall, but NOT in this supporting quote
    notice_tokens_found = [tok for tok in dl_tokens if tok in clean_notice]
    notice_token_ratio = len(notice_tokens_found) / len(dl_tokens)

    if notice_token_ratio >= 0.5:
        return False, "DEADLINE_NOT_IN_SUPPORTING_QUOTE"

    # 4. Hallucinated deadline (not in circular at all)
    return False, "HALLUCINATED_DEADLINE_NOT_IN_CIRCULAR"


def detect_contradictions(text_segment: str) -> bool:
    """Detects mutually contradictory or conflicting timing patterns within a text segment."""
    if not text_segment:
        return False
    lower = text_segment.lower()
    
    # 1. Direct contradiction / revision markers
    direct_markers = [
        "revision without notice",
        "subject to change without notice",
        "subject to revision",
        "conflicting deadline",
        "conflicting schedule"
    ]
    if any(m in lower for m in direct_markers):
        return True

    # 2. Contrasting conjunctions alongside distinct time mentions
    contrast_markers = ["however", "contrary", "instead", "tentative", "alternatively"]
    has_contrast = any(c in lower for c in contrast_markers)

    # Distinct clock times: e.g. "10:00 am" vs "5:00 pm"
    time_matches = set(re.findall(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", lower))
    if len(time_matches) >= 2 and has_contrast:
        return True

    # Distinct calendar dates with contrast
    date_matches = set(re.findall(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}\b", lower))
    if len(date_matches) >= 2 and has_contrast:
        return True

    return False


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
    is_contradictory = (
        detect_contradictions(source_quote) or
        detect_contradictions(action_text) or
        detect_contradictions(notice_text) or
        deadline_category == "CONTRADICTORY_TIMING_REQUIRES_REVIEW"
    )

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
        if deadline_category == "DEADLINE_NOT_IN_SUPPORTING_QUOTE":
            badge_text = "⚠️ Date Mismatch (Not in Quote)"
            notes = "The extracted date appears elsewhere in the circular, but is NOT supported by this action's evidence quote."
        elif deadline_category == "UNRELATED_HISTORICAL_DATE_TRAP":
            badge_text = "⚠️ Historical Date Trap"
            notes = "The extracted deadline matched a historical founding or anniversary date."
        elif deadline_category == "MISSED_DEADLINE_IN_QUOTE":
            badge_text = "⚠️ Date Missed in Quote"
            notes = "The supporting quote contains an explicit date trigger, but deadline was marked NOT STATED."
        else:
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
