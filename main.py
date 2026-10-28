"""
Notice2Next - FastAPI Server Application
Turn School Circulars into Source-Backed Action Checklists.
Hacktoberfest 2026 Week 3 Official Entry.
"""

import os
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from app.extractor import extract_action_items, clean_ocr_text, BACKBOARD_API_KEY, GEMMA_MODEL
from app.validator import validate_extracted_checklist, validate_action_item
from app.samples import SAMPLE_NOTICES, get_sample_by_id, get_all_samples_metadata
from app.exporter import generate_csv, generate_markdown
from app.browser_fetcher import fetch_notice_from_url
from app.audio import synthesize_spoken_briefing

app = FastAPI(
    title="Notice2Next API",
    description="Extracts source-backed action checklists from school circulars using Google Gemma 2 and deterministic grounding.",
    version="1.0.0"
)

# Mount static assets
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# Pydantic Request Models
class ExtractRequest(BaseModel):
    text: str = Field(..., min_length=10, description="Raw school circular or memo text")
    verify_quotes: bool = Field(True, description="Enforce deterministic substring quote verification")


class ExportCSVRequest(BaseModel):
    items: List[Dict[str, Any]] = Field(..., description="List of action items to export")


class FetchURLRequest(BaseModel):
    url: str = Field(..., min_length=8, description="Public notice webpage or direct PDF URL")


class SpeakBriefingRequest(BaseModel):
    items: List[Dict[str, Any]] = Field(..., description="List of validated action items")
    summary: Optional[str] = Field("", description="Optional notice overview summary")


class CleanOCRRequest(BaseModel):
    raw_text: str = Field(..., min_length=3, description="Raw OCR scanned text from photo")


@app.get("/")
def get_index():
    """Serves the main single-page UI."""
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Notice2Next API running. Open /docs for OpenAPI documentation."}


@app.get("/health")
def health_check():
    """Service health and model readiness check for Render blueprint."""
    has_key = bool(BACKBOARD_API_KEY and not BACKBOARD_API_KEY.startswith("your_"))
    return {
        "status": "healthy",
        "service": "notice2next",
        "version": "1.0.0",
        "live_gemma_configured": has_key,
        "gemma_model": GEMMA_MODEL if has_key else "offline-deterministic-fallback",
        "environment": "production" if os.environ.get("RENDER") else "local"
    }


@app.get("/api/samples")
def get_samples():
    """Returns metadata for all 6 synthetic test circulars."""
    return {"samples": SAMPLE_NOTICES}


@app.get("/api/samples/{sample_id}")
def get_single_sample(sample_id: str):
    """Retrieve full text and metadata for a specific sample."""
    sample = get_sample_by_id(sample_id)
    return sample


@app.post("/api/extract")
def extract_notice_actions(req: ExtractRequest):
    """
    Extracts action items using Gemma 2 and runs deterministic substring validation.
    """
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Notice text cannot be empty.")

    # 1. Extraction Layer (Gemma 2 or Deterministic Fallback)
    extraction_result = extract_action_items(req.text)
    raw_items = extraction_result["raw_items"]

    # 2. Evidence Grounding & Anti-Hallucination Validation Layer
    validation_report = validate_extracted_checklist(req.text, raw_items, verify_quotes=req.verify_quotes)

    return {
        "engine": extraction_result["engine"],
        "model_name": extraction_result["model_name"],
        "live_model_called": extraction_result["live_model_called"],
        "latency_ms": extraction_result["latency_ms"],
        "summary": {
            "total_items": validation_report["total_items"],
            "verified_count": validation_report["verified_count"],
            "flagged_count": validation_report["flagged_count"],
            "grounding_rate": validation_report["overall_grounding_rate"],
            "disclaimer": validation_report["disclaimer"]
        },
        "items": validation_report["items"]
    }


@app.post("/api/export/csv")
def export_csv(req: ExportCSVRequest):
    """Exports action items into downloadable CSV format."""
    csv_content = generate_csv(req.items)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=notice2next_action_checklist.csv"}
    )


