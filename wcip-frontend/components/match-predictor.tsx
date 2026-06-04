"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useSimulateMatch, useTeams } from "@/lib/queries";
import { NEUTRAL_MODIFIERS, TeamModifiers } from "@/lib/types";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { ProbabilityBar } from "@/components/probability-bar";
import { pct } from "@/lib/utils";

const MOD_FIELDS: { key: keyof TeamModifiers; label: string; min: number; max: number; step: number }[] = [
  { key: "injury", label: "Availability", min: 0.4, max: 1, step: 0.05 },
  { key: "morale", label: "Morale", min: 0.7, max: 1.3, step: 0.05 },
  { key: "fatigue", label: "Freshness", min: 0.6, max: 1, step: 0.05 },
  { key: "attack", label: "Form", min: 0.6, max: 1.6, step: 0.05 },
];

function ModifierPanel({
  title, mods, onChange,
}: { title: string; mods: TeamModifiers; onChange: (m: TeamModifiers) => void }) {
  return (
    <div className="space-y-3">
      <span className="kicker">{title} adjustments</span>
      {MOD_FIELDS.map((f) => (
        <Slider
          key={f.key}
          label={f.label}
          display={`${mods[f.key].toFixed(2)}×`}
          min={f.min} max={f.max} step={f.step} value={mods[f.key]}
          onChange={(e) => onChange({ ...mods, [f.key]: parseFloat(e.target.value) })}
        />
      ))}
    </div>
  );
}

export function MatchPredictor() {
  const { data: teams } = useTeams();
  const mutation = useSimulateMatch();
  const [home, setHome] = useState("France");
  const [away, setAway] = useState("Argentina");
  const [showMods, setShowMods] = useState(false);
  const [homeMods, setHomeMods] = useState<TeamModifiers>(NEUTRAL_MODIFIERS);
  const [awayMods, setAwayMods] = useState<TeamModifiers>(NEUTRAL_MODIFIERS);

  const run = () =>
    mutation.mutate({
      home, away,
      home_modifiers: homeMods, away_modifiers: awayMods,
    });

  const result = mutation.data;

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_1.1fr]">
      <Card>
        <CardHeader className="flex items-center justify-between">
          <span className="kicker">Fixture</span>
          <button
            onClick={() => setShowMods((s) => !s)}
            className="text-xs uppercase tracking-wide text-muted hover:text-pitch"
          >
            {showMods ? "Hide" : "Scenario"} controls
          </button>
        </CardHeader>
        <CardBody className="space-y-4">
          <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
            <Select value={home} onChange={(e) => setHome(e.target.value)}>
              {teams?.map((t) => <option key={t.id} value={t.name}>{t.name}</option>)}
            </Select>
            <span className="display text-muted text-sm">VS</span>
            <Select value={away} onChange={(e) => setAway(e.target.value)}>
              {teams?.map((t) => <option key={t.id} value={t.name}>{t.name}</option>)}
            </Select>
          </div>

          <AnimatePresence>
            {showMods && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden grid sm:grid-cols-2 gap-5 pt-2"
              >
                <ModifierPanel title={home} mods={homeMods} onChange={setHomeMods} />
                <ModifierPanel title={away} mods={awayMods} onChange={setAwayMods} />
              </motion.div>
            )}
          </AnimatePresence>

          <Button onClick={run} disabled={mutation.isPending || home === away} className="w-full">
            {mutation.isPending ? "Simulating…" : "Predict outcome"}
          </Button>
          {home === away && <p className="text-xs text-signal">Pick two different teams.</p>}
        </CardBody>
      </Card>

      <Card>
        <CardHeader><span className="kicker">Prediction</span></CardHeader>
        <CardBody>
          {!result ? (
            <p className="text-muted text-sm py-12 text-center">
              Choose a fixture and run a prediction to see win/draw/loss
              probabilities, expected goals, and the reasoning.
            </p>
          ) : (
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">
              <ProbabilityBar home={result.home} away={result.away} probabilities={result.probabilities} />
              <div className="flex justify-around border-y border-line py-3">
                <div className="text-center">
                  <div className="kicker">{result.home} xG</div>
                  <div className="tnum text-2xl text-pitch">{result.home_xg.toFixed(2)}</div>
                </div>
                <div className="text-center">
                  <div className="kicker">{result.away} xG</div>
                  <div className="tnum text-2xl text-signal">{result.away_xg.toFixed(2)}</div>
                </div>
              </div>
              <div>
                <span className="kicker">Why</span>
                <p className="text-sm mt-1 leading-relaxed">{result.explanation}</p>
              </div>
              <div className="space-y-1.5">
                {result.factors.slice(0, 4).map((f) => (
                  <div key={f.name} className="flex justify-between text-xs border-b border-line/60 pb-1.5">
                    <span className="text-muted">{f.name}</span>
                    <span className="text-fg text-right">{f.detail}</span>
                  </div>
                ))}
              </div>
            </motion.div>
          )}
          {mutation.isError && (
            <p className="text-signal text-sm mt-3">{(mutation.error as Error).message}</p>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

export { pct };
