"""Prediction, simulation, and scenario API tests."""


def test_list_teams_seeded(client):
    r = client.get("/api/v1/teams")
    assert r.status_code == 200
    teams = r.json()
    assert len(teams) >= 48
    assert {"Brazil", "Mexico", "Czechia", "DR Congo"}.issubset({team["name"] for team in teams})


def test_team_detail_and_404(client):
    teams = client.get("/api/v1/teams").json()
    tid = teams[0]["id"]
    assert client.get(f"/api/v1/teams/{tid}").status_code == 200
    assert client.get("/api/v1/teams/999999").status_code == 404


def test_match_simulate_probabilities(client):
    r = client.post("/api/v1/match/simulate",
                    json={"home": "Brazil", "away": "Ghana"})
    assert r.status_code == 200
    body = r.json()
    p = body["probabilities"]
    assert abs(sum(p.values()) - 1.0) < 1e-6
    assert p["home_win"] > p["away_win"]      # Brazil favoured
    assert body["explanation"]
    assert body["factors"]


def test_match_unknown_team(client):
    r = client.post("/api/v1/match/simulate",
                    json={"home": "Atlantis", "away": "Brazil"})
    assert r.status_code == 404


def test_injury_modifier_shifts_probability(client):
    base = client.post("/api/v1/match/simulate",
                       json={"home": "France", "away": "Brazil"}).json()
    hurt = client.post("/api/v1/match/simulate",
                       json={"home": "France", "away": "Brazil",
                             "away_modifiers": {"injury": 0.7}}).json()
    assert hurt["probabilities"]["home_win"] > base["probabilities"]["home_win"]


def test_tournament_sync(client):
    r = client.post("/api/v1/tournament/simulate",
                    json={"edition": "2022", "runs": 300})
    assert r.status_code == 200
    body = r.json()
    total = sum(t["champion"] for t in body["teams"])
    # API rounds each probability to 5 dp; allow accumulated rounding error.
    assert abs(total - 1.0) < 1e-3


def test_tournament_sync_threshold_guard(client):
    r = client.post("/api/v1/tournament/simulate",
                    json={"edition": "2022", "runs": 49999})
    assert r.status_code == 413  # too big for sync, must use /simulations


def test_world_cup_2026_simulation_runs(client):
    r = client.post("/api/v1/world-cup/simulate",
                    json={"year": 2026, "runs": 100})
    assert r.status_code == 200
    body = r.json()
    assert body["year"] == 2026
    assert body["runs"] == 100
    assert body["seed"] is not None
    assert body["deterministic"] is False
    assert body["teams"]
    assert sum(t["champion"] for t in body["teams"]) > 0


def test_tournament_seed_semantics(client):
    first = client.post("/api/v1/world-cup/simulate",
                        json={"year": 2026, "runs": 100}).json()
    second = client.post("/api/v1/world-cup/simulate",
                         json={"year": 2026, "runs": 100}).json()
    assert first["seed"] != second["seed"]
    assert first["deterministic"] is False
    assert second["deterministic"] is False

    seeded_a = client.post("/api/v1/world-cup/simulate",
                           json={"year": 2026, "runs": 100, "seed": 99}).json()
    seeded_b = client.post("/api/v1/world-cup/simulate",
                           json={"year": 2026, "runs": 100, "seed": 99}).json()
    assert seeded_a["seed"] == seeded_b["seed"] == 99
    assert seeded_a["deterministic"] is True
    assert seeded_a["teams"] == seeded_b["teams"]


def test_world_cup_2026_groups_are_official_shape(client):
    r = client.get("/api/v1/world-cup/groups?year=2026")
    assert r.status_code == 200
    body = r.json()
    assert body["draw_complete"] is True
    assert len(body["groups"]) == 12
    assert all(len(teams) == 4 for teams in body["groups"].values())
    assert body["groups"]["A"] == ["Mexico", "South Africa", "South Korea", "Czechia"]


def test_player_registry_endpoints(client):
    assert client.get("/api/v1/players").status_code == 200
    assert client.get("/api/v1/players/999999").status_code == 404


def test_compatibility_aliases(client):
    assert client.get("/api/v1/world_cup/groups?year=2026").status_code == 200
    assert client.get("/api/v1/world_cup/standings?year=2026").status_code == 200
    r = client.post("/api/v1/matches/predict",
                    json={"home": "Mexico", "away": "Czechia"})
    assert r.status_code == 200

    sim = client.post("/api/v1/simulations/tournament",
                      json={"edition": "2026", "runs": 100})
    assert sim.status_code == 200
    assert sim.json()["year"] == 2026

    scenarios = client.post("/api/v1/scenarios",
                            json={"edition": "2026", "runs": 100,
                                  "scenarios": [
                                      {"label": "base", "overrides": {}},
                                      {"label": "mexico boost",
                                       "overrides": {"Mexico": {"attack": 1.1}}},
                                  ]})
    assert scenarios.status_code == 200
    assert scenarios.json()["edition"] == "2026"


