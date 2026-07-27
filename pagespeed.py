"""Optional Website Speed Score via Google PageSpeed Insights API.
Needs its own free API key in .env as PAGESPEED_API_KEY.
If no key is set, returns None gracefully (speed score just stays blank)."""

import os, requests

PAGESPEED_KEY = os.getenv("PAGESPEED_API_KEY")


def speed_score(url, timeout=25):
    """Returns 0-100 performance score, or None if unavailable/no key."""
    if not PAGESPEED_KEY or not url:
        return None
    try:
        r = requests.get(
            "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
            params={"url": url, "key": PAGESPEED_KEY, "strategy": "mobile",
                    "category": "performance"},
            timeout=timeout)
        if r.status_code != 200:
            return None
        data = r.json()
        score = data["lighthouseResult"]["categories"]["performance"]["score"]
        return round(score * 100)
    except Exception:
        return None