"""Sales Intelligence layer for Zyro AI Solutions.
Turns raw lead+audit data into the full sales picture.
All deterministic. No paid APIs. No fake data."""

# ── Zyro full service catalogue ───────────────────────────────────────────────
ZYRO_SERVICES = {
    "AI Chatbot":                        "no_chatbot",
    "AI Voice Agent":                    "always",
    "AI Receptionist":                   "always",
    "Appointment Booking Bot":           "no_booking",
    "CRM":                               "no_crm",
    "Missed-Call Automation":            "always",
    "WhatsApp Automation":               "no_whatsapp",
    "Review Automation":                 "few_reviews",
    "SEO":                               "weak_seo",
    "Google Business Optimization":      "weak_seo",
    "Google Ads":                        "always",
    "Meta Ads":                          "weak_social",
    "Lead Generation":                   "always",
    "Website Upgrade":                   "bad_website",
}

# Per-service monthly revenue opportunity (low, high) in ₹
_SVC_REVENUE = {
    "AI Chatbot":                   (8000,  20000),
    "AI Voice Agent":               (6000,  18000),
    "AI Receptionist":              (6000,  15000),
    "Appointment Booking Bot":      (8000,  25000),
    "CRM":                          (6000,  18000),
    "Missed-Call Automation":       (4000,  12000),
    "WhatsApp Automation":          (5000,  18000),
    "Review Automation":            (3000,  12000),
    "SEO":                          (4000,  15000),
    "Google Business Optimization": (3000,  10000),
    "Google Ads":                   (8000,  30000),
    "Meta Ads":                     (6000,  25000),
    "Lead Generation":              (5000,  20000),
    "Website Upgrade":              (10000, 35000),
}

# Follow-up cadence templates (keyed by gap signal)
_FOLLOWUP_LINES = {
    "no_booking":   ("patients lose them when they can't book online instantly",
                     "an AI Appointment Bot would capture those leads 24/7"),
    "no_whatsapp":  ("most patients prefer WhatsApp over phone calls today",
                     "WhatsApp Automation can handle 80% of queries automatically"),
    "few_reviews":  ("clinics with 100+ reviews get 3× more walk-ins",
                     "our Review Automation gets you reviews on autopilot"),
    "weak_seo":     ("competitors who rank on Google get the calls first",
                     "local SEO puts you at the top of Google Maps in weeks"),
    "no_crm":       ("without a CRM, missed follow-ups mean lost patients",
                     "CRM + Reminder Automation recovers 20-30% more patients"),
    "no_chatbot":   ("a chatbot answers patient questions even at 2 AM",
                     "AI Chatbot converts website visitors into booked appointments"),
    "bad_website":  ("your website is the first impression — it's losing you patients",
                     "a premium website converts 3-5× more visitors"),
    "weak_social":  ("competitors with active social media dominate local mindshare",
                     "Meta Ads + social presence drives consistent new patient flow"),
}


# ── Signal extraction ─────────────────────────────────────────────────────────

def _signals(lead):
    s = set()
    if not lead.get("website"):                                          s.add("no_website")
    if lead.get("audit_error"):                                          s.add("site_down")
    if not lead.get("whatsapp"):                                         s.add("no_whatsapp")
    if not lead.get("has_booking"):                                      s.add("no_booking")
    if not lead.get("has_crm"):                                          s.add("no_crm")
    if not lead.get("has_live_chat") and not lead.get("has_chatbot"):    s.add("no_chatbot")
    if (lead.get("seo_score") or 0) < 70 and lead.get("website") and not lead.get("audit_error"):
                                                                         s.add("weak_seo")
    if lead.get("ssl") == 0 and lead.get("website"):                     s.add("no_ssl")
    if (lead.get("reviews") or 0) < 50:                                  s.add("few_reviews")
    if (lead.get("rating") or 5) < 4.2:                                  s.add("low_rating")
    if not lead.get("email") and lead.get("website"):                    s.add("no_email")
    socials = lead.get("socials") or {}
    active = len([k for k in ("facebook","instagram","linkedin","youtube","twitter") if socials.get(k)])
    if active < 2:                                                        s.add("weak_social")
    if not lead.get("has_google_analytics") and lead.get("website"):     s.add("no_ga")
    if not lead.get("has_facebook_pixel") and lead.get("website"):       s.add("no_pixel")
    if (not lead.get("website") or lead.get("audit_error") or
            (lead.get("seo_score") or 0) < 50):                          s.add("bad_website")
    return s


