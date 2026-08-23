import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx,html}"],
  theme: {
    extend: {
      colors: {
        // Prism design tokens — OKLCH-tuned for perceptual uniformity.
        // See docs/design for the design brief.
        ink: {
          DEFAULT: "oklch(0.145 0 0)",
          muted: "oklch(0.55 0 0)",
          subtle: "oklch(0.72 0 0)",
        },
        surface: {
          DEFAULT: "oklch(1 0 0)",
          alt: "oklch(0.98 0.012 285)",
          sunken: "oklch(0.97 0 0)",
        },
        border: {
          DEFAULT: "oklch(0.92 0 0)",
          strong: "oklch(0.85 0 0)",
        },
        accent: {
          DEFAULT: "oklch(0.5 0.22 285)",
          hover: "oklch(0.45 0.22 285)",
          subtle: "oklch(0.96 0.03 285)",
          fg: "oklch(1 0 0)",
        },
        supported: {
          DEFAULT: "oklch(0.55 0.10 145)",
          bg: "oklch(0.98 0.02 145)",
          border: "oklch(0.55 0.10 145)",
        },
        partial: {
          DEFAULT: "oklch(0.65 0.10 75)",
          bg: "oklch(0.98 0.02 75)",
          border: "oklch(0.65 0.10 75)",
        },
        refused: {
          DEFAULT: "oklch(0.58 0.14 25)",
          bg: "oklch(0.97 0.02 25)",
          border: "oklch(0.58 0.14 25)",
        },
        // shadcn/ui primitive tokens (internal chrome only — app components
        // must use the tokens above, not these).
        background: "var(--background)",
        foreground: "var(--foreground)",
        card: {
          DEFAULT: "var(--card)",
          foreground: "var(--card-foreground)",
        },
        popover: {
          DEFAULT: "var(--popover)",
          foreground: "var(--popover-foreground)",
        },
        primary: {
          DEFAULT: "var(--primary)",
          foreground: "var(--primary-foreground)",
        },
        secondary: {
          DEFAULT: "var(--secondary)",
          foreground: "var(--secondary-foreground)",
        },
        muted: {
          DEFAULT: "var(--muted)",
          foreground: "var(--muted-foreground)",
        },
        destructive: "var(--destructive)",
        input: "var(--input)",
        ring: "var(--ring)",
      },
      fontFamily: {
        sans: ['"Inter Variable"', "ui-sans-serif", "system-ui", "sans-serif"],
        display: ['"Manrope Variable"', '"Inter Variable"', "ui-sans-serif", "sans-serif"],
        mono: ['"JetBrains Mono Variable"', "ui-monospace", "monospace"],
      },
      borderRadius: {
        xs: "4px",
        sm: "6px",
        md: "8px",
        lg: "10px",
      },
      boxShadow: {
        card: "0 1px 2px 0 oklch(0.145 0 0 / 0.04), 0 1px 3px 0 oklch(0.145 0 0 / 0.06)",
        "card-hover": "0 2px 4px 0 oklch(0.145 0 0 / 0.06), 0 4px 8px 0 oklch(0.145 0 0 / 0.08)",
        drawer: "-4px 0 24px 0 oklch(0.145 0 0 / 0.04)",
      },
      transitionTimingFunction: {
        smooth: "cubic-bezier(0.32, 0.72, 0, 1)",
      },
      transitionDuration: {
        quick: "120ms",
        smooth: "200ms",
      },
    },
  },
} satisfies Config;
