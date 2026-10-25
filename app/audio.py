"""
Notice2Next — ElevenLabs Spoken Audio Briefing Module
Supports:
1. ElevenLabs Text-to-Speech API (when ELEVENLABS_API_KEY is configured)
2. Semantic Spoken Briefing Text Generation with Browser Web Speech API Fallback
"""

import os
import base64
from typing import List, Dict, Any
import httpx

# Default ElevenLabs Voice ID (Adam - clear, professional narrator)
DEFAULT_ELEVENLABS_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"

def generate_spoken_briefing_text(items: List[Dict[str, Any]], notice_summary: str = "") -> str:
    """Generates a concise, natural, 30-45 second spoken briefing of extracted circular duties."""
    if not items:
        return "Notice briefing: This circular contains general informational announcements. No required teacher or student actions were detected."

    total = len(items)
    sentences = [f"Official notice briefing. {total} next action {'item' if total == 1 else 'items'} detected."]

    verified_actions = [it for it in items if it.get("validation_status") == "VERIFIED_QUOTE_GROUNDED"]
    flagged_actions = [it for it in items if it.get("validation_status") != "VERIFIED_QUOTE_GROUNDED"]

    for idx, item in enumerate(items[:3], 1):
        action = item.get("action", "").rstrip(".")
        assignee = item.get("assignee", "Designated staff")
        deadline = item.get("deadline", "an unspecified date")
        fee = item.get("fee_or_docs", "")

        sentence = f"Action {idx}: {assignee} must {action.lower()}"
        if deadline and deadline != "NOT STATED":
            sentence += f", due by {deadline}"
        if fee and fee.upper() not in ["NOT STATED", "NONE", "NO FEE", ""]:
            sentence += f". Requirement: {fee}"
        sentence += "."
        sentences.append(sentence)

    if flagged_actions:
        sentences.append(f"Please note: {len(flagged_actions)} {'item requires' if len(flagged_actions) == 1 else 'items require'} human review before proceeding.")

    sentences.append("All cited evidence quotes are linked in your morning ledger.")
    return " ".join(sentences)


async def synthesize_spoken_briefing(items: List[Dict[str, Any]], notice_summary: str = "") -> Dict[str, Any]:
    """
    Synthesizes audio briefing using ElevenLabs API if key is present.
    Always returns the structured briefing text for client-side Web Speech fallback.
    """
    briefing_text = generate_spoken_briefing_text(items, notice_summary)
    api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", DEFAULT_ELEVENLABS_VOICE_ID).strip()

    if not api_key:
        return {
            "success": True,
            "briefing_text": briefing_text,
            "has_audio": False,
            "engine": "Browser Web Speech Engine (Offline Fallback)",
            "voice": "Default System Narrator"
        }

    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        }
        payload = {
            "text": briefing_text,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(url, headers=headers, json=payload)
            if res.status_code == 200:
                audio_b64 = base64.b64encode(res.content).decode("utf-8")
                return {
                    "success": True,
                    "briefing_text": briefing_text,
                    "has_audio": True,
                    "audio_base64": audio_b64,
                    "content_type": "audio/mpeg",
                    "engine": "ElevenLabs Turbo v2.5",
                    "voice_id": voice_id
                }
            else:
                return {
                    "success": True,
                    "briefing_text": briefing_text,
                    "has_audio": False,
                    "engine": f"ElevenLabs API returned {res.status_code}; using Web Speech fallback",
                    "error": res.text
                }
    except Exception as e:
        return {
            "success": True,
            "briefing_text": briefing_text,
            "has_audio": False,
            "engine": f"ElevenLabs request error: {str(e)}; using Web Speech fallback"
        }
