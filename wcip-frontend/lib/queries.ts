"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { Team } from "./types";

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

export function useEloHistory(id: number) {
  return useQuery({
    queryKey: ["elo-history", id], queryFn: () => api.eloHistory(id), enabled: !!id,
  });
}

export function useSimulateMatch() {
  return useMutation({ mutationFn: (body: unknown) => api.simulateMatch(body) });
}

export function useSimulateTournament() {
  return useMutation({ mutationFn: (body: unknown) => api.simulateTournament(body) });
}

export function useCompareScenarios() {
  return useMutation({ mutationFn: (body: unknown) => api.compareScenarios(body) });
}

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

export function useAdminAnalytics() {
  return useQuery({ queryKey: ["admin-analytics"], queryFn: () => api.adminAnalytics(), retry: false });
}

export type { Team };
