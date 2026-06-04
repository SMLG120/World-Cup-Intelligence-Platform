"""Prediction, simulation, and scenario API tests."""


def test_list_teams_seeded(client):
    r = client.get("/api/v1/teams")
    assert r.status_code == 200
    teams = r.json()
    assert len(teams) == 32
    # Sorted by Elo desc -> Brazil first in the 2022 seed.
    assert teams[0]["name"] == "Brazil"


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
