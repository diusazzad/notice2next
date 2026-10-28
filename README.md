# Notice2Next 📋
> **Turn Dense School Circulars & Administrative Memos into Source-Backed Action Checklists.**  
> Built for **Hacktoberfest 2026 Week 3 Challenge: "Slow and Steady"**.  
> Core AI: **Google Gemma 2** | Platform: **Render** | Integrity: **Deterministic Python Grounding**

[![Render Live](https://img.shields.io/badge/Render-Live%20Deploy-00b894?logo=render&logoColor=white)](https://notice2next.onrender.com/)
[![Model](https://img.shields.io/badge/Model-Google%20Gemma%202-8e44ad)](https://ai.google.dev/gemma)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.13-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/diusazzad/notice2next/actions/workflows/ci.yml/badge.svg)](https://github.com/diusazzad/notice2next/actions)

---

## 📌 1. The Friction & The Persona: Teacher Administrative Burden

According to the **OECD TALIS (Teaching and Learning International Survey) 2024 data**, an average of **52% of teachers across participating education systems report general administrative work as a primary source of workplace stress**. In schools across the globe, educators spend considerable morning time deciphering bureaucratic circulars, internal memos, and academic decrees.

A typical school circular is buried in passive voice, bureaucratic jargon, and multiple fragmented instructions:
- *"It is hereby notified that all Grade 9 homeroom teachers shall collect medical clearance forms by Friday 3 PM, except..."*
- Deadlines are buried inside run-on paragraphs.
- Fees or document requirements are scattered across clauses.
- Many circulars mandate an urgent action but **omit the deadline entirely**.

Missing a compliance deadline leads to administrative reprimands. Manually transcribing circulars into a to-do list is tedious and error-prone.

**Notice2Next** is a functional open-source web application designed to streamline this task:
1. **Multi-Modal Notice Ingestion:** Paste text, upload/capture physical paper circular photos with client-side **OCR (Tesseract.js)**, or fetch public portal circulars & PDFs (e.g. Bangladesh Open University `bou.ac.bd`, National University `nu.ac.bd`, or district school portals) via an SSRF-safe scraper.
2. **Deterministic Evidence Grounding:** Every action item extracted by **Google Gemma 2** is verified against the source text with mathematical boundary assertions (exact date/time matching, quote-scoped whole-word assignee tokens, and contextual fee/document validation).
3. **Human-in-the-Loop Educator Governance Simulation:** Ambiguous or contradictory tasks are flagged for human review. In this demo, educators can simulate role-based review to authorize flagged items (`TEACHER_APPROVED_SIMULATION`), modeling human-in-the-loop oversight.
4. **ElevenLabs Audio Briefing:** Generates an accessible, spoken morning briefing of prioritized tasks for teachers on the go.
5. **Personal Notice Library:** Saves processed notices locally with safe browser storage fallbacks.

---

## 🏗️ 2. Architecture: Multi-Modal Ingestion & Deterministic Grounding

```mermaid
flowchart TD
    A1[Direct Text / Memo Paste] --> B[Multi-Modal Ingest Gate]
    A2[Paper Notice Photo / Camera OCR] --> B
    A3[Public Portal URL / PDF Scraper] --> B
    B --> C[Layer 1: Text Sanitizer, Size Bounds & SSRF Protection]
    C --> D{Model Execution Engine}
    D -->|Remote Backboard API| E[Google Gemma 2 Open-Weight Inference]
    D -->|Offline / Fallback Mode| F[Deterministic Heuristic Pattern Extractor]
    E --> G[Raw Structured Actions JSON Sanitizer]
    F --> G
    G --> H[Layer 2: Deterministic Evidence Grounding Engine]
    H --> I[Strict Verbatim Quote Verification]
    H --> J[Semantic Date & Time Component Parsing]
    H --> K[Whole-Word Assignee Token Matcher]
    H --> L[Fee Amount Boundary & Disclaimer Check]
    H --> M[Required Document Preservation]
    I & J & K & L & M --> N{Multi-Field Guardrail Checks}
    N -->|All Grounding Checks Satisfied| O[Status: VERIFIED_QUOTE_GROUNDED]
    N -->|Date/Role/Fee Mismatch or Missing Evidence| P[Status: FLAGGED_FOR_HUMAN_REVIEW]
    P --> Q[Educator Governance Simulation Gate]
    Q -->|Teacher Review & Override| R[Status: TEACHER_APPROVED_SIMULATION]
    O & R --> S[Layer 3: UI Checklist, Safe CSV Exporter & ElevenLabs Audio Briefing]
```

### Layer 1: Multi-Modal Ingestion & Hardened Gateway
- **Photo / Document OCR:** Integrated browser-side Tesseract.js allows teachers to photograph printed paper notices and immediately extract clean text with deterministic typo correction.
- **SSRF-Safe Public Notice Fetcher:** Ingests circulars directly from official education portals and PDFs. Enforces strict SSRF defense covering RFC 1918 private subnets, Carrier-Grade NAT (`100.64.0.0/10`), IPv6 loopbacks/unique local, DNS pre-resolution against rebinding, destination re-validation across up to 5 redirect hops, and a 10MB streaming download cap. Completely eliminates TLS verification bypasses (`verify=False`).
- **Request Body & Length Bounds:** Text input is bounded to 50,000 characters with 2MB maximum payload middleware to prevent memory exhaustion DoS attacks.
- **Model Layer:** Extracted text is processed by **Google Gemma 2** (`google/gemma-2-9b-it`) via Backboard with zero-downtime deterministic heuristic fallback.

### Layer 2: Deterministic Evidence Grounding (Python Engine)
Before any action reaches the educator, our Python validation layer inspects every field:
1. **Strict Verbatim Substring Matching:** Verifies that `source_quote` exists verbatim in the circular. Punctuation-stripped matches fail closed to flagged status.
2. **Schema Sanitization:** Discards or coerces malformed LLM dictionaries and non-string types, supporting key aliases (`task`, `role`, `due_date`).
3. **Semantic Date Component Parsing:** Separates calendar year, month, and day from clock times, eliminating substring matching collisions.
4. **Whole-Word Assignee Token Matching:** Uses word-boundary token equality (`\b\w+\b`) to prevent numeric/substring collisions (e.g., Grade 1 cannot match Grade 10).
5. **Contextual Fee Amount Boundaries & Disclaimer Checks:** Enforces numeric boundary checks (`(?<!\d){num}(?!\d)`) preventing $15 from matching $150, and rejects fee claims when the notice disclaims fees ("no fee is required").
6. **Preserved Required Documents:** Ensures core document requirements (e.g. "Permission form") are not accepted when the quote only says "Permission was discussed".
7. **Explicit `NOT STATED` Enforcement:** Missing deadlines are strictly labeled `NOT STATED` rather than hallucinated.
8. **Contradiction Detection:** Conflicting directives trigger `⚠️ Contradiction Detected (Review)`.
9. **Configurable Verification:** Supports `verify_quotes=False` requests, clearly marking quotes as `UNVERIFIED_BY_REQUEST` with informative disclaimers.

### Layer 3: Interactive Teacher Interface, Audio & Export
- **Educator Governance Simulation:** Models a human-in-the-loop decision-maker for ambiguous agent extractions with client-side role switching.
- **ElevenLabs Audio Briefing:** Generates concise spoken audio summaries via ElevenLabs REST API with browser Web Speech fallback.
- **Safe CSV & Markdown Export:** Neutralizes CSV / Spreadsheet Formula Injection (CWE-1236) by escaping leading formula triggers (`=`, `+`, `-`, `@`, `\t`, `\r`) with single quotes.
- **Defensive Client Storage:** Browser library and theme persistence wrap `localStorage` defensively with in-memory fallbacks when privacy mode or cookies block storage.

---

## 🧪 3. Synthetic Regression Benchmark

Notice2Next includes an automated evaluation benchmark covering difficult boundary edge cases:

| Case ID | Scenario Description | Language | Expected Count | Extracted Count | Grounding Status | Measured Outcome |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Case 1** | Complete Circular (Science Fair & Field Trip) | English | 2 | 2 | **100% Verbatim** | ✓ Verified both Science and Homeroom duties, Oct 29/Nov 02 dates, and $15 fee. |
| **Case 2** | Action Stated but Deadline Omitted | English | 1 | 1 | **100% Verbatim** | ✓ Correctly marked deadline as `NOT STATED` without guessing. |
| **Case 3** | Purely Informational Advisory (Congratulations) | English | 0 | 0 | **N/A (0 Tasks)** | ✓ Correctly detected 0 actionable tasks. |
| **Case 4** | Unrelated Historical Date Trap (1974 founding) | English | 1 | 1 | **100% Verbatim** | ✓ Target deadline Nov 10 captured; founding year 1974 rejected. |
| **Case 5** | Multi-Role Bangla Circular (শ্রেণি শিক্ষক ও আইসিটি) | Bangla | 2 | 2 | **100% Verbatim** | ✓ Distinct duties & deadlines extracted for homeroom vs lab staff. |
| **Case 6** | Contradictory & Malformed Staff Note | English | 1 | 1 | **Flagged Review** | ✓ Correctly flagged contradictory timing (10 AM vs 5 PM) for human educator review. |

> **Cost Protection:** `/api/benchmark` evaluates against deterministic offline fixtures by default to eliminate provider cost exhaustion and Denial of Service. Live model execution on the benchmark requires an administrative key (`BENCHMARK_ADMIN_KEY`).

---

## 🛠️ 4. Post-Submission Hardening & Audited Pull Requests

Following the Hacktoberfest competition submission, the repository underwent an exhaustive engineering and security audit documented in [`docs/maintenance/security-and-reliability-audit.md`](docs/maintenance/security-and-reliability-audit.md). Remediation was executed across isolated, reviewable Pull Requests:

| PR # | Branch Name | Scope & Finding Addressed | Severity |
| :---: | :--- | :--- | :---: |
| **#1** | `fix/request-safety-benchmark-protection` | Bounded text inputs (50KB / 2MB middleware); protected `/api/benchmark` against live model cost exhaustion. | **P1** |
| **#2** | `fix/safe-url-ssrf-ingestion` | Hardened SSRF defense; removed `verify=False`; added DNS pre-resolution, redirect re-validation, and 10MB streaming size caps. | **P1** |
| **#3** | `fix/ai-schema-and-evidence-correctness` | Enforced raw LLM schema sanitization; honored `verify_quotes` request flag with explicit `UNVERIFIED_BY_REQUEST` status. | **P2** |
| **#4** | `fix/privacy-and-bounded-retries` | Implemented ephemeral assistant thread deletion (`DELETE /threads/{id}`) and sanitized PII logs. | **P3** |
| **#5** | `fix/client-storage-and-honest-auth-ui` | Wrapped browser storage defensively with in-memory fallback; ensured honest labeling of client-side educator demo simulation (Rule 8). | **P2** |
| **#6** | `fix/csv-formula-injection-protection` | Neutralized spreadsheet formula injection (CWE-1236) across all exported CSV cells. | **P2** |
| **#7** | `docs/operational-clarifications` | Comprehensive operational documentation and baseline security audit report. | **Docs** |

---

## ⚡ 5. Quickstart & Local Installation

### Prerequisites
- Python 3.10+ (Tested on Python 3.11, 3.12, 3.13)
- Git

### 1. Clone & Set Up Virtual Environment
```bash
git clone https://github.com/diusazzad/notice2next.git
cd notice2next

python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment (Optional)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Available environment variables:
```ini
BACKBOARD_API_KEY=your_backboard_api_key_here
BACKBOARD_BASE_URL=https://api.backboard.io/v1
GEMMA_MODEL=google/gemma-2-9b-it
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM
BENCHMARK_ADMIN_KEY=optional_secret_for_live_benchmark
PORT=8000
```

### 3. Run Automated Tests
```bash
pytest tests/ -v
```

### 4. Start the Application
```bash
uvicorn main:app --reload --port 8000
```
Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## ☁️ 6. Cloud Deployment & CI/CD

Notice2Next is natively configured for:
- **Render (`render.yaml`):** Automated container build, Uvicorn service, and `/health` monitoring.
- **GitHub Actions (`.github/workflows/ci.yml`):** Runs the full pytest test suite across Python 3.11 and 3.12 on every push and pull request.

---

## ⚠️ 7. Limitations & Honest Disclaimers

1. **Evidence Grounding is Not Semantic Truth:** An exact substring match verifies that the quoted phrase appears verbatim in the circular. It does not certify that the administrative memo was authorized or legally binding. Teachers must review all items before taking action.
2. **Client-Side Educator Simulation vs Production Auth:** The educator sign-in feature is a client-side simulation demonstrating human-in-the-loop review. It does not provide server-side identity or cryptographic authorization.
3. **Hosted Prototype Privacy:** While open weights enable private on-premise execution, the live hosted prototype transmits text over HTTPS. **Do not paste sensitive student health or disciplinary records on the hosted public demo.**

---

## 📄 8. License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for details.  
Maintained by **Sazzad Hossain** for Hacktoberfest 2026.
