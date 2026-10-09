# Prism App Inventory

This document provides a comprehensive, current-state audit of the Prism.Web React frontend app.

## SECTION 1 — TECH STACK & STYLING SETUP
- **Framework & Bundler:** React 19.2.0, Vite 7.3.1, TypeScript 5.9.3.
- **Styling Approach:** Tailwind CSS v4.3.3 (`@tailwindcss/vite`), driven by `tailwind.config.ts`. No CSS modules or Styled Components in use. Some custom CSS (mostly animations like `prism-fade-in` and markdown styling for `.bubble`) is present in `src/index.css`. Inline styles are very rare, used mostly for dynamic width (e.g., progress bar in `PaperActivityView.tsx`) or textarea auto-resize (`PaperChatStrip.tsx`).
- **Component Library:** `shadcn/ui` (heavily customized, configured for `radix-nova` style in `components.json`).
- **Icon Library:** `lucide-react` (with some `react-icons` installed but largely unused in the checked files).
- **Font Loading Strategy:** Fonts are loaded via `@fontsource-variable` (Inter, JetBrains Mono, Manrope) and imported in `src/main.tsx`.
- **Theme System:** There is no functional dark mode/light mode toggle. A comprehensive design tokens system is defined in `tailwind.config.ts` using `oklch()` color functions to ensure perceptual uniformity. `shadcn/ui` primitive tokens (e.g., `--background`, `--foreground`) are overridden in `src/index.css` to map to OKLCH variables.

## SECTION 2 — CURRENT DESIGN TOKENS
### Colors Used in the App
**Theme-Defined (in `tailwind.config.ts`):**
- `ink`: `DEFAULT`, `muted`, `subtle`
- `surface`: `DEFAULT`, `alt`, `sunken`
- `border`: `DEFAULT`, `strong`
- `accent`: `DEFAULT`, `hover`, `subtle`, `fg`
- `supported`: `DEFAULT`, `bg`, `border`
- `partial`: `DEFAULT`, `bg`, `border`
- `refused`: `DEFAULT`, `bg`, `border`

**Hardcoded in Components/CSS:**
- `rgba(128, 128, 128, 0.3)`, `rgba(128, 128, 128, 0.1)`, `rgba(128, 128, 128, 0.15)` for markdown tables/code in `src/index.css`
- `#111` for `pre` block backgrounds in `src/index.css`
- `bg-[radial-gradient(circle_at_50%_45%,_oklch(0.96_0.03_285)_0%,_transparent_55%)]` in `PaperActivityView.tsx`

### Fonts Used
- **Sans (`font-sans`):** `"Inter Variable"`, `ui-sans-serif`, `system-ui`, `sans-serif`
- **Display (`font-display`):** `"Manrope Variable"`, `"Inter Variable"`, `ui-sans-serif`, `sans-serif`
- **Mono (`font-mono`):** `"JetBrains Mono Variable"`, `ui-monospace`, `monospace`
Loaded via `@fontsource-variable` imports in `main.tsx`.

### Border Radii, Shadows, and Common Spacing
- **Border Radii:** `xs` (4px), `sm` (6px), `md` (8px), `lg` (10px). Tailwind default classes like `rounded-full`, `rounded-lg`, `rounded-md`, and `rounded-2xl` are prevalent.
- **Shadows:** `card`, `card-hover`, `drawer` defined in `tailwind.config.ts`.
- **Spacing:** standard Tailwind spacing scale is heavily utilized (e.g. `p-4`, `mt-6`, `gap-2`).

## SECTION 3 — SURFACE-BY-SURFACE INVENTORY

### Top nav bar ("Prism Audit Console" header)
- **File path:** `src/components/TopBar.tsx`
- **Component tree:** `<header>` > `div` (Sparkles Icon, Title) > `div` (Avatar `div`, Name `span`, ChevronDown Icon)
- **Current visual description:** A fixed slim header at the top of the app displaying the application name with an icon, and a user profile indicator (Nitin) on the right.
- **Class lists:**
  - Wrapper: `flex h-14 shrink-0 items-center justify-between border-b border-border bg-surface px-6`
  - Title: `font-display text-sm font-semibold tracking-tight text-ink`
  - Avatar: `flex h-8 w-8 items-center justify-center rounded-full bg-surface-sunken text-sm font-medium text-ink`