# ── Maturity ──────────────────────────────────────────────────────────────────

def maturity(lead):
    pts = 0
    if lead.get("website") and not lead.get("audit_error"): pts += 1
    if (lead.get("seo_score") or 0) >= 70:                  pts += 1
    if lead.get("has_booking"):                              pts += 1
    if lead.get("whatsapp"):                                 pts += 1
    if lead.get("has_crm"):                                  pts += 1
    socials = lead.get("socials") or {}
    if len([k for k in socials if socials.get(k)]) >= 2:    pts += 1
    if (lead.get("reviews") or 0) >= 100:                    pts += 1
    if (lead.get("rating") or 0) >= 4.5:                    pts += 1
    if pts <= 2:  return "Basic"
    if pts <= 5:  return "Growing"
    return "Advanced"


# ── Health & Opportunity scores (0-100) ───────────────────────────────────────

def health_score(lead):
    """Digital health 0-100: higher = better established online."""
    pts = 0
    if lead.get("website") and not lead.get("audit_error"): pts += 15
    if (lead.get("seo_score") or 0) >= 70:                  pts += 15
    if lead.get("ssl"):                                      pts += 10
    if lead.get("has_booking"):                              pts += 15
    if lead.get("whatsapp"):                                 pts += 10
    if lead.get("has_crm"):                                  pts += 10
    if lead.get("has_google_analytics"):                     pts += 5
    socials = lead.get("socials") or {}
    pts += min(len([k for k in socials if socials.get(k)]) * 3, 10)
    if (lead.get("reviews") or 0) >= 50:                    pts += 5
    if (lead.get("rating") or 0) >= 4.2:                    pts += 5
    return min(pts, 100)


def opportunity_score(lead):
    """Sales opportunity 0-100: higher = more Zyro can sell."""
    return max(0, 100 - health_score(lead))


# ── Missing / recommended ─────────────────────────────────────────────────────

def missing_and_recommended(lead):
    sig = _signals(lead)
    label = {
        "no_website":"No website","site_down":"Website not working/blocked",
        "no_whatsapp":"No WhatsApp automation","no_booking":"No online booking",
        "no_crm":"No CRM","no_chatbot":"No AI chatbot",
        "weak_seo":"Weak SEO","no_ssl":"No HTTPS security",
        "few_reviews":"Few Google reviews","low_rating":"Low rating",
        "no_email":"No email shown","weak_social":"Weak social media presence",
        "no_ga":"No Google Analytics","no_pixel":"No Facebook Pixel",
        "bad_website":"Poor/broken website",
    }
    missing, recommended = [], []
    for svc, trigger in ZYRO_SERVICES.items():
        if trigger == "always":
            continue
        if trigger in sig:
            lbl = label.get(trigger, trigger)
            recommended.append({"missing": lbl, "service": svc})
            if lbl not in missing:
                missing.append(lbl)
    if not recommended:
        recommended = [
            {"missing":"Missed calls after hours","service":"AI Voice Agent"},
            {"missing":"Manual follow-up","service":"CRM"},
        ]
    return missing, recommended


# ── Service Gap Matrix ────────────────────────────────────────────────────────

