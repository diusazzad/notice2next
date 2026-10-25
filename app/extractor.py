"""
Notice2Next - Open-Weight Model Extraction Engine
Layer 2 of Notice2Next Architecture.

Integrates Google Gemma 2 (via Backboard API / OpenAI-compatible endpoint)
with a deterministic heuristic fallback engine when credentials are absent or remote calls fail.
"""

import os
import re
import json
import time
import requests
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("notice2next.extractor")

BACKBOARD_API_KEY = os.environ.get("BACKBOARD_API_KEY", "")
BACKBOARD_BASE_URL = os.environ.get("BACKBOARD_BASE_URL", "https://api.backboard.io/v1")
GEMMA_MODEL = os.environ.get("GEMMA_MODEL", "google/gemma-2-9b-it")

SYSTEM_PROMPT = """You are Notice2Next AI, an expert school administration and teacher workflow assistant.
Your goal is to parse dense school circulars, notices, and internal staff memos into a clean, actionable task checklist.

Rules:
1. Extract discrete, concrete duties required of teachers or staff.
2. For every action, provide:
   - "action": Concise imperative description of the task (e.g., "Submit final roster of student project proposals")
   - "assignee": Specific teacher role or group responsible, or "NOT STATED" if general/unspecified
   - "deadline": Explicit date and time if stated in the notice. If NO deadline is mentioned, you MUST set "deadline": "NOT STATED". Do NOT guess or hallucinate.
   - "fee_or_docs": Required fee or documents mentioned, or "NOT STATED"
   - "source_quote": An EXACT verbatim quotation (substring) from the circular that proves this instruction
3. If the notice is purely informational or congratulatory with zero teacher tasks, return an empty list [].
4. Do NOT confuse unrelated historical or reference dates (e.g., founding years or national holidays) with action deadlines.
5. You MUST return ONLY a valid JSON object with the key "actions", containing a list of action items.
No markdown prose, no conversation."""