- **Hardcoded copy:** "Prism Audit Console", "N", "Nitin"

### Sidebar
- **File path:** `src/components/Sidebar.tsx`
- **Component tree:** `<aside>` > Logo `div` > `UploadZone` > `CurrentContextCard` > `PaperListItem` (mapped) > `SidebarFooter`
- **Current visual description:** A left-hand navigation pane with a logo at the top, a prominent upload button, a section detailing the currently active context, a list of uploaded papers, and a footer note.
- **Class lists:**
  - Wrapper: `flex h-full flex-col overflow-y-auto border-r border-border bg-surface-alt px-3 py-4`
  - Section headers: `pb-2 text-xs font-semibold uppercase tracking-[0.05em] text-ink-subtle`
- **Hardcoded copy:** "Prism", "Current Context", "Papers", "No papers uploaded yet."

### Empty state (no paper selected)
- **File path:** `src/components/MatrixView.tsx`
- **Component tree:** `div` > `FileText` (icon) > `p`
- **Current visual description:** Centered icon with prompt text instructing the user to upload or select a paper.
- **Class lists:**
  - Wrapper: `flex h-full flex-col items-center justify-center gap-2 p-8 text-center`
  - Icon: `h-12 w-12 text-ink-subtle`
  - Text: `text-sm text-ink-muted`
- **Hardcoded copy:** "Select a paper from the sidebar, or upload a paper to get started."

### Paper header
- **File path:** `src/components/matrix/PaperHeader.tsx`
- **Component tree:** `div` > `div` (Icon + Title/Status) > `div` (Share, Export, More buttons)
- **Current visual description:** The title of the paper in large display font, followed by an extraction status pill, with action buttons on the far right.
- **Class lists:**
  - Wrapper: `flex items-center justify-between`
  - Title: `font-display text-2xl font-bold tracking-[-0.02em] text-ink`
  - Buttons (`secondaryButtonClass`): `gap-1.5 border-border bg-surface text-ink hover:border-border-strong hover:bg-surface-sunken`
- **Hardcoded copy:** "Share", "Export", "Completed", "Coming soon"

### Audit Summary strip
- **File path:** `src/components/matrix/SummaryStrip.tsx`
- **Component tree:** `div` > `div` (Warning box) > `div` (Prose vs Score) > `div` (Stat tiles)
- **Current visual description:** A large bordered block that provides a natural language summary of the paper's claims, a giant fraction indicating how many claims are supported, and 4 statistical tiles at the bottom.
- **Class lists:**
  - Wrapper: `space-y-4 rounded-lg border border-border bg-surface p-5`
  - Warning: `rounded-lg border border-refused bg-refused-bg p-3 text-sm text-refused`
  - Prose: `text-base leading-relaxed text-ink`
  - Score fraction: `font-display text-3xl font-bold tabular-nums tracking-[-0.03em] text-supported`
- **Hardcoded copy:** "AUDIT SUMMARY", "This paper makes {X} empirical claims.", "{Y} are supported by the paper's own evidence.", "{Z} refused"

### Stat tiles row
- **File path:** `src/components/matrix/SummaryStrip.tsx` (SummaryCell)
- **Component tree:** `div` (wrapper) > `div` (icon) > `div` (label + value)
- **Current visual description:** Four small stat blocks separated in a flex row (Claims, Supported, Partially, Not Supported) with colorful icons.
- **Class lists:**
  - Wrapper: `flex items-center justify-between gap-8 border-t border-border pt-4`
  - Tile: `flex items-center gap-3`
  - Label: `text-xs uppercase tracking-[0.05em] text-ink-subtle`
  - Value: `font-display text-2xl font-bold tabular-nums text-ink`
- **Hardcoded copy:** "Claims", "Supported", "Partially", "Not Supported"

### Verdict pills
- **Locations used:**
  1. `src/components/matrix/ClaimRow.tsx` (inline span using `claimMeta.tsx` classes)
  2. `src/components/matrix/AbsenceRow.tsx` (inline span using `claimMeta.tsx` classes)
  3. `src/components/matrix/PaperChatStrip.tsx` (using local `claimPillClasses`)
  4. `src/components/EvidenceDrawer.tsx` (inline span at the bottom)
  5. `src/components/sidebar/PaperListItem.tsx` (extraction status pill)
