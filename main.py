"""
Zyro OS — Full Stack Business Discovery & Intelligence Platform
Combines V4 working features + V5 architecture improvements
SQLite-based, no Docker required
"""

import os, json, sqlite3, csv, io, hashlib, math
from contextlib import closing
from datetime import datetime
from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
import requests

from audit import audit_website
from recommend import what_zyro_can_do
from sales import sales_pack
from intelligence import full_intelligence, maturity
from pagespeed import speed_score

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or GOOGLE_API_KEY
DB_PATH        = "/tmp/zyro.db"
BASE_DIR       = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="Zyro OS", version="5.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Serve static files
if os.path.isdir(os.path.join(BASE_DIR, "static")):
    app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
@app.get("/dashboard.html")
def serve_dashboard():
    return FileResponse(os.path.join(BASE_DIR, "dashboard.html"))

@app.get("/")
def serve_root():
    return FileResponse(os.path.join(BASE_DIR, "dashboard.html"))

# ─────────────────────── DATABASE ───────────────────────

def init_db():
    with closing(sqlite3.connect(DB_PATH)) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS leads (
            place_id TEXT PRIMARY KEY,
            name TEXT, industry TEXT, phone TEXT, website TEXT,
            address TEXT, rating REAL, reviews INTEGER,
            lat REAL, lng REAL, maps_url TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

        # Add all columns if they don't exist
        cols = {
            "email":"TEXT","whatsapp":"INTEGER","ssl":"INTEGER","seo_score":"INTEGER",
            "socials":"TEXT","seo_issues":"TEXT","has_booking":"INTEGER","audit_error":"TEXT",
            "priority_score":"INTEGER","tier":"TEXT","deal_size":"TEXT","best_offer":"TEXT",
            "close_probability":"TEXT","call_script":"TEXT","whatsapp_message":"TEXT",
            "zyro_services":"TEXT","all_phones":"TEXT","whatsapp_number":"TEXT",
            "is_market_leader":"INTEGER","doctor_name":"TEXT","contact_page":"TEXT",
            "speed_score":"INTEGER","maturity":"TEXT","strengths":"TEXT","weaknesses":"TEXT",
            "why_contact":"TEXT","checklist":"TEXT","competitors":"TEXT","social_score":"INTEGER",
            "revenue_opportunity":"TEXT","action_plan":"TEXT","services_matrix":"TEXT",
            "email_outreach":"TEXT","linkedin_message":"TEXT",
            "has_google_analytics":"INTEGER","has_facebook_pixel":"INTEGER",
            "has_live_chat":"INTEGER","has_crm":"INTEGER","crm_detected":"TEXT",
            "health_score":"INTEGER","opportunity_score":"INTEGER",
            "revenue_engine":"TEXT","service_gap_matrix":"TEXT",
            "how_to_sell":"TEXT","follow_up_engine":"TEXT","competitor_war_room":"TEXT",
            "source":"TEXT",
        }
        for col, decl in cols.items():
            try: db.execute(f"ALTER TABLE leads ADD COLUMN {col} {decl}")
            except sqlite3.OperationalError: pass

        # CRM table
        db.execute("""CREATE TABLE IF NOT EXISTS crm_leads (
            id TEXT PRIMARY KEY,
            place_id TEXT REFERENCES leads(place_id),
            stage TEXT DEFAULT 'new',
            owner TEXT,
            deal_value REAL,
            notes TEXT,
            next_follow_up TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

        db.execute("""CREATE TABLE IF NOT EXISTS crm_activities (
            id TEXT PRIMARY KEY,
            crm_lead_id TEXT REFERENCES crm_leads(id),
            type TEXT,
            content TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

        db.commit()

init_db()

# ─────────────────────── HELPERS ───────────────────────

def point_in_polygon(lat, lng, polygon):
    if not polygon or len(polygon) < 3: return True
    inside = False
    n = len(polygon); j = n - 1
    for i in range(n):
        yi, xi = polygon[i][0], polygon[i][1]
        yj, xj = polygon[j][0], polygon[j][1]
        if ((yi > lat) != (yj > lat)) and \
           (lng < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside

def polygon_centroid_and_radius(polygon):
    lats = [p[0] for p in polygon]; lngs = [p[1] for p in polygon]
    c_lat = sum(lats)/len(lats); c_lng = sum(lngs)/len(lngs)
    def hav(lat1,lng1,lat2,lng2):
        R=6371; dlat=math.radians(lat2-lat1); dlng=math.radians(lng2-lng1)
        a=math.sin(dlat/2)**2+math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlng/2)**2
        return 2*R*math.asin(math.sqrt(a))
    radius = max(hav(c_lat,c_lng,p[0],p[1]) for p in polygon)
    return c_lat, c_lng, max(radius, 0.3)

def priority(lead, a):
    s = 0
    if not lead.get("website"):              s += 50
    elif a and not a.get("reachable"):       s += 30
    if a and not a.get("whatsapp"):          s += 15
    if a and not a.get("has_booking"):       s += 15
    if a and a.get("seo_score",100) < 50:   s += 15
    if a and not a.get("ssl"):               s += 10
    if (lead.get("reviews") or 0) < 50:     s += 15
    if (lead.get("rating") or 5) < 4.0:     s += 10
    s = min(s, 100)
    return s, ("HOT" if s>=70 else "WARM" if s>=40 else "LOW")

def find_competitors(this_lead, all_leads):
    others = [l for l in all_leads if l["place_id"] != this_lead["place_id"]]
    others.sort(key=lambda l: (l.get("reviews") or 0), reverse=True)
    return [{"name":c.get("name"),"rating":c.get("rating"),"reviews":c.get("reviews"),
             "website":bool(c.get("website")),"whatsapp":bool(c.get("whatsapp")),
             "booking":bool(c.get("has_booking"))} for c in others[:3]]

def leader_score(l):
    s = (l.get("reviews") or 0)
    if (l.get("rating") or 0) >= 4.5: s += 200
    if l.get("has_booking"):           s += 100
    if l.get("whatsapp"):              s += 50
    if (l.get("seo_score") or 0) >= 70: s += 50
    return s

def serialize_lead(row: dict) -> dict:
    json_fields = ["socials","seo_issues","zyro_services","all_phones","strengths",
                   "weaknesses","checklist","competitors","revenue_opportunity",
                   "action_plan","services_matrix","email_outreach","revenue_engine",
                   "service_gap_matrix","how_to_sell","follow_up_engine","competitor_war_room"]
    for f in json_fields:
        if row.get(f):
            try: row[f] = json.loads(row[f])
            except: pass
    return row

# ─────────────────────── GOOGLE SEARCH ───────────────────────

def google_search(query, n, lat=None, lng=None, radius_km=5):
    if not GOOGLE_API_KEY:
        raise HTTPException(500, "GOOGLE_API_KEY not set in .env")
    payload = {"textQuery": query, "maxResultCount": min(n, 20)}
    if lat and lng:
        payload["locationBias"] = {
            "circle": {"center": {"latitude": lat, "longitude": lng},
                       "radius": radius_km * 1000}}
    r = requests.post(
        "https://places.googleapis.com/v1/places:searchText",
        headers={"Content-Type":"application/json","X-Goog-Api-Key":GOOGLE_API_KEY,
            "X-Goog-FieldMask": ",".join(["places.id","places.displayName","places.formattedAddress",
                "places.nationalPhoneNumber","places.websiteUri","places.rating",
                "places.userRatingCount","places.location","places.googleMapsUri"])},
        json=payload, timeout=30)
    if r.status_code != 200:
        raise HTTPException(502, f"Google error {r.status_code}: {r.text[:300]}")
    return r.json().get("places", [])

def osm_search(query, lat, lng, radius_km=5, count=20):
    """Free OpenStreetMap fallback via Overpass API"""
    radius_m = int(radius_km * 1000)
    overpass_q = f"""
    [out:json][timeout:25];
    (node["name"](around:{radius_m},{lat},{lng});
     way["name"](around:{radius_m},{lat},{lng}););
    out center {count};
    """
    try:
        r = requests.post("https://overpass-api.de/api/interpreter",
            data={"data": overpass_q},
            headers={"User-Agent":"ZyroOS/5.0"}, timeout=20)
        if r.status_code != 200: return []
        results = []
        for el in r.json().get("elements", [])[:count]:
            tags = el.get("tags", {})
            name = tags.get("name")
            if not name: continue
            center = el.get("center") or el
            results.append({
                "id": f"osm_{el.get('type','')}_{el.get('id','')}",
                "displayName": {"text": name},
                "formattedAddress": ", ".join(filter(None,[
                    tags.get("addr:housenumber",""), tags.get("addr:street",""),
                    tags.get("addr:city",""), tags.get("addr:state","")])),
                "nationalPhoneNumber": tags.get("phone", tags.get("contact:phone","")),
                "websiteUri": tags.get("website", tags.get("contact:website","")),
                "googleMapsUri": "",
                "location": {"latitude": center.get("lat"), "longitude": center.get("lon")},
            })
        return results
    except Exception:
        return []

# ─────────────────────── PROCESS PIPELINE ───────────────────────

def process_places(places, business_type, include_competitors, include_speed, db, source="google_places"):
    out = []
    for p in places:
        loc = p.get("location", {}) or {}
        lead = {
            "place_id": p.get("id"),
            "name":     (p.get("displayName") or {}).get("text", ""),
            "industry": business_type,
            "phone":    p.get("nationalPhoneNumber", ""),
            "website":  p.get("websiteUri", ""),
            "address":  p.get("formattedAddress", ""),
            "rating":   p.get("rating"),
            "reviews":  p.get("userRatingCount"),
            "lat":      loc.get("latitude"),
            "lng":      loc.get("longitude"),
            "maps_url": p.get("googleMapsUri", ""),
            "source":   source,
        }

        a = audit_website(lead["website"])
        all_phones = []
        if lead["phone"]: all_phones.append(lead["phone"])
        for ph in (a.get("all_phones") or []):
            if ph not in all_phones: all_phones.append(ph)

        lead.update({
            "email":                a.get("email"),
            "whatsapp":             int(bool(a.get("whatsapp"))),
            "whatsapp_number":      a.get("whatsapp_number"),
            "all_phones":           all_phones,
            "doctor_name":          a.get("doctor_name"),
            "contact_page":         a.get("contact_page"),
            "ssl":                  int(bool(a.get("ssl"))),
            "seo_score":            a.get("seo_score"),
            "socials":              a.get("socials"),
            "seo_issues":           a.get("seo_issues"),
            "has_booking":          int(bool(a.get("has_booking"))),
            "audit_error":          a.get("error"),
            "has_google_analytics": int(bool(a.get("has_google_analytics"))),
            "has_facebook_pixel":   int(bool(a.get("has_facebook_pixel"))),
            "has_live_chat":        int(bool(a.get("has_live_chat"))),
            "has_crm":              int(bool(a.get("has_crm"))),
            "crm_detected":         a.get("crm_detected"),
            "speed_score":          speed_score(lead["website"]) if include_speed else None,
        })

        score, tier = priority(lead, a)
        lead["priority_score"] = score
        lead["tier"]           = tier
        lead["competitors"]    = []
        lead["is_market_leader"] = 0

        sp       = sales_pack(lead)
        services = what_zyro_can_do(lead)
        intel    = full_intelligence(lead, tier)

        lead["_sp"] = sp; lead["_services"] = services; lead["_intel"] = intel
        out.append(lead)

    # Mark market leader
    if out:
        best = max(out, key=leader_score)
        for l in out: l["is_market_leader"] = 1 if l is best else 0

    # Competitors
    for l in out:
        l["competitors"] = find_competitors(l, out) if include_competitors else []

    # Persist
    for lead in out:
        sp = lead.pop("_sp"); services = lead.pop("_services"); intel = lead.pop("_intel")
        try:
            db.execute("""INSERT INTO leads
                (place_id,name,industry,phone,website,address,rating,reviews,lat,lng,maps_url,
                 email,whatsapp,whatsapp_number,all_phones,ssl,seo_score,socials,seo_issues,
                 has_booking,audit_error,priority_score,tier,deal_size,best_offer,
                 close_probability,call_script,whatsapp_message,zyro_services,is_market_leader,
                 doctor_name,contact_page,speed_score,maturity,strengths,weaknesses,
                 why_contact,checklist,competitors,social_score,revenue_opportunity,
                 action_plan,services_matrix,email_outreach,linkedin_message,
                 has_google_analytics,has_facebook_pixel,has_live_chat,has_crm,crm_detected,
                 health_score,opportunity_score,revenue_engine,service_gap_matrix,
                 how_to_sell,follow_up_engine,competitor_war_room,source)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(place_id) DO UPDATE SET
                 phone=excluded.phone,email=excluded.email,whatsapp=excluded.whatsapp,
                 seo_score=excluded.seo_score,has_booking=excluded.has_booking,
                 priority_score=excluded.priority_score,tier=excluded.tier,
                 deal_size=excluded.deal_size,best_offer=excluded.best_offer,
                 call_script=excluded.call_script,whatsapp_message=excluded.whatsapp_message,
                 zyro_services=excluded.zyro_services,is_market_leader=excluded.is_market_leader,
                 maturity=excluded.maturity,strengths=excluded.strengths,weaknesses=excluded.weaknesses,
                 why_contact=excluded.why_contact,checklist=excluded.checklist,
                 competitors=excluded.competitors,revenue_opportunity=excluded.revenue_opportunity,
                 action_plan=excluded.action_plan,services_matrix=excluded.services_matrix,
                 email_outreach=excluded.email_outreach,linkedin_message=excluded.linkedin_message,
                 health_score=excluded.health_score,opportunity_score=excluded.opportunity_score,
                 how_to_sell=excluded.how_to_sell,follow_up_engine=excluded.follow_up_engine,
                 competitor_war_room=excluded.competitor_war_room,source=excluded.source""",
                (lead["place_id"],lead["name"],lead["industry"],lead["phone"],lead["website"],
                 lead["address"],lead["rating"],lead["reviews"],lead["lat"],lead["lng"],lead["maps_url"],
                 lead["email"],lead["whatsapp"],lead.get("whatsapp_number"),
                 json.dumps(lead.get("all_phones") or []),
                 lead["ssl"],lead["seo_score"],
                 json.dumps(lead["socials"] or {}),json.dumps(lead["seo_issues"] or []),
                 lead["has_booking"],lead["audit_error"],lead["priority_score"],lead["tier"],
                 sp["deal_size"],sp["best_offer"],sp["close_probability"],sp["call_script"],
                 sp["whatsapp_message"],json.dumps(services),lead["is_market_leader"],
                 lead.get("doctor_name"),lead.get("contact_page"),lead.get("speed_score"),
                 intel["maturity"],json.dumps(intel["strengths"]),json.dumps(intel["weaknesses"]),
                 intel["why_contact"],json.dumps(intel["checklist"]),
                 json.dumps(lead.get("competitors") or []),
                 intel["social_score"],json.dumps(intel["revenue_opportunity"]),
                 json.dumps(intel["action_plan"]),json.dumps(intel["services_matrix"]),
                 json.dumps(intel["email_outreach"]),intel["linkedin_message"],
                 lead["has_google_analytics"],lead["has_facebook_pixel"],
                 lead["has_live_chat"],lead["has_crm"],lead.get("crm_detected"),
                 intel["health_score"],intel["opportunity_score"],
                 json.dumps(intel["revenue_engine"]),json.dumps(intel["service_gap_matrix"]),
                 json.dumps(intel["how_to_sell"]),json.dumps(intel["follow_up_engine"]),
                 json.dumps(intel["competitor_war_room"]),lead.get("source","google_places")))
        except Exception as e:
            pass  # skip bad rows silently

        lead.update(sp); lead["zyro_services"] = services; lead.update(intel)

    db.commit()
    out.sort(key=lambda x: x["priority_score"], reverse=True)
    return out

# ─────────────────────── ROUTES ───────────────────────

@app.get("/")
def health():
    return {"status": "ok", "version": "5.0.0", "key_loaded": bool(GOOGLE_API_KEY)}


class MultiDiscoverRequest(BaseModel):
    business_type: str
    district:      str  = ""
    state:         str  = ""
    count:         int  = 20
    connectors:    list[str] = ["google_places"]
    include_speed: bool = False

@app.post("/discover-multi")
def discover_multi(req: MultiDiscoverRequest):
    """
    Master discovery endpoint — search across Google, IndiaMART,
    FSSAI, Justdial and OpenStreetMap in one call.
    """
    location = ", ".join(filter(None, [req.district, req.state])) or req.district
    query    = f"{req.business_type} in {location}" if location else req.business_type
    all_raw  = []

    # ── Google Places ──
    if "google_places" in req.connectors and GOOGLE_API_KEY:
        try:
            places = google_search(query, req.count)
            all_raw.extend(places)
        except Exception:
            pass

    # ── OpenStreetMap ──
    if "openstreetmap" in req.connectors and location:
        try:
            geo = requests.get("https://nominatim.openstreetmap.org/search",
                params={"q": location, "format": "json", "limit": 1},
                headers={"User-Agent": "ZyroOS/5.0"}, timeout=8)
            if geo.status_code == 200 and geo.json():
                res = geo.json()[0]
                osm = osm_search(req.business_type, float(res["lat"]),
                                 float(res["lon"]), 10, req.count)
                all_raw.extend(osm)
        except Exception:
            pass

    # ── IndiaMART ──
    if "indiamart" in req.connectors:
        try:
            from connectors.indiamart import search_indiamart, search_indiamart_api
            im = search_indiamart_api(req.business_type, location, req.count)
            if not im:
                im = search_indiamart(req.business_type, location, req.count)
            # Convert to places-like format
            for b in im:
                all_raw.append(_biz_to_place(b))
        except Exception as e:
            pass

    # ── FSSAI ──
    if "fssai" in req.connectors:
        try:
            from connectors.fssai import search_fssai
            fs = search_fssai(req.business_type, location, req.count)
            for b in fs:
                all_raw.append(_biz_to_place(b))
        except Exception:
            pass

    # ── Justdial ──
    if "justdial" in req.connectors:
        try:
            from connectors.justdial import search_justdial
            jd = search_justdial(req.business_type, location, req.count)
            for b in jd:
                all_raw.append(_biz_to_place(b))
        except Exception:
            pass

    # Deduplicate by name similarity
    all_raw = _deduplicate(all_raw, req.count * 2)

    with closing(sqlite3.connect(DB_PATH)) as db:
        out = process_places(all_raw[:req.count * 2], req.business_type,
                             False, req.include_speed, db)

    return {"found": len(out), "query": query, "leads": out}


def _biz_to_place(b: dict) -> dict:
    """Convert generic business dict to Google Places-like format."""
    return {
        "id":               b.get("place_id") or f"ext_{hash(b.get('name','')) & 0xFFFFFF}",
        "displayName":      {"text": b.get("name", "")},
        "formattedAddress": b.get("address", ""),
        "nationalPhoneNumber": b.get("phone", ""),
        "websiteUri":       b.get("website", ""),
        "rating":           b.get("google_rating"),
        "userRatingCount":  b.get("google_reviews"),
        "googleMapsUri":    b.get("maps_url", ""),
        "location":         {"latitude": b.get("lat"), "longitude": b.get("lng")},
        "_source":          b.get("source", "external"),
        "_email":           b.get("email", ""),
    }


def _deduplicate(places: list, limit: int) -> list:
    """Remove duplicate businesses by name similarity."""
    seen = set()
    out  = []
    for p in places:
        name = ((p.get("displayName") or {}).get("text") or "").lower().strip()
        key  = name[:30]  # first 30 chars as dedup key
        if key and key not in seen:
            seen.add(key)
            out.append(p)
        if len(out) >= limit:
            break
    return out


@app.get("/dashboard")
def dashboard():
    p = os.path.join(BASE_DIR, "templates", "dashboard.html")

    print("=" * 60)
    print("SERVING:", p)
    print("=" * 60)

    with open(p, "r", encoding="utf-8") as f:
        print(f.read()[:300])   # prints first 300 characters

    return FileResponse(p)
# ── AI Search (Gemini) ──

class AIParseRequest(BaseModel):
    context: str
    count:   int = 30

@app.post("/ai-parse")
def ai_parse(req: AIParseRequest):
    if not GEMINI_API_KEY:
        raise HTTPException(500, "GEMINI_API_KEY not set in .env")

    prompt = f"""You are a business lead discovery assistant.
The user has provided a requirement (prompt) and/or filled manual fields.
Combine ALL the information to extract the best search parameters.
Return ONLY valid JSON, no explanation, no markdown.

{req.context}

Return this exact JSON:
{{
  "business_type": "best search term combining prompt + manual input",
  "district": "city/district — use manual field if given, else extract from prompt, else empty",
  "state": "state — use manual field if given, else extract from prompt, else empty",
  "count": {req.count},
  "filters": {{
    "no_website": true or false,
    "no_whatsapp": true or false,
    "low_reviews": true or false,
    "tier": "HOT" or "WARM" or "ALL"
  }},
  "pitch_angle": "one line: what service should Zyro pitch to these businesses",
  "connectors": ["google_places"]
}}"""

    try:
        r = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
            params={"key": GEMINI_API_KEY},
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        clean = text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except requests.exceptions.HTTPError:
        raise HTTPException(502, f"Gemini API error: {r.text}")
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise HTTPException(502, f"Could not parse Gemini response: {e}")

# ── Discovery ──

class DiscoverRequest(BaseModel):
    business_type:      str
    area:               str  = ""
    distance_km:        float = 5
    count:              int   = 15
    include_competitors:bool  = False
    include_speed:      bool  = False
    connectors:         list[str] = ["google_places"]

@app.post("/discover")
def discover(req: DiscoverRequest):
    query = f"{req.business_type} in {req.area}" if req.area else req.business_type
    all_places = []

    if "google_places" in req.connectors:
        try:
            places = google_search(query, req.count)
            all_places.extend(places)
        except HTTPException as e:
            if "openstreetmap" not in req.connectors:
                raise

    if "openstreetmap" in req.connectors or not all_places:
        # Try to geocode area via Nominatim
        try:
            r = requests.get("https://nominatim.openstreetmap.org/search",
                params={"q": req.area or req.business_type, "format": "json", "limit": 1},
                headers={"User-Agent": "ZyroOS/5.0"}, timeout=10)
            if r.status_code == 200 and r.json():
                res = r.json()[0]
                osm = osm_search(req.business_type, float(res["lat"]), float(res["lon"]),
                                 req.distance_km, req.count)
                # Deduplicate by name
                existing_names = {p.get("displayName",{}).get("text","").lower() for p in all_places}
                for p in osm:
                    if (p.get("displayName",{}).get("text","") or "").lower() not in existing_names:
                        p["_source"] = "openstreetmap"
                        all_places.append(p)
        except Exception:
            pass

    with closing(sqlite3.connect(DB_PATH)) as db:
        out = process_places(all_places[:req.count], req.business_type,
                             req.include_competitors, req.include_speed, db)
    return {"found": len(out), "query": query, "leads": out}

class DiscoverAreaRequest(BaseModel):
    business_type:      str
    polygon:            list
    count:              int  = 20
    include_competitors:bool = False
    include_speed:      bool = False

@app.post("/discover-by-area")
def discover_by_area(req: DiscoverAreaRequest):
    if not req.polygon or len(req.polygon) < 3:
        raise HTTPException(400, "Need at least 3 polygon points")
    c_lat, c_lng, radius_km = polygon_centroid_and_radius(req.polygon)
    raw = google_search(f"{req.business_type}", req.count * 2, c_lat, c_lng, radius_km)
    inside = [p for p in raw if point_in_polygon(
        (p.get("location") or {}).get("latitude") or 0,
        (p.get("location") or {}).get("longitude") or 0,
        req.polygon)][:req.count]
    with closing(sqlite3.connect(DB_PATH)) as db:
        out = process_places(inside, req.business_type,
                             req.include_competitors, req.include_speed, db)
    return {"found": len(out), "center": {"lat": c_lat, "lng": c_lng}, "leads": out}

# ── Leads CRUD ──

@app.get("/leads")
def leads(
    tier: str = Query(None),
    industry: str = Query(None),
    city: str = Query(None),
    search: str = Query(None),
    source: str = Query(None),
    skip: int = 0,
    limit: int = 500,
):
    with closing(sqlite3.connect(DB_PATH)) as db:
        db.row_factory = sqlite3.Row
        q = "SELECT * FROM leads WHERE 1=1"
        params = []
        if tier:     q += " AND tier=?";           params.append(tier.upper())
        if industry: q += " AND industry LIKE ?";  params.append(f"%{industry}%")
        if city:     q += " AND address LIKE ?";   params.append(f"%{city}%")
        if search:   q += " AND name LIKE ?";      params.append(f"%{search}%")
        if source:   q += " AND source=?";         params.append(source)
        q += " ORDER BY priority_score DESC, created_at DESC LIMIT ? OFFSET ?"
        params += [limit, skip]
        rows = [serialize_lead(dict(r)) for r in db.execute(q, params).fetchall()]
        total = db.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    return {"count": total, "skip": skip, "limit": limit, "leads": rows}

@app.delete("/leads/{place_id}")
def delete_lead(place_id: str):
    with closing(sqlite3.connect(DB_PATH)) as db:
        db.execute("DELETE FROM leads WHERE place_id=?", (place_id,))
        db.commit()
    return {"deleted": True}

# ── Dashboard Stats ──

@app.get("/stats")
def stats():
    with closing(sqlite3.connect(DB_PATH)) as db:
        db.row_factory = sqlite3.Row
        total  = db.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        hot    = db.execute("SELECT COUNT(*) FROM leads WHERE tier='HOT'").fetchone()[0]
        warm   = db.execute("SELECT COUNT(*) FROM leads WHERE tier='WARM'").fetchone()[0]
        low    = db.execute("SELECT COUNT(*) FROM leads WHERE tier='LOW'").fetchone()[0]
        top_i  = db.execute("SELECT industry, COUNT(*) c FROM leads WHERE industry IS NOT NULL GROUP BY industry ORDER BY c DESC LIMIT 5").fetchall()
        sources= db.execute("SELECT source, COUNT(*) c FROM leads WHERE source IS NOT NULL GROUP BY source ORDER BY c DESC").fetchall()
        crm_total = db.execute("SELECT COUNT(*) FROM crm_leads").fetchone()[0]
        crm_won   = db.execute("SELECT COUNT(*) FROM crm_leads WHERE stage='won'").fetchone()[0]
    return {
        "companies": {"total": total, "hot": hot, "warm": warm, "low": low},
        "top_industries": [{"industry": r[0], "count": r[1]} for r in top_i],
        "sources": [{"source": r[0], "count": r[1]} for r in sources],
        "crm": {"total": crm_total, "won": crm_won},
    }

# ── Upload ──

@app.post("/upload-leads")
async def upload_leads(file: UploadFile = File(...)):
    contents = await file.read()
    ext = file.filename.rsplit(".", 1)[-1].lower()

    rows = []
    if ext == "csv":
        import csv as _csv
        reader = _csv.DictReader(io.StringIO(contents.decode("utf-8", errors="replace")))
        rows = [{k.strip().lower(): (v or "").strip() for k, v in r.items()} for r in reader]
    elif ext in ("xlsx", "xls"):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(contents), read_only=True, data_only=True)
        ws = wb.active; headers = None
        for r in ws.iter_rows(values_only=True):
            if not any(r): continue
            if headers is None:
                headers = [str(c).strip().lower() if c else "" for c in r]; continue
            rows.append({headers[i]: str(v).strip() if v is not None else "" for i, v in enumerate(r)})
    elif ext == "pdf":
        try:
            import pdfplumber
            lines = []
            with pdfplumber.open(io.BytesIO(contents)) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t: lines.extend(t.split("\n"))
            clean = [l.strip() for l in lines if l.strip()]
            rows = [{"name": clean[i], "address": clean[i+1] if i+1 < len(clean) else ""}
                    for i in range(0, len(clean), 2)]
        except ImportError:
            raise HTTPException(500, "pip install pdfplumber")
    else:
        raise HTTPException(400, "Upload CSV, Excel (.xlsx), or PDF")

    def g(row, *keys):
        for k in keys:
            v = row.get(k, "").strip()
            if v and v.lower() not in ("none","n/a","-",""): return v
        return ""

    out = []
    with closing(sqlite3.connect(DB_PATH)) as db:
        for row in rows:
            name = g(row,"name","business name","company","clinic","store")
            if not name: continue
            address = g(row,"address","location","area","place")
            place_id = "upload_" + hashlib.md5((name+address).encode()).hexdigest()[:12]
            lead = {
                "place_id": place_id,
                "name":     name,
                "industry": g(row,"industry","type","category") or "business",
                "phone":    g(row,"phone","mobile","contact"),
                "website":  g(row,"website","url","site"),
                "address":  address,
                "rating":   None,"reviews":None,"lat":None,"lng":None,"maps_url":"",
                "source":   "upload",
            }
            a = audit_website(lead["website"]) if lead["website"] else {}
            lead.update({
                "email":lead.get("email") or g(row,"email","e-mail","mail") or a.get("email"),
                "whatsapp":int(bool(a.get("whatsapp"))),"whatsapp_number":a.get("whatsapp_number"),
                "all_phones":[lead["phone"]] if lead["phone"] else [],
                "doctor_name":a.get("doctor_name"),"contact_page":a.get("contact_page"),
                "ssl":int(bool(a.get("ssl"))),"seo_score":a.get("seo_score"),
                "socials":a.get("socials"),"seo_issues":a.get("seo_issues"),
                "has_booking":int(bool(a.get("has_booking"))),"audit_error":a.get("error"),
                "has_google_analytics":int(bool(a.get("has_google_analytics"))),
                "has_facebook_pixel":int(bool(a.get("has_facebook_pixel"))),
                "has_live_chat":int(bool(a.get("has_live_chat"))),
                "has_crm":int(bool(a.get("has_crm"))),"crm_detected":a.get("crm_detected"),
                "speed_score":None,
            })
            score, tier = priority(lead, a)
            lead["priority_score"] = score; lead["tier"] = tier
            lead["is_market_leader"] = 0; lead["competitors"] = []

            sp = sales_pack(lead); services = what_zyro_can_do(lead)
            intel = full_intelligence(lead, tier)

            try:
                db.execute("""INSERT INTO leads
                    (place_id,name,industry,phone,website,address,rating,reviews,lat,lng,maps_url,
                     email,whatsapp,whatsapp_number,all_phones,ssl,seo_score,socials,seo_issues,
                     has_booking,audit_error,priority_score,tier,deal_size,best_offer,
                     close_probability,call_script,whatsapp_message,zyro_services,is_market_leader,
                     doctor_name,contact_page,speed_score,maturity,strengths,weaknesses,
                     why_contact,checklist,competitors,social_score,revenue_opportunity,
                     action_plan,services_matrix,email_outreach,linkedin_message,
                     has_google_analytics,has_facebook_pixel,has_live_chat,has_crm,crm_detected,
                     health_score,opportunity_score,revenue_engine,service_gap_matrix,
                     how_to_sell,follow_up_engine,competitor_war_room,source)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(place_id) DO UPDATE SET name=excluded.name""",
                    (place_id,lead["name"],lead["industry"],lead["phone"],lead["website"],
                     lead["address"],None,None,None,None,"",
                     lead["email"],lead["whatsapp"],lead.get("whatsapp_number"),
                     json.dumps(lead.get("all_phones") or []),
                     lead["ssl"],lead["seo_score"],
                     json.dumps(lead["socials"] or {}),json.dumps(lead["seo_issues"] or []),
                     lead["has_booking"],lead["audit_error"],lead["priority_score"],lead["tier"],
                     sp["deal_size"],sp["best_offer"],sp["close_probability"],sp["call_script"],
                     sp["whatsapp_message"],json.dumps(services),0,
                     lead.get("doctor_name"),lead.get("contact_page"),None,
                     intel["maturity"],json.dumps(intel["strengths"]),json.dumps(intel["weaknesses"]),
                     intel["why_contact"],json.dumps(intel["checklist"]),json.dumps([]),
                     intel["social_score"],json.dumps(intel["revenue_opportunity"]),
                     json.dumps(intel["action_plan"]),json.dumps(intel["services_matrix"]),
                     json.dumps(intel["email_outreach"]),intel["linkedin_message"],
                     lead["has_google_analytics"],lead["has_facebook_pixel"],
                     lead["has_live_chat"],lead["has_crm"],lead.get("crm_detected"),
                     intel["health_score"],intel["opportunity_score"],
                     json.dumps(intel["revenue_engine"]),json.dumps(intel["service_gap_matrix"]),
                     json.dumps(intel["how_to_sell"]),json.dumps(intel["follow_up_engine"]),
                     json.dumps(intel["competitor_war_room"]),"upload"))
            except Exception: pass

            lead.update(sp); lead["zyro_services"] = services; lead.update(intel)
            out.append(lead)
        db.commit()

    out.sort(key=lambda x: x["priority_score"], reverse=True)
    return {"found": len(out), "leads": out}

# ── Export ──

@app.get("/export-csv")
@app.post("/export-csv")
def export_csv(tier: str = Query(None), industry: str = Query(None)):
    with closing(sqlite3.connect(DB_PATH)) as db:
        db.row_factory = sqlite3.Row
        q = "SELECT * FROM leads WHERE 1=1"
        params = []
        if tier:     q += " AND tier=?";          params.append(tier.upper())
        if industry: q += " AND industry LIKE ?"; params.append(f"%{industry}%")
        q += " ORDER BY priority_score DESC"
        rows = [dict(r) for r in db.execute(q, params).fetchall()]

    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["Name","Industry","Doctor/Owner","All Phones","Email","WhatsApp","Website",
                "Contact Page","Rating","Reviews","SSL","SEO","Speed","Booking","Maturity",
                "Priority","Tier","Deal Size","Best Offer","Health","Opportunity",
                "Missing Services","Why Contact","GA","FB Pixel","Live Chat","CRM",
                "Market Leader","Source","Address","Maps URL"])
    for r in rows:
        def js(f):
            try: return ", ".join(str(x) for x in json.loads(r.get(f) or "[]"))
            except: return r.get(f) or ""
        w.writerow([r.get("name"),r.get("industry"),r.get("doctor_name"),
            js("all_phones"),r.get("email"),
            r.get("whatsapp_number") or ("Yes" if r.get("whatsapp") else "No"),
            r.get("website"),r.get("contact_page"),r.get("rating"),r.get("reviews"),
            "Yes" if r.get("ssl") else "No",r.get("seo_score"),r.get("speed_score"),
            "Yes" if r.get("has_booking") else "No",r.get("maturity"),
            r.get("priority_score"),r.get("tier"),r.get("deal_size"),r.get("best_offer"),
            r.get("health_score"),r.get("opportunity_score"),
            js("weaknesses"),r.get("why_contact"),
            "Yes" if r.get("has_google_analytics") else "No",
            "Yes" if r.get("has_facebook_pixel") else "No",
            "Yes" if r.get("has_live_chat") else "No",
            r.get("crm_detected") or ("Yes" if r.get("has_crm") else "No"),
            "Yes" if r.get("is_market_leader") else "",
            r.get("source",""),r.get("address"),r.get("maps_url")])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition":"attachment; filename=zyro_leads.csv"})

# ── CRM ──

class CreateCRMLead(BaseModel):
    place_id:       str
    stage:          str  = "new"
    owner:          str  = ""
    deal_value:     float = 0
    notes:          str  = ""
    next_follow_up: str  = ""

class UpdateCRMLead(BaseModel):
    stage:          str  = None
    owner:          str  = None
    deal_value:     float = None
    notes:          str  = None
    next_follow_up: str  = None

class AddActivity(BaseModel):
    type:    str
    content: str

import uuid as _uuid

@app.get("/crm/pipeline")
def crm_pipeline():
    stages = ["new","contacted","qualified","proposal","won","lost"]
    with closing(sqlite3.connect(DB_PATH)) as db:
        db.row_factory = sqlite3.Row
        result = {}
        for stage in stages:
            rows = db.execute(
                """SELECT c.*, l.name, l.industry, l.phone, l.tier, l.priority_score
                   FROM crm_leads c LEFT JOIN leads l ON c.place_id=l.place_id
                   WHERE c.stage=? ORDER BY c.updated_at DESC""", (stage,)).fetchall()
            result[stage] = [dict(r) for r in rows]
    return result

@app.get("/crm/leads")
def crm_leads():
    with closing(sqlite3.connect(DB_PATH)) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            """SELECT c.*, l.name, l.industry, l.phone, l.tier, l.priority_score, l.website
               FROM crm_leads c LEFT JOIN leads l ON c.place_id=l.place_id
               ORDER BY c.updated_at DESC""").fetchall()
    return [dict(r) for r in rows]

