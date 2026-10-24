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
    Measures extraction accuracy, quote verification rate, and failure admissions.
    """
    results = []
    total_samples = len(SAMPLE_NOTICES)
    passed_cases = 0

    for sample in SAMPLE_NOTICES:
        text = sample["text"]
        expected_count = sample["expected_items_count"]
        
        ext = extract_action_items(text)
        val = validate_extracted_checklist(text, ext["raw_items"])

        items = val["items"]
        item_count = len(items)

        # Evaluate correctness according to expected traits
        case_passed = True
        notes = []

        if sample["id"] == "case_3_informational":
            # Must detect 0 action items
            if item_count == 0:
                notes.append("Correctly detected 0 tasks in informational notice.")
            else:
                case_passed = False
                notes.append(f"Failed: Extracted {item_count} tasks from informational notice.")
        elif sample["id"] == "case_2_omitted_deadline":
            # Must set deadline to NOT STATED
            has_not_stated = any(it["deadline"] == "NOT STATED" for it in items)
            if has_not_stated:
                notes.append("Correctly marked deadline as NOT STATED without guessing.")
            else:
                case_passed = False
                notes.append("Failed: Did not mark missing deadline as NOT STATED.")
        elif sample["id"] == "case_4_unrelated_date":
            # Must NOT use 1974 or March 26 as deadline
            used_trap = any("1974" in it["deadline"] or "March 26" in it["deadline"] for it in items)
            if not used_trap:
                notes.append("Correctly rejected unrelated historical dates (1974, March 26).")
            else:
                case_passed = False
                notes.append("Failed: Trapped by unrelated historical date.")
        else:
            # Check quote verification rate
            if val["verified_count"] >= 1:
                notes.append(f"Successfully verified {val['verified_count']} action items with exact quotes.")
            else:
                case_passed = False
                notes.append("Failed: No verified action items found.")

        if case_passed:
            passed_cases += 1

        results.append({
            "case_id": sample["id"],
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
        "total_test_cases": total_samples,
        "passed_cases": passed_cases,
        "pass_rate_percentage": pass_rate,
        "test_results": results,
        "transparency_statement": (
            "This benchmark is conducted across 6 synthetic school notices covering edge cases "
            "(informational text, omitted deadlines, multi-role Bangla, and historical date traps). "
            "It demonstrates evidence verification mechanics but does not claim universal real-world accuracy across all school systems."
        )
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, reload=True)