_GAP_MATRIX_DEFS = [
    # (display_name, category, signal_that_means_missing, need_level_if_missing)
    ("AI Chatbot",                 "AI Automation", "no_chatbot",   "HIGH"),
    ("AI Voice Agent",             "AI Automation", None,           "MEDIUM"),
    ("AI Receptionist",            "AI Automation", None,           "MEDIUM"),
    ("Appointment Booking Bot",    "AI Automation", "no_booking",   "HIGH"),
    ("CRM",                        "AI Automation", "no_crm",       "HIGH"),
    ("Missed-Call Automation",     "AI Automation", None,           "MEDIUM"),
    ("WhatsApp Automation",        "AI Automation", "no_whatsapp",  "HIGH"),
    ("Review Automation",          "AI Automation", "few_reviews",  "HIGH"),
    ("SEO",                        "Marketing",     "weak_seo",     "HIGH"),
    ("Google Business Optimization","Marketing",    "weak_seo",     "HIGH"),
    ("Meta Ads",                   "Marketing",     "weak_social",  "MEDIUM"),
    ("Google Ads",                 "Marketing",     None,           "MEDIUM"),
    ("Lead Generation",            "Marketing",     None,           "MEDIUM"),
    ("Website Upgrade",            "Website",       "bad_website",  "HIGH"),
]

_NEED_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}


def service_gap_matrix(lead):
    """
    Returns list of dicts per service:
      service, category, status (Missing|Has It|Upsell),
      need_level (HIGH/MEDIUM/LOW), revenue_low, revenue_high, priority (1-3)
    """
    sig = _signals(lead)
    rows = []
    for svc, cat, gap_signal, need_if_missing in _GAP_MATRIX_DEFS:
        lo, hi = _SVC_REVENUE.get(svc, (3000, 10000))
        if gap_signal and gap_signal in sig:
            status   = "Missing"
            need     = need_if_missing
        elif gap_signal is None:
            status   = "Upsell"
            need     = "MEDIUM"
        else:
            status   = "Has It"
            need     = "LOW"
        rows.append({
            "service":     svc,
            "category":    cat,
            "status":      status,
            "need_level":  need,
            "revenue_low": lo,
            "revenue_high":hi,
            "priority":    _NEED_RANK[need],
        })
    rows.sort(key=lambda r: -r["priority"])
    return rows


# ── Revenue Engine ────────────────────────────────────────────────────────────

def revenue_engine(lead):
    """Per-service ₹ opportunity + grand total, only for gaps."""
    sig = _signals(lead)
    breakdown = []
    total_low, total_high = 0, 0

    # Always-on services everyone can benefit from
    always_on = ["AI Voice Agent", "Missed-Call Automation", "Google Ads", "Lead Generation"]

    for svc, trigger in ZYRO_SERVICES.items():
        lo, hi = _SVC_REVENUE.get(svc, (3000, 10000))
        include = (trigger == "always") or (trigger in sig)
        if include:
            breakdown.append({
                "service": svc,
                "low": lo,
                "high": hi,
                "label": f"₹{lo:,} – ₹{hi:,}/mo",
            })
            total_low  += lo
            total_high += hi

    return {
        "breakdown":   breakdown,
        "total_low":   total_low,
        "total_high":  total_high,
        "total_label": f"₹{total_low:,} – ₹{total_high:,}/mo",
    }


# ── How To Sell ───────────────────────────────────────────────────────────────

