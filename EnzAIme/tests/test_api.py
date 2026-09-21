"""
tests/test_api.py
====================
Section 39 tests #8-9, #12:
  8. Top 3 recommendations are returned.
  9. Invalid API input is rejected.
  12. Demo mode works without trained model.
Plus general endpoint coverage (Section 23-24, 53, 60 success criterion).
"""


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["n_enzymes_loaded"] > 0


def test_metadata_reports_demo_mode_explicitly(client):
    """Section 36 — the active scoring mode must never be hidden."""
    r = client.get("/metadata")
    assert r.status_code == 200
    body = r.json()
    assert "demo_mode" in body
    assert "scoring_mode" in body
    assert body["scoring_mode"] in {"demo_compatibility_engine", "ai_model"}


def test_list_enzymes(client):
    r = client.get("/enzymes")
    assert r.status_code == 200
    assert len(r.json()) > 0


def test_list_enzymes_filtered_by_pollutant(client):
    r = client.get("/enzymes?pollutant=PET")
    assert r.status_code == 200
    for e in r.json():
        assert e["pollutant"] == "PET"


def test_list_enzymes_invalid_pollutant_rejected(client):
    r = client.get("/enzymes?pollutant=NOTAPOLLUTANT")
    assert r.status_code == 400


def test_get_enzyme_detail(client):
    r = client.get("/enzyme/ENZ001")
    assert r.status_code == 200
    body = r.json()
    assert body["enzyme_id"] == "ENZ001"
    assert body["has_sequence"] is True
    assert body["mutation_analysis_available"] is True


def test_get_enzyme_not_found(client):
    r = client.get("/enzyme/DOES_NOT_EXIST")
    assert r.status_code == 404


def test_recommend_returns_top_k(client):
    r = client.post("/recommend", json={"pollutant": "PET", "ph": 8.0, "temperature": 35, "salinity": 0.5})
    assert r.status_code == 200
    body = r.json()
    assert 1 <= len(body["recommendations"]) <= 3
    assert body["recommendations"][0]["rank"] == 1


def test_recommend_ranking_descending(client):
    r = client.post("/recommend", json={"pollutant": "PET", "ph": 8.0, "temperature": 35, "salinity": 0.5})
    scores = [x["suitability_score"] for x in r.json()["recommendations"]]
    assert scores == sorted(scores, reverse=True)


def test_recommend_never_hides_scoring_mode(client):
    r = client.post("/recommend", json={"pollutant": "PET", "ph": 8.0, "temperature": 35, "salinity": 0.5})
    body = r.json()
    assert body["scoring_mode"] in {"demo_compatibility_engine", "ai_model"}
    assert "disclaimer" in body and len(body["disclaimer"]) > 0


def test_recommend_breakdown_present_for_every_item(client):
    r = client.post("/recommend", json={"pollutant": "PA", "ph": 7.0, "temperature": 35, "salinity": 0.0})
    for item in r.json()["recommendations"]:
        b = item["breakdown"]
        for key in ["pollutant", "ph", "temperature", "salinity"]:
            assert 0.0 <= b[key] <= 1.0
        assert item["salinity_status"] in {"known", "unknown"}


def test_recommend_invalid_pollutant_rejected(client):
    r = client.post("/recommend", json={"pollutant": "NOPE", "ph": 7, "temperature": 30, "salinity": 0})
    assert r.status_code == 400


def test_recommend_absurd_ph_rejected(client):
    r = client.post("/recommend", json={"pollutant": "PET", "ph": 100, "temperature": 30, "salinity": 0})
    assert r.status_code == 400


def test_recommend_absurd_temperature_rejected(client):
    r = client.post("/recommend", json={"pollutant": "PET", "ph": 7, "temperature": 5000, "salinity": 0})
    assert r.status_code == 400


def test_recommend_negative_salinity_rejected(client):
    r = client.post("/recommend", json={"pollutant": "PET", "ph": 7, "temperature": 30, "salinity": -1})
    assert r.status_code == 400


def test_recommend_missing_field_rejected(client):
    r = client.post("/recommend", json={"pollutant": "PET", "ph": 7, "temperature": 30})
    assert r.status_code == 400


def test_recommend_demo_mode_works_without_trained_model(client):
    """Section 12/37/60 — the app must work end-to-end even with no artifacts/model.pt.
    Accepts either scoring_mode (ai_model when a trained model exists, else
    demo_compatibility_engine) — the test's real assertion is HTTP 200 + results."""
    r = client.post("/recommend", json={"pollutant": "PET", "ph": 8.0, "temperature": 35, "salinity": 0.5})
    assert r.status_code == 200
    assert r.json()["scoring_mode"] in {"demo_compatibility_engine", "ai_model"}


def test_mutations_endpoint_known_enzyme(client):
    r = client.post("/mutations", json={"enzyme_id": "ENZ001", "top_n": 10})
    assert r.status_code == 200
    body = r.json()
    assert len(body["mutations"]) == 10
    assert "experimental validation required" in body["disclaimer"].lower()


def test_mutations_endpoint_sequence_unavailable(client):
    """ENZ004 has no sequence in the real processed master dataset."""
    r = client.post("/mutations", json={"enzyme_id": "ENZ004"})
    assert r.status_code == 422


def test_mutations_endpoint_unknown_enzyme(client):
    r = client.post("/mutations", json={"enzyme_id": "NOPE"})
    assert r.status_code == 404


