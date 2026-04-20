"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { askApi, type AskTeamOption } from "@/lib/api/endpoints/ask";

const LAST_TEAM_STORAGE_KEY = "synapseflow.current-team";

interface TeamScopeContextValue {
  teamId: number | null;
  setTeamId: (teamId: number | null) => void;
  teams: AskTeamOption[];
  teamsLoading: boolean;
  selectedTeam: AskTeamOption | null;
}

const TeamScopeContext = createContext<TeamScopeContextValue | null>(null);

function buildStorageKey(userId: number): string {
  return `${LAST_TEAM_STORAGE_KEY}.${userId}`;
}

function readStoredTeamId(storageKey: string): number | null {
  if (typeof window === "undefined") return null;
  const rawValue = window.localStorage.getItem(storageKey);
  if (!rawValue) return null;
  const parsed = Number(rawValue);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function writeStoredTeamId(storageKey: string, teamId: number | null) {
  if (typeof window === "undefined") return;
  if (teamId == null) {
    window.localStorage.removeItem(storageKey);
    return;
  }
  window.localStorage.setItem(storageKey, String(teamId));
}

export function TeamScopeProvider({
  userId,
  children,
}: {
  userId: number;
  children: ReactNode;
}) {
  const storageKey = useMemo(() => buildStorageKey(userId), [userId]);
  const [teamIdState, setTeamIdState] = useState<number | null>(null);
  const [teams, setTeams] = useState<AskTeamOption[]>([]);
  const [teamsLoading, setTeamsLoading] = useState(true);

  const setTeamId = useCallback(
    (nextTeamId: number | null) => {
      setTeamIdState(nextTeamId);
      writeStoredTeamId(storageKey, nextTeamId);
    },
    [storageKey],
  );

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      setTeamsLoading(true);
      try {
        const nextTeams = await askApi.listTeams();
        if (cancelled) return;

        setTeams(nextTeams);

        const storedTeamId = readStoredTeamId(storageKey);
        const resolvedTeamId =
          storedTeamId && nextTeams.some((team) => team.id === storedTeamId)
            ? storedTeamId
            : nextTeams[0]?.id ?? null;

        setTeamIdState(resolvedTeamId);
        writeStoredTeamId(storageKey, resolvedTeamId);
      } catch {
        if (cancelled) return;
        setTeams([]);
        setTeamIdState(null);
        writeStoredTeamId(storageKey, null);
      } finally {
        if (!cancelled) {
          setTeamsLoading(false);
        }
      }
    };

    void run();

    return () => {
      cancelled = true;
    };
  }, [storageKey]);

  const value = useMemo<TeamScopeContextValue>(
    () => ({
      teamId: teamIdState,
      setTeamId,
      teams,
      teamsLoading,
      selectedTeam: teams.find((team) => team.id === teamIdState) ?? null,
    }),
    [setTeamId, teamIdState, teams, teamsLoading],
  );

  return <TeamScopeContext.Provider value={value}>{children}</TeamScopeContext.Provider>;
}

export function useTeamScope() {
  const context = useContext(TeamScopeContext);
  if (!context) {
    throw new Error("useTeamScope must be used within TeamScopeProvider");
  }
  return context;
}