- **Current visual description:** Small, pill-shaped colored badges that denote status (Supported, Partially Supported, Refused, etc.).
- **Class lists:** Examples include `inline-flex h-7 items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 text-xs font-semibold uppercase tracking-wider` coupled with dynamic color classes.
- **Requires visual verification:** Since styling classes (e.g. `meta.bgClass`) are passed dynamically from `src/lib/claimMeta.tsx`, any restyle requires verifying `claimMeta.tsx` or building a centralized component.

### Claim rows (in Matrix view)
- **File path:** `src/components/matrix/ClaimRow.tsx` and `src/components/matrix/AbsenceRow.tsx`
- **Component tree:** `div` > Verdict Pill > `div` (Summary, Source text, Citation info) > `button` ("View Evidence")
- **Current visual description:** A list of claims, each depicted as a bordered card with a thick colored left border (dependent on status), holding a pill, the claim summary, quoted evidence, and a view evidence button.
- **Class lists:**
  - Wrapper: `flex items-start gap-4 rounded-r-md rounded-l-none border border-border border-l-4 px-6 py-4` (plus dynamic colors and hover rings)
  - Claim Summary: `text-[15px] font-semibold leading-snug text-ink`
  - Citation: `text-xs text-ink-subtle uppercase tracking-[0.05em]`
- **Hardcoded copy:** "View Evidence", "(No Evidence)", "No supporting evidence in this paper."

### Sort control
- **File path:** `src/components/MatrixView.tsx`
- **Component tree:** `div` > `span` > `Select` (from `shadcn/ui`)
- **Current visual description:** A small dropdown on the right side above the claim list to change the sorting order.
- **Class lists:**
  - Wrapper: `flex items-center gap-2`
  - Trigger: `border-border text-sm text-ink hover:border-border-strong`
- **Hardcoded copy:** "Sort by:", "Position", "Support", "Section"

### Evidence drawer (right panel)
- **File path:** `src/components/EvidenceDrawer.tsx` and `src/components/drawer/EvidenceCard.tsx`
- **Component tree:** `<aside>` > Header > `div` (Paper details) > `EvidenceCard` (list) > `div` (Linked claim)
- **Current visual description:** A right-aligned slide-out drawer (400px wide) displaying the underlying source text for a selected claim. 
- **Class lists:**
  - Wrapper: `flex h-full w-[400px] shrink-0 flex-col border-l border-border bg-surface p-6 shadow-drawer`
  - Title: `font-display text-base font-semibold text-ink`
  - Card Wrapper (`EvidenceCard.tsx`): `space-y-3 rounded-md border border-border bg-surface p-4`
- **Hardcoded copy:** "Evidence", "Open Paper", "Source", "Linked to Claim", "The auditor considered these passages but rejected them as sufficient support."

### Chat strip
- **File path:** `src/components/matrix/PaperChatStrip.tsx`
- **Component tree:** `motion.div` > Messages Scroll Area (`UserTurnBubble`, `AssistantTurn`) > `ChatInput` (textarea + send button)
- **Current visual description:** A floating chat interface at the bottom of the MatrixView. Features conversational bubbles, suggestion chips, a pulsing thinking indicator, and an auto-resizing input box.
- **Class lists:**
  - Wrapper: `flex shrink-0 flex-col border-t border-border bg-gradient-to-b from-surface-alt/60 to-surface-alt/90 backdrop-blur-sm`
  - Input Wrapper: `flex items-end gap-2 rounded-2xl border border-border bg-surface p-2`
  - User Bubble: `max-w-[80%] rounded-2xl rounded-br-md bg-accent-subtle px-4 py-2.5 text-sm leading-relaxed text-ink`
  - Suggestion Pill: `rounded-full border border-border bg-surface px-3 py-1 text-xs text-ink-muted transition-all hover:border-border-strong hover:bg-surface-sunken`
- **Hardcoded copy:** "Ask about this paper...", "What are the main claims?", "Show me the strongest refusals", "New messages ↓", "Copied", "Could not copy"

