"""Seed realistic synthetic advisories into `advisory-history`.

The agent/workflow only writes one advisory-history doc per chat, so the index
is nearly empty in a fresh project. The FarmSense Command Center dashboard
(Kibana Maps + Lens over advisory-history) needs volume to look alive. This
script generates geo-distributed advisories that are byte-compatible with what
`advisory-alert-workflow` writes (see workflows/advisory_alert_workflow.yaml):

    @timestamp, session_id, location {lat, lon} (geo_point), country, region,
    crop, symptoms_reported, risk_level, advisory_text, primary_diagnosis,
    pest_flagged, climate_anomaly

Usage:
    uv run python ingestion/seed_advisory_history.py            # 220 docs, last 30 days
    uv run python ingestion/seed_advisory_history.py -n 500     # more volume
    uv run python ingestion/seed_advisory_history.py --days 60  # wider time window
    uv run python ingestion/seed_advisory_history.py --reset    # wipe existing first
"""
import argparse
import os
import random
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

from utils import get_es_client, bulk_index

INDEX = "advisory-history"

# Minimal mapping so the script is standalone if create_indices.py wasn't run.
# Mirrors ingestion/create_indices.py (location as geo_point is what the map needs).
MAPPING = {
    "mappings": {
        "properties": {
            "@timestamp": {"type": "date"},
            "session_id": {"type": "keyword"},
            "location": {"type": "geo_point"},
            "country": {"type": "keyword"},
            "region": {"type": "keyword"},
            "crop": {"type": "keyword"},
            "symptoms_reported": {"type": "text"},
            "risk_level": {"type": "keyword"},
            "advisory_text": {"type": "text"},
            "primary_diagnosis": {"type": "keyword"},
            "pest_flagged": {"type": "keyword"},
            "climate_anomaly": {"type": "text"},
        }
    }
}

# region -> (country, lat, lon, [typical crops]). Centroids match the demo
# scenarios and spread across Sub-Saharan Africa + South Asia for a rich map.
REGIONS = [
    ("Oyo",          "Nigeria",     7.85,   3.95, ["maize", "cassava", "cowpea"]),
    ("Kaduna",       "Nigeria",    10.52,   7.44, ["maize", "sorghum", "groundnut"]),
    ("Western",      "Kenya",       0.43,  34.56, ["maize", "beans", "cassava"]),
    ("Rift Valley",  "Kenya",      -0.30,  36.08, ["maize", "wheat", "beans"]),
    ("Oromia",       "Ethiopia",    8.50,  39.50, ["maize", "wheat", "sorghum"]),
    ("Dhaka",        "Bangladesh", 23.81,  90.41, ["rice", "jute", "maize"]),
    ("Uttar Pradesh","India",      26.85,  80.95, ["wheat", "rice", "sugarcane"]),
    ("Maharashtra",  "India",      19.75,  75.71, ["cotton", "sorghum", "maize"]),
    ("Morogoro",     "Tanzania",   -6.82,  37.66, ["maize", "rice", "cassava"]),
    ("Central",      "Uganda",      0.35,  32.60, ["maize", "cassava", "beans"]),
    ("Ashanti",      "Ghana",       6.75,  -1.50, ["maize", "cassava", "cocoa"]),
    ("Central",      "Malawi",    -13.00,  34.00, ["maize", "groundnut", "beans"]),
    ("Lusaka",       "Zambia",    -15.40,  28.30, ["maize", "soybean", "sorghum"]),
    ("Nampula",      "Mozambique",-15.10,  39.30, ["cassava", "maize", "cowpea"]),
]

# Scenario archetypes -> coherent (pest, diagnosis, risk weights, symptoms,
# climate anomaly, crop override). Keeps seeded docs internally consistent.
ARCHETYPES = [
    {
        "diagnosis": "Drought stress",
        "pest": "None", "risks": ["MEDIUM", "HIGH", "HIGH"],
        "symptoms": "Leaves yellowing and curling, stunted growth, dry soil.",
        "anomaly": "Rainfall ~60% below seasonal normal over the last 30 days.",
    },
    {
        "diagnosis": "Pest infestation (Fall Armyworm)",
        "pest": "Fall Armyworm", "risks": ["HIGH", "HIGH", "CRITICAL"],
        "symptoms": "Ragged holes and windowing on leaves, frass in the whorl.",
        "anomaly": "", "crops": ["maize", "sorghum"],
    },
    {
        "diagnosis": "Fungal disease (Rice Blast)",
        "pest": "Rice Blast", "risks": ["MEDIUM", "HIGH", "HIGH"],
        "symptoms": "Diamond-shaped lesions on leaves, browning panicle necks.",
        "anomaly": "Prolonged leaf wetness; humidity above 85%.", "crops": ["rice"],
    },
    {
        "diagnosis": "Fungal disease (Late Blight)",
        "pest": "Late Blight", "risks": ["HIGH", "CRITICAL"],
        "symptoms": "Dark water-soaked lesions on leaves and stems, white mould.",
        "anomaly": "Cool, very humid conditions following rain.",
        "crops": ["tomato", "potato"],
    },
    {
        "diagnosis": "Nitrogen deficiency",
        "pest": "None", "risks": ["LOW", "MEDIUM", "MEDIUM"],
        "symptoms": "Older leaves yellowing from the tip, poor vigour.",
        "anomaly": "",
    },
    {
        "diagnosis": "Minor pest pressure (Aphids)",
        "pest": "Aphids", "risks": ["LOW", "LOW", "MEDIUM"],
        "symptoms": "Small aphid clusters on new growth, slight leaf curl.",
        "anomaly": "",
    },
    {
        "diagnosis": "Locust threat",
        "pest": "Desert Locust", "risks": ["CRITICAL", "CRITICAL"],
        "symptoms": "Swarms reported nearby; rapid defoliation risk.",
        "anomaly": "Favourable breeding conditions reported regionally.",
    },
    {
        "diagnosis": "Waterlogging stress",
        "pest": "None", "risks": ["MEDIUM", "HIGH"],
        "symptoms": "Yellowing and wilting after flooding, standing water.",
        "anomaly": "Rainfall ~150% above normal; fields waterlogged.",
    },
    {
        "diagnosis": "Viral disease (Cassava Mosaic)",
        "pest": "Cassava Mosaic Virus", "risks": ["MEDIUM", "HIGH"],
        "symptoms": "Mottled, distorted leaves; reduced tuber sizing.",
        "anomaly": "", "crops": ["cassava"],
    },
    {
        "diagnosis": "Pest infestation (Stem Borer)",
        "pest": "Stem Borer", "risks": ["MEDIUM", "HIGH"],
        "symptoms": "Deadhearts, small holes and tunnels in stems.",
        "anomaly": "", "crops": ["maize", "sorghum", "rice"],
    },
]