def test_saved_simulation_lifecycle(client, auth_headers):
    created = client.post("/api/v1/simulations", headers=auth_headers,
                          json={"edition": "2022", "runs": 300,
                                "name": "Test sim"}).json()
    assert created["status"] == "completed"
    sim_id = created["id"]

    got = client.get(f"/api/v1/simulations/{sim_id}", headers=auth_headers)
    assert got.status_code == 200
    assert got.json()["result"] is not None

    # Make public, fetch via token.
    patched = client.patch(f"/api/v1/simulations/{sim_id}", headers=auth_headers,
                           json={"is_public": True}).json()
    token = patched["public_token"]
    assert client.get(f"/api/v1/simulations/public/{token}").status_code == 200

    # Duplicate.
    dup = client.post(f"/api/v1/simulations/{sim_id}/duplicate", headers=auth_headers)
    assert dup.status_code == 201
    assert dup.json()["name"].endswith("(copy)")

    # Delete.
    assert client.delete(f"/api/v1/simulations/{sim_id}",
                         headers=auth_headers).status_code == 204
    assert client.get(f"/api/v1/simulations/{sim_id}",
                      headers=auth_headers).status_code == 404


def test_saved_simulation_full_result_and_compare_are_user_scoped(client, auth_headers):
    payload_a = {
        "name": "WC 2026 saved run A",
        "simulation_type": "wc2026",
        "edition": "2026",
        "runs": 100,
        "seed": 123,
        "deterministic": True,
        "tournament_result": {
            "year": 2026,
            "runs": 100,
            "seed": 123,
            "deterministic": True,
            "teams": [
                {"team": "France", "champion": 0.2, "final": 0.3, "semi": 0.4,
                 "quarter": 0.5, "round_of_16": 0.8, "expected_finish": 5,
                 "champion_ci_low": 0.1, "champion_ci_high": 0.3},
                {"team": "Brazil", "champion": 0.1, "final": 0.2, "semi": 0.3,
                 "quarter": 0.4, "round_of_16": 0.7, "expected_finish": 6,
                 "champion_ci_low": 0.05, "champion_ci_high": 0.2},
            ],
        },
    }
    payload_b = {
        **payload_a,
        "name": "WC 2026 saved run B",
        "seed": 456,
        "tournament_result": {
            **payload_a["tournament_result"],
            "seed": 456,
            "teams": [
                {**payload_a["tournament_result"]["teams"][0], "champion": 0.15},
                {**payload_a["tournament_result"]["teams"][1], "champion": 0.2},
            ],
        },
    }

    created_a = client.post("/api/v1/simulations", headers=auth_headers, json=payload_a)
    created_b = client.post("/api/v1/simulations", headers=auth_headers, json=payload_b)
    assert created_a.status_code == 201
    assert created_b.status_code == 201
    sim_a = created_a.json()["id"]
    sim_b = created_b.json()["id"]
    assert created_a.json()["status"] == "completed"
    assert created_a.json()["result"]["teams"][0]["team"] == "France"

    comparison = client.post(
        f"/api/v1/simulations/{sim_a}/compare",
        headers=auth_headers,
        json={"simulation_ids": [sim_b]},
    )
    assert comparison.status_code == 200
    delta_rows = comparison.json()["champion_deltas"][0]["deltas"]
    brazil_delta = next(row["delta"] for row in delta_rows if row["team"] == "Brazil")
    assert round(brazil_delta, 6) == 0.1

    client.post("/api/v1/auth/register",
                json={"email": "other@example.com", "password": "password123"})
    other_token = client.post("/api/v1/auth/login",
                              data={"username": "other@example.com", "password": "password123"}).json()
    other_headers = {"Authorization": f"Bearer {other_token['access_token']}"}
    assert client.get(f"/api/v1/simulations/{sim_a}", headers=other_headers).status_code == 404
    assert client.post(
        f"/api/v1/simulations/{sim_a}/compare",
        headers=other_headers,
        json={"simulation_ids": [sim_b]},
    ).status_code == 404


def test_simulations_require_auth(client):
    assert client.get("/api/v1/simulations").status_code == 401


def test_scenario_compare(client):
    r = client.post("/api/v1/scenario/compare",
                    json={"edition": "2022", "runs": 200,
                          "scenarios": [
                              {"label": "base", "overrides": {}},
                              {"label": "no mbappe",
                               "overrides": {"France": {"injury": 0.75}}},
                          ]})
    assert r.status_code == 200
    assert len(r.json()["scenarios"]) == 2


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"
