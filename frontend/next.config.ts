import type { NextConfig } from "next";

const allowedDevOrigins =
  process.env.NEXT_ALLOWED_DEV_ORIGINS?.split(",")
    .map((s) => s.trim())
    .filter(Boolean) ?? [];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async redirects() {
    return [
      { source: "/kb-chat", destination: "/ask", permanent: false },
      { source: "/assistant-lab", destination: "/ask", permanent: false },
      { source: "/kb-curation", destination: "/admin", permanent: false },
      { source: "/revision", destination: "/admin", permanent: false },
      { source: "/prototype", destination: "/admin", permanent: false },
      { source: "/documents", destination: "/admin/documents", permanent: false },
    ];
  },
  ...(allowedDevOrigins.length > 0 ? { allowedDevOrigins } : {}),
};

export default nextConfig;