# Risk -> weight so the map shows realistic hotspots (more CRITICAL = redder).
ARCHETYPE_WEIGHTS = [5, 4, 3, 2, 4, 4, 1, 3, 2, 3]


def _immediate_action(arch):
    pest = arch["pest"]
    if pest == "Fall Armyworm":
        return "Scout whorls at dawn; hand-pick egg masses; apply approved biopesticide if >20% infested."
    if pest == "Rice Blast":
        return "Drain the field briefly; avoid excess nitrogen; apply a labelled fungicide at first lesions."
    if pest == "Late Blight":
        return "Remove and bury infected plants; apply protectant fungicide; improve airflow."
    if pest == "Desert Locust":
        return "Report to local authority immediately; prepare to protect priority plots."
    if pest == "Aphids":
        return "Encourage natural predators; spot-treat heavy clusters with soapy water."
    if pest == "Stem Borer":
        return "Destroy crop residues; consider push-pull intercropping; apply biopesticide to whorls."
    if pest == "Cassava Mosaic Virus":
        return "Rogue infected plants; use clean, certified cuttings for replanting."
    if arch["diagnosis"].startswith("Drought"):
        return "Mulch to conserve moisture; prioritise irrigation at flowering; reduce weed competition."
    if arch["diagnosis"].startswith("Waterlogging"):
        return "Open drainage channels; topdress nitrogen after water recedes."
    if arch["diagnosis"].startswith("Nitrogen"):
        return "Split-apply nitrogen; consider organic manure; confirm with a soil test."
    return "Monitor closely and follow good agronomic practice."


def make_doc(now, days):
    region, country, lat, lon, crops = random.choice(REGIONS)
    idx = random.choices(range(len(ARCHETYPES)), weights=ARCHETYPE_WEIGHTS, k=1)[0]
    arch = ARCHETYPES[idx]

    crop = random.choice(arch.get("crops") or crops)
    risk = random.choice(arch["risks"])

    # Jitter the point so advisories cluster naturally around region centroids.
    jlat = round(lat + random.uniform(-0.6, 0.6), 4)
    jlon = round(lon + random.uniform(-0.6, 0.6), 4)

    ts = now - timedelta(
        days=random.uniform(0, days),
        hours=random.uniform(0, 24),
    )

    advisory = (
        f"RISK LEVEL: {risk}. PRIMARY DIAGNOSIS: {arch['diagnosis']}. "
        f"IMMEDIATE ACTION: {_immediate_action(arch)}"
    )

    return {
        "@timestamp": ts.replace(tzinfo=timezone.utc).isoformat(),
        "session_id": "seed-%08x" % random.getrandbits(32),
        "location": {"lat": jlat, "lon": jlon},
        "country": country,
        "region": region,
        "crop": crop,
        "symptoms_reported": arch["symptoms"],
        "risk_level": risk,
        "advisory_text": advisory,
        "primary_diagnosis": arch["diagnosis"],
        "pest_flagged": arch["pest"],
        "climate_anomaly": arch["anomaly"],
    }


def main():
    ap = argparse.ArgumentParser(description="Seed synthetic advisories for the Command Center demo.")
    ap.add_argument("-n", "--count", type=int, default=220, help="number of advisories to generate")
    ap.add_argument("--days", type=int, default=30, help="spread timestamps over the last N days")
    ap.add_argument("--reset", action="store_true", help="delete existing advisory-history docs first")
    ap.add_argument("--seed", type=int, default=42, help="RNG seed for reproducibility")
    args = ap.parse_args()

    random.seed(args.seed)
    client = get_es_client()

    if not client.indices.exists(index=INDEX):
        client.indices.create(index=INDEX, body=MAPPING)
        print(f"Created index: {INDEX}")

    if args.reset:
        deleted = client.delete_by_query(
            index=INDEX, body={"query": {"match_all": {}}}, refresh=True, conflicts="proceed"
        )
        print(f"Reset: deleted {deleted.get('deleted', 0)} existing docs.")

    now = datetime.now(timezone.utc)
    docs = [make_doc(now, args.days) for _ in range(args.count)]
    bulk_index(client, INDEX, docs)
    client.indices.refresh(index=INDEX)

    # Quick distribution summary so you can sanity-check before the demo.
    from collections import Counter
    by_risk = Counter(d["risk_level"] for d in docs)
    by_country = Counter(d["country"] for d in docs)
    print("\nSeeded distribution:")
    print("  By risk:   ", dict(sorted(by_risk.items())))
    print("  By country:", dict(sorted(by_country.items(), key=lambda x: -x[1])))
    print(f"\nDone. {args.count} advisories in '{INDEX}'. Build the Command Center map in Kibana.")


if __name__ == "__main__":
    main()
