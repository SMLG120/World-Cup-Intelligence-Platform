"use client";

import { Save } from "lucide-react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useCreateSimulation } from "@/lib/queries";
import { useToast } from "@/components/ui/toast";
import { Button } from "@/components/ui/button";

interface SaveSimulationButtonProps {
  defaultName: string;
  simulationType: "tournament" | "wc2026" | "prediction" | "scenario" | "match";
  edition?: string;
  runs?: number;
  seed?: number | null;
  deterministic?: boolean;
  inputTeams?: string[];
  inputParameters?: Record<string, unknown>;
  scenarioOverrides?: Record<string, unknown>;
  statisticalResult?: unknown;
  mlResult?: unknown;
  ensembleResult?: unknown;
  tournamentResult?: unknown;
  championProbabilities?: unknown;
  bracketOutput?: unknown;
  result?: unknown;
  size?: "sm" | "md" | "lg";
  variant?: "primary" | "outline" | "ghost" | "danger";
}

export function SaveSimulationButton({
  defaultName,
  simulationType,
  edition,
  runs,
  seed,
  deterministic = false,
  inputTeams,
  inputParameters,
  scenarioOverrides,
  statisticalResult,
  mlResult,
  ensembleResult,
  tournamentResult,
  championProbabilities,
  bracketOutput,
  result,
  size = "sm",
  variant = "outline",
}: SaveSimulationButtonProps) {
  const { user } = useAuth();
  const router = useRouter();
  const create = useCreateSimulation();
  const { toast } = useToast();

  async function save() {
    if (!user) {
      toast("Sign in to save simulations to your account.", "warning");
      router.push("/login");
      return;
    }

    const name = window.prompt("Simulation name", defaultName)?.trim();
    if (!name) return;

    try {
      await create.mutateAsync({
        name,
        simulation_type: simulationType,
        edition,
        runs,
        seed,
        deterministic,
        input_teams: inputTeams,
        input_parameters: inputParameters ?? {},
        scenario_overrides: scenarioOverrides ?? {},
        statistical_result: statisticalResult,
        ml_result: mlResult,
        ensemble_result: ensembleResult,
        tournament_result: tournamentResult,
        champion_probabilities: championProbabilities,
        bracket_output: bracketOutput,
        result,
      });
      toast("Simulation saved.", "success");
    } catch (err) {
      toast(err instanceof Error ? err.message : "Simulation could not be saved.", "error");
    }
  }

  return (
    <Button onClick={save} disabled={create.isPending} variant={variant} size={size}>
      <Save size={14} />
      {create.isPending ? "Saving…" : "Save Simulation"}
    </Button>
  );
}
