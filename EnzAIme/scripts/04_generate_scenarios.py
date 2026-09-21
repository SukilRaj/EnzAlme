#!/usr/bin/env python3
"""
scripts/04_generate_scenarios.py
===================================
Generates the MVP "Synthetic evaluation scenarios" grid (Section 17):
  pH x temperature x salinity x pollutant = 5 x 5 x 3 x 3 = 225 scenarios.

These are NOT real wastewater observations — every artifact produced here
is labelled accordingly, and the generator is designed to be swapped for a
real industrial-wastewater dataset later (Section 4/17) without touching
any downstream code (scoring.py / model.py just consume a flat
pH/temperature/salinity/pollutant table either way).

Independently executable: python scripts/04_generate_scenarios.py
"""
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))
import pandas as pd  # noqa: E402
from enzaime_core import config  # noqa: E402


def main():
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    combos = list(itertools.product(
        config.SCENARIO_PH_VALUES,
        config.SCENARIO_TEMP_VALUES,
        config.SCENARIO_SALINITY_VALUES,
        config.SCENARIO_POLLUTANTS,
    ))
    rows = [
        {"scenario_id": f"SCN{idx:04d}", "pH": ph, "temperature": t, "salinity": s, "pollutant": p,
         "is_synthetic": True, "source": "synthetic_evaluation_scenario_generator"}
        for idx, (ph, t, s, p) in enumerate(combos, start=1)
    ]
    df = pd.DataFrame(rows)
    out_path = config.PROCESSED_DIR / "environmental_scenarios.csv"
    df.to_csv(out_path, index=False)
    print(f"Generated {len(df)} SYNTHETIC evaluation scenarios -> {out_path}")
    print("Grid: pH(%d) x T(%d) x salinity(%d) x pollutant(%d) = %d" % (
        len(config.SCENARIO_PH_VALUES), len(config.SCENARIO_TEMP_VALUES),
        len(config.SCENARIO_SALINITY_VALUES), len(config.SCENARIO_POLLUTANTS), len(df)
    ))

    # Also emit a small demo_scenarios.json with 3+ known-good demo scenarios
    # (Section 50) for the frontend / manual QA to use directly.
    demo_scenarios = [
        {
            "name": "Scenario 1 — PET, mild alkaline, moderate warm",
            "pollutant": "PET", "ph": 8.0, "temperature": 35, "salinity": 0.5,
            "note": "Software demonstration scenario — not an experimental observation.",
        },
        {
            "name": "Scenario 2 — PET, neutral, warmer",
            "pollutant": "PET", "ph": 7.0, "temperature": 45, "salinity": 1.0,
            "note": "Software demonstration scenario — not an experimental observation.",
        },
        {
            "name": "Scenario 3 — PA (nylon), neutral, moderate",
            "pollutant": "PA", "ph": 7.0, "temperature": 35, "salinity": 0.0,
            "note": "Software demonstration scenario — not an experimental observation.",
        },
        {
            "name": "Scenario 4 — PUR, mild alkaline, ambient",
            "pollutant": "PUR", "ph": 7.5, "temperature": 30, "salinity": 0.0,
            "note": "Software demonstration scenario — not an experimental observation.",
        },
    ]
    config.DEMO_DIR.mkdir(parents=True, exist_ok=True)
    config.SCENARIOS_JSON.write_text(json.dumps(demo_scenarios, indent=2))
    print(f"Wrote {len(demo_scenarios)} demo scenarios -> {config.SCENARIOS_JSON}")


if __name__ == "__main__":
    main()
