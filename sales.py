"""Stage 3 — sales intelligence derived from lead + audit data.
Deterministic (no AI key needed). Produces deal size, best offer,
close probability, call script and WhatsApp message per lead."""

def _gaps(lead):
    g = []
    if not lead.get("website"): g.append("no_website")
    if lead.get("audit_error"): g.append("site_down")
    if not lead.get("whatsapp"): g.append("no_whatsapp")
    if not lead.get("has_booking"): g.append("no_booking")
    if (lead.get("seo_score") or 100) < 70: g.append("weak_seo")
    if (lead.get("reviews") or 0) < 50: g.append("few_reviews")
    if (lead.get("rating") or 5) < 4.2: g.append("low_rating")
    if lead.get("ssl") == 0 and lead.get("website"): g.append("no_ssl")
    return g

def deal_size(lead):
    g = _gaps(lead)
    if "no_website" in g:      return "₹50,000 – ₹95,000"
    if "site_down" in g:       return "₹40,000 – ₹80,000"
    if "weak_seo" in g and "no_booking" in g: return "₹35,000 – ₹70,000"
    if "no_booking" in g or "no_whatsapp" in g: return "₹25,000 – ₹55,000"
    return "₹15,000 – ₹35,000"

def best_offer(lead):
    g = _gaps(lead)
    if "no_website" in g:   return "Website + Google Business setup"
    if "no_booking" in g:   return "AI Appointment Booking Bot"
    if "no_whatsapp" in g:  return "WhatsApp Booking & Follow-up Automation"
    if "weak_seo" in g:     return "Local SEO + Website Optimization"
    if "few_reviews" in g:  return "Google Review Automation"
    return "AI Voice Agent for missed calls"

def close_probability(lead):
    # more gaps + reachable owner (has phone) => higher chance
    score = 30 + 7 * len(_gaps(lead))
    if lead.get("phone"): score += 12
    if lead.get("email"): score += 8
    return f"{min(score, 92)}%"

def call_script(lead):
    name = lead.get("name", "your clinic")
    rating = lead.get("rating")
    reviews = lead.get("reviews")
    offer = best_offer(lead)
    g = _gaps(lead)
    pain = []
    if "no_booking" in g: pain.append("patients can't book online")
    if "no_whatsapp" in g: pain.append("there's no WhatsApp for quick enquiries")
    if "weak_seo" in g: pain.append("the site isn't ranking well locally")
    if "few_reviews" in g: pain.append(f"you have only {reviews} Google reviews")
    pain_txt = ", and ".join(pain[:2]) if pain else "there's room to attract more patients online"
    star = f" Your {rating}\u2605 rating is strong, but" if rating else ""
    return (f"Hi, am I speaking with someone from {name}? This is from Zyro AI Solutions.\n\n"
            f"I was looking at {name} online.{star} I noticed {pain_txt}.\n\n"
            f"We help clinics fix exactly this \u2014 the quickest win for you would be a {offer}. "
            f"It usually pays for itself within a couple of months in recovered patients.\n\n"
            f"Could I show you a 5-minute demo this week?")

def whatsapp_msg(lead):
    name = lead.get("name", "your clinic")
    offer = best_offer(lead)
    return (f"Hi 👋 this is Zyro AI. Saw {name} online \u2014 great reviews! "
            f"Quick one: we set up {offer.lower()} for clinics like yours so you stop "
            f"losing after-hours enquiries. Want a 1-min demo?")

def sales_pack(lead):
    return {
        "deal_size": deal_size(lead),
        "best_offer": best_offer(lead),
        "close_probability": close_probability(lead),
        "call_script": call_script(lead),
        "whatsapp_message": whatsapp_msg(lead),
    }