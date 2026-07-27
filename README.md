# Zyro OS — Full Stack Business Intelligence Platform

## Setup (2 minutes)

### 1. Install dependencies
```
pip install -r requirements.txt
```

### 2. Set your API key in .env
```
GOOGLE_API_KEY=your_key_here
```

### 3. Start the server
```
uvicorn main:app --reload
```

### 4. Open browser
```
http://localhost:8000/dashboard
```

---

## Project Structure

```
leads scrapper/
├── main.py                  ← Backend (all API routes)
├── audit.py                 ← Website auditor
├── intelligence.py          ← AI intelligence engine
├── sales.py                 ← Sales pack generator
├── recommend.py             ← Zyro service recommender
├── pagespeed.py             ← Google PageSpeed
├── .env                     ← GOOGLE_API_KEY here
├── zyro.db                  ← SQLite database (auto-created)
│
├── templates/
│   └── dashboard.html       ← Full dashboard UI
│
├── static/                  ← CSS/JS/images (optional)
│
├── ai/
│   ├── scoring.py           ← Opportunity scoring
│   ├── maturity.py          ← Digital maturity
│   └── recommendation.py   ← Service recommendations
│
├── connectors/
│   └── __init__.py          ← Connector registry
│
├── crm/
│   └── followup.py          ← Follow-up sequences
│
└── proposal/
    └── proposal_builder.py  ← Auto proposal generator
```

---

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/dashboard` | Open the dashboard |
| GET | `/` | Health check |
| POST | `/discover` | Discover businesses |
| POST | `/discover-by-area` | Search within drawn polygon |
| GET | `/leads` | List all saved leads |
| GET | `/stats` | Dashboard statistics |
| POST | `/upload-leads` | Upload CSV/Excel/PDF |
| GET | `/export-csv` | Export all leads to CSV |
| GET | `/crm/pipeline` | CRM kanban data |
| POST | `/crm/leads` | Add lead to CRM |
| PUT | `/crm/leads/{id}` | Update CRM lead stage |
| GET | `/crm/leads/{id}/activities` | Lead activity log |

---

## Features

- ⚡ **Discover** — Google Places + OpenStreetMap (free fallback)
- 🗺️ **Map View** — Interactive map with circle-draw search
- 📊 **Stats** — Live dashboard statistics
- 🎯 **CRM** — Kanban pipeline (New → Contacted → Won)
- 📂 **Upload** — CSV / Excel / PDF bulk import
- 📥 **Export** — CSV export with full intelligence data
- 🤖 **AI Scoring** — HOT/WARM/LOW + health + opportunity scores
- 📞 **Sales Packs** — Call scripts, WhatsApp, email, LinkedIn outreach