def how_to_sell(lead, tier):
    sig    = _signals(lead)
    _, rec = missing_and_recommended(lead)
    name   = lead.get("name", "this business")

    # Best service to pitch
    best_svc = rec[0]["service"] if rec else "AI Voice Agent"

    # Upsells (next 2)
    upsells = [r["service"] for r in rec[1:3]] if len(rec) > 1 else ["CRM", "WhatsApp Automation"]

    # Opening line
    gap_text = rec[0]["missing"].lower() if rec else "room for digital growth"
    opening = f"I noticed {name} {gap_text} — we can fix that in under 2 weeks."

    # Pain point
    pain_map = {
        "no_booking":  "Patients who can't book online simply call a competitor who can.",
        "no_whatsapp": "Most patients prefer WhatsApp — if you're not there, they go elsewhere.",
        "few_reviews": "Clinics with more reviews win the local search almost every time.",
        "weak_seo":    "If you don't rank on Google Maps, new patients never find you.",
        "no_crm":      "Without follow-up automation, every missed call is a lost patient.",
        "no_chatbot":  "Your website gets visitors at night when your staff aren't there to answer.",
        "bad_website": "A poor website signals low trust — patients judge in 3 seconds.",
        "weak_social": "Competitors with active social media dominate local awareness.",
        "no_ssl":      "A website without HTTPS shows a 'Not Secure' warning — patients leave.",
    }
    primary_sig = next((s for s in [
        "no_booking","no_whatsapp","no_crm","no_chatbot","few_reviews",
        "weak_seo","bad_website","weak_social","no_ssl"
    ] if s in sig), None)
    pain = pain_map.get(primary_sig, "Digital gaps are costing this business patients every week.")

    # Lead type
    if tier == "HOT":
        lead_type = "High-Priority / Quick Win"
    elif tier == "WARM":
        lead_type = "Medium-Priority / Nurture"
    else:
        lead_type = "Long-Term Upsell"

    # Objection & response
    obj_map = {
        "no_booking":  ("We already take calls for appointments.",
                        "Calls miss patients who are browsing at night or on weekends — an AI bot captures them 24/7."),
        "no_whatsapp": ("We reply on phone already.",
                        "WhatsApp Automation handles 80% of queries instantly so your staff focus on in-clinic care."),
        "few_reviews": ("We get reviews organically.",
                        "Organic is slow. Automation sends a reminder the moment a patient leaves — 3× more reviews in 30 days."),
        "weak_seo":    ("We don't really do online marketing.",
                        "Your competitors do — that's why they show up first. Local SEO is the highest-ROI channel for clinics."),
        "no_crm":      ("We manage patients manually.",
                        "Manual follow-up misses 30-40% of patients. CRM automation recovers them without extra staff cost."),
    }
    objection, response = obj_map.get(primary_sig, (
        "We're not ready for this right now.",
        "Most clinics say that — then a competitor takes their patients. A 2-week pilot costs less than one lost patient."
    ))

    lo, hi = _SVC_REVENUE.get(best_svc, (5000, 20000))

    return {
        "lead_type":    lead_type,
        "main_problem": gap_text,
        "opening_line": opening,
        "pain_point":   pain,
        "best_service": best_svc,
        "upsells":      upsells,
        "deal_value":   f"₹{lo:,} – ₹{hi:,}/mo",
        "objection":    objection,
        "objection_response": response,
    }


# ── Follow-up Engine ──────────────────────────────────────────────────────────

