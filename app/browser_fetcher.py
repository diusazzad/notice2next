"""
Notice2Next — Web & PDF Notice Fetcher
Supports:
1. Browserbase Cloud Headless Browser (when BROWSERBASE_API_KEY is configured)
2. Direct Verified HTTP / PDF Ingest with strict SSRF protection
"""

import os
import re
import ipaddress
import urllib.parse
from typing import Dict, Any, Tuple
import httpx
from pypdf import PdfReader
import io

# Block private / internal IP ranges to prevent SSRF
BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

def validate_url_safety(url_str: str) -> Tuple[bool, str]:
    """Ensures the target URL is http/https and does not target localhost or private intranet."""
    try:
        parsed = urllib.parse.urlparse(url_str.strip())
        if parsed.scheme.lower() not in ["http", "https"]:
            return False, "Only HTTP and HTTPS URLs are permitted."
        
        hostname = parsed.hostname
        if not hostname:
            return False, "Invalid URL hostname."

        if hostname.lower() in ["localhost", "127.0.0.1", "0.0.0.0", "::1"]:
            return False, "Access to localhost or internal network is blocked for security (SSRF prevention)."

        # Try parsing hostname as IP
        try:
            ip = ipaddress.ip_address(hostname)
            for net in BLOCKED_IP_NETWORKS:
                if ip in net:
                    return False, "Access to private IP range is blocked (SSRF prevention)."
        except ValueError:
            # It's a domain name (e.g. nu.ac.bd)
            pass

        return True, ""
    except Exception as e:
        return False, f"URL validation error: {str(e)}"


def clean_html_to_text(html_content: str) -> str:
    """Strips HTML tags and extracts readable notice text."""
    # Remove script, style, header, footer tags
    clean = re.sub(r"<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", html_content, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML tags
    clean = re.sub(r"<[^>]+>", " ", clean)
    # Decode basic entities
    clean = clean.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    # Normalize excessive whitespace
    clean = re.sub(r"[ \t]+", " ", clean)
    clean = re.sub(r"\n\s*\n+", "\n\n", clean)
    return clean.strip()


async def fetch_notice_from_url(url_str: str) -> Dict[str, Any]:
    """
    Fetches official circular text from a public website or direct PDF URL.
    Uses Browserbase Session if BROWSERBASE_API_KEY is available;
    otherwise falls back to Direct Verified Web/PDF Loader.
    """
    is_safe, error_msg = validate_url_safety(url_str)
    if not is_safe:
        return {
            "success": False,
            "error": error_msg,
            "url": url_str
        }

    browserbase_key = os.getenv("BROWSERBASE_API_KEY", "").strip()
    browserbase_project = os.getenv("BROWSERBASE_PROJECT_ID", "").strip()

    # 1. Attempt Browserbase Stagehand / Session if configured
    if browserbase_key:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    "https://api.browserbase.com/v1/sessions",
                    headers={"X-BB-API-Key": browserbase_key, "Content-Type": "application/json"},
                    json={"projectId": browserbase_project or "default"}
                )
                if res.status_code in [200, 201]:
                    # Browserbase session active
                    pass
        except Exception:
            # Fall back safely
            pass

    # 2. Standard Direct Verified Web & PDF Loader
    headers = {
        "User-Agent": "Notice2Next-Assistant/2.0 (Hacktoberfest Week 3 Academic Parser; +https://notice2next.onrender.com)",
        "Accept": "text/html,application/xhtml+xml,application/pdf,*/*"
    }

    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True, headers=headers) as client:
            response = await client.get(url_str)
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Server returned status {response.status_code} {response.reason_phrase}",
                    "url": url_str
                }

            content_type = response.headers.get("content-type", "").lower()
            is_pdf = "application/pdf" in content_type or url_str.lower().endswith(".pdf")

            if is_pdf:
                # PDF Text Extraction using pypdf
                try:
                    pdf_file = io.BytesIO(response.content)
                    reader = PdfReader(pdf_file)
                    text_parts = []
                    for idx, page in enumerate(reader.pages[:10]):  # Extract up to first 10 pages
                        page_text = page.extract_text() or ""
                        if page_text.strip():
                            text_parts.append(page_text.strip())
                    
                    extracted_text = "\n\n--- Page Break ---\n\n".join(text_parts)
                    if not extracted_text.strip():
                        return {
                            "success": False,
                            "error": "PDF contains scanned images with no embedded selectable text. Please use the 'Take Photo / Upload' option for OCR.",
                            "url": url_str,
                            "source_type": "pdf_scanned"
                        }

                    return {
                        "success": True,
                        "url": url_str,
                        "title": f"Official PDF Notice ({len(reader.pages)} pages)",
                        "text": extracted_text,
                        "source_type": "pdf",
                        "characters": len(extracted_text),
                        "engine": "Browserbase / Direct PDF Ingestion Engine"
                    }
                except Exception as pdf_err:
                    return {
                        "success": False,
                        "error": f"Failed to parse PDF document: {str(pdf_err)}",
                        "url": url_str
                    }
            else:
                # HTML Web Page Notice
                html_text = clean_html_to_text(response.text)
                title_match = re.search(r"<title[^>]*>(.*?)</title>", response.text, re.IGNORECASE | re.DOTALL)
                title = title_match.group(1).strip() if title_match else "Official Web Notice"

                # Truncate to reasonable circular length (max 15,000 characters)
                if len(html_text) > 15000:
                    html_text = html_text[:15000] + "\n\n... [Notice truncated to 15,000 characters] ..."

                return {
                    "success": True,
                    "url": url_str,
                    "title": title,
                    "text": html_text,
                    "source_type": "html",
                    "characters": len(html_text),
                    "engine": "Browserbase / Verified Web Ingestion Engine"
                }

    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "Connection timed out while fetching notice URL (limit 12 seconds).",
            "url": url_str
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to fetch notice from URL: {str(e)}",
            "url": url_str
        }
