"""Auto Proposal Generator — generates a text proposal for any lead"""


def build_proposal(lead: dict) -> str:
    name = lead.get("name", "Your Business")
    offer = lead.get("best_offer", "Digital Services")
    deal = lead.get("deal_size", "₹30,000 – ₹60,000")
    issues = lead.get("weaknesses") or []
    services = lead.get("zyro_services") or []

    issues_text = "\n".join(f"  • {i}" for i in (issues if isinstance(issues, list) else [issues])[:4])
    services_text = "\n".join(f"  • {s['name'] if isinstance(s,dict) else s}" for s in (services[:4] if isinstance(services,list) else []))

    return f"""
PROPOSAL FOR {name.upper()}
{"="*50}

Prepared by: Zyro AI Solutions
Date: {__import__('datetime').date.today().strftime('%d %B %Y')}

─────────────────────────────────────────────────
EXECUTIVE SUMMARY
─────────────────────────────────────────────────
We identified several digital growth opportunities
for {name} that Zyro AI Solutions can address
quickly and affordably.

─────────────────────────────────────────────────
CURRENT CHALLENGES
─────────────────────────────────────────────────
{issues_text or '  • General digital presence improvements needed'}

─────────────────────────────────────────────────
RECOMMENDED SERVICES
─────────────────────────────────────────────────
{services_text or f'  • {offer}'}

─────────────────────────────────────────────────
INVESTMENT
─────────────────────────────────────────────────
Estimated Project Value: {deal}
Timeline: 2–4 weeks for initial setup

─────────────────────────────────────────────────
NEXT STEPS
─────────────────────────────────────────────────
1. 15-minute discovery call
2. Free website audit report
3. Custom proposal with exact pricing

Contact: team@zyroai.in | WhatsApp: +91-XXXXXXXXXX
{"="*50}
""".strip()