def follow_up_engine(lead):
    sig   = _signals(lead)
    name  = lead.get("name", "the clinic")

    # Pick top 3 gaps for personalised follow-ups
    priority_order = ["no_booking","no_whatsapp","few_reviews","weak_seo",
                      "no_crm","no_chatbot","bad_website","weak_social"]
    top_gaps = [g for g in priority_order if g in sig][:3]

    # Pad with generic gaps if fewer than 3
    generic = [
        ("no_booking",  "missed bookings",         "AI Appointment Bot"),
        ("no_whatsapp", "unanswered WhatsApp queries","WhatsApp Automation"),
        ("few_reviews", "low review count",         "Review Automation"),
    ]
    while len(top_gaps) < 3:
        for g, _, _ in generic:
            if g not in top_gaps:
                top_gaps.append(g)
                break

    msgs = []
    templates = {
        "no_booking": {
            "whatsapp": (
                f"Hi! Just following up — {name} is still missing an online booking system. "
                f"Patients expect to book instantly. We can go live in 10 days. Worth a quick look?"
            ),
            "email_subject": f"Quick follow-up: Online booking for {name}",
            "email_body": (
                f"Hi,\n\nI wanted to follow up on my earlier message. "
                f"{name} still has no online booking — patients searching at night or over the weekend "
                f"simply book the next clinic that lets them. "
                f"We can have an AI Appointment Bot live for you in under 2 weeks.\n\n"
                f"Would a 15-minute call this week work?\n\nBest,\nZyro AI Solutions"
            ),
        },
        "no_whatsapp": {
            "whatsapp": (
                f"Hi again! Most patients today prefer WhatsApp over a phone call. "
                f"{name} is missing a WhatsApp automation setup. We can set this up in days. Interested?"
            ),
            "email_subject": f"WhatsApp Automation opportunity for {name}",
            "email_body": (
                f"Hi,\n\nQuick follow-up: 80% of clinic patients prefer WhatsApp for communication. "
                f"{name} currently handles this manually. Our WhatsApp Automation handles "
                f"queries, reminders, and bookings automatically — saving your staff hours every day.\n\n"
                f"Can I show you a 2-minute demo?\n\nBest,\nZyro AI Solutions"
            ),
        },
        "few_reviews": {
            "whatsapp": (
                f"Hi! One more thing — {name} has fewer reviews than nearby competitors. "
                f"Our Review Automation gets you more Google reviews on autopilot. "
                f"Clinics see 3× more reviews in the first month. Want to try it?"
            ),
            "email_subject": f"More Google reviews for {name} — automated",
            "email_body": (
                f"Hi,\n\nA quick note: {name} has fewer reviews than competing clinics nearby. "
                f"Patients read reviews before booking — more reviews = more patients.\n\n"
                f"Our Review Automation sends a review request the moment a patient visits. "
                f"Most clinics 3× their review count in 30 days.\n\n"
                f"Worth a short call?\n\nBest,\nZyro AI Solutions"
            ),
        },
        "weak_seo": {
            "whatsapp": (
                f"Hi! {name} doesn't rank strongly on Google Maps yet. "
                f"Competitors who do get the calls first. Our Local SEO package changes that in weeks. "
                f"Want to see a quick audit?"
            ),
            "email_subject": f"Google ranking opportunity for {name}",
            "email_body": (
                f"Hi,\n\nFollowing up — {name} currently ranks below competitors on Google Maps. "
                f"That means patients searching nearby find them first.\n\n"
                f"Our Local SEO + Google Business Optimization puts you at the top. "
                f"We've done this for 50+ clinics.\n\nCan I share a free ranking report?\n\nBest,\nZyro AI Solutions"
            ),
        },
        "no_crm": {
            "whatsapp": (
                f"Hi! {name} doesn't have a CRM yet — that means missed follow-ups and lost patients. "
                f"Our CRM Automation fixes this in days. Happy to show you how?"
            ),
            "email_subject": f"Stop losing patients: CRM for {name}",
            "email_body": (
                f"Hi,\n\nA missed follow-up = a lost patient. {name} currently has no CRM, "
                f"which means staff manually track everything — and inevitably miss people.\n\n"
                f"Our CRM + Reminder Automation recovers 20-30% more patients with zero extra staff cost.\n\n"
                f"Quick 15 min call this week?\n\nBest,\nZyro AI Solutions"
            ),
        },
        "no_chatbot": {
            "whatsapp": (
                f"Hi! {name}'s website gets visitors at night when no one is answering. "
                f"An AI Chatbot captures those leads 24/7. Want to see a demo?"
            ),
            "email_subject": f"Capture late-night patient queries for {name}",
            "email_body": (
                f"Hi,\n\nDid you know {name}'s website receives visitors after hours when no one is available?\n\n"
                f"Our AI Chatbot answers their questions and books appointments automatically — "
                f"even at 2 AM. Most clinics recover 15-25% more leads this way.\n\n"
                f"Can I show you a quick demo?\n\nBest,\nZyro AI Solutions"
            ),
        },
        "bad_website": {
            "whatsapp": (
                f"Hi! {name}'s website could be doing a lot more for you. "
                f"A modern, fast website converts 3-5× more visitors. We build them in 2 weeks. Interested?"
            ),
            "email_subject": f"Website upgrade opportunity for {name}",
            "email_body": (
                f"Hi,\n\nYour website is often the first impression patients get of {name}. "
                f"A slow or outdated site loses patients in 3 seconds.\n\n"
                f"We build premium clinic websites that rank on Google, load fast, and convert visitors to bookings. "
                f"Live in 2 weeks.\n\nWant to see examples?\n\nBest,\nZyro AI Solutions"
            ),
        },
        "weak_social": {
            "whatsapp": (
                f"Hi! {name} has a limited social media presence. "
                f"Competitors with active Instagram/Facebook pages get consistent walk-ins. "
                f"We manage this for you. Interested in hearing more?"
            ),
            "email_subject": f"Social media growth for {name}",
            "email_body": (
                f"Hi,\n\nLast follow-up — {name} has limited social media presence compared to "
                f"nearby competitors who post regularly and run Meta Ads.\n\n"
                f"We handle content, ads, and growth — you focus on patients. "
                f"Most clinics see new enquiries within the first 2 weeks.\n\nQuick call?\n\nBest,\nZyro AI Solutions"
            ),
        },
    }

    labels = ["Follow-Up #1", "Follow-Up #2", "Follow-Up #3"]
    for i, gap in enumerate(top_gaps[:3]):
        t = templates.get(gap, {
            "whatsapp": f"Hi! Just checking in on the Zyro AI proposal for {name}. Any questions?",
            "email_subject": f"Following up: Zyro AI Solutions for {name}",
            "email_body": f"Hi,\n\nJust wanted to follow up on our earlier conversation about {name}.\n\nAre you available for a quick call this week?\n\nBest,\nZyro AI Solutions",
        })
        msgs.append({
            "label":         labels[i],
            "gap":           gap,
            "whatsapp":      t["whatsapp"],
            "email_subject": t["email_subject"],
            "email_body":    t["email_body"],
        })
    return msgs


