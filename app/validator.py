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
from typing import Dict, Any, List, Tuple, Set


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


def extract_normalized_times(text: str) -> List[str]:
    """Extracts and normalizes clock times (e.g. '4:00 PM' -> '4:00pm', '12:00 PM' -> '12:00pm', 'দুপুর ২:০০' -> '২:০০')."""
    if not text:
        return []
    lower = text.lower()
    times = []
    
    # 1. 12-hour AM/PM times: e.g. 4:00 pm, 4:00pm, 4 pm, 12:00 pm
    ampm_matches = re.finditer(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", lower)
    for m in ampm_matches:
        hr = int(m.group(1))
        mn = m.group(2) if m.group(2) else "00"
        period = m.group(3)
        times.append(f"{hr}:{mn}{period}")
        
    # 2. 24-hour / colon times: e.g. 14:00, 16:30
    colon_matches = re.finditer(r"\b(\d{1,2}):(\d{2})\b", lower)
    for m in colon_matches:
        hr = int(m.group(1))
        mn = m.group(2)
        times.append(f"{hr}:{mn}")

    # 3. Bangla clock times: e.g. ২:০০ ঘটিকা
    bn_matches = re.finditer(r"([০-৯]{1,2}:[০-৯]{2})", lower)
    for m in bn_matches:
        times.append(m.group(1))

    return times


def parse_date_components(text: str) -> Dict[str, Any]:
    """
    Parses date components explicitly into year, month, day, weekday, and times.
    Separates calendar day of month from clock time hours so that
    'October 3, 2026 at 3:00 PM' vs 'October 30, 2026 at 3:00 PM' are strictly distinguished.
    """
    if not text:
        return {"year": None, "month": None, "day": None, "weekday": None, "times": []}

    lower = text.lower()
    times = extract_normalized_times(text)

    # Clean clock times out so digits don't get confused with day of month
    cleaned = lower
    cleaned = re.sub(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", " ", cleaned)
    cleaned = re.sub(r"\b\d{1,2}:\d{2}\b", " ", cleaned)
    cleaned = re.sub(r"(?:দুপুর|সকাল|বিকাল|সন্ধ্যা|রাত)?\s*[০-৯]{1,2}:[০-৯]{2}\s*(?:ঘটিকা)?", " ", cleaned)

    # Year (4 digits)
    year = None
    y_match = re.search(r"\b(19\d{2}|20\d{2})\b", cleaned)
    if y_match:
        year = y_match.group(1)
        cleaned = cleaned[:y_match.start()] + " " + cleaned[y_match.end():]
    else:
        y_bn = re.search(r"\b(১৯[০-৯]{2}|২০[০-৯]{2})\b", cleaned)
        if y_bn:
            year = y_bn.group(1)
            cleaned = cleaned[:y_bn.start()] + " " + cleaned[y_bn.end():]

    en_months = [
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december"
    ]
    en_short = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    bn_months = [
        "জানুয়ারি", "ফেব্রুয়ারি", "মার্চ", "এপ্রিল", "মে", "জুন",
        "জুলাই", "আগস্ট", "সেপ্টেম্বর", "অক্টোবর", "নভেম্বর", "ডিসেম্বর"
    ]

    month = None
    for m in en_months:
        if re.search(rf"\b{m}\b", cleaned):
            month = m
            break
    if not month:
        for m in bn_months:
            if m in cleaned:
                month = m
                break
    if not month:
        for m in en_short:
            if re.search(rf"\b{m}\b", cleaned):
                month = m
                break

    weekday = None
    weekdays = [
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        "রবিবার", "সোমবার", "মঙ্গলবার", "বুধবার", "বৃহস্পতিবার", "শুক্রবার", "শনিবার"
    ]
    for w in weekdays:
        if w in cleaned:
            weekday = w
            break

    day = None
    if month:
        m1 = re.search(rf"\b{re.escape(month)}\s+([0-9]{{1,2}}|[০-৯]{{1,2}})\b", cleaned)
        if m1:
            day = m1.group(1).lstrip("0") or "0"
        else:
            m2 = re.search(rf"([0-9]{{1,2}}|[০-৯]{{1,2}})\s+{re.escape(month)}", cleaned)
            if m2:
                day = m2.group(1).lstrip("0") or "0"
    if not day:
        day_match = re.search(r"\b([0-9]{1,2}|[০-৯]{1,2})\b", cleaned)
        if day_match:
            d_val = day_match.group(1)
            try:
                if int(d_val) <= 31:
                    day = d_val.lstrip("0") or "0"
            except ValueError:
                day = d_val

    return {"year": year, "month": month, "day": day, "weekday": weekday, "times": times}


def verify_fee_or_docs(quote: str, fee_or_docs: str) -> Tuple[bool, str]:
    """
    Validates that any extracted fee or required document is grounded in the supporting quote.
    If model invents a fee (e.g. '$15') or document not in the quote, fails closed for review.
    
    Returns: (is_grounded, category)
    """
    if not fee_or_docs or fee_or_docs.strip().upper() in [
        "NOT STATED", "NONE", "N/A", "NO FEE", "UNSPECIFIED", "NO DOCUMENTS", ""
    ]:
        return True, "FEE_DOCS_NOT_STATED"

    norm_quote = normalize_whitespace(quote).lower() if quote else ""
    if not norm_quote:
        return False, "FEE_DOCS_QUOTE_EMPTY"

    clean_quote = re.sub(r"[^\w\s\$৳]", "", norm_quote)
    clean_val = re.sub(r"[^\w\s\$৳]", "", fee_or_docs.lower())

    # 1. Verify Monetary Fees
    # Extract monetary patterns e.g. $15, 15 dollars, 15 টাকা, 15 tk
    fee_patterns = re.findall(r"(\$\s*\d+(?:\.\d{2})?|\d+\s*(?:dollars?|টাকা|tk))", clean_val)
    if fee_patterns:
        # Check if supporting quote explicitly disclaims any fee (e.g. "no fee is required")
        no_fee_disclaimer = bool(
            re.search(
                r"\b(?:no\s+fee|no\s+fees|no\s+charge|no\s+charges|free\s+of\s+charge|without\s+(?:any\s+)?fee)\b",
                norm_quote,
                re.IGNORECASE,
            )
        )

        for fee in fee_patterns:
            num_match = re.search(r"\d+(?:\.\d{2})?", fee)
            if not num_match:
                continue
            num = num_match.group(0)

            # Strict numeric boundary: amount must not be a prefix/suffix of a larger number (e.g. 15 vs 150)
            num_boundary = rf"(?<!\d){re.escape(num)}(?!\d)"

            # If quote explicitly states no fee is required, candidate claiming a fee is ungrounded / requires human review
            if no_fee_disclaimer:
                return False, "FEE_NOT_IN_SUPPORTING_QUOTE"

            has_fee_evidence = False

            # Check explicit currency symbol match with strict numeric boundary: e.g. $15, ৳15
            if "$" in fee:
                if re.search(rf"\$\s*{num_boundary}", norm_quote):
                    has_fee_evidence = True
            elif "৳" in fee or "tk" in fee:
                if re.search(rf"(?:৳|\btk\b)\s*{num_boundary}|{num_boundary}\s*(?:৳|\btk\b)", norm_quote):
                    has_fee_evidence = True
            elif "dollar" in fee:
                if re.search(rf"{num_boundary}\s*dollars?|\$\s*{num_boundary}", norm_quote):
                    has_fee_evidence = True
            elif "টাকা" in fee:
                if re.search(rf"{num_boundary}\s*টাকা|৳\s*{num_boundary}", norm_quote):
                    has_fee_evidence = True

            # If not matched directly by symbol, check if the bounded number appears adjacent to monetary context
            if not has_fee_evidence:
                fee_ctx = rf"(?:\$|৳|\btk\b|\bdollars?\b|\bfee\b|\bfees\b|\bcost\b|\bcharge\b|\bcharges\b|\bটাকা\b)\s*(?:of\s+)?{num_boundary}|{num_boundary}\s*(?:\$|৳|\btk\b|\bdollars?\b|\bটাকা\b|\btk\b|\bfee\b|\bfees\b)"
                if re.search(fee_ctx, norm_quote, re.IGNORECASE):
                    has_fee_evidence = True

            if not has_fee_evidence:
                return False, "FEE_NOT_IN_SUPPORTING_QUOTE"

    # 2. Verify Key Document Requirements
    # Note: Strip metadata labels (fee:, document:, required:) but do NOT strip 'forms?' words
    cleaned_docs = re.sub(r"\b(fee:|required:|fees:|document:|documents?:?)\s*", " ", fee_or_docs, flags=re.IGNORECASE)
    doc_words = [
        w for w in re.sub(r"[^\w\s]", "", cleaned_docs.lower()).split()
        if len(w) >= 3 and w not in ["student", "students", "teachers", "stated", "none", "each", "team", "final", "before", "with", "from", "and", "the", "for", "fee", "fees"]
    ]
    if doc_words:
        # Conservative check: Every material document term (including 'form', 'forms', 'declaration', etc.) must be supported in quote
        quote_words = set(re.findall(r"\b\w+\b", norm_quote))
        missing = [w for w in doc_words if w not in quote_words]
        if missing:
            return False, "DOCS_NOT_IN_SUPPORTING_QUOTE"

    return True, "FEE_DOCS_GROUNDED_IN_QUOTE"


def verify_deadline(notice_text: str, quote: str, stated_deadline: str) -> Tuple[bool, str]:
    """
    Validates that a stated deadline is strictly grounded in the RELEVANT supporting quote.
    Parses and compares date components (year, month, day, weekday, time) explicitly.
    Fails closed when dates/times are missing or mismatched.
    
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

    # 1. Contradiction & Ambiguity Check: Flag if circular has conflicting timing
    if detect_contradictions(norm_quote) or detect_contradictions(norm_notice):
        return False, "CONTRADICTORY_TIMING_REQUIRES_REVIEW"

    # 2. Handling NOT STATED: Fail if quote contains an explicit deadline trigger
    if is_not_stated:
        deadline_patterns = [
            r"\bby\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
            r"\bbefore\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)",
            r"\bby\s+[a-z]+\s+\d{1,2}",
            r"\bআগামী\s+[০-৯0-9]{1,2}\s+(?:জানুয়ারি|ফেব্রুয়ারি|মার্চ|এপ্রিল|মে|জুন|জুলাই|আগস্ট|সেপ্টেম্বর|অক্টোবর|নভেম্বর|ডিসেম্বর)",
            r"\bতারিখের\s+মধ্যে\b"
        ]
        for pat in deadline_patterns:
            if re.search(pat, norm_quote, re.IGNORECASE):
                return False, "MISSED_DEADLINE_IN_QUOTE"
        return True, "CORRECTLY_MARKED_NOT_STATED"

    clean_dl = re.sub(r"[^\w\s]", "", stated_deadline.lower()).strip()
    if not clean_dl:
        return False, "EMPTY_DEADLINE_TOKENS"

    # 3. Historical Date Trap Check: If deadline matches founding or anniversary dates
    founding_indicators = ["founding", "founded", "established", "independence", "historic", "golden jubilee"]
    clean_dl_tokens = [re.escape(w) for w in re.sub(r"[^\w\s]", " ", stated_deadline.lower()).split()]
    if clean_dl_tokens:
        dl_pat = r"[\s,\.-]+".join(clean_dl_tokens)
        for ind in founding_indicators:
            if ind in norm_notice:
                pat = rf"{ind}[^.]*?{dl_pat}"
                if re.search(pat, norm_notice, re.IGNORECASE):
                    return False, "UNRELATED_HISTORICAL_DATE_TRAP"

    dl_comp = parse_date_components(stated_deadline)
    quote_times = extract_normalized_times(quote)

    # 4. Strict Clock Time Verification:
    # If the candidate specified a time, every stated time MUST exist in quote
    if dl_comp["times"]:
        for t in dl_comp["times"]:
            if t not in quote_times:
                return False, "DEADLINE_TIME_MISMATCH_IN_QUOTE"

    # 5. Strict Semantic Date Verification (Year, Month, Day, Weekday):
    has_candidate_date = dl_comp["month"] is not None or dl_comp["day"] is not None or dl_comp["year"] is not None
    
    quote_clean_no_time = re.sub(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", " ", norm_quote, flags=re.IGNORECASE)
    quote_clean_no_time = re.sub(r"\b\d{1,2}:\d{2}\b", " ", quote_clean_no_time)
    quote_clean_no_time = re.sub(r"[০-৯]{1,2}:[০-৯]{2}", " ", quote_clean_no_time)
    
    quote_has_year = bool(re.search(r"\b(19\d{2}|20\d{2}|১৯[০-৯]{2}|২০[০-৯]{2})\b", quote_clean_no_time))
    quote_has_month = any(
        re.search(rf"\b{m}\b", quote_clean_no_time, re.IGNORECASE)
        for m in [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
            "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
            "জানুয়ারি", "ফেব্রুয়ারি", "মার্চ", "এপ্রিল", "মে", "জুন",
            "জুলাই", "আগস্ট", "সেপ্টেম্বর", "অক্টোবর", "নভেম্বর", "ডিসেম্বর"
        ]
    )
    quote_has_day = bool(re.search(r"\b([0-9]{1,2}|[০-৯]{1,2})\b", quote_clean_no_time))
    has_quote_date = quote_has_year or quote_has_month or quote_has_day

    if has_candidate_date and not has_quote_date:
        # Candidate extracted a date, but the supporting quote contains no date
        clean_notice = re.sub(r"[^\w\s]", "", norm_notice)
        if clean_dl in clean_notice or (dl_comp["month"] and dl_comp["month"] in clean_notice):
            return False, "DEADLINE_NOT_IN_SUPPORTING_QUOTE"
        return False, "HALLUCINATED_DEADLINE_NOT_IN_CIRCULAR"

    # Year: Candidate year MUST exist as a distinct word in quote
    if dl_comp["year"]:
        if not re.search(r"\b" + re.escape(dl_comp["year"]) + r"\b", norm_quote):
            return False, "DEADLINE_DATE_COMPONENT_MISMATCH"

    # Month: Candidate month MUST exist in quote
    if dl_comp["month"]:
        if not re.search(r"\b" + re.escape(dl_comp["month"]) + r"\b", norm_quote, re.IGNORECASE):
            return False, "DEADLINE_DATE_COMPONENT_MISMATCH"

    # Weekday: Candidate weekday MUST exist in quote
    if dl_comp["weekday"]:
        if not re.search(r"\b" + re.escape(dl_comp["weekday"]) + r"\b", norm_quote, re.IGNORECASE):
            return False, "DEADLINE_DATE_COMPONENT_MISMATCH"

    # Day: Candidate day MUST be grounded as a distinct day token (not a clock time digit)
    if dl_comp["day"]:
        d_val = dl_comp["day"]
        m_val = dl_comp["month"]
        day_matched = False
        if m_val:
            pat1 = r"\b" + re.escape(m_val) + r"\s+0?" + re.escape(d_val) + r"\b"
            pat2 = r"\b0?" + re.escape(d_val) + r"\s+" + re.escape(m_val) + r"\b"
            if re.search(pat1, norm_quote, re.IGNORECASE) or re.search(pat2, norm_quote, re.IGNORECASE):
                day_matched = True
        if not day_matched:
            if re.search(r"\b0?" + re.escape(d_val) + r"(?:st|nd|rd|th)?\b", quote_clean_no_time, re.IGNORECASE):
                day_matched = True
        if not day_matched:
            return False, "DEADLINE_DATE_COMPONENT_MISMATCH"

    # 6. Overall Content Word Grounding: Fail closed if meaningful words are missing from quote
    stop_words = {"at", "by", "before", "on", "sharp", "sharp.", "the", "of", "and", "to", "in", "দুপুর", "সকাল", "তারিখের", "মধ্যে"}
    dl_words = [w for w in clean_dl.split() if w not in stop_words]
    clean_quote = re.sub(r"[^\w\s]", "", norm_quote)
    missing_words = [w for w in dl_words if w not in clean_quote]

    if missing_words:
        clean_notice = re.sub(r"[^\w\s]", "", norm_notice)
        in_notice = [w for w in missing_words if w in clean_notice]
        if in_notice:
            return False, "DEADLINE_NOT_IN_SUPPORTING_QUOTE"
        return False, "HALLUCINATED_DEADLINE_NOT_IN_CIRCULAR"

    return True, "DEADLINE_GROUNDED_IN_QUOTE"


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

    # 3. Verify Assignee Grounding (Strictly against Supporting Quote)
    norm_notice = normalize_whitespace(notice_text).lower()
    norm_quote = normalize_whitespace(source_quote).lower() if source_quote else ""
    norm_assignee = normalize_whitespace(assignee).lower()
    assignee_tokens = [t for t in norm_assignee.split() if (len(t) > 2 or t.isdigit()) and t not in ["all", "the", "and", "for", "with"]]
    role_stop_words = {"all", "the", "and", "for", "with", "teachers", "teacher", "staff", "members"}
    distinguishing_tokens = [t for t in assignee_tokens if t not in role_stop_words]

    quote_word_tokens = set(re.findall(r"\b\w+\b", norm_quote)) if norm_quote else set()
    notice_word_tokens = set(re.findall(r"\b\w+\b", norm_notice)) if norm_notice else set()

    if assignee.upper() in ["NOT STATED", "UNSPECIFIED", "GENERAL", "ALL STAFF", ""]:
        assignee_status = "EXPLICIT_NOT_STATED"
        assignee_grounded = True
    elif norm_quote and (re.search(r"\b" + re.escape(norm_assignee) + r"\b", norm_quote) or (assignee_tokens and all(t in quote_word_tokens for t in assignee_tokens))):
        assignee_status = "ROLE_FOUND_IN_QUOTE"
        assignee_grounded = True
    elif distinguishing_tokens and not any(t in quote_word_tokens for t in distinguishing_tokens) and any(t in notice_word_tokens for t in distinguishing_tokens):
        # Distinguishing role name (e.g. 'homeroom') is in circular, but absent from this quote!
        assignee_status = "ROLE_NOT_IN_SUPPORTING_QUOTE"
        assignee_grounded = False
    elif norm_quote and assignee_tokens and any(t in quote_word_tokens for t in assignee_tokens):
        # Some tokens in quote, but specific grade or role conflicts (e.g. Grade 1 vs Grade 10)
        assignee_status = "ROLE_PARTIAL_MATCH"
        assignee_grounded = False
    elif re.search(r"\b" + re.escape(norm_assignee) + r"\b", norm_notice) or (assignee_tokens and any(t in notice_word_tokens for t in assignee_tokens)):
        # Role exists elsewhere in circular, but is absent from this action's evidence quote!
        # Multi-role confusion trap: Assignee assigned to the wrong action
        assignee_status = "ROLE_NOT_IN_SUPPORTING_QUOTE"
        assignee_grounded = False
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

    # 5. Verify Fee or Required Documents
    fee_ok, fee_category = verify_fee_or_docs(source_quote, fee_or_docs)

    # 6. Build Independent Evidence Dict
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
            "status": fee_category,
            "is_grounded": fee_ok,
            "value": fee_or_docs
        }
    }

    # 7. Overall Verification Status & Badge
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
        if deadline_category == "DEADLINE_TIME_MISMATCH_IN_QUOTE":
            badge_text = "⚠️ Time Mismatch (Not in Quote)"
            notes = "The extracted time does not match the time specified in this action's evidence quote."
        elif deadline_category in ["DEADLINE_NOT_IN_SUPPORTING_QUOTE", "DEADLINE_DATE_COMPONENT_MISMATCH"]:
            badge_text = "⚠️ Date Mismatch (Not in Quote)"
            notes = "The extracted date appears elsewhere in the circular or does not match this action's evidence quote."
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
        if assignee_status in ["ROLE_PARTIAL_MATCH", "ROLE_NOT_IN_SUPPORTING_QUOTE"]:
            badge_text = "⚠️ Role Mismatch (Review)"
            notes = f"Assigned role '{assignee}' does not match this action's evidence quote. Teacher review required to verify specific grade or role."
        else:
            badge_text = "⚠️ Role Warning"
            notes = "Assigned role could not be grounded in circular text."
    elif not fee_ok:
        status = "FLAGGED_FOR_HUMAN_REVIEW"
        badge = "warning"
        if fee_category == "FEE_NOT_IN_SUPPORTING_QUOTE":
            badge_text = "⚠️ Fee Mismatch (Review)"
            notes = "The extracted fee amount is not supported by this action's evidence quote."
        elif fee_category == "DOCS_NOT_IN_SUPPORTING_QUOTE":
            badge_text = "⚠️ Document Mismatch (Review)"
            notes = "The required document specified is not mentioned in this action's evidence quote."
        else:
            badge_text = "⚠️ Fee/Doc Warning"
            notes = f"Requirement verification issue: {fee_category}."
    else:
        # STRICT VERBATIM MATCH + GROUNDED DEADLINE + GROUNDED ROLE + GROUNDED FEE/DOCS
        status = "VERIFIED_QUOTE_GROUNDED"
        badge = "quote-verified"
        badge_text = "✓ Verbatim Quote Found"
        notes = "Supporting quote is an authentic verbatim substring, deadline and role are grounded. Review action text before proceeding."

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
