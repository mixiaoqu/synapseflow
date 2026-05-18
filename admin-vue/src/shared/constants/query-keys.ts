function compactObject(input?: Record<string, unknown>) {
  if (!input) {
    return {};
  }

  return Object.fromEntries(
    Object.entries(input).filter(([, value]) => value !== undefined && value !== null && value !== ""),
  );
}

export const queryKeys = {
  auth: {
    all: ["auth"] as const,
    currentUser: ["auth", "current-user"] as const,
  },
  dashboard: {
    all: ["dashboard"] as const,
    summary: ["dashboard", "summary"] as const,
  },
  resources: {
    all: ["resources"] as const,
    list: (resource: string, filters?: Record<string, unknown>) =>
      ["resources", resource, "list", compactObject(filters)] as const,
    detail: (resource: string, id: string | number) =>
      ["resources", resource, "detail", String(id)] as const,
  },
} as const;