@app.post("/api/fetch-notice-url")
async def fetch_notice_url(req: FetchURLRequest):
    """
    Fetches official circular text from a public website or direct PDF URL.
    Supports Browserbase headless session when BROWSERBASE_API_KEY is configured.
    Enforces SSRF defense against private IPs.
    """
    result = await fetch_notice_from_url(req.url)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to fetch URL"))
    return result


@app.post("/api/speak-briefing")
async def speak_briefing_endpoint(req: SpeakBriefingRequest):
    """
    Synthesizes a 30-second spoken briefing audio via ElevenLabs API,
    with automatic fallback text for client-side Web Speech narration.
    """
    result = await synthesize_spoken_briefing(req.items, req.summary or "")
    return result


@app.post("/api/clean-ocr-text")
def clean_ocr_text_endpoint(req: CleanOCRRequest):
    """
    Cleans noisy raw OCR text using Google Gemma 2 or deterministic OCR normalizer.
    Fixes broken line breaks, hyphenated words, and scan artifacts.
    """
    return clean_ocr_text(req.raw_text)


@app.get("/api/sample-public-notice")
def get_sample_public_notice():
    """
    Returns a synthetic benchmark demo circular memo.
    Serves as a guaranteed 200 OK test target for web/PDF URL ingestion evaluation.
    """
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Synthetic Academic Memo — Benchmark Test Notice</title>
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 2rem auto; padding: 1.5rem; border: 1px solid #ccc;">
      <h2 style="text-align: center; color: #1e3a8a;">BOARD OF INTERMEDIATE & SECONDARY EDUCATION</h2>
      <h4 style="text-align: center; color: #475569; margin-top: -0.5rem;">SYNTHETIC EVALUATION DIRECTIVE (REF: BISE-ACAD-2026-904)</h4>
      <p style="font-size: 0.9rem; color: #64748b; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.5rem;">
        Published: October 21, 2026 | Distribution: Synthetic Benchmark Test Target
      </p>
      
      <p>It is hereby notified for the information of all Heads of Institutions, Grade 10 Homeroom Teachers, and Examination Coordinators that the final student candidate nomination lists for the upcoming 2027 Secondary Certificate Examinations must be submitted to the Board Controller Office by <strong>Tuesday, November 03, 2026 at 3:30 PM</strong>.</p>
      
      <p>Furthermore, all Accounts Officers and Class In-Charges must collect the mandatory board verification fee of <strong>$25 per candidate</strong> and deposit the treasury receipt slip before the deadline. Homeroom Teachers must verify and attach the student attendance declaration form with each submission packet.</p>
      
      <p style="margin-top: 2rem;">
        By order of the Board Chairman,<br>
        <strong>Dr. A. K. Azad</strong><br>
        Controller of Examinations
      </p>
    </body>
    </html>
    """
    return Response(content=html, media_type="text/html")


@app.get("/api/sample-university-circular")
def get_sample_university_circular():
    """
    Synthetic benchmark circular: University semester examination and fees directive.
    """
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Synthetic University Directive — Benchmark Test Notice</title>
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 2rem auto; padding: 1.5rem; border: 1px solid #ccc;">
      <h2 style="text-align: center; color: #1e3a8a;">NATIONAL ACADEMIC CONTROLLER BOARD & UNIVERSITY ADMINISTRATION</h2>
      <h4 style="text-align: center; color: #475569; margin-top: -0.5rem;">SYNTHETIC SEMESTER NOTIFICATION (REF: NUB-EXAM-2026-44)</h4>
      <p style="font-size: 0.9rem; color: #64748b; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.5rem;">
        Published: October 24, 2026 | Distribution: Synthetic Benchmark Test Target
      </p>
      
      <p>All Department Heads, Faculty Advisors, and Program Coordinators are hereby instructed that the final student admit card nomination lists for the upcoming 2026 Degree & Honours Final Examinations must be submitted to the Controller Office by <strong>Thursday, November 12, 2026 at 4:00 PM</strong>.</p>
      
      <p>In addition, Accounts Officers must verify that all examination fees of <strong>$35 per candidate</strong> have been collected and verified with the treasury registrar. Faculty Advisors must attach the course completion certificates before final dispatch.</p>
      
      <p style="margin-top: 2rem;">
        Approved by Office of the Registrar,<br>
        <strong>Prof. Dr. M. R. Chowdhury</strong><br>
        Controller of Examinations
      </p>
    </body>
    </html>
    """
    return Response(content=html, media_type="text/html")


