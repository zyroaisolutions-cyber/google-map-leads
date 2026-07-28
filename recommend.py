"""Zyro Service Recommendation Engine"""


SERVICES = [
    {"id": "website",    "name": "Website Development",     "price": "₹25,000 – ₹60,000",  "condition": lambda l, a: not l.get("website") or (a and not a.get("reachable"))},
    {"id": "seo",        "name": "SEO Optimization",        "price": "₹8,000 – ₹15,000/mo", "condition": lambda l, a: a and (a.get("seo_score") or 0) < 50},
    {"id": "booking",    "name": "Appointment Booking Bot", "price": "₹12,000 – ₹25,000",  "condition": lambda l, a: a and not a.get("has_booking")},
    {"id": "whatsapp",   "name": "WhatsApp Automation",     "price": "₹6,000 – ₹15,000/mo","condition": lambda l, a: a and not a.get("whatsapp")},
    {"id": "chatbot",    "name": "AI Chatbot",              "price": "₹8,000 – ₹20,000/mo","condition": lambda l, a: True},
    {"id": "crm",        "name": "CRM Setup",               "price": "₹10,000 – ₹30,000",  "condition": lambda l, a: a and not a.get("has_crm")},
    {"id": "analytics",  "name": "Analytics Setup",         "price": "₹5,000 – ₹10,000",   "condition": lambda l, a: a and not a.get("has_google_analytics")},
    {"id": "gbs",        "name": "Google Business Setup",   "price": "₹3,000 – ₹8,000",    "condition": lambda l, a: (l.get("reviews") or 0) < 20},
    {"id": "social",     "name": "Social Media Management", "price": "₹8,000 – ₹20,000/mo","condition": lambda l, a: (l.get("social_score") or 0) < 30},
]


def recommend(lead: dict, audit: dict) -> list[dict]:
    """Return list of recommended services with reasoning."""
    recs = []
    for svc in SERVICES:
        try:
            if svc["condition"](lead, audit):
                recs.append({"id": svc["id"], "name": svc["name"], "price": svc["price"]})
        except Exception:
            pass
    return recs[:5]  # top 5
def what_zyro_can_do(lead, audit):
    return recommend(lead, audit)