### Paper Activity / ingestion progress view
- **File path:** `src/components/matrix/PaperActivityView.tsx`
- **Component tree:** `motion.div` > Radial Gradient Bg > Header > `motion.div` (Process Card with `StageRow` items) > Insight footer
- **Current visual description:** A full-pane loading screen centered in the main view showing real-time extraction progress (Preparing, Extracting, Grounding, Finalizing). Uses a radial gradient background and animated pulsing states.
- **Class lists:**
  - Wrapper: `relative min-h-full overflow-hidden bg-surface`
  - Card: `rounded-xl border border-border bg-surface p-8 shadow-card`
  - Title: `font-display text-3xl font-bold tracking-[-0.02em] text-ink`
  - Current Stage Indicator: `flex h-8 w-8 items-center justify-center rounded-full border-2 border-accent bg-accent-subtle`
- **Hardcoded copy:** "AUDITING PAPER", "Preparing paper", "Extracting claims", "Auditing evidence", "Finalizing", "Complete", "Failed", "Prism grounds every claim in the paper's own evidence."

### Any modal, toast, or dropdown components used
- **Dropdown:** `<Select>` in `src/components/MatrixView.tsx` leveraging `src/components/ui/select.tsx` (shadcn).
- **Toast:** `<Toaster>` included in `src/components/AppShell.tsx` from `src/components/ui/sonner.tsx`. No standard modal components (e.g. `dialog.tsx`) are currently implemented.

## SECTION 4 — REUSABLE COMPONENTS
All standard reusable components live in `src/components/ui/`.
- `src/components/ui/button.tsx`: Core button component used in `PaperHeader`, `UploadZone`, and `EvidenceDrawer`.
- `src/components/ui/select.tsx`: Core dropdown select component used in `MatrixView`.
- `src/components/ui/skeleton.tsx`: Skeleton loading frame used in `MatrixView`.
- `src/components/ui/sonner.tsx`: Toast container.
*(Note: Files like `badge.tsx`, `card.tsx`, `dialog.tsx`, `scroll-area.tsx`, `separator.tsx`, and `sheet.tsx` exist in the folder but remain mostly unused across the audited components).*

**Duplicates Flag:** Verdict pills and status badges are rendered via inline `<span>` elements using identical or similar classes populated from `src/lib/claimMeta.tsx` across `ClaimRow.tsx`, `AbsenceRow.tsx`, `PaperChatStrip.tsx`, and `EvidenceDrawer.tsx`. They should be refactored into a shared `<VerdictPill />` component.

## SECTION 5 — WHAT'S ALREADY GOOD
- **Token-based Architecture:** The color configuration using `oklch()` in `tailwind.config.ts` (`ink`, `surface`, `supported`, `partial`, `refused`, `accent`) provides excellent perceptual uniformity and semantic meaning.
- **Clean Layouts:** The core layout mapped in `AppShell.tsx` (`grid-cols-[240px_minmax(0,1fr)_400px]`) seamlessly supports a slide-out drawer pattern while minimizing UI jumping.
- **Animation Use:** Excellent application of `framer-motion` for transitions within `PaperActivityView` and `MatrixView`. The smooth fades and layout transitions handle state switching very elegantly.

## SECTION 6 — RISK MAP
Files handling complex logic and behavior that must NOT be broken during the restyle:
- **`src/hooks/*.ts`** (`useSignalR`, `useChatStream`, `useChats`, `useActivePaper`, `usePaperClaims`): Core API and web-socket abstractions managing state.
- **`src/services/signalRService.ts`**: Handles actual WebSocket connections.
- **`src/contexts/SelectedClaimContext.tsx`**: Governs drawer toggling and row highlighting.
- **`src/components/matrix/PaperChatStrip.tsx`**: While it needs restyling, the component heavily relies on `useRef` auto-resizing the textarea, scroll-to-bottom logic triggered by stream states (`isSending`, `isStreaming`), and focus management. Tangled UI and behavior requiring extreme care.
- **`src/components/sidebar/UploadZone.tsx`**: Employs hidden file inputs and FormData uploading mechanism. The `inputRef` must be retained.
- **`src/components/MatrixView.tsx`**: Holds the sorting logic and orchestrates which view shows up when.

*Note: Proceed carefully when editing `PaperActivityView.tsx` and `ClaimRow.tsx`, as they rely heavily on conditionally applied Tailwind classes (using the `cn` utility) based on exact data states.*