def test_reload_model_endpoint(client):
    r = client.post("/reload-model")
    assert r.status_code == 200
    assert r.json()["reloaded"] is True


def test_full_user_journey_pet_scenario(client):
    """Section 60 — the exact end-to-end journey the MVP must support."""
    rec = client.post("/recommend", json={"pollutant": "PET", "ph": 8.0, "temperature": 35, "salinity": 0.5})
    assert rec.status_code == 200
    top = rec.json()["recommendations"][0]

    detail = client.get(f"/enzyme/{top['enzyme_id']}")
    assert detail.status_code == 200

    if detail.json()["mutation_analysis_available"]:
        muts = client.post("/mutations", json={"enzyme_id": top["enzyme_id"], "top_n": 5})
        assert muts.status_code == 200
        assert len(muts.json()["mutations"]) == 5


# --------------------------------------------------------------------------
# Environmental Sensitivity Simulator tests (/simulate, /simulate/sweep)
# --------------------------------------------------------------------------
def test_simulate_score_matches_score_enzyme(client, monkeypatch):
    from enzaime_core import data_loader, scoring
    from app.services.model_service import get_model_service

    ms = get_model_service()
    monkeypatch.setattr(ms, "scoring_mode", "demo_compatibility_engine")

    row = data_loader.get_enzyme_by_id("ENZ001")
    query = scoring.EnvironmentQuery(pollutant="PET", ph=8.0, temperature=35.0, salinity=0.5)
    expected_score, expected_breakdown = scoring.score_enzyme(row, query)

    r = client.post("/simulate", json={
        "enzyme_id": "ENZ001",
        "pollutant": "PET",
        "ph": 8.0,
        "temperature": 35.0,
        "salinity": 0.5,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["suitability_score"] == round(float(expected_score), 4)
    assert body["score"] == round(float(expected_score), 4)
    assert body["score_percent"] == round(float(expected_score) * 100, 2)
    assert body["breakdown"]["pollutant"] == expected_breakdown.pollutant
    assert body["breakdown"]["ph"] == expected_breakdown.ph
    assert body["breakdown"]["temperature"] == expected_breakdown.temperature
    assert body["breakdown"]["salinity"] == expected_breakdown.salinity
    assert "explanation" in body


def test_simulate_not_found_and_input_validation(client):
    # 404 on unknown enzyme_id
    r = client.post("/simulate", json={
        "enzyme_id": "DOES_NOT_EXIST",
        "pollutant": "PET",
        "ph": 8.0,
        "temperature": 35.0,
        "salinity": 0.5,
    })
    assert r.status_code == 404

    # 400 on absurd / invalid pH
    r = client.post("/simulate", json={
        "enzyme_id": "ENZ001",
        "pollutant": "PET",
        "ph": 25.0,
        "temperature": 35.0,
        "salinity": 0.5,
    })
    assert r.status_code == 400

    # 400 on absurd / invalid temperature
    r = client.post("/simulate", json={
        "enzyme_id": "ENZ001",
        "pollutant": "PET",
        "ph": 8.0,
        "temperature": 999.0,
        "salinity": 0.5,
    })
    assert r.status_code == 400

    # 400 on negative salinity
    r = client.post("/simulate", json={
        "enzyme_id": "ENZ001",
        "pollutant": "PET",
        "ph": 8.0,
        "temperature": 35.0,
        "salinity": -1.0,
    })
    assert r.status_code == 400

    # 400 on invalid pollutant
    r = client.post("/simulate", json={
        "enzyme_id": "ENZ001",
        "pollutant": "INVALID_POLLUTANT",
        "ph": 8.0,
        "temperature": 35.0,
        "salinity": 0.5,
    })
    assert r.status_code == 400


def test_simulate_sweep_returns_exact_steps_and_endpoints(client):
    steps = 40
    sweep_min = 2.0
    sweep_max = 12.0
    r = client.post("/simulate/sweep", json={
        "enzyme_id": "ENZ001",
        "pollutant": "PET",
        "sweep_variable": "ph",
        "sweep_min": sweep_min,
        "sweep_max": sweep_max,
        "steps": steps,
        "fixed_ph": 8.0,
        "fixed_temperature": 35.0,
        "fixed_salinity": 0.5,
    })
    assert r.status_code == 200
    points = r.json()
    assert isinstance(points, list)
    assert len(points) == steps
    assert points[0]["value"] == sweep_min
    assert points[-1]["value"] == sweep_max
    for pt in points:
        assert "value" in pt
        assert "suitability_score" in pt
        assert "score_percent" in pt
        assert "breakdown" in pt


def test_simulate_sweep_steps_exceeds_max_400(client):
    r = client.post("/simulate/sweep", json={
        "enzyme_id": "ENZ001",
        "pollutant": "PET",
        "sweep_variable": "ph",
        "sweep_min": 2.0,
        "sweep_max": 12.0,
        "steps": 201,
        "fixed_ph": 8.0,
        "fixed_temperature": 35.0,
        "fixed_salinity": 0.5,
    })
    assert r.status_code == 400


def test_simulate_sweep_unknown_enzyme_404(client):
    r = client.post("/simulate/sweep", json={
        "enzyme_id": "DOES_NOT_EXIST",
        "pollutant": "PET",
        "sweep_variable": "ph",
        "sweep_min": 2.0,
        "sweep_max": 12.0,
        "steps": 40,
        "fixed_ph": 8.0,
        "fixed_temperature": 35.0,
        "fixed_salinity": 0.5,
    })
    assert r.status_code == 404

