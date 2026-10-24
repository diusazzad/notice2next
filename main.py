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

from app.extractor import extract_action_items, BACKBOARD_API_KEY, GEMMA_MODEL
from app.validator import validate_extracted_checklist, validate_action_item
from app.samples import SAMPLE_NOTICES, get_sample_by_id, get_all_samples_metadata
from app.exporter import generate_csv, generate_markdown

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
    validation_report = validate_extracted_checklist(req.text, raw_items)

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
