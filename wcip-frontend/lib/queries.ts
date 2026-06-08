"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { Team } from "./types";

// ── Teams ─────────────────────────────────────────────────────────────────────

export function useTeams(confederation?: string) {
  return useQuery({
    queryKey: ["teams", confederation ?? "all"],
    queryFn: () => api.teams(confederation),
    staleTime: 5 * 60 * 1000,
  });
}

export function useTeam(id: number) {
  return useQuery({ queryKey: ["team", id], queryFn: () => api.team(id), enabled: !!id });
}

export function usePlayer(id: number, enabled = true) {
  return useQuery({
    queryKey: ["player", id],
    queryFn: () => api.player(id),
    enabled: enabled && Number.isFinite(id) && id > 0,
    retry: false,
  });
}

export function useEloHistory(id: number) {
  return useQuery({
    queryKey: ["elo-history", id], queryFn: () => api.eloHistory(id), enabled: !!id,
  });
}

// ── Statistical predictions ───────────────────────────────────────────────────

export function useSimulateMatch() {
  return useMutation({ mutationFn: (body: unknown) => api.simulateMatch(body) });
}

export function useSimulateTournament() {
  return useMutation({ mutationFn: (body: unknown) => api.simulateTournament(body) });
}

export function useCompareScenarios() {
  return useMutation({ mutationFn: (body: unknown) => api.compareScenarios(body) });
}

// ── Simulations (saved, authed) ───────────────────────────────────────────────

export function useSimulations(page = 1) {
  return useQuery({ queryKey: ["simulations", page], queryFn: () => api.listSimulations(page) });
}

export function useSimulation(id: number) {
  return useQuery({
    queryKey: ["simulation", id], queryFn: () => api.getSimulation(id), enabled: !!id,
  });
}

export function useCreateSimulation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: unknown) => api.createSimulation(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["simulations"] }),
  });
}

export function useUpdateSimulation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: unknown }) => api.updateSimulation(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["simulations"] }),
  });
}

export function useDuplicateSimulation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.duplicateSimulation(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["simulations"] }),
  });
}

export function useDeleteSimulation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteSimulation(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["simulations"] }),
  });
}

// ── Admin ─────────────────────────────────────────────────────────────────────

export function useAdminAnalytics() {
  return useQuery({ queryKey: ["admin-analytics"], queryFn: () => api.adminAnalytics(), retry: false });
}

// ── ML predictions (Phase 2) ──────────────────────────────────────────────────

export function useMLPredict() {
  return useMutation({
    mutationFn: (body: Parameters<typeof api.mlPredict>[0]) => api.mlPredict(body),
  });
}

export function useMLModels() {
  return useQuery({
    queryKey: ["ml-models"],
    queryFn: () => api.mlModels(),
    staleTime: 60 * 1000,
  });
}

export function useMLFeatures(home: string, away: string, date?: string, enabled = true) {
  return useQuery({
    queryKey: ["ml-features", home, away, date ?? "today"],
    queryFn: () => api.mlFeatures(home, away, date),
    enabled: enabled && !!home && !!away,
    staleTime: 5 * 60 * 1000,
  });
}

export function useMLExplanations(
  home: string,
  away: string,
  model = "xgboost",
  date?: string,
  enabled = true,
) {
  return useQuery({
    queryKey: ["ml-explanations", home, away, model, date ?? "today"],
    queryFn: () => api.mlExplanations(home, away, model, date),
    enabled: enabled && !!home && !!away,
    staleTime: 5 * 60 * 1000,
  });
}

// ── WC 2026 ───────────────────────────────────────────────────────────────────

export function useWC2026Teams(params?: { confederation?: string; confirmed_only?: boolean }) {
  return useQuery({
    queryKey: ["wc2026-teams", params?.confederation ?? "all", params?.confirmed_only ?? false],
    queryFn: () => api.wc2026Teams(params),
    staleTime: 10 * 60 * 1000,
  });
}

export function useWC2026Groups() {
  return useQuery({
    queryKey: ["wc2026-groups"],
    queryFn: () => api.wc2026Groups(),
    staleTime: 10 * 60 * 1000,
  });
}

export function useWC2026Simulate() {
  return useMutation({
    mutationFn: ({
      runs,
      overrides,
    }: {
      runs: number;
      overrides?: Record<string, Record<string, number>>;
    }) => api.wc2026Simulate(runs, overrides),
  });
}

export function useWC2026TeamDetail(teamName: string, enabled = true) {
  return useQuery({
    queryKey: ["wc2026-team-detail", teamName],
    queryFn: () => api.wc2026TeamDetail(teamName),
    enabled: enabled && !!teamName,
    staleTime: 5 * 60 * 1000,
  });
}

export function useWC2026Players(teamName: string, enabled = true) {
  return useQuery({
    queryKey: ["wc2026-players", teamName],
    queryFn: () => api.wc2026Players(teamName),
    enabled: enabled && !!teamName,
    staleTime: 5 * 60 * 1000,
  });
}

export type { Team };
