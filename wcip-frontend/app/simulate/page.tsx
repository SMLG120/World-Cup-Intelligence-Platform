import { MatchPredictor } from "@/components/match-predictor";

export default function SimulatePage() {
  return (
    <div className="space-y-8">
      <header>
        <p className="kicker mb-2">Single match</p>
        <h1 className="display text-4xl">Match predictor</h1>
        <p className="text-muted mt-2 max-w-2xl">
          Pick two nations and get win/draw/loss probabilities, expected goals,
          and a plain-language explanation. Open the scenario controls to model
          injuries, morale, freshness, and form.
        </p>
      </header>
      <MatchPredictor />
    </div>
  );
}