@app.get("/api/sample-stem-directive")
def get_sample_stem_directive():
    """
    Synthetic benchmark circular: Inter-School Science Fair and Lab Protocol directive.
    """
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Synthetic STEM Memorandum — Benchmark Test Notice</title>
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 2rem auto; padding: 1.5rem; border: 1px solid #ccc;">
      <h2 style="text-align: center; color: #1e3a8a;">INTER-SCHOOL STEM & SCIENCE COMMITTEE</h2>
      <h4 style="text-align: center; color: #475569; margin-top: -0.5rem;">SYNTHETIC SCIENCE FAIR MEMORANDUM</h4>
      <p style="font-size: 0.9rem; color: #64748b; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.5rem;">
        Published: October 25, 2026 | Distribution: Synthetic Benchmark Test Target
      </p>
      
      <p>1. All Grade 9 and Grade 10 Science Teachers must submit the finalized list of participating student project teams to the Central Exhibition Committee by <strong>Friday, November 06, 2026 at 3:00 PM</strong>.</p>
      
      <p>2. Laboratory Assistants and STEM Coordinators are requested to collect the science kit safety fee of <strong>$15 per team</strong> and verify student chemical safety clearance slips before <strong>November 04, 2026</strong>.</p>
      
      <p style="margin-top: 2rem;">
        By order of the Organizing Committee,<br>
        <strong>Dr. Arthur Pendelton</strong><br>
        Chief Coordinator, STEM Cell
      </p>
    </body>
    </html>
    """
    return Response(content=html, media_type="text/html")


@app.get("/api/benchmark")
def run_live_benchmark():
    """
    Runs automated evaluation across all 6 synthetic test circulars.
    Strictly verifies expected item counts, field presence, date grounding, and human-review flags.
    Fails if any expected trait does not match.
    """
    results = []
    total_samples = len(SAMPLE_NOTICES)
    passed_cases = 0
    engine_name = "Unknown"
    live_called = False

    for sample in SAMPLE_NOTICES:
        text = sample["text"]
        expected_count = sample["expected_items_count"]
        sample_id = sample["id"]
        
        ext = extract_action_items(text)
        engine_name = ext["engine"]
        live_called = ext["live_model_called"]
        
        val = validate_extracted_checklist(text, ext["raw_items"])
        items = val["items"]
        item_count = len(items)

        case_passed = True
        notes = []

        # 1. Exact Item Count Check (Strict)
        if item_count != expected_count:
            case_passed = False
            notes.append(f"Count mismatch: Expected {expected_count} tasks, got {item_count}.")
        else:
            notes.append(f"Task count exact match ({item_count}/{expected_count}).")

        # 2. Case-Specific Assertions
        if sample_id == "case_1_complete":
            assignees = " ".join([it["assignee"] for it in items])
            deadlines = " ".join([it["deadline"] for it in items])
            fees_docs = " ".join([it["fee_or_docs"] for it in items])
            
            if "Science Teachers" not in assignees or "Homeroom Teachers" not in assignees:
                case_passed = False
                notes.append("Failed: Expected both Science and Homeroom teachers.")
            if "October 29" not in deadlines or "November 02" not in deadlines:
                case_passed = False
                notes.append("Failed: Expected October 29 and November 02 deadlines.")
            if "$15" not in fees_docs:
                case_passed = False
                notes.append("Failed: Expected $15 fee.")
            if val["verified_count"] != 2:
                case_passed = False
                notes.append("Failed: Expected both items to have verbatim verified quotes.")

        elif sample_id == "case_2_omitted_deadline":
            if item_count > 0:
                item = items[0]
                if item["deadline"] != "NOT STATED":
                    case_passed = False
                    notes.append(f"Failed: Deadline should be 'NOT STATED', got '{item['deadline']}'.")
                if "homeroom teachers" not in item["assignee"].lower():
                    case_passed = False
                    notes.append("Failed: Expected Homeroom Teachers assignee.")
                if not item["quote_verified"]:
                    case_passed = False
                    notes.append("Failed: Expected supporting quote to be verbatim verified.")
                else:
                    notes.append("Correctly enforced 'NOT STATED' without hallucinating a date.")

        elif sample_id == "case_3_informational":
            if item_count != 0:
                case_passed = False
                notes.append(f"Failed: Extracted {item_count} tasks from congratulatory advisory.")
            else:
                notes.append("Correctly identified 0 actionable tasks.")

        elif sample_id == "case_4_unrelated_date":
            if item_count > 0:
                item = items[0]
                dl = item["deadline"]
                if "1974" in dl or "March 26" in dl:
                    case_passed = False
                    notes.append(f"Failed: Trapped by historical date in deadline '{dl}'.")
                elif "November 10" not in dl:
                    case_passed = False
                    notes.append(f"Failed: Target deadline November 10 not found in '{dl}'.")
                else:
                    notes.append("Successfully isolated Nov 10 deadline and rejected 1974 founding trap.")

        elif sample_id == "case_5_multi_role_bangla":
            assignees = " ".join([it["assignee"] for it in items])
            deadlines = " ".join([it["deadline"] for it in items])
            if "শ্রেণি শিক্ষক" not in assignees or ("আইসিটি" not in assignees and "ল্যাব" not in assignees):
                case_passed = False
                notes.append("Failed: Did not distinguish শ্রেণি শিক্ষক from আইসিটি/ল্যাব সহকারী.")
            if "২৮ অক্টোবর" not in deadlines or "৩০ অক্টোবর" not in deadlines:
                case_passed = False
                notes.append("Failed: Missing expected Bangla deadlines (২৮ অক্টোবর or ৩০ অক্টোবর).")
            else:
                notes.append("Successfully parsed distinct Bangla roles and deadlines.")

        elif sample_id == "case_6_contradictory_malformed":
            if item_count > 0:
                item = items[0]
                if item["validation_status"] != "FLAGGED_FOR_HUMAN_REVIEW":
                    case_passed = False
                    notes.append(f"Failed: Contradictory notice should be FLAGGED_FOR_HUMAN_REVIEW, got {item['validation_status']}.")
                else:
                    notes.append("Correctly flagged contradictory timing for human review.")

        if case_passed:
            passed_cases += 1

        results.append({
            "case_id": sample_id,
            "title": sample["title"],
            "language": sample["language"],
            "passed": case_passed,
            "items_extracted": item_count,
            "expected_count": expected_count,
            "grounding_rate": f"{val['overall_grounding_rate']}%",
            "notes": " ".join(notes)
        })

    pass_rate = round((passed_cases / total_samples) * 100.0, 1)

    return {
        "engine_evaluated": engine_name,
        "live_model_called": live_called,
        "total_test_cases": total_samples,
        "passed_cases": passed_cases,
        "pass_rate_percentage": pass_rate,
        "test_results": results,
        "transparency_statement": (
            "This synthetic regression benchmark evaluates Notice2Next across 6 handcrafted edge cases "
            "with strict expected-count and field assertions. It validates pipeline mechanics and boundary guards, "
            "but does not claim universal real-world accuracy across arbitrary school circulars."
        )
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, reload=True)
