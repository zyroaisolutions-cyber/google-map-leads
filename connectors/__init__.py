"""
Connector registry — add new connectors here.
Every connector must implement search(query) -> list[dict]
"""

AVAILABLE = {
    "google_places": "Google Places API (New) — requires GOOGLE_API_KEY",
    "openstreetmap": "OpenStreetMap Overpass API — free, no key needed",
}