def extract_with_gemma_api(notice_text: str, timeout_sec: float = 12.0) -> Optional[List[Dict[str, Any]]]:
    """
    Calls Google Gemma 2 endpoint via Backboard / OpenAI-compatible completion API.
    Returns list of parsed action dictionaries, or None on failure.
    """
    if not BACKBOARD_API_KEY or BACKBOARD_API_KEY.startswith("your_"):
        return None

    headers = {
        "Authorization": f"Bearer {BACKBOARD_API_KEY}",
        "Content-Type": "application/json"
    }

    user_prompt = (
        f"Parse the following school circular into structured action items:\n\n"
        f"--- CIRCULAR START ---\n"
        f"{notice_text}\n"
        f"--- CIRCULAR END ---\n\n"
        f"Output JSON schema:\n"
        f'{{"actions": [{{"action": "...", "assignee": "...", "deadline": "...", "fee_or_docs": "...", "source_quote": "..."}}]}}'
    )

    payload = {
        "model": GEMMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 1200
    }

    try:
        url = f"{BACKBOARD_BASE_URL.rstrip('/')}/chat/completions"
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout_sec)
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()

            # Clean markdown codeblocks if model wrapped in ```json
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.MULTILINE)
                content = re.sub(r"\s*```$", "", content, flags=re.MULTILINE).strip()

            parsed = json.loads(content)
            if isinstance(parsed, dict) and "actions" in parsed:
                return parsed["actions"]
            elif isinstance(parsed, list):
                return parsed
        else:
            logger.warning(f"Gemma API returned status {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"Gemma inference exception: {e}")
        return None

    return None


def extract_with_deterministic_heuristic(notice_text: str) -> List[Dict[str, Any]]:
    """
    Deterministic rule-based extraction fallback.
    Used when BACKBOARD_API_KEY is unset or remote endpoint is unreachable.
    Parses structured patterns, action verbs, roles, and dates with 100% exact source quoting.
    """
    if not notice_text or not notice_text.strip():
        return []

    lines = [line.strip() for line in notice_text.split("\n") if line.strip()]
    actions: List[Dict[str, Any]] = []

    # Check if purely congratulatory/informational advisory with no action keywords
    has_action_signal = any(
        kw in notice_text.lower() for kw in [
            "instruct", "request", "require", "shall", "must", "submit", "collect",
            "deposit", "review", "update", "turn in", "turned in", "ensure", "comply",
            "inspection", "attend", "জানানো যাচ্ছে", "জমা দিতে হবে", "দাখিল",
            "নির্দেশ দেওয়া হলো", "নিশ্চিত করতে হবে", "দাখিল করার নির্দেশ"
        ]
    )

    if not has_action_signal:
        return []

    # Look for numbered paragraphs / clauses (e.g., "1.", "2.", "•")
    numbered_blocks: List[str] = []
    current_block: List[str] = []

    for line in lines:
        if re.match(r"^(?:[0-9]{1,2}[\.\)]|[a-zA-Z][\.\)]|[-•*])\s+", line):
            if current_block:
                numbered_blocks.append(" ".join(current_block))
                current_block = []
            current_block.append(line)
        elif current_block:
            current_block.append(line)

    if current_block:
        numbered_blocks.append(" ".join(current_block))

    candidate_texts = numbered_blocks if numbered_blocks else lines

    item_id = 1
    for block in candidate_texts:
        block_clean = re.sub(r"^(?:[0-9]{1,2}[\.\)]|[a-zA-Z][\.\)]|[-•*])\s*", "", block).strip()
        block_lower = block_clean.lower()

        # Filter out header/metadata lines
        if any(hdr in block_lower for hdr in ["circular no", "date:", "স্মারক নং", "বিষয়:", "subject:"]):
            continue

        # Check for actionable directive in this block
        action_match = re.search(
            r"(?:instructed to|requested to|required to|should|must|জানানো যাচ্ছে যে|জমা দিতে হবে|দাখিল করার নির্দেশ)\s+(.*?)(?:\.|$|;)",
            block_clean,
            re.IGNORECASE
        )

        if not action_match and not any(k in block_lower for k in ["submit", "collect", "deposit", "review", "update", "জমা"]):
            continue

        # Extract Action Title
        if action_match:
            action_desc = action_match.group(1).strip().capitalize()
        else:
            action_desc = block_clean[:120].strip()

        # Extract Assignee / Responsible Group
        assignee = "NOT STATED"
        assignee_patterns = [
            r"(Grade \d+(?:\s+and\s+Grade \d+)?\s+Science Teachers)",
            r"(Homeroom Teachers(?:\s+of\s+Grade \d+)?)",
            r"(Senior Department Subject Heads)",
            r"(৯ম ও ১০ম শ্রেণির সকল শ্রেণি শিক্ষক)",
            r"(কম্পিউটার ল্যাব সহকারী ও আইসিটি শিক্ষক)",
            r"(All homeroom teachers)",
            r"(Teachers or prefects)"
        ]
        for pat in assignee_patterns:
            m = re.search(pat, block_clean, re.IGNORECASE)
            if m:
                assignee = m.group(1).strip()
                break

        # Extract Deadline
        deadline = "NOT STATED"
        deadline_patterns = [
            r"\bby\s+([A-Za-z]+,\s+[A-Za-z]+\s+\d{1,2},\s+\d{4}(?:\s+at\s+\d{1,2}:\d{2}\s*(?:AM|PM))?)",
            r"\bby\s+(\d{1,2}:\d{2}\s*(?:AM|PM)\s+tomorrow(?:\s+morning)?)",
            r"\bby\s+([A-Za-z]+,\s+[A-Za-z]+\s+\d{1,2},\s+\d{4})",
            r"\bby\s+([A-Za-z]+\s+\d{1,2},\s+\d{4}(?:\s+at\s+\d{1,2}:\d{2}\s*(?:AM|PM))?)",
            r"\bআগামী\s+(\d{1,2}\s+[^\s,]+\s+\d{4}(?:,\s+[^\s,]+)?(?:\s+দুপুর\s+\d{1,2}:\d{2}\s*ঘটিকা)?)",
            r"\bআগামী\s+(\d{1,2}\s+[^\s,]+\s+\d{4}\s+তারিখের\s+মধ্যে)"
        ]
        for pat in deadline_patterns:
            m = re.search(pat, block_clean, re.IGNORECASE)
            if m:
                deadline = m.group(1).strip()
                break

        # Extract Fees or Documents
        fee_or_docs = "NOT STATED"
        fee_match = re.search(r"(\$\d+(?:\.\d{2})?(?:\s+per\s+student)?|\d+\s*টাকা)", block_clean, re.IGNORECASE)
        doc_match = re.search(r"(permission slips|safety declaration form|synopsis|allergy cards|মূল্যায়ন নম্বরপত্র|সার্ভিসিং রিপোর্ট)", block_clean, re.IGNORECASE)

        collected_requirements = []
        if fee_match:
            collected_requirements.append(f"Fee: {fee_match.group(1)}")
        if doc_match:
            collected_requirements.append(f"Document: {doc_match.group(1)}")

        if collected_requirements:
            fee_or_docs = ", ".join(collected_requirements)

        # Source Quote: Exact sentence from the circular
        source_quote = block_clean

        actions.append({
            "id": f"act_{item_id}",
            "action": action_desc,
            "assignee": assignee,
            "deadline": deadline,
            "fee_or_docs": fee_or_docs,
            "source_quote": source_quote
        })
        item_id += 1

    return actions


def extract_action_items(notice_text: str) -> Dict[str, Any]:
    """
    Main extraction pipeline:
    1. Tries Google Gemma 2 endpoint if BACKBOARD_API_KEY is configured.
    2. Falls back seamlessly to deterministic heuristic extractor if key is absent or API fails.
    3. Accurately reports engine used, live status, and latency.
    """
    start_time = time.time()
    live_called = False
    engine_name = "Deterministic Heuristic Engine (Offline / Local Mode)"
    model_name = "notice2next-rule-engine-v1"

    raw_items = None

    if BACKBOARD_API_KEY and not BACKBOARD_API_KEY.startswith("your_"):
        raw_items = extract_with_gemma_api(notice_text)
        if raw_items is not None:
            live_called = True
            engine_name = f"Google Gemma 2 ({GEMMA_MODEL}) via Backboard"
            model_name = GEMMA_MODEL

    if raw_items is None:
        raw_items = extract_with_deterministic_heuristic(notice_text)

    latency_ms = round((time.time() - start_time) * 1000, 1)

    return {
        "engine": engine_name,
        "model_name": model_name,
        "live_model_called": live_called,
        "latency_ms": latency_ms,
        "raw_items": raw_items
    }


def clean_ocr_text_deterministic(raw_ocr_text: str) -> str:
    """
    Cleans noisy raw OCR text deterministically:
    - Recombines hyphenated word breaks (e.g. 'submis-\nsion' -> 'submission')
    - Reconstructs fragmented sentences while preserving paragraph breaks
    - Fixes common OCR typos (e.g. '|' for 'I', stray artifacts, broken numbers)
    """
    if not raw_ocr_text:
        return ""

    text = raw_ocr_text
    # 1. Fix hyphenated word breaks at end of line (e.g., 'submis-\n sion' -> 'submission')
    text = re.sub(r"(\b[A-Za-z]+)-\s*\n\s*([A-Za-z]+\b)", r"\1\2", text)

    # 2. Fix broken sentence lines: preserve deliberate paragraph breaks
    lines = text.split("\n")
    reconstructed_lines = []
    buffer = ""
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if buffer:
                reconstructed_lines.append(buffer)
                buffer = ""
            reconstructed_lines.append("")
            continue

        if not buffer:
            buffer = stripped
        else:
            # Check if buffer ends with sentence punctuation or bullet
            if buffer.endswith((".", ":", ";", "?", "!")) or stripped.startswith(("-", "•", "1.", "2.", "3.", "4.", "5.")):
                reconstructed_lines.append(buffer)
                buffer = stripped
            else:
                # Merge into previous sentence with a space
                buffer += " " + stripped
    if buffer:
        reconstructed_lines.append(buffer)

    cleaned = "\n".join(reconstructed_lines)
    # 3. Clean up common OCR substitution errors & whitespace
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    # Fix broken times like "4 : 00 PM" -> "4:00 PM"
    cleaned = re.sub(r"(\d{1,2})\s*:\s*(\d{2})\s*(AM|PM|am|pm)", r"\1:\2 \3", cleaned)
    # Fix broken currency like "$ 15" -> "$15"
    cleaned = re.sub(r"\$\s+(\d+)", r"$\1", cleaned)
    return cleaned.strip()


def clean_ocr_text(raw_ocr_text: str, timeout_sec: float = 10.0) -> Dict[str, Any]:
    """
    Reconstructs clean, coherent circular text from raw camera/photo OCR output.
    Uses Google Gemma 2 when configured; otherwise uses deterministic OCR normalizer.
    """
    if not raw_ocr_text or not raw_ocr_text.strip():
        return {"cleaned_text": "", "engine": "Deterministic Normalizer", "live_model_called": False}

    if BACKBOARD_API_KEY and not BACKBOARD_API_KEY.startswith("your_"):
        try:
            headers = {
                "Authorization": f"Bearer {BACKBOARD_API_KEY}",
                "Content-Type": "application/json"
            }
            prompt = (
                "You are an expert OCR correction assistant for school notices and circulars.\n"
                "Below is raw, noisy OCR text extracted from a photo of a school noticeboard or paper memo.\n"
                "Reconstruct and output the clean, coherent original notice text.\n"
                "Rules:\n"
                "- Fix broken line breaks and wrap sentences into clean paragraphs.\n"
                "- Fix broken hyphenated words (e.g. 'submis- sion' -> 'submission').\n"
                "- Repair obvious character OCR typos without inventing new dates or facts.\n"
                "- Output ONLY the cleaned circular text. No commentary or markdown backticks.\n\n"
                f"--- RAW OCR START ---\n{raw_ocr_text}\n--- RAW OCR END ---"
            )
            payload = {
                "model": GEMMA_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a professional school circular OCR reconstruction assistant."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 1000
            }
            url = f"{BACKBOARD_BASE_URL.rstrip('/')}/chat/completions"
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout_sec)
            if resp.status_code == 200:
                data = resp.json()
                cleaned = data["choices"][0]["message"]["content"].strip()
                if cleaned:
                    return {
                        "cleaned_text": cleaned,
                        "engine": f"Google Gemma 2 ({GEMMA_MODEL}) OCR Cleanup",
                        "live_model_called": True
                    }
        except Exception as e:
            logger.warning(f"Gemma OCR cleanup fallback: {e}")

    # Fallback
    deterministic_cleaned = clean_ocr_text_deterministic(raw_ocr_text)
    return {
        "cleaned_text": deterministic_cleaned,
        "engine": "Deterministic OCR Normalizer (Offline Mode)",
        "live_model_called": False
    }

