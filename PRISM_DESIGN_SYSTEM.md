# PRISM_DESIGN_SYSTEM.md

Visual restyle spec for `Prism.Web/`. Match the prism-landing design
system with app-appropriate adaptations for light theme and long
reading surfaces.

**Scope:** visual restyle + component polish only. No layout changes.
No behavior changes. Ship in the PR order at the bottom of this doc.

**Sources of truth:**
- `LANDING_DESIGN_EXTRACT.md` — landing design tokens and components
- `PRISM_APP_INVENTORY.md` — current app state and file paths
- This document — resolved decisions and implementation spec

If any conflict, this document wins.

---

## 1 · Design Tokens

Add these to `Prism.Web/tailwind.config.ts` (extend, don't replace).
Every color used in components must reference these tokens. No
hardcoded hex anywhere.

### Colors

```ts
// tailwind.config.ts theme.extend.colors
{
  // Brand
  brand: {
    DEFAULT: 'oklch(0.705 0.213 47.604)',   // orange-500
    hover:   'oklch(0.646 0.222 41.116)',   // orange-600
    subtle:  'oklch(0.98  0.016 73.684)',   // orange-50
  },

  // Verdict labels (light-tuned — see decision 2 in Claude thread)
  verdict: {
    supported: {
      bg:    'oklch(0.962 0.044 156.743)',  // emerald-50
      text:  'oklch(0.508 0.118 165.612)',  // emerald-700
      icon:  'oklch(0.696 0.170 162.480)',  // emerald-500
      border:'oklch(0.696 0.170 162.480)',  // emerald-500
    },
    partial: {
      bg:    'oklch(0.987 0.022 95.277)',   // amber-50
      text:  'oklch(0.555 0.163 48.998)',   // amber-700
      icon:  'oklch(0.769 0.188 70.080)',   // amber-500
      border:'oklch(0.769 0.188 70.080)',   // amber-500
    },
    refused: {
      bg:    'oklch(0.969 0.015 12.422)',   // rose-50
      text:  'oklch(0.514 0.222 16.935)',   // rose-700
      icon:  'oklch(0.645 0.246 16.439)',   // rose-500
      border:'oklch(0.645 0.246 16.439)',   // rose-500
    },
    other: {
      bg:    'oklch(0.968 0.007 247.896)',  // slate-50
      text:  'oklch(0.446 0.043 257.281)',  // slate-700
      icon:  'oklch(0.554 0.046 257.417)',  // slate-500
      border:'oklch(0.554 0.046 257.417)',  // slate-500
    },
  },

  // Surface & text (semantic aliases over Tailwind zinc)
  surface: {
    DEFAULT: 'oklch(1 0 0)',                // white
    subtle:  'oklch(0.985 0 0)',            // zinc-50
    muted:   'oklch(0.967 0.001 286.375)',  // zinc-100
  },
  ink: {
    DEFAULT:   'oklch(0.141 0.005 285.823)',// zinc-900 (primary text)
    secondary: 'oklch(0.442 0.017 285.786)',// zinc-600
    tertiary:  'oklch(0.705 0.015 286.067)',// zinc-400
  },
  hairline: {
    DEFAULT: 'oklch(0.920 0.004 286.320)',  // zinc-200
    strong:  'oklch(0.871 0.006 286.286)',  // zinc-300
  },
}
```

### Gradient

Signature move. Used on the audit summary number and any hero-style
moments (empty state headline highlight).

```css
/* Add to globals.css */
.gradient-brand {
  background: linear-gradient(90deg,
    oklch(0.705 0.213 47.604) 0%,   /* orange-500 */
    oklch(0.645 0.246 16.439) 100%  /* rose-500 */
  );
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
```

### Fonts

```bash
npm install @fontsource-variable/geist @fontsource-variable/jetbrains-mono
```

In `Prism.Web/src/main.tsx`:
```ts
import '@fontsource-variable/geist';
import '@fontsource-variable/jetbrains-mono';
```

In `tailwind.config.ts`:
```ts
fontFamily: {
  sans: ['"Geist Variable"', 'system-ui', 'sans-serif'],
  mono: ['"JetBrains Mono Variable"', 'ui-monospace', 'monospace'],
}
```

**Usage rule (locked):**
- **Mono (`font-mono`):** numbers, section refs (`Section 3.3`, `Table 1`, `p. 7`), verdict pill labels, eyebrow labels, code identifiers, "Ready" / status labels, timestamps
- **Sans (`font-sans`):** everything else — headlines, claim summaries, verbatim quotes, buttons, UI chrome, empty state copy

### Radii, borders, shadows

- Buttons: `rounded-lg`
- Pills: `rounded-full`
- Cards: `rounded-xl`
- Drawer: `rounded-none` (flush edges)
- Input: `rounded-full` (chat) / `rounded-lg` (form fields)
- Borders: 1px default (`border` + `border-hairline`), 3px accent (verdict left border on claim rows)
- Shadows: **none** on cards. Elevated overlays (dropdowns, tooltips) use `shadow-sm` maximum. Landing uses no shadows either.

### Spacing rhythm

- Section vertical padding: `py-6` (compact surfaces) / `py-8` (main content sections)
- Card padding: `p-5` default, `p-4` for compact tiles
- Row gap in lists: `space-y-3`
- Sidebar inner padding: `px-4 py-6`

---

## 2 · Logo

Extract from `prism-landing/components/site/prism-logo.tsx`. Copy the
SVG into `Prism.Web/src/assets/prism-logo.svg` and create a matching
React component at `Prism.Web/src/components/PrismLogo.tsx` that
accepts a `className` prop.

Use it everywhere the current black diamond appears (sidebar top,
top nav, empty state, favicon). Replace favicon in
`Prism.Web/public/` with a 32x32 rendering of the same logo.

---

## 3 · Verdict Pill — consolidate first

App currently renders verdict pills inline in multiple places. Build
one component, use it everywhere.

**File:** `Prism.Web/src/components/VerdictPill.tsx`

```tsx
import { Check, AlertTriangle, X } from 'lucide-react';
import { cn } from '@/lib/utils';

type Verdict = 'supported' | 'partial' | 'refused' | 'other';

const config = {
  supported: {
    label: 'SUPPORTED',
    Icon: Check,
    classes: 'bg-verdict-supported-bg text-verdict-supported-text',
    iconClass: 'text-verdict-supported-icon',
  },
  partial: {
    label: 'PARTIAL',
    Icon: AlertTriangle,
    classes: 'bg-verdict-partial-bg text-verdict-partial-text',
    iconClass: 'text-verdict-partial-icon',
  },
  refused: {
    label: 'NOT SUPPORTED',
    Icon: X,
    classes: 'bg-verdict-refused-bg text-verdict-refused-text',
    iconClass: 'text-verdict-refused-icon',
  },
  other: {
    label: 'OTHER',
    Icon: AlertTriangle,
    classes: 'bg-verdict-other-bg text-verdict-other-text',
    iconClass: 'text-verdict-other-icon',
  },
};

export function VerdictPill({
  verdict,
  size = 'default',
  className,
}: {
  verdict: Verdict;
  size?: 'default' | 'sm';
  className?: string;
}) {
  const c = config[verdict];
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full font-mono uppercase tracking-wider',
        size === 'default' ? 'px-2.5 py-1 text-xs' : 'px-2 py-0.5 text-[10px]',
        c.classes,
        className
      )}
    >
      <c.Icon className={cn('h-3 w-3', c.iconClass)} strokeWidth={2.5} />
      {c.label}
    </span>
  );
}
```

Then find every place a verdict is currently rendered inline (see
`PRISM_APP_INVENTORY.md` section 4 for the list) and replace with
`<VerdictPill verdict={...} />`.

---

## 4 · Surface-by-surface changes

Format: file path → before → after. When "after" says a class, use the
exact class. When it says a token, use the token defined in section 1.

### 4A · Top nav bar

**Files:** the top nav component from `PRISM_APP_INVENTORY.md` §3.

- Background: `bg-surface` (white)
- Bottom border: `border-b border-hairline`
- Left: `<PrismLogo className="h-6 w-6" />` + wordmark `<span className="font-sans font-semibold text-ink">Prism</span>`
- Remove "Audit Console" subtitle text
- Right: avatar unchanged, user dropdown unchanged
- Padding: `px-6 py-3`

### 4B · Sidebar

- Background: `bg-surface` (was gray, now white)
- Right border: `border-r border-hairline`
- Logo row: same `<PrismLogo />` + "Prism" wordmark treatment as nav
- **Upload button:** `bg-brand hover:bg-brand-hover text-white rounded-lg px-4 py-2.5 font-sans text-sm font-medium flex items-center gap-2`. Use `<Upload />` icon from lucide-react.
- Section eyebrows ("CURRENT CONTEXT", "PAPERS"): `font-sans text-xs uppercase tracking-wider text-ink-tertiary`
- Paper row:
  - Default: `hover:bg-surface-subtle rounded-lg px-3 py-2 transition-colors`
  - Filename: `font-sans text-sm text-ink`
  - "Ready" badge: `<VerdictPill verdict="supported" size="sm" />` with label overridden to "READY" (add a `label` prop override to the pill component)
  - Timestamp: `font-mono text-xs text-ink-tertiary`
- Footer note: `border-t border-hairline pt-4 mt-6 font-sans text-xs text-ink-tertiary`

### 4C · Empty state (no paper selected)

Full editorial treatment. This is the first thing a returning user
sees — make it feel like the landing.

```tsx
<div className="flex h-full flex-col items-center justify-center gap-6 px-6">
  <PrismLogo className="h-16 w-16 opacity-40" />
  <div className="text-center space-y-2 max-w-md">
    <h1 className="font-sans text-2xl font-semibold text-ink">
      Select a paper to see its audit.
    </h1>
    <p className="font-sans text-base text-ink-secondary">
      Or upload a new paper to get started.
    </p>
  </div>
  <button className="rounded-lg border border-brand text-brand hover:bg-brand hover:text-white transition-colors px-5 py-2.5 font-sans text-sm font-medium flex items-center gap-2">
    <Upload className="h-4 w-4" />
    Upload a paper
  </button>
</div>
```

Wire the button to the same upload handler as the sidebar Upload
button — don't duplicate the logic.

### 4D · Paper header

- File icon: `<FileText className="h-5 w-5 text-ink-tertiary" />`
- Filename: `font-sans text-2xl font-semibold text-ink`
- Completed status: emerald dot (`h-1.5 w-1.5 rounded-full bg-verdict-supported-icon`) + `font-sans text-sm text-ink-secondary`
- Share / Export buttons: `bg-surface border border-hairline hover:border-hairline-strong text-ink rounded-lg px-3 py-1.5 font-sans text-sm flex items-center gap-1.5`. Icons from lucide (`Share2`, `Download`, `MoreHorizontal`).

### 4E · Audit summary strip

- Container: `bg-surface border border-hairline rounded-xl p-5`
- Eyebrow "AUDIT SUMMARY": `font-sans text-xs uppercase tracking-wider text-ink-tertiary`
- Prose: `font-sans text-ink-secondary`. Wrap the numbers `14`, `11`, `3` in `<span className="font-mono text-ink font-semibold">14</span>`.
- Right-side "11/14 Supported":
  - Wrapper: `text-right`
  - Number: `font-mono text-4xl gradient-brand` — this is the signature moment. The whole "11 / 14" gets the orange→rose gradient via the `.gradient-brand` class from section 1.
  - Label "Supported": `font-sans text-sm text-ink-secondary mt-1`

### 4F · Stat tiles row

Four cards, `grid grid-cols-4 gap-3`. Each card:

```tsx
<div className="bg-surface border border-hairline rounded-xl p-5">
  <div className="flex items-center gap-2 mb-3">
    <Icon className="h-4 w-4 text-verdict-{v}-icon" />
    <span className="font-sans text-xs uppercase tracking-wider text-verdict-{v}-text">
      {LABEL}
    </span>
  </div>
  <div className="font-mono text-4xl text-ink">{count}</div>
</div>
```

Verdict-specific colors from the `verdict.*` tokens. "CLAIMS" total
uses `verdict.other` (slate).

### 4G · Claim rows

- Container: `bg-surface border border-hairline rounded-xl p-5 relative`
- Left accent border: absolute-positioned `w-1 h-full` at left edge, colored by verdict (`bg-verdict-{v}-border`)
- Hover: `hover:border-hairline-strong transition-colors`
- Row gap: `space-y-3`
- Verdict pill: `<VerdictPill verdict={...} />` top-left
- Claim summary: `font-sans text-base text-ink font-medium mt-2`
- Verbatim quote: **sans, not mono** (decision locked)
```tsx
  <blockquote className="mt-3 pl-3 border-l-2 border-hairline font-sans text-sm italic text-ink-secondary">
    {quote}
  </blockquote>
```
- Section ref: `font-mono text-xs uppercase tracking-wider text-ink-tertiary mt-2`
- View Evidence link: right side, `text-brand hover:text-brand-hover font-sans text-sm inline-flex items-center gap-1`. `<ArrowRight className="h-3.5 w-3.5 group-hover:translate-x-0.5 transition-transform" />`

### 4H · Sort control

Use shadcn `Select` if already installed, otherwise minimal custom.

- Label "Sort by:": `font-sans text-sm text-ink-secondary`
- Trigger: `bg-surface border border-hairline rounded-lg px-3 py-1.5 font-sans text-sm text-ink hover:border-hairline-strong`

### 4I · Evidence drawer

- Background: `bg-surface`
- Left border: `border-l border-hairline`
- Heading "Evidence": `font-sans text-lg font-semibold text-ink`
- Close: `<X className="h-4 w-4 text-ink-tertiary hover:text-ink" />`
- Filename: `font-sans text-sm text-ink`
- "Open Paper" link: `text-brand hover:text-brand-hover font-sans text-sm inline-flex items-center gap-1` + `<ExternalLink className="h-3 w-3" />`
- "SOURCE" heading: `font-sans text-xs uppercase tracking-wider text-ink-tertiary`
- Source quote block: `bg-surface-subtle border border-hairline rounded-lg p-3 font-mono text-sm text-ink`
- Section ref under quote: `font-mono text-xs uppercase tracking-wider text-ink-tertiary mt-2`
- PASS / FAIL badges: `<VerdictPill verdict="supported" size="sm" />` (label override "PASS") or `verdict="refused"` (label override "FAIL")
- "LINKED TO CLAIM" section: eyebrow + claim summary + verdict pill, spaced with `space-y-2`

### 4J · Chat strip

- "Ask about this paper" label: `font-sans text-sm text-ink-secondary text-center`
- Suggested prompt chips:
```tsx
  <button className="bg-surface border border-hairline hover:border-brand hover:text-brand rounded-full px-4 py-1.5 font-sans text-sm text-ink-secondary transition-colors">
    {prompt}
  </button>
```
- Input: `bg-surface border border-hairline focus:border-brand focus:ring-2 focus:ring-brand-subtle rounded-full px-5 py-3 font-sans text-sm text-ink placeholder:text-ink-tertiary w-full`
- Send button: circular `h-9 w-9 rounded-full flex items-center justify-center`. When input empty: `bg-hairline text-ink-tertiary`. When input has text: `bg-brand hover:bg-brand-hover text-white`. Icon: `<ArrowUp className="h-4 w-4" />`

### 4K · Paper Activity / progress view

- Background: `bg-surface`
- Stage labels ("PREPARING", "EXTRACTING", "GROUNDING", "FINALIZING", "DONE"): `font-mono text-xs uppercase tracking-wider`
  - Completed stages: `text-verdict-supported-icon` with `<Check />` icon
  - Current stage: `text-brand` with pulsing dot
  - Upcoming stages: `text-ink-tertiary`
- Progress bar: `h-1 bg-hairline rounded-full overflow-hidden`. Fill: `bg-brand transition-all`.
- Sub-progression text ("Parsed 3 pages", "5 / 10 verified"): `font-sans text-sm text-ink-secondary`

---

## 5 · Files to touch (from PRISM_APP_INVENTORY.md)

Cross-reference the file paths in the app inventory doc. Implementation
in exactly this order, one PR per group:

**PR 1 — Foundation** (blocks nothing visually but enables everything)
- `tailwind.config.ts` — add all tokens from section 1
- `Prism.Web/src/index.css` (or `globals.css`) — add `.gradient-brand`
- `Prism.Web/src/main.tsx` — Fontsource imports
- No visual changes yet. Verify build succeeds.

**PR 2 — Logo swap**
- Create `PrismLogo.tsx`, favicon, replace all diamond usages
- Small, verifiable win

**PR 3 — Verdict pill consolidation**
- Create `VerdictPill.tsx`
- Sweep all inline pill renders (inventory §4 lists them)
- Add `label` prop override for "READY" / "PASS" / "FAIL" repurposing

**PR 4 — Top nav + sidebar**
- High visual impact, surrounds every screen
- All 4B / 4A changes

**PR 5 — Paper header + audit summary + stat tiles**
- 4D, 4E, 4F together — they sit next to each other, share the surface

**PR 6 — Claim rows**
- 4G — most visually dense component in the app

**PR 7 — Evidence drawer**
- 4I

**PR 8 — Chat strip**
- 4J

**PR 9 — Empty state**
- 4C

**PR 10 — Paper Activity view**
- 4K

PRs 4–10 are independent of each other after PR 1–3 land. Can ship in
parallel if desired.

---

## 6 · What Claude Code must NOT touch

Copied from `PRISM_APP_INVENTORY.md` §6 risk map. Restate here so
there's no ambiguity:

- Any file under `Prism.Web/src/services/` — SignalR, API clients
- Any file under `Prism.Web/src/hooks/` — chat streaming, ingestion progress, state
- Routing / router config
- Any prop that controls behavior (only touch className / style props)
- The `userId = "demo-user-01"` hardcode
- Any conditional logic based on data state — restyle the visual, leave the condition

If a component has behavior and styling tangled (inventory flagged
`ClaimRow`, `EvidenceDrawer`, `ChatStrip` here): extract the styling
into a sibling component or wrapper, leave the behavior file alone.

---

## 7 · Definition of done per PR

Before merging any PR:

1. Build passes: `npm run build` clean, no TypeScript errors
2. No hardcoded hex values introduced (grep for `#[0-9a-fA-F]{3,6}` in changed files — should return only tokens in globals.css)
3. Every color reference uses a token from section 1
4. Every font reference uses `font-sans` or `font-mono` — no arbitrary font stacks
5. Visual verification: screenshot the changed surface, compare against this spec

---

## 8 · Deferred (not in this restyle)

- Dark mode toggle — separate PR after restyle ships
- Any layout changes
- Any new features
- Auth flow (`userId` hardcode stays)
- The "Prism Audit Console" branding review — keep or drop as separate decision