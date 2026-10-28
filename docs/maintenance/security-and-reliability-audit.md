# Notice2Next — Security, Reliability, and Engineering Baseline Audit

**Document Version:** 1.0.0  
**Date:** October 28, 2026  
**Auditor:** Engineering Hardening & AppSec Review  
**Target Repository:** `https://github.com/diusazzad/notice2next`  
**Current Baseline Commit:** `128f401` (`main`)  
**Existing Test Suite:** 41 tests passing (`pytest tests/test_notice2next.py`)

---

## 1. Executive Summary

Notice2Next transforms educational circulars and administrative memos into structured, source-grounded action checklists. The application pairs open-weight language synthesis (Google Gemma 2 served via Backboard API) with a deterministic Python evidence validation layer.

Following the competition submission, this audit examines the codebase for production reliability, request safety, SSRF resilience, cost control, data integrity, and compliance with the project's non-negotiable engineering rules.

All findings below have been directly verified against the repository code and runtime behavior.

---

## 2. Findings Matrix

| Finding ID | Severity | Category | File & Location | Status | Proposed Fix PR |
| :--- | :---: | :--- | :--- | :---: | :---: |
| **COST-01** | **P1** | Provider Cost & DoS | `main.py:270-290` (`run_live_benchmark`) | **Reproduced** | **PR 1** |
| **DOS-01** | **P1** | Resource Exhaustion | `main.py:34-36`, `52-54` (`ExtractRequest`) | **Reproduced** | **PR 1** |
| **SSRF-01** | **P1** | Insecure TLS Fallback | `app/browser_fetcher.py:180-186` | **Reproduced** | **PR 2** |
| **SSRF-02** | **P1** | SSRF on Redirects & DNS | `app/browser_fetcher.py:30-56`, `177` | **Reproduced** | **PR 2** |
| **AI-01** | **P2** | Schema Validation | `app/extractor.py:113-118` | **Reproduced** | **PR 3** |
| **CORR-01** | **P2** | API Contract Correctness | `main.py:36, 105`; `app/validator.py:622` | **Reproduced** | **PR 3** |
| **PRIV-01** | **P3** | Privacy & Resource Leak | `app/extractor.py:65-80` | **Reproduced** | **PR 4** |
| **UX-01** | **P2** | Client Resilience & Auth | `static/app.js:473-485, 515-524` | **Reproduced** | **PR 5** |
| **EXPORT-01**| **P2** | CSV Formula Injection | `app/exporter.py:11-41` | **Reproduced** | **PR 6** |

---

## 3. Detailed Technical Findings

### COST-01: Unbounded Live Model Invocation in Public Benchmark Route
- **Severity:** P1 (High — Cost Control & DoS)
- **File:** `main.py:270-295` in `run_live_benchmark()`
- **Conditions Required:** Calling `GET /api/benchmark` while `BACKBOARD_API_KEY` is configured in production.
- **Reproducible Evidence:**
  ```python
  for sample in SAMPLE_NOTICES:
      text = sample["text"]
      ext = extract_action_items(text) # Triggers live remote model when BACKBOARD_API_KEY is present
  ```
- **Impact:** Every single HTTP request to `/api/benchmark` executes 6 consecutive live remote Gemma 2 calls over the network. A bot or automated monitor hitting this endpoint repeatedly can exhaust monthly API token quotas in minutes and cause financial cost spikes.
- **Proposed Fix:** Protect the benchmark pipeline so that `/api/benchmark` evaluates against deterministic offline fixtures by default, or requires an administrative authorization token (`X-Benchmark-Key`) to invoke live paid cloud inference.
- **Regression Tests Needed:** Unit test confirming `/api/benchmark` executes deterministically without triggering remote HTTP network requests unless explicitly authorized.

---

### DOS-01: Unbounded Request Payload and Notice Text Length
- **Severity:** P1 (High — Service Availability)
- **File:** `main.py:34-36` (`ExtractRequest`), `main.py:52-54` (`CleanOCRRequest`)
- **Conditions Required:** Submitting an oversized payload (e.g. 50MB string) to `POST /api/extract` or `POST /api/clean-ocr`.
- **Reproducible Evidence:**
  ```python
  class ExtractRequest(BaseModel):
      text: str = Field(..., min_length=10) # No max_length defined
  ```
- **Impact:** Ingesting arbitrarily large texts causes excessive memory allocation, long CPU stalls in regex substring normalization, and server process worker starvation.
- **Proposed Fix:** Enforce `max_length=50000` (approx. 25-30 pages of text, well beyond any realistic school circular) on `text` fields, and add a payload size guard in FastAPI middleware or route validation.
- **Regression Tests Needed:** Tests verifying that payloads exceeding length limits fail immediately with HTTP 422 / 400 without invoking extraction.