# ── Competitor War Room ───────────────────────────────────────────────────────

def competitor_war_room(lead, competitors):
    """
    competitors: list of dicts from find_competitors() in main.py
    Returns enriched comparison + 'why winning' list for the top rival.
    """
    if not competitors:
        return {"top_competitor": None, "comparison": [], "why_winning": []}

    top = competitors[0]
    why = []
    if (top.get("reviews") or 0) > (lead.get("reviews") or 0):
        why.append(f"More reviews ({top.get('reviews','?')} vs {lead.get('reviews','?')})")
    if (top.get("rating") or 0) > (lead.get("rating") or 0):
        why.append(f"Higher rating ({top.get('rating','?')}★ vs {lead.get('rating','?')}★)")
    if top.get("booking") and not lead.get("has_booking"):
        why.append("Offers online booking — you don't")
    if top.get("whatsapp") and not lead.get("whatsapp"):
        why.append("Has WhatsApp for patients — you don't")
    if top.get("website") and (not lead.get("website") or lead.get("audit_error")):
        why.append("Has a working website — yours is down/missing")
    if not why:
        why.append("Competitor is similarly positioned — slight edge on reviews")

    comparison = []
    dims = [
        ("Reviews",   str(lead.get("reviews") or "?"),  str(top.get("reviews") or "?")),
        ("Rating",    f"{lead.get('rating') or '?'}★",  f"{top.get('rating') or '?'}★"),
        ("Website",   "✓" if (lead.get("website") and not lead.get("audit_error")) else "✗",
                      "✓" if top.get("website") else "✗"),
        ("Booking",   "✓" if lead.get("has_booking") else "✗",
                      "✓" if top.get("booking") else "✗"),
        ("WhatsApp",  "✓" if lead.get("whatsapp") else "✗",
                      "✓" if top.get("whatsapp") else "✗"),
    ]
    for dim, you, them in dims:
        comparison.append({"dimension": dim, "lead": you, "competitor": them})

    return {
        "top_competitor": top.get("name"),
        "competitor_rating": top.get("rating"),
        "competitor_reviews": top.get("reviews"),
        "comparison": comparison,
        "why_winning": why,
        "all_competitors": competitors,
    }


# ── Existing helpers kept intact ──────────────────────────────────────────────

def social_score(lead):
    socials = lead.get("socials") or {}
    weights = {"instagram":30,"facebook":25,"youtube":20,"linkedin":15,"twitter":10}
    return sum(w for k,w in weights.items() if socials.get(k))


