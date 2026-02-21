"""Generate and ingest synthetic NASA POWER-style climate time-series for West Africa and South Asia.
   Uses realistic seasonal patterns: dry spell in recent weeks for West Africa (Nov–Feb),
   so agent queries for 'last 90 days' return plausible deficit when farmers report little rain."""
import os
import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

from utils import get_es_client, bulk_index

INDEX = "climate-timeseries"

# Demo regions: (lat, lon, country, region_name). West Africa = realistic dry spell in recent weeks.
REGIONS = [
    (7.85, 3.95, "Nigeria", "Oyo"),
    (7.62, 4.18, "Nigeria", "Osun"),
    (7.16, 3.35, "Nigeria", "Ogun"),
    (23.81, 90.41, "Bangladesh", "Dhaka"),
    (22.36, 91.78, "Bangladesh", "Chittagong"),
    (26.85, 80.95, "India", "Uttar Pradesh"),
    (31.15, 75.34, "India", "Punjab"),
    (-0.02, 34.75, "Kenya", "Western"),
    (8.53, 39.44, "Ethiopia", "Oromia"),
]

# West African regions (Nigeria, etc.): apply dry-season pattern in recent weeks.
WEST_AFRICA_COUNTRIES = {"Nigeria", "Ghana", "Senegal"}


def _rainfall_mm(lat, lon, country, region_name, ts, ref_today):
    """Realistic weekly rainfall: West Africa dry season (Nov–Feb) has low rain; recent 4 weeks even lower."""
    week_delta = (ref_today - ts).days // 7
    is_west_africa = country in WEST_AFRICA_COUNTRIES
    month = ts.month
    # Dry season in West Africa roughly Nov–Feb (month in [11,12,1,2])
    is_dry_season = month in (1, 2, 11, 12)
    if is_west_africa and week_delta <= 4:
        # Last 4 weeks: dry spell (5–18 mm/week) so "little rain for 3 weeks" matches
        return round(random.uniform(5, 18), 1)
    if is_west_africa and week_delta <= 12 and is_dry_season:
        # Rest of last 90 days in dry season: 10–35 mm/week
        return round(random.uniform(10, 35), 1)
    if is_west_africa and is_dry_season:
        return round(random.uniform(12, 40), 1)
    # Wet season or other regions: 25–85 mm/week
    return round(random.uniform(25, 85), 1)


def generate_docs(start_year=2020, end_year=2026, docs_per_region_per_year=52, ref_today=None):
    """Generate weekly aggregates per region. ref_today used for realistic 'recent dry spell' (default: 2026-02-21)."""
    if ref_today is None:
        ref_today = datetime(2026, 2, 21)
    random.seed(42)
    docs = []
    for lat, lon, country, region_name in REGIONS:
        for year in range(start_year, end_year + 1):
            base = datetime(year, 1, 1)
            for week in range(min(docs_per_region_per_year, 52)):
                ts = base + timedelta(weeks=week)
                if ts.year != year:
                    continue
                rainfall_mm = _rainfall_mm(lat, lon, country, region_name, ts, ref_today)
                temp_max = round(random.uniform(28, 37), 1)
                temp_min = round(temp_max - random.uniform(5, 11), 1)
                humidity_pct = round(random.uniform(50, 92), 1)
                solar_radiation = round(random.uniform(18, 25), 2)
                ts_str = ts.isoformat() + "Z"
                pt = {"lat": lat, "lon": lon}
                docs.append({
                    "@timestamp": ts_str,
                    "ts": ts_str,
                    "location": pt,
                    "point": pt,
                    "country": country,
                    "region_name": region_name,
                    "rainfall_mm": rainfall_mm,
                    "temp_max_celsius": temp_max,
                    "temp_min_celsius": temp_min,
                    "humidity_pct": humidity_pct,
                    "solar_radiation": solar_radiation,
                })
    return docs


def main():
    client = get_es_client()
    docs = generate_docs()
    # Use chunked bulk to avoid huge requests
    chunk = 500
    for i in range(0, len(docs), chunk):
        bulk_index(client, INDEX, docs[i : i + chunk])
    print(f"Done. Ingested {len(docs)} documents to {INDEX}.")


if __name__ == "__main__":
    main()