---

### SSRF-01: TLS Certificate Verification Bypass on Ingestion Fallback
- **Severity:** P1 (High — Transport Security & Rule 7 Violation)
- **File:** `app/browser_fetcher.py:180-186`
- **Conditions Required:** Fetching a remote notice from a server with an incomplete or self-signed certificate chain.
- **Reproducible Evidence:**
  ```python
  except (httpx.ConnectError, httpx.SecurityError, Exception) as primary_net_err:
      async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=headers, verify=False) as insecure_client:
          response = await insecure_client.get(url_str)
  ```
- **Impact:** Violates Non-Negotiable Engineering Rule 7 (*"Never weaken certificate verification. Do not add verify=False or equivalent TLS bypasses as a workaround"*). Allows attacker-in-the-middle (MitM) attacks to spoof educational notices and inject malicious directives.
- **Proposed Fix:** Remove `verify=False` entirely. Enforce strict TLS validation on all external HTTPS requests. If an institution server fails TLS handshake, return a clear error advising the user to copy/paste the circular text directly.
- **Regression Tests Needed:** Verify that all HTTP client initializations enforce `verify=True`.

---

### SSRF-02: Unvalidated Redirects and DNS Rebinding in URL Ingestion
- **Severity:** P1 (High — Application Security)
- **File:** `app/browser_fetcher.py:30-56`, `177`
- **Conditions Required:** Supplying a public URL that issues an HTTP 301/302 redirect to `http://169.254.169.254/` (cloud metadata) or `http://127.0.0.1:8000/`.
- **Reproducible Evidence:**
  `validate_url_safety()` only performs string matching on the initial URL's hostname. `httpx.AsyncClient(follow_redirects=True)` follows redirect hops without re-evaluating each target against `BLOCKED_IP_NETWORKS`. Additionally, domain names that resolve to loopback/private IPs (e.g. `127.0.0.1.nip.io`) are not pre-resolved.
- **Impact:** Server-Side Request Forgery (SSRF) against internal container services, localhost APIs, or cloud metadata endpoints.
- **Proposed Fix:** Implement custom redirect handling or an event hook that resolves and validates the IP address of every redirect target against `BLOCKED_IP_NETWORKS`. Add a strict 10MB response streaming limit to prevent memory exhaustion from oversized PDF downloads.
- **Regression Tests Needed:** Adversarial tests with redirect chains targeting private IPs, loopback, and metadata endpoints.

---

### AI-01: Missing Schema Validation on Model Response JSON
- **Severity:** P2 (Medium — AI Systems Correctness)
- **File:** `app/extractor.py:113-118`, `200-210`
- **Conditions Required:** Language model returns malformed inner action structures (e.g., list of strings, null values, or missing required keys).
- **Reproducible Evidence:**
  ```python
  parsed = json.loads(content)
  if isinstance(parsed, dict) and "actions" in parsed:
      return parsed["actions"] # Does not validate that actions contains dicts with action, assignee, deadline keys
  ```
- **Impact:** Downstream validator components expecting dictionary keys (`it["action"]`, `it["deadline"]`) can crash with `TypeError` or `KeyError`, causing HTTP 500 errors.
- **Proposed Fix:** Define an explicit Pydantic or schema validator for raw extracted action items (`RawActionItem`). Discard or sanitize malformed entries before passing to validation.
- **Regression Tests Needed:** Unit tests mocking LLM output with missing keys, null fields, non-dict elements, and malformed structures.

---

### CORR-01: Ignored `verify_quotes` Request Parameter (Dead Option)
- **Severity:** P2 (Medium — Correctness & API Integrity)
- **File:** `main.py:36, 105`; `app/validator.py:622`
- **Conditions Required:** Calling `POST /api/extract` with `verify_quotes=False`.
- **Reproducible Evidence:**
  `ExtractRequest` accepts `verify_quotes: bool = Field(True)`, but `main.py:extract_notice_actions()` calls `validate_extracted_checklist(req.text, raw_items)` without passing `req.verify_quotes`. `validate_extracted_checklist()` does not accept or implement this option.
- **Impact:** Misleading API contract. A client attempting to bypass quote verification for speed or custom handling still has full quote verification enforced.
- **Proposed Fix:** Update `validate_extracted_checklist(notice_text, items, verify_quotes=True)`. When `verify_quotes=False`, record quote status as `UNVERIFIED_BY_REQUEST` with clear disclaimer notes.
- **Regression Tests Needed:** Test verifying that `verify_quotes=False` produces unverified quote status and skips verbatim substring enforcement.

---

