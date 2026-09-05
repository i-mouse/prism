# Prism UI Diagnostic Report

## Summary
The Prism.Web application is currently in a functional and stable state, building successfully with zero TypeScript errors. However, recent visual restyling efforts have introduced several design system regressions, particularly involving hardcoded hex colors, bypassed component abstractions (e.g., raw SVGs instead of Lucide icons), and a complete deviation from the Collapsible Audit Overview pattern specified in the original design system.

## Critical issues (blockers)
1. **Hardcoded Hex Colors in Core Layout:** `PaperActivityView.tsx` uses `bg-[#18181B]` and `PaperHeader.tsx` uses `bg-[#EEF2FF]`, `border-[#E0E7FF]`, and `text-[#6366F1]`. 
   - *File:Line:* `Prism.Web/src/components/matrix/PaperActivityView.tsx:182` and `Prism.Web/src/components/matrix/PaperHeader.tsx:51-52`.
   - *Why it matters:* Violates the strict `oklch` token system, causing these components to break if the theme or dark mode is updated.
   - *Fix:* Replace with appropriate semantic tailwind tokens (e.g. `bg-surface-subtle`, `bg-brand`, etc.).
2. **Missing `flex-1` in MatrixView Container:** The main wrapper for `MatrixView` uses `h-full` instead of `flex-1` within a flex-col parent.
   - *File:Line:* `Prism.Web/src/components/MatrixView.tsx:178` (`<motion.div className="flex h-full min-h-0 flex-col">`)
   - *Why it matters:* Relying on `h-full` inside a flex container can cause inconsistent layout expansion and scrolling bugs across different browser engines (especially Safari).
   - *Fix:* Change `h-full` to `flex-1`.

## Non-critical issues (should fix)
1. **Raw `<button>` Usage Over UI Component:** `PaperChatStrip.tsx` and `EvidenceDrawer.tsx` extensively use raw `<button>` elements with heavily duplicated Tailwind classes instead of the shared `Button` component from `shadcn/ui`.
   - *File:Line:* `Prism.Web/src/components/matrix/PaperChatStrip.tsx:185, 271, 379, 403`
   - *Why it matters:* Leads to inconsistent focus rings, padding, hover states, and touch-target sizes.
   - *Fix:* Refactor to use `<Button variant="ghost">` or similar variants.
2. **Inline SVG Duplication vs. Lucide Icons:** SVGs are hardcoded in place of standard Lucide icons in multiple places.
   - *File:Line:* `ClaimRow.tsx:61`, `PaperActivityView.tsx:194`, `PaperListItem.tsx:52, 59`.
   - *Why it matters:* Increases bundle size, prevents consistent line weights, and breaks the iconography language.
   - *Fix:* Replace with equivalent `lucide-react` imports (e.g., `FileText`, `Check`, `X`).
3. **Hardcoded Markdown Styles:** `index.css` contains hardcoded `rgba()` and `#111` for styling Markdown inside chat bubbles.
   - *File:Line:* `Prism.Web/src/index.css:171, 177, 181, 189`
   - *Why it matters:* Bypasses Tailwind token system for chat prose.
   - *Fix:* Use Tailwind `@apply` with theme tokens like `bg-surface-subtle` and `border-hairline`.