@app.post("/crm/leads")
def create_crm_lead(body: CreateCRMLead):
    lid = str(_uuid.uuid4())
    now = datetime.utcnow().isoformat()
    with closing(sqlite3.connect(DB_PATH)) as db:
        db.execute(
            "INSERT INTO crm_leads (id,place_id,stage,owner,deal_value,notes,next_follow_up,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (lid, body.place_id, body.stage, body.owner, body.deal_value, body.notes, body.next_follow_up, now, now))
        db.commit()
    return {"id": lid, "stage": body.stage}

@app.put("/crm/leads/{lead_id}")
def update_crm_lead(lead_id: str, body: UpdateCRMLead):
    now = datetime.utcnow().isoformat()
    with closing(sqlite3.connect(DB_PATH)) as db:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates: return {"ok": True}
        sets = ", ".join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [now, lead_id]
        db.execute(f"UPDATE crm_leads SET {sets}, updated_at=? WHERE id=?", vals)
        db.commit()
    return {"ok": True}

@app.post("/crm/leads/{lead_id}/activity")
def add_activity(lead_id: str, body: AddActivity):
    aid = str(_uuid.uuid4())
    now = datetime.utcnow().isoformat()
    with closing(sqlite3.connect(DB_PATH)) as db:
        db.execute("INSERT INTO crm_activities (id,crm_lead_id,type,content,created_at) VALUES (?,?,?,?,?)",
            (aid, lead_id, body.type, body.content, now))
        db.commit()
    return {"id": aid}

@app.get("/crm/leads/{lead_id}/activities")
def get_activities(lead_id: str):
    with closing(sqlite3.connect(DB_PATH)) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            "SELECT * FROM crm_activities WHERE crm_lead_id=? ORDER BY created_at DESC", (lead_id,)).fetchall()
    return [dict(r) for r in rows]