### UX-01: Unhandled `localStorage` Exceptions & Misleading Auth0 Claims
- **Severity:** P2 (Medium — User Experience & Honest Claims)
- **File:** `static/app.js:473-485`, `515-524`
- **Conditions Required:** User has browser storage disabled (e.g., strict privacy mode) or `localStorage` contains corrupted JSON.
- **Reproducible Evidence:**
  `JSON.parse(localStorage.getItem('notice2next_saved_library') || '[]')` without `try...catch`. Calling `id: 'auth0|educator_' + Date.now()` and displaying `Authenticated via Auth0 Governance Gate`.
- **Impact:** Application script crashes silently on page load if storage is inaccessible or invalid. Claims of real Auth0 authentication are inaccurate since it is purely a client-side simulated role.
- **Proposed Fix:** Wrap all storage operations in defensive helper functions (`safeStorageGet`, `safeStorageSet`). Update UI labels to explicitly state: `Demo Educator Role (Client Simulation)` to maintain technical honesty.
- **Regression Tests Needed:** JavaScript syntax and headless verification of storage fallback when storage throws `SecurityError`.

---

### EXPORT-01: CSV Formula Injection (CWE-1236)
- **Severity:** P2 (Medium — Application Security)
- **File:** `app/exporter.py:11-41`
- **Conditions Required:** Exporting action items or notices containing leading formula trigger characters (`=`, `+`, `-`, `@`).
- **Reproducible Evidence:**
  ```python
  writer.writerow([
      status_str,
      it.get("action", ""), # Unsanitized string written to CSV
      ...
  ])
  ```
- **Impact:** When an educator opens the exported CSV file in Microsoft Excel, LibreOffice Calc, or Google Sheets, cell values starting with `=CMD|...` or `@SUM(...)` can execute arbitrary formulas or trigger DDE execution alerts.
- **Proposed Fix:** Sanitize exported CSV cell values: if a string starts with `=`, `+`, `-`, or `@`, prepend an apostrophe (`'`) or quote character to neutralize spreadsheet formula evaluation.
- **Regression Tests Needed:** Tests confirming that dangerous formula prefixes are escaped in CSV output while preserving ordinary text semantics.

---

### PRIV-01: Unbounded Third-Party Assistant Threads
- **Severity:** P3 (Low — Privacy & Resource Lifecycle)
- **File:** `app/extractor.py:65-80`
- **Conditions Required:** Using Backboard native API (`espr_...` key) where assistant threads are created per request.
- **Reproducible Evidence:**
  `POST https://app.backboard.io/api/assistants/{id}/threads` creates a thread, but no deletion or cleanup (`DELETE /threads/{id}`) is attempted after message retrieval.
- **Impact:** Lingering notice text stored in remote provider assistant memory.
- **Proposed Fix:** Attempt best-effort deletion of ephemeral threads when Backboard API supports thread deletion, and document residual retention policies.
- **Regression Tests Needed:** Mock test verifying thread cleanup is attempted after successful or failed message execution.

---

## 4. Remediation Roadmap

Remediation will proceed across separate, reviewable Pull Requests:

1. **PR 1 (`fix/request-safety-benchmark-protection`):**
   - Implements `max_length` bounds on `ExtractRequest` and `CleanOCRRequest`.
   - Protects `/api/benchmark` against live model invocation; defaults to deterministic fixtures.
   - Adds regression tests for payload limits and benchmark cost protection.

2. **PR 2 (`fix/safe-url-ssrf-ingestion`):**
   - Eliminates `verify=False` in `app/browser_fetcher.py`.
   - Implements redirect destination safety validation and streaming size caps (10MB).
   - Adds tests for malicious redirect chains and private IP blocking.

3. **PR 3 (`fix/ai-schema-and-evidence-correctness`):**
   - Adds schema validation for LLM output items.
   - Implements real tested semantics for `req.verify_quotes`.
   - Adds tests for malformed LLM JSON and optional verification flags.

4. **PR 4 (`fix/privacy-and-bounded-retries`):**
   - Implements best-effort ephemeral thread cleanup.
   - Sanitizes log statements to prevent PII leakage.

5. **PR 5 (`fix/client-storage-and-honest-auth-ui`):**
   - Adds defensive `try...catch` storage wrappers in `static/app.js`.
   - Labels educator authentication as `Demo Simulation` to ensure transparency.

6. **PR 6 (`fix/csv-formula-injection-protection`):**
   - Sanitizes CSV exports against CWE-1236 formula injection (`=`, `+`, `-`, `@`).
   - Adds unit tests for formula prefixes and Unicode preservation.

7. **PR 7 (`docs/operational-clarifications`):**
   - Updates `README.md` and documentation to accurately reflect hardened controls and limitations.
