"""Dynamic head-to-head prediction regressions."""


def _predict(client, home: str, away: str) -> dict:
    response = client.post(
        "/api/v1/match/predict",
        json={"home_team": home, "away_team": away, "include_shap": False},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_different_team_pairs_produce_different_predictions(client):
    mexico_czechia = _predict(client, "Mexico", "Czechia")
    brazil_mexico = _predict(client, "Brazil", "Mexico")

    assert mexico_czechia["probabilities"] != brazil_mexico["probabilities"]
    assert mexico_czechia["feature_snapshot"]["features"] != brazil_mexico["feature_snapshot"]["features"]


def test_reversed_teams_logically_reverse_probabilities(client):
    forward = _predict(client, "Mexico", "Czechia")
    reverse = _predict(client, "Czechia", "Mexico")

    assert abs(forward["probabilities"]["home_win"] - reverse["probabilities"]["away_win"]) < 0.20
    assert abs(forward["probabilities"]["away_win"] - reverse["probabilities"]["home_win"]) < 0.20
    assert abs(forward["probabilities"]["draw"] - reverse["probabilities"]["draw"]) < 0.12


def test_missing_team_data_uses_safe_fallbacks(client):
    body = _predict(client, "Atlantis", "Brazil")
    probs = body["probabilities"]

    assert abs(sum(probs.values()) - 1.0) < 0.001
    assert body["method_breakdown"]["elo"]
    assert body["feature_snapshot"]["features"]["elo_diff"] != 0


def test_ensemble_output_matches_method_weights(client):
    body = _predict(client, "Mexico", "Czechia")
    methods = body["method_breakdown"]
    weights = body["method_weights"]

    expected = {
        outcome: sum(methods[name][outcome] * weights[name] for name in weights)
        for outcome in ("home_win", "draw", "away_win")
    }
    for outcome, value in expected.items():
        assert abs(value - body["probabilities"][outcome]) < 0.001
