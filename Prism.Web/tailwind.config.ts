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
          // Restyle tokens (PRISM_DESIGN_SYSTEM.md §1) — additive alongside
          // muted/subtle above until call sites migrate.
          secondary: "oklch(0.442 0.017 285.786)",
          tertiary: "oklch(0.705 0.015 286.067)",
        },
        surface: {
          DEFAULT: "oklch(1 0 0)",
          alt: "oklch(0.98 0.012 285)",
          sunken: "oklch(0.97 0 0)",
          // Restyle tokens (PRISM_DESIGN_SYSTEM.md §1) — additive alongside
          // alt/sunken above until call sites migrate.
          subtle: "oklch(0.985 0 0)",
          muted: "oklch(0.967 0.001 286.375)",
        },
        border: {
          DEFAULT: "oklch(0.92 0 0)",
          strong: "oklch(0.85 0 0)",
        },
        // Restyle hairline tokens (PRISM_DESIGN_SYSTEM.md §1) — border
        // aliases used by the restyled surfaces.
        hairline: {
          DEFAULT: "oklch(0.920 0.004 286.320)",
          strong: "oklch(0.871 0.006 286.286)",
        },
        accent: {
          DEFAULT: "oklch(0.5 0.22 285)",
          hover: "oklch(0.45 0.22 285)",
          subtle: "oklch(0.96 0.03 285)",
          fg: "oklch(1 0 0)",
        },
        // Restyle brand tokens (PRISM_DESIGN_SYSTEM.md §1).
        brand: {
          DEFAULT: "oklch(0.705 0.213 47.604)",
          hover: "oklch(0.646 0.222 41.116)",
          subtle: "oklch(0.98 0.016 73.684)",
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
        // Restyle verdict tokens (PRISM_DESIGN_SYSTEM.md §1) — nested
        // bg/text/icon/border sets for the consolidated VerdictPill (PR 3).
        verdict: {
          supported: {
            bg: "oklch(0.962 0.044 156.743)",
            text: "oklch(0.508 0.118 165.612)",
            icon: "oklch(0.696 0.170 162.480)",
            border: "oklch(0.696 0.170 162.480)",
          },
          partial: {
            bg: "oklch(0.987 0.022 95.277)",
            text: "oklch(0.555 0.163 48.998)",
            icon: "oklch(0.769 0.188 70.080)",
            border: "oklch(0.769 0.188 70.080)",
          },
          refused: {
            bg: "oklch(0.969 0.015 12.422)",
            text: "oklch(0.514 0.222 16.935)",
            icon: "oklch(0.645 0.246 16.439)",
            border: "oklch(0.645 0.246 16.439)",
          },
          other: {
            bg: "oklch(0.968 0.007 247.896)",
            text: "oklch(0.446 0.043 257.281)",
            icon: "oklch(0.554 0.046 257.417)",
            border: "oklch(0.554 0.046 257.417)",
          },
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
        // Restyle font (PRISM_DESIGN_SYSTEM.md §1). No component currently
        // applies the `font-sans` utility (body copy is set directly in
        // index.css), so this swap has no visual effect until PR 4+ adopts it.
        sans: ['"Geist Variable"', "system-ui", "sans-serif"],
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