def revenue_opportunity(lead):
    low, high = 0, 0
    reasons = []
    sig = _signals(lead)
    if "no_booking"  in sig: low+=8000; high+=25000; reasons.append("No online booking")
    if "no_whatsapp" in sig: low+=5000; high+=18000; reasons.append("No WhatsApp automation")
    if "weak_seo"    in sig: low+=4000; high+=15000; reasons.append("Poor SEO / low visibility")
    if "few_reviews" in sig: low+=3000; high+=12000; reasons.append("Low review count")
    if "no_crm"      in sig: low+=6000; high+=18000; reasons.append("No CRM / follow-up system")
    if "no_chatbot"  in sig: low+=4000; high+=12000; reasons.append("No AI chatbot")
    if "no_website" in sig or "site_down" in sig:
        low+=10000; high+=30000; reasons.append("No working website")
    if low == 0:
        return {"range":"₹5,000 – ₹15,000","reasons":["Minor optimisation upside only"]}
    return {"range":f"₹{low:,} – ₹{high:,}/mo","reasons":reasons}


_ACTION_ORDER = [
    ("no_booking","AI Appointment Booking Bot"),
    ("no_whatsapp","WhatsApp Automation"),
    ("few_reviews","Review Collection Automation"),
    ("weak_seo","Local SEO + Google Business"),
    ("no_crm","CRM + Reminder Automation"),
    ("no_chatbot","AI Chatbot"),
    ("no_website","Clinic Website Development"),
    ("site_down","Website Rebuild"),
    ("weak_social","Social Media Management"),
    ("no_email","Lead-Capture + Email Automation"),
]

def action_plan(lead):
    sig = _signals(lead)
    plan = [svc for trig,svc in _ACTION_ORDER if trig in sig]
    if not plan:
        plan = ["AI Voice Agent (24/7 receptionist)","CRM + Reminder Automation"]
    return plan[:4]


_MATRIX = [
    ("Website",          lambda l: bool(l.get("website")) and not l.get("audit_error")),
    ("SEO",              lambda l: (l.get("seo_score") or 0) >= 70),
    ("AI Chatbot",       lambda l: bool(l.get("has_live_chat") or l.get("has_chatbot"))),
    ("AI Voice Agent",   lambda l: False),
    ("WhatsApp",         lambda l: bool(l.get("whatsapp"))),
    ("CRM",              lambda l: bool(l.get("has_crm"))),
    ("Booking System",   lambda l: bool(l.get("has_booking"))),
    ("Review Automation",lambda l: False),
    ("Google Ads",       lambda l: False),
    ("Lead Generation",  lambda l: False),
    ("Google Analytics", lambda l: bool(l.get("has_google_analytics"))),
    ("Facebook Pixel",   lambda l: bool(l.get("has_facebook_pixel"))),
]

def services_matrix(lead):
    return [{"service":name,"has":bool(fn(lead)),"zyro":True} for name,fn in _MATRIX]


def strengths(lead):
    out = []
    if (lead.get("rating") or 0) >= 4.5:      out.append(f"Strong reputation ({lead['rating']}★)")
    if (lead.get("reviews") or 0) >= 100:      out.append(f"High review count ({lead['reviews']})")
    if lead.get("has_booking"):                 out.append("Already offers online booking")
    if lead.get("whatsapp"):                    out.append("WhatsApp available")
    if (lead.get("seo_score") or 0) >= 70:     out.append("Good website SEO")
    if lead.get("has_crm"):                     out.append(f"CRM in use ({lead.get('crm_detected','Yes')})")
    if lead.get("has_google_analytics"):        out.append("Google Analytics installed")
    if lead.get("has_facebook_pixel"):          out.append("Facebook Pixel installed")
    if lead.get("has_live_chat"):               out.append("Live chat / chatbot present")
    socials = lead.get("socials") or {}
    if len([k for k in socials if socials.get(k)]) >= 3:
        out.append("Active on social media")
    return out or ["No standout digital strengths yet"]


def weaknesses(lead):
    missing, _ = missing_and_recommended(lead)
    return missing or ["No major weaknesses — mostly upsell territory"]


