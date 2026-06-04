import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{vue,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f6f8fb",
          100: "#eef2f7",
          500: "#3b82f6",
          700: "#1d4ed8",
        },
      },
      boxShadow: {
        panel: "0 1px 2px rgba(15, 23, 42, 0.06), 0 8px 24px rgba(15, 23, 42, 0.04)",
      },
      borderRadius: {
        panel: "16px",
      },
    },
  },
  plugins: [],
} satisfies Config;