## Nice-to-have (backlog)
1. **Consolidate Status Badges:** `PaperActivityView` builds custom status circles (green checks, red X's) for its stepper rather than leaning on standard Verdict Pills or generalized badge components.
2. **Orphaned CSS File:** `App.css` is entirely unimported but contains legacy hex variables and styles.
   - *File:Line:* `Prism.Web/src/App.css`
   - *Fix:* Delete the file to reduce confusion.

## What's working correctly
- **Build Health:** The app compiles successfully (`npm run build`) in <5 seconds with 0 TypeScript errors.
- **Routing & State:** The URL syncs flawlessly with the UI via `?claim=id` using `replaceState`, ensuring a clean back-button history.
- **Chat Resize Handle:** The desktop chat drag handle correctly utilizes keyboard accessibility (`role="slider"`, `aria-valuemin/max`, and `ArrowUp/Down` support).
- **Mobile Chat Sheet:** The bottom sheet uses `window.visualViewport?.height` for robust layout calculations, preventing the iOS keyboard from cutting off the input field.

## Regression analysis
| Feature | Specified (PRISM_DESIGN_SYSTEM) | Current Reality | Cause |
| :--- | :--- | :--- | :--- |
| **Audit Overview** | Rendered as a `CollapsibleRegion` above the claim list. | Entirely removed in favor of a Tab system (`Claims` vs `Overview`). | Later PR overrode this without updating spec. |
| **Paper Activity** | White surface card with progress bar and stage labels. | Custom black terminal window with pulsing header and detailed logs. | New mockups applied overrode the previous spec. |
| **Sort Control** | Includes "Section" as an active sorting mechanism. | "Section" is hard-disabled. | Implementation constraint. |
| **Evidence View** | Includes left/right navigation arrows for claims. | Navigation arrows removed. | Removed directly per recent feedback. |

## Recommended fix order
1. **Fix Critical Token Violations:** Sweep `PaperActivityView` and `PaperHeader` to remove `#hex` colors immediately.
2. **Update Flex Layout in MatrixView:** Replace `h-full` with `flex-1` to guarantee layout stability.
3. **Consolidate SVGs and Buttons:** Swap out hardcoded SVGs for `lucide-react` icons and replace generic `<button>` instances with the shared `<Button>` component to unify hover/focus states.
4. **Clean up CSS:** Translate the markdown `.bubble` styles in `index.css` to use tokens, and delete the orphaned `App.css` file.


===============================================================
SECTION 1 — GIT CONTEXT
===============================================================
**Git Log:**
```
5a14ade Grounding: stance-aware reason strings + evidence rendering (#45)
c216b89 Polish Mobile and Chat Layout (#44)
fd9490e updating decsion and obesrvation in descion file (#43)
f3d4145 Fix auditor model assignment and stale eval matcher default (#42)
78bc510 Prism UI match (#41)
c31bcbe Trap-claim recall + labeling: extractor v4.1 + auditor v2 (#40)
bb5f033 docs uadpteds for Live
4bfc44c PR 5: port Azure fixes to code + reactUI JS app migration (#39)
6fdbc44 feat(pr5): first Azure deploy - live URL (#38)
ba79d14 Azure resource declarations + Blob Storage code swap (#37)
```

**Git Status:**
```
On branch main
Your branch is up to date with 'origin/main'.

Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   Prism.Web/src/components/EvidenceDrawer.tsx
	modified:   Prism.Web/src/components/MatrixView.tsx
	modified:   Prism.Web/src/components/Sidebar.tsx
	modified:   Prism.Web/src/components/drawer/EvidenceCard.tsx
	modified:   Prism.Web/src/components/matrix/ClaimRow.tsx
	modified:   Prism.Web/src/components/matrix/PaperActivityView.tsx
	modified:   Prism.Web/src/components/matrix/PaperChatStrip.tsx
	modified:   Prism.Web/src/components/matrix/PaperHeader.tsx
	modified:   Prism.Web/src/components/sidebar/PaperListItem.tsx
```

**Modified files in the last 10 commits under Prism.Web/:**
`index.html`, `nginx.conf`, `package-lock.json`, `package.json`, `public/favicon.svg`, `public/vite.svg`, `src/App.tsx`, `src/assets/prism-logo.svg`, `src/components/AppShell.tsx`, `src/components/EvidenceDrawer.tsx`, `src/components/MatrixView.tsx`, `src/components/PrismLogo.tsx`, `src/components/Sidebar.tsx`, `src/components/TopBar.tsx`, `src/components/VerdictPill.tsx`, `src/components/drawer/EvidenceCard.tsx`, `src/components/matrix/AbsenceRow.tsx`, `src/components/matrix/ClaimList.tsx`, `src/components/matrix/ClaimRow.tsx`, `src/components/matrix/PaperActivityView.tsx`, `src/components/matrix/PaperChatStrip.tsx`, `src/components/matrix/PaperHeader.tsx`, `src/components/matrix/SummaryStrip.tsx`, `src/components/matrix/chat/ChatBottomSheet.tsx`, `src/components/matrix/chat/ChatMarkdown.tsx`, `src/components/matrix/chat/ChatResizeHandle.tsx`, `src/components/matrix/chat/chatHeight.ts`, `src/components/sidebar/PaperListItem.tsx`, `src/components/sidebar/SidebarFooter.tsx`, `src/components/sidebar/UploadZone.tsx`, `src/components/ui/dropdown-menu.tsx`, `src/hooks/useBodyScrollLock.ts`, `src/hooks/useOverviewCollapsed.ts`, `src/index.css`, `src/lib/claimMeta.tsx`, `src/main.tsx`, `tailwind.config.ts`.

===============================================================
SECTION 2 — BUILD HEALTH
===============================================================
- **Status:** Success
- **Warnings:** Some chunks are larger than 500 kB after minification. `@microsoft/signalr` contains an annotation that Rollup cannot interpret due to the position of the comment (removed automatically).
- **TypeScript Errors:** 0
- **Bundle Size:** `index-[hash].js` is ~832 kB (259 kB gzip)
- **New "use client" boundaries:** None detected (Standard Vite/React setup).
- **Dev-only imports leaking:** None detected.

===============================================================
SECTION 3 — DESIGN TOKEN COMPLIANCE
===============================================================
- `Prism.Web/src/components/matrix/PaperActivityView.tsx:182` - `bg-[#18181B]` (Should be a tailwind token)
- `Prism.Web/src/components/matrix/PaperHeader.tsx:51` - `bg-[#EEF2FF] border-[#E0E7FF]` (Should be a tailwind token)
- `Prism.Web/src/components/matrix/PaperHeader.tsx:52` - `text-[#6366F1]` (Should be a tailwind token)
- `Prism.Web/src/index.css:171, 177, 189` - `rgba(128, 128, 128, 0.3/0.1/0.15)` (Should use `@apply` with tokens)
- `Prism.Web/src/index.css:181` - `#111` (Should use `@apply` with tokens)
- `Prism.Web/src/App.css` - Contains many legacy `#hex` values but is orphaned.

===============================================================
SECTION 4 — COMPONENT DUPLICATION AUDIT
===============================================================
- **VerdictPill:** Used mostly consistently, but `ClaimRow.tsx`, `AbsenceRow.tsx` and `SummaryStrip.tsx` still rely on raw text color classes (`text-verdict-partial-text`, `text-verdict-refused-text`) instead of badges in a few locations. 
- **PrismLogo:** Consistent, but inline SVGs for other icons exist in `ClaimRow.tsx:61`, `PaperActivityView.tsx:194`, and `PaperListItem.tsx:52`.
- **Button Styling:** `PaperChatStrip.tsx` heavily uses one-off raw `<button>` elements for suggested prompts and send actions rather than `Button`.
- **Card Styling:** Generally consistent using `border-hairline rounded-xl p-5 bg-surface`.

===============================================================
SECTION 5 — LAYOUT & OVERFLOW ISSUES
===============================================================
- **Main app layout:** 100dvh handled properly via `h-dvh-safe`. The `MatrixView` component uses `h-full` on its `motion.div` (`MatrixView.tsx:178`); this should technically be `flex-1` for absolute flexbox safety.
- **Chat area:** Correct `flex-1 min-h-0` on `MessageList` wrapper and `overflow-y-auto` inside. `ChatInput` is properly `shrink-0`.
- **Evidence drawer:** Scrollable area uses `flex-1 overflow-y-auto`.
- **Sidebar:** Nested list uses `flex-1 overflow-y-auto`.

===============================================================
SECTION 6 — MOBILE VIEWPORT ISSUES (390x844)
===============================================================
- **Top nav:** Fits within width.
- **Paper header:** Truncates long filenames gracefully.
- **Audit overview:** Was replaced by a Tab system, bypassing the collapsible requirement.
- **Stat tiles:** Stack properly in single-column on mobile.
- **Claim rows:** Pad appropriately (`p-3 md:p-5`).
- **View Evidence link:** Drops below the section ref correctly on mobile (`ClaimRow.tsx:70`).
- **Chat sheet:** Adapts cleanly via `visualViewport` height API. Handles bottom safe areas.
- **Body scroll:** Unlocked successfully when modals and drawers close via `useBodyScrollLock`.

===============================================================
SECTION 7 — CHAT AREA SPECIFIC
===============================================================
- **Message list container:** Has `overflow-y-auto` and `min-height: 0`.
- **Input row:** Is `flex-shrink-0`.
- **Streaming text:** Has `minHeight: "1.5em"` to prevent layout jump.
- **Auto-scroll:** Uses `IntersectionObserver` on bottom sentinel correctly.
- **User messages:** Right-aligned bubbles with `bg-brand-subtle`.
- **Assistant messages:** Left-aligned.
- **Claim citations:** Rendered inline successfully.
- **Drag handle:** Fully accessible with `role="slider"`, bounds, and keyboard up/down controls.

===============================================================
SECTION 8 — NAVIGATION & URL STATE
===============================================================
- **URL Updates:** Correctly pushes to `/paper/{id}` on selection.
- **Evidence Drawer:** URL syncs `?claim={cid}` via `replaceState`, keeping back-stack clean.
- **Browser Back:** Empty state fallback works.

===============================================================
SECTION 9 — ACCESSIBILITY REGRESSION CHECK
===============================================================
- **Verdict pills:** Rely on visual colors and icon, but lacking dedicated `aria-label` text for screen readers.
- **Buttons:** Most use `type="button"`. Icon-only buttons (like drawer close) have `aria-label="Close"`.
- **Focus rings:** Input elements leverage `focus-visible:ring-2 focus-visible:ring-brand-subtle`.
- **Chat drag handle:** Excellent ARIA support implemented.

===============================================================
SECTION 10 & 11 — REGRESSIONS & GENUINELY BROKEN
===============================================================
*Refer to the Regression Analysis and Critical Issues tables at the top of the document.*
