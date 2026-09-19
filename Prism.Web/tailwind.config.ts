import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx,html}"],
  theme: {
    extend: {
      colors: {
        // Prism design tokens — OKLCH-tuned for perceptual uniformity.
        // See docs/design for the design brief.
        ink: {
          // Locked paper-theme text token — do not deviate without asking.
          DEFAULT: "#1A1917",
          muted: "oklch(0.55 0 0)",
          subtle: "oklch(0.72 0 0)",
          // Restyle tokens (PRISM_DESIGN_SYSTEM.md §1) — additive alongside
          // muted/subtle above until call sites migrate. Re-hued off the old
          // 285 (blue-violet) axis onto a warm axis to match the paper theme
          // and the "no blue anywhere" rule — chroma is low enough that this
          // reads as neutral gray either way.
          secondary: "oklch(0.442 0.017 80)",
          tertiary: "oklch(0.705 0.015 80)",
        },
        surface: {
          // Locked paper-theme background token — do not deviate without asking.
          DEFAULT: "#FAF9F5",
          alt: "#F5F3EC",
          sunken: "#ECE9DD",
          // Restyle tokens (PRISM_DESIGN_SYSTEM.md §1) — additive alongside
          // alt/sunken above until call sites migrate.
          subtle: "#F1EFE6",
          muted: "#ECE9DD",
        },
        border: {
          // Locked paper-theme border token — do not deviate without asking.
          DEFAULT: "#E7E4DA",
          strong: "#D6D2C4",
        },
        // Restyle hairline tokens (PRISM_DESIGN_SYSTEM.md §1) — border
        // aliases used by the restyled surfaces.
        hairline: {
          DEFAULT: "#E7E4DA",
          strong: "#D6D2C4",
        },
        // Primary-CTA surface — a lighter charcoal than `ink` (#1A1917),
        // used only for genuine primary-action buttons (Upload & Analyze,
        // chat send/stop, cache-hit Continue). Every other ink-black surface
        // (badges, avatars, overlays, code blocks) stays on `ink` itself.
        charcoal: {
          DEFAULT: "#343533",
        },
        // Accent is monochrome/ink-black per the locked design tokens — no
        // blue anywhere in the UI. DEFAULT/foreground double as the
        // shadcn "accent" hover-fill pairing (e.g. select/dropdown items).
        accent: {
          DEFAULT: "#F1EFE6",
          hover: "#1A1917",
          subtle: "#F1EFE6",
          fg: "#FFFFFF",
          foreground: "#1A1917",
        },
        // Restyle brand tokens (PRISM_DESIGN_SYSTEM.md §1).
        brand: {
          DEFAULT: "oklch(0.705 0.213 47.604)",
          hover: "oklch(0.646 0.222 41.116)",
          subtle: "oklch(0.98 0.016 73.684)",
        },
        // Unified 4-color status system for the audit progress screen
        // (PaperActivityView) — the SAME tokens drive both the stepper dots
        // and the log panel's bracketed stage tags, so the two never drift
        // into separate palettes again. pending/active reuse existing
        // ink-tertiary/brand tones; complete/failed match the emerald-500/
        // red-500 shades already used throughout the app.
        status: {
          pending: "oklch(0.705 0.015 286.067)",
          active: "oklch(0.705 0.213 47.604)",
          complete: "oklch(0.696 0.170 162.480)",
          failed: "oklch(0.637 0.237 25.331)",
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
      // Locked: nothing rounder than 6px, anywhere (except literal circles
      // via `rounded-full`, which this scale doesn't touch). Every step is
      // capped centrally here so no component needs a one-off override.
      borderRadius: {
        xs: "4px",
        sm: "6px",
        md: "6px",
        lg: "6px",
        xl: "6px",
        "2xl": "6px",
        "3xl": "6px",
        "4xl": "6px",
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
