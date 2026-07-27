"""
Stage 2 — website audit.
Given a website URL, fetch it and extract contact + SEO signals.
"""

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"\+?91[\-\s]?[6-9]\d{9}|\b[6-9]\d{9}\b|0\d{2,4}[\-\s]?\d{6,8}")


def _plain_reason(status):
    if status in (403, 503, 429):
        return ("This clinic's website blocks automated visitors (bot protection), "
                "so we couldn't read it. Check it manually before calling.")
    if status in (404, 410):
        return "The website link is broken or the page no longer exists."
    if status in (500, 502, 504):
        return "The clinic's website is currently down or erroring."
    if status and status >= 400:
        return "The website wouldn't let us read it."
    return None


def _normalize(url):
    if not url:
        return None
    if not url.startswith("http"):
        url = "https://" + url
    return url


def audit_website(raw_url, timeout=12):
    url = _normalize(raw_url)
    result = {
        "url": url, "reachable": False, "ssl": False,
        "email": None, "phone": None, "all_phones": [], "whatsapp": False, "whatsapp_link": None,
        "whatsapp_number": None,
        "socials": {}, "has_contact_form": False, "has_booking": False,
        "doctor_name": None, "contact_page": None,
        "seo": {}, "seo_score": 0, "seo_issues": [], "error": None,
    }
    if not url:
        result["error"] = "no website"
        return result

    try:
        sess = requests.Session()
        sess.headers.update(HEADERS)
        r = sess.get(url, timeout=timeout, allow_redirects=True)
        if r.status_code in (403, 429, 503):
            sess.headers.update({"Referer": "https://www.google.com/"})
            r = sess.get(url, timeout=timeout, allow_redirects=True)
        result["ssl"] = r.url.startswith("https://")
        result["reachable"] = r.status_code == 200
        if r.status_code != 200:
            result["error"] = _plain_reason(r.status_code)
            return result
    except requests.exceptions.SSLError:
        result["error"] = "The website's security certificate is broken (no valid HTTPS)."
        return result
    except requests.exceptions.ConnectTimeout:
        result["error"] = "The website took too long to respond (possibly down)."
        return result
    except requests.exceptions.ConnectionError:
        result["error"] = "We couldn't connect to the website - it may be offline."
        return result
    except Exception:
        result["error"] = "Something went wrong reading the website."
        return result

    html = r.text
    soup = BeautifulSoup(html, "html.parser")
    text_lower = html.lower()

    mailto = soup.select_one('a[href^="mailto:"]')
    if mailto:
        result["email"] = mailto["href"].replace("mailto:", "").split("?")[0].strip()
    else:
        m = EMAIL_RE.search(html)
        if m:
            result["email"] = m.group(0)

    phones = []
    for tel in soup.select('a[href^="tel:"]'):
        num = tel["href"].replace("tel:", "").strip()
        if num and num not in phones:
            phones.append(num)
    for m in PHONE_RE.findall(soup.get_text(" ")):
        clean = m.strip()
        digits = re.sub(r"\D", "", clean)
        if len(digits) >= 10 and clean not in phones:
            phones.append(clean)
    result["all_phones"] = phones[:6]
    result["phone"] = phones[0] if phones else None

    dr = re.search(r"\bDr\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}", soup.get_text(" "))
    if dr:
        result["doctor_name"] = dr.group(0).strip()

    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if re.search(r"contact|reach-us|get-in-touch", href, re.I):
            result["contact_page"] = urljoin(url, href)
            break

    wa = soup.select_one('a[href*="wa.me"], a[href*="api.whatsapp.com"], a[href*="whatsapp.com/send"]')
    if wa:
        result["whatsapp"] = True
        result["whatsapp_link"] = wa.get("href")
        wm = re.search(r"(?:wa\.me/|phone=)(\+?\d{10,15})", wa.get("href", ""))
        if wm:
            result["whatsapp_number"] = wm.group(1)
    elif "whatsapp" in text_lower:
        result["whatsapp"] = True

    socials = {}
    for a in soup.select("a[href]"):
        href = a["href"]
        for net, pat in {"instagram": "instagram.com", "facebook": "facebook.com",
                         "linkedin": "linkedin.com", "youtube": "youtube.com",
                         "twitter": "twitter.com"}.items():
            if pat in href and net not in socials:
                socials[net] = href
    result["socials"] = socials

    result["has_contact_form"] = bool(soup.find("form"))
    result["has_booking"] = any(k in text_lower for k in
                                ["book appointment", "book now", "schedule", "calendly", "appointment"])

    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    meta_desc = soup.find("meta", attrs={"name": "description"})
    meta_desc = meta_desc.get("content", "").strip() if meta_desc else ""
    h1s = soup.find_all("h1")
    has_schema = "application/ld+json" in text_lower or "schema.org" in text_lower
    has_viewport = bool(soup.find("meta", attrs={"name": "viewport"}))

    seo = {
        "title": title[:120], "has_title": bool(title),
        "has_meta_description": bool(meta_desc),
        "h1_count": len(h1s), "has_h1": len(h1s) > 0,
        "has_schema": has_schema, "mobile_viewport": has_viewport,
    }
    issues = []
    score = 100
    if not seo["has_title"]:            issues.append("Missing page title");         score -= 20
    if not seo["has_meta_description"]: issues.append("No meta description");         score -= 15
    if not seo["has_h1"]:               issues.append("No H1 heading");               score -= 15
    if seo["h1_count"] > 1:             issues.append("Multiple H1 headings");        score -= 5
    if not seo["has_schema"]:           issues.append("No structured data (schema)"); score -= 15
    if not seo["mobile_viewport"]:      issues.append("Not mobile-friendly");         score -= 20
    if not result["ssl"]:               issues.append("No HTTPS/SSL");                score -= 10

    result["seo"] = seo
    result["seo_score"] = max(score, 0)
    result["seo_issues"] = issues
    return result