def why_contact(lead, tier):
    sig = _signals(lead)
    bits = []
    if "no_website"  in sig: bits.append("has no website")
    if "site_down"   in sig: bits.append("their website isn't working")
    if "no_booking"  in sig: bits.append("can't take bookings online")
    if "no_whatsapp" in sig: bits.append("has no WhatsApp automation")
    if "no_crm"      in sig: bits.append("has no CRM or follow-up system")
    if "no_chatbot"  in sig: bits.append("has no AI chatbot")
    if "weak_seo"    in sig: bits.append("ranks poorly on Google")
    if "few_reviews" in sig: bits.append("has few reviews")
    if "weak_social" in sig: bits.append("has weak social presence")
    if not bits:
        return ("This business is well set up — approach as an upsell for "
                "AI voice agent and CRM automation to save staff time.")
    gap_txt = ", ".join(bits[:3])
    return (f"This {tier} lead {gap_txt} — clear openings for Zyro to add immediate value.")


CHECKLIST_ITEMS = [
    ("Website",        lambda l: bool(l.get("website")) and not l.get("audit_error")),
    ("Booking system", lambda l: bool(l.get("has_booking"))),
    ("WhatsApp",       lambda l: bool(l.get("whatsapp"))),
    ("SEO (good)",     lambda l: (l.get("seo_score") or 0) >= 70),
    ("CRM",            lambda l: bool(l.get("has_crm"))),
    ("Google Analytics",lambda l: bool(l.get("has_google_analytics"))),
    ("Facebook Pixel", lambda l: bool(l.get("has_facebook_pixel"))),
    ("Live Chat",      lambda l: bool(l.get("has_live_chat"))),
    ("Facebook",       lambda l: bool((l.get("socials") or {}).get("facebook"))),
    ("Instagram",      lambda l: bool((l.get("socials") or {}).get("instagram"))),
    ("YouTube",        lambda l: bool((l.get("socials") or {}).get("youtube"))),
    ("Google reviews", lambda l: (l.get("reviews") or 0) >= 50),
    ("Strong rating",  lambda l: (l.get("rating") or 0) >= 4.5),
]

def checklist(lead):
    return [{"item":name,"has":bool(fn(lead))} for name,fn in CHECKLIST_ITEMS]


def outreach_email(lead, tier):
    name = lead.get("name","your clinic")
    _, recs = missing_and_recommended(lead)
    offer = recs[0]["service"] if recs else "AI automation"
    gaps = weaknesses(lead)
    gap_line = gaps[0].lower() if gaps and "no major" not in gaps[0].lower() else "a few quick wins online"
    subject = f"Quick idea for {name}"
    body = (f"Hi,\n\nI was looking at {name} online and noticed {gap_line}. "
            f"At Zyro AI Solutions we help clinics fix exactly this — the fastest win for you "
            f"would be a {offer}.\n\nIt usually pays for itself within a couple of months in recovered "
            f"patients. Could I send over a short 2-minute demo video?\n\nBest,\nZyro AI Solutions")
    return {"subject": subject, "body": body}


def outreach_linkedin(lead):
    name = lead.get("name","your clinic")
    _, recs = missing_and_recommended(lead)
    offer = recs[0]["service"] if recs else "AI automation"
    return (f"Hi! I run Zyro AI Solutions — we set up {offer.lower()} for clinics like {name}. "
            f"Saw your profile and thought there might be a quick win here. Open to a short chat?")


def full_intelligence(lead, tier):
    competitors = lead.get("competitors") or []
    return {
        "maturity":             maturity(lead),
        "health_score":         health_score(lead),
        "opportunity_score":    opportunity_score(lead),
        "missing_services":     missing_and_recommended(lead)[0],
        "recommended_services": missing_and_recommended(lead)[1],
        "strengths":            strengths(lead),
        "weaknesses":           weaknesses(lead),
        "why_contact":          why_contact(lead, tier),
        "checklist":            checklist(lead),
        "social_score":         social_score(lead),
        "revenue_opportunity":  revenue_opportunity(lead),
        "revenue_engine":       revenue_engine(lead),
        "action_plan":          action_plan(lead),
        "services_matrix":      services_matrix(lead),
        "service_gap_matrix":   service_gap_matrix(lead),
        "how_to_sell":          how_to_sell(lead, tier),
        "follow_up_engine":     follow_up_engine(lead),
        "competitor_war_room":  competitor_war_room(lead, competitors),
        "email_outreach":       outreach_email(lead, tier),
        "linkedin_message":     outreach_linkedin(lead),
    }
