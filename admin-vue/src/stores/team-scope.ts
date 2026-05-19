import { defineStore } from "pinia";

import { listTeams } from "@/shared/api/teams";
import type { TeamSummary } from "@/shared/types/team";

const SELECTED_TEAM_ID_KEY = "synapseflow.admin.selected_team_id";

function getStoredSelectedTeamId() {
  if (typeof window === "undefined") {
    return null;
  }

  const raw = window.localStorage.getItem(SELECTED_TEAM_ID_KEY);
  if (!raw) {
    return null;
  }

  const parsed = Number(raw);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

function setStoredSelectedTeamId(teamId: number | null) {
  if (typeof window === "undefined") {
    return;
  }

  if (teamId === null) {
    window.localStorage.removeItem(SELECTED_TEAM_ID_KEY);
    return;
  }

  window.localStorage.setItem(SELECTED_TEAM_ID_KEY, String(teamId));
}

interface TeamScopeState {
  teams: TeamSummary[];
  selectedTeamId: number | null;
  loading: boolean;
  errorMessage: string;
}

export const useTeamScopeStore = defineStore("team-scope", {
  state: (): TeamScopeState => ({
    teams: [],
    selectedTeamId: getStoredSelectedTeamId(),
    loading: false,
    errorMessage: "",
  }),
  getters: {
    selectedTeam: (state) =>
      state.teams.find((item) => item.id === state.selectedTeamId) ?? null,
    hasTeams: (state) => state.teams.length > 0,
  },
  actions: {
    async bootstrap() {
      if (this.loading) {
        return;
      }

      this.loading = true;
      this.errorMessage = "";

      try {
        const teams = await listTeams();
        this.teams = teams;

        if (teams.length === 0) {
          this.selectedTeamId = null;
          setStoredSelectedTeamId(null);
          return;
        }

        const hasStoredSelection = teams.some((item) => item.id === this.selectedTeamId);
        if (hasStoredSelection) {
          return;
        }

        this.selectedTeamId = teams[0]?.id ?? null;
        setStoredSelectedTeamId(this.selectedTeamId);
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : "团队列表加载失败";
      } finally {
        this.loading = false;
      }
    },
    setSelectedTeam(teamId: number | null) {
      this.selectedTeamId = teamId;
      setStoredSelectedTeamId(teamId);
    },
    clear() {
      this.teams = [];
      this.selectedTeamId = null;
      this.loading = false;
      this.errorMessage = "";
      setStoredSelectedTeamId(null);
    },
  },
});
