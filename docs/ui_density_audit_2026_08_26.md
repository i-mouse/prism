# Prism UI Density Audit — 2026-08-26

> **Scope**: Completed-status branch of the Matrix View panel  
> **Trigger**: Slice 3b.1 (chat strip polish) shipped; density issues surfaced on the ReAct paper (9 claims)  
> **Method**: Static code analysis only — no app runtime, no code changes  

---

## 1. Vertical Space Budget

Heights estimated from Tailwind utility classes, padding/margin values, and font sizes in the source code. Default Tailwind base is 16 px; `text-sm` = 14 px (line-height ~20 px), `text-base` = 16 px (line-height ~24 px), `text-lg` = 18 px, `text-2xl` = 24 px, `text-3xl` = 30 px.

### a. Container top padding

| Source | Class | Value |
|---|---|---|
| [MatrixView.tsx:117](file:///H:/Work%20projects/Prism/Prism.Web/src/components/MatrixView.tsx#L117) | `pt-6` | **24 px** top padding |

### b. PaperHeader

[PaperHeader.tsx](file:///H:/Work%20projects/Prism/Prism.Web/src/components/matrix/PaperHeader.tsx)

| Element | Derivation | px |
|---|---|---|
| Icon box | `h-11` | 44 |
| File name | `text-2xl font-bold` → ~30 px line height | 30 |
| Status row | `text-sm` → ~20 px + icon `h-4` | 20 |
| Outer | `flex items-center` — single row, height driven by taller child | — |

The icon box (44 px) is the tallest element, so the whole header row = **~44 px**. The status text sits below the title inside the left column, so actual height is **max(44, 30+20) = 50 px**.

**PaperHeader total ≈ 50 px**

### c. Gap between PaperHeader and SummaryStrip

[MatrixView.tsx:124](file:///H:/Work%20projects/Prism/Prism.Web/src/components/MatrixView.tsx#L124): `mt-6` = **24 px**

### d. SummaryStrip (Audit Summary card)

[SummaryStrip.tsx](file:///H:/Work%20projects/Prism/Prism.Web/src/components/matrix/SummaryStrip.tsx)

| Element | Derivation | px |
|---|---|---|
| Card padding | `p-6` → 24 top + 24 bottom | 48 |
| Card border | `border` → 1 top + 1 bottom | 2 |
| "AUDIT SUMMARY" label | `text-xs uppercase` → ~16 px line | 16 |
| `space-y-3` gap below label | 12 | 12 |
| Summary paragraph | `text-base leading-relaxed` (~26 px line). For 9-claim ReAct paper with refusals, text is ~3 lines | ~78 |
| `space-y-6` gap before 4-cell strip | 24 | 24 |
| Right column: `text-3xl` score + `text-sm` "Claims supported" + `text-sm` "N refused" | 30 + 4(mt-1) + 20 + 8(mt-2) + 20 = 82 | 82 |
| 4-cell strip separator | `border-t pt-6` → 1 + 24 | 25 |
| 4-cell strip | icon `h-9` (36) + label `text-xs` (16) + value `text-2xl` (30) → items-center row height ≈ max(36, 46) = 46 | 46 |

**SummaryStrip total ≈ 48 (pad) + 2 (border) + 16 + 12 + 78 + 25 + 46 ≈ 227 px**

> [!NOTE]
> The summary paragraph is variable-length. For the ReAct paper (9 claims, with refusals), the
> four-sentence paragraph wraps to ~3 lines. For a paper with fewer categories, it could be 2 lines (~52 px),
> saving ~26 px.

### e. Gap between SummaryStrip and Claims section header

[MatrixView.tsx:128](file:///H:/Work%20projects/Prism/Prism.Web/src/components/MatrixView.tsx#L128): `mt-4` = **16 px**

### f. "Claims" section header + Sort dropdown row

[MatrixView.tsx:128-158](file:///H:/Work%20projects/Prism/Prism.Web/src/components/MatrixView.tsx#L128-L158)

| Element | Derivation | px |
|---|---|---|
| h2 "Claims" | `text-lg font-semibold` → ~22 px line | 22 |
| Count pill | `h-6` | 24 |
| Sort dropdown trigger | `size="sm"` → ~32 px height | 32 |
| Row height | `flex items-center` → max(22, 24, 32) | 32 |

**Section header row ≈ 32 px**

### g. Gap between section header and first ClaimRow

[MatrixView.tsx:161](file:///H:/Work%20projects/Prism/Prism.Web/src/components/MatrixView.tsx#L161): `pt-2` = **8 px**  
[ClaimList.tsx:12](file:///H:/Work%20projects/Prism/Prism.Web/src/components/matrix/ClaimList.tsx#L12): `space-y-3` gap between rows = 12 px (but first item has no gap above).

**Gap to first claim row ≈ 8 px**

### h. PaperChatStrip — empty state

[PaperChatStrip.tsx:124-191](file:///H:/Work%20projects/Prism/Prism.Web/src/components/matrix/PaperChatStrip.tsx#L124-L191)

| Element | Derivation | px |
|---|---|---|
| `border-t` on outer container | 1 | 1 |
| Empty-state wrapper | `px-6 py-6` → 24 top + 24 bottom | 48 |
| "Ask Prism…" text | `text-sm` → ~20 px | 20 |
| `gap-3` between text and chips | 12 | 12 |
| Chips row | 4 chips, `rounded-full px-3 py-1.5 text-xs` → each ~30 px tall; wraps to 2 rows on narrow panel (gap-2 = 8 between rows) → ~68 | 68 |
| ChatInput wrapper | `px-6 pb-6` → 0 top + 24 bottom | 24 |
| Input container | `rounded-2xl border p-2` + textarea `py-1.5` + button `h-8` → ~44 | 44 |

**PaperChatStrip empty state ≈ 1 + 48 + 20 + 12 + 68 + 24 + 44 ≈ 217 px**

### i. PaperChatStrip — active state (with turns)

[PaperChatStrip.tsx:148-182](file:///H:/Work%20projects/Prism/Prism.Web/src/components/matrix/PaperChatStrip.tsx#L148-L182)

| Element | Derivation | px |
|---|---|---|
| `border-t` | 1 | 1 |
| Turns container | `max-h-96 px-6 py-6` → max 384 px visible, 24+24 pad | max 432 |
| ChatInput | same as above | 68 |

**PaperChatStrip active state ≈ 1 + min(turns height, 432) + 68 = 69–501 px**

With even a single Q/A exchange (~100 px content), active state ≈ **~169 px**.

### Total "chrome before first claim row" on a 900 px viewport

| Layer | px |
|---|---|
| Container top padding (`pt-6`) | 24 |
| PaperHeader | 50 |
| Gap (mt-6) | 24 |
| SummaryStrip | 227 |
| Gap (mt-4) | 16 |
| Claims section header row | 32 |
| Gap to first row (`pt-2`) | 8 |
| **Sub-total above first row** | **381 px** |
| PaperChatStrip (empty, pinned to bottom) | 217 |
| **Total chrome** | **598 px** |

> [!CAUTION]
> **381 px of 900 px (42 %) is consumed before the first claim row.**  
> The chat strip adds 217 px at the bottom, leaving only **302 px (34 %)** for actual claim rows.  
> A single ClaimRow is ~100-130 px tall (py-4 = 32 pad + summary ~20 + quote ~40 + section ~16 + gaps ≈ 108–130 px), so **at most 2.5 claim rows are visible** on initial load.

---

## 2. "Claims" Word Deduplication

### Every user-visible occurrence of "claim(s)" (case-insensitive)

#### Occurrence 1 — SummaryStrip paragraph
[SummaryStrip.tsx:13](file:///H:/Work%20projects/Prism/Prism.Web/src/components/matrix/SummaryStrip.tsx#L13)
```tsx
// Line 12-14:
const sentences: string[] = [
  total === 1 ? "This paper makes 1 empirical claim." : `This paper makes ${total} empirical claims.`,
];
```
**Renders**: "This paper makes 9 empirical **claims**."

#### Occurrence 2 — SummaryStrip right column
[SummaryStrip.tsx:52](file:///H:/Work%20projects/Prism/Prism.Web/src/components/matrix/SummaryStrip.tsx#L52)
```tsx
// Line 50-54:
  {supported} / {total}
</p>
<p className="mt-1 text-sm text-ink-muted">Claims supported</p>
{notSupported > 0 && (
  <p className="mt-2 text-sm tabular-nums text-refused">{notSupported} refused</p>
```
**Renders**: "**Claims** supported"

#### Occurrence 3 — SummaryStrip 4-cell strip
[SummaryStrip.tsx:60](file:///H:/Work%20projects/Prism/Prism.Web/src/components/matrix/SummaryStrip.tsx#L60)
```tsx
// Line 59-61:
<div className="flex items-center justify-between gap-8 border-t border-border pt-6">
  <SummaryCell icon={FileText} iconClass="bg-surface-sunken text-ink-muted" label="Claims" value={total} />
  <SummaryCell
```
**Renders**: "CLAIMS 9" (uppercase via `text-xs uppercase`)

#### Occurrence 4 — Section heading in MatrixView
[MatrixView.tsx:130](file:///H:/Work%20projects/Prism/Prism.Web/src/components/MatrixView.tsx#L130)
```tsx
// Line 129-133:
<div className="flex items-center gap-3">
  <h2 className="font-display text-lg font-semibold text-ink">Claims</h2>
  <span className="inline-flex h-6 items-center rounded-full bg-surface-sunken px-2 text-xs font-medium tabular-nums text-ink-muted">
    {derivedSummary.total} claims
  </span>
</div>
```
**Renders**: "**Claims**  `9 claims`" — the word appears **twice on the same line**.

#### Occurrence 5 — PaperChatStrip empty state prompt
[PaperChatStrip.tsx:132](file:///H:/Work%20projects/Prism/Prism.Web/src/components/matrix/PaperChatStrip.tsx#L132)
```tsx
// Line 131-133:
<p className="text-center text-sm text-ink-muted">
  Ask Prism about this paper's claims, evidence, or audit.
</p>
```
**Renders**: "Ask Prism about this paper's **claims**, evidence, or audit."

#### Occurrence 6 — PaperChatStrip suggested prompt chips
[PaperChatStrip.tsx:16](file:///H:/Work%20projects/Prism/Prism.Web/src/components/matrix/PaperChatStrip.tsx#L16)
```tsx
// Line 15-20:
const SUGGESTED_PROMPTS = [
  "What are the main claims of this paper?",
  "Show me the strongest refusals",
  "Explain the grounding methodology",
  "Which claims are only partially supported?",
];
```
**Renders**: "What are the main **claims** of this paper?" and "Which **claims** are only partially supported?"

#### Occurrence 7 — PaperChatStrip follow-up suggestions
[PaperChatStrip.tsx:57-59](file:///H:/Work%20projects/Prism/Prism.Web/src/components/matrix/PaperChatStrip.tsx#L57-L59)
```tsx
return ["What CAN this paper answer?", "Show me the main claims"];
// ...
return ["Which claims support this?", "Show me the evidence"];
```
These only appear after user interaction, not on initial load.

### Redundancy Analysis

| # | Text | Redundant with | Verdict |
|---|---|---|---|
| 1 | "…makes 9 empirical claims" (paragraph) | #3 (CLAIMS 9 in 4-cell strip) | **Redundant** — the 4-cell strip already shows the total |
| 2 | "Claims supported" (right column label) | #3 (CLAIMS cell) | **Partially redundant** — but this labels the fraction, so it's load-bearing |
| 3 | "CLAIMS 9" (4-cell strip) | #4 (section heading "Claims 9 claims") | **Redundant** — the count is repeated immediately below |
| 4 | "Claims  `9 claims`" (section heading + pill) | Itself — the word appears twice in 4 words | **Self-redundant** — "Claims" heading + "9 claims" pill is tautological |
| 5 | "…this paper's claims, evidence, or audit." | Contextual in chat prompt | **Not redundant** — different context (chat CTA) |
| 6 | Chip text mentioning "claims" | Contextual in interactive prompts | **Not redundant** — actionable suggestions |
| 7 | Follow-up suggestions | Only shown after interaction | **Not redundant** |

### Which could be removed without losing information?

- **Occurrence 4 count pill** (`9 claims`): Remove entirely. The heading "Claims" is sufficient as a section label; the count is already in the 4-cell strip 32 px above.
- **Occurrence 1 sentence**: Could drop the first sentence ("This paper makes 9 empirical claims.") since the 4-cell strip shows `CLAIMS 9`. The remaining sentences about support/refusal carry unique info.
- **Occurrence 3 label**: Could change from "Claims" to "Total" since it's in a row with Supported/Partially/Not Supported.

### Which are load-bearing?

- **Occurrence 2** ("Claims supported"): Labels the prominent `X / Y` fraction — removing it makes the number ambiguous.
- **Occurrence 5** (chat CTA): Tells users what the chat can do — removing it degrades onboarding.

---

## 3. Chat Strip Empty State Size

### Quoted JSX

[PaperChatStrip.tsx:129-146](file:///H:/Work%20projects/Prism/Prism.Web/src/components/matrix/PaperChatStrip.tsx#L129-L146) + [PaperChatStrip.tsx:185-190](file:///H:/Work%20projects/Prism/Prism.Web/src/components/matrix/PaperChatStrip.tsx#L185-L190):

```tsx
{turns.length === 0 ? (
  <div className="flex flex-col items-center gap-3 px-6 py-6">
    <p className="text-center text-sm text-ink-muted">
      Ask Prism about this paper's claims, evidence, or audit.
    </p>
    <div className="flex max-w-lg flex-wrap justify-center gap-2">
      {SUGGESTED_PROMPTS.map((prompt) => (
        <button
          key={prompt}
          type="button"
          onClick={() => sendMessage(prompt)}
          className="rounded-full border border-border bg-surface px-3 py-1.5 text-xs text-ink-muted ..."
        >
          {prompt}
        </button>
      ))}
    </div>
  </div>
) : ( /* ... turns ... */ )}

<ChatInput
  onSend={sendMessage}
  onStop={abort}
  isSending={isSending}
  placeholder="Ask about this paper..."
/>
```

### Height breakdown

| Element | px |
|---|---|
| `border-t` on outer `motion.div` | 1 |
| Empty state `py-6` padding (top) | 24 |
| "Ask Prism…" text line (`text-sm`) | 20 |
| `gap-3` | 12 |
| Chips: 4 chips at `py-1.5 text-xs` ≈ 30 px each; wraps to 2 rows in typical panel widths, `gap-2` = 8 px between rows | ~68 |
| Empty state `py-6` padding (bottom) | 24 |
| ChatInput `pb-6` padding (bottom) | 24 |
| Input container (`p-2` + textarea `py-1.5` + button `h-8`) | ~44 |
| **Total** | **~217 px** |

At **900 px viewport height**, this is **24 % of the viewport**.

### Required vs optional elements

| Element | Required? | Rationale |
|---|---|---|
| ChatInput (textarea + submit) | ✅ **Required** | Core interaction |
| "Ask Prism…" helper text | ❌ **Optional** | Becomes the input placeholder ("Ask about this paper…" is already there) |
| 4 suggestion chips | ❌ **Optional** | Helpful for discovery but not essential; could reduce to 2 or show post-first-turn |

### Could it collapse to just input + 2 chips on one row?

**Yes.** The input is already ~44 px tall. Two short chips ("Main claims?" / "Strongest refusals") at ~30 px would fit beside the input in a `flex-row` layout if the panel is ≥ 600 px wide (each chip ~180 px + input ~300 px + gaps). Total height with `py-3` padding: **~62–70 px**, saving **~150 px**.

---

## 4. Density Comparison to Reference Mockup

Reference: [PRISM_UI_DESIGN_SAMPLE_V2.png](file:///H:/Work%20projects/Prism/docs/design/PRISM_UI_DESIGN_SAMPLE_V2.png)

### Mockup measurements (estimated from pixel proportions)

The mockup viewport appears to be ~900 px tall based on standard 1440×900 design frames.

| Element in Mockup | Est. px | % of 900 |
|---|---|---|
| Top nav bar ("Prism Audit Console") | ~50 | 5.5 % |
| PaperHeader (title + status + buttons) | ~50 | 5.5 % |
| Audit Summary card (paragraph + fraction + 4-cell strip) | ~180 | 20 % |
| "Claims  `21 claims`" heading + Sort row | ~40 | 4.4 % |
| **Total chrome before first claim row** | **~320** | **~36 %** |

### Current implementation vs mockup

| Metric | Mockup | Current Code | Delta |
|---|---|---|---|
| Chrome before first row | ~320 px (36 %) | ~381 px (42 %) | **+61 px (+6 %)** |
| Summary card height | ~180 px | ~227 px | **+47 px** — extra from `space-y-6` between paragraph and 4-cell strip, and `p-6` on card |
| Claim section header | ~40 px | ~32 px | −8 px (actually tighter in code) |
| Chat strip at bottom | ~70 px (inline input + 3 chips in 1 row) | ~217 px (stacked) | **+147 px** |
| Visible claim rows | 3 full rows | ~2.5 rows | **−0.5 rows** |

### Does the mockup show a chat strip empty state?

**Yes**, but it's minimal — a single-line input ("Ask a follow-up about these results…") with 3 short chip buttons **on the same row**, directly below the claim list. No explanatory paragraph. The mockup's chat area is approximately **~70 px tall** — one-third of the current implementation.

### Chrome-to-content ratio

| | Mockup | Current |
|---|---|---|
| Chrome (header + summary + section heading + chat strip) | ~390 px (43 %) | ~598 px (66 %) |
| Content (claim rows) | ~510 px (57 %) | ~302 px (34 %) |

> [!WARNING]
> The current implementation dedicates nearly **twice as much** vertical space to chrome as the mockup, and shows **40 % less content**.

---

## 5. Recommended Re-Composition (Slice 3b.2)

### Change 1 — Tighten SummaryStrip internal spacing

**File**: [SummaryStrip.tsx](file:///H:/Work%20projects/Prism/Prism.Web/src/components/matrix/SummaryStrip.tsx)

| Property | Current | Proposed | Saved |
|---|---|---|---|
| Card padding | `p-6` (24 all sides) | `px-6 py-4` (16 top/bottom) | 16 px |
| `space-y-6` (top section gap) | 24 px | `space-y-4` → 16 px | 8 px |
| 4-cell separator | `border-t pt-6` → 25 px | `border-t pt-4` → 17 px | 8 px |

```diff
- <div className="space-y-6 rounded-lg border border-border bg-surface p-6">
+ <div className="space-y-4 rounded-lg border border-border bg-surface px-6 py-4">
```
```diff
- <div className="flex items-center justify-between gap-8 border-t border-border pt-6">
+ <div className="flex items-center justify-between gap-8 border-t border-border pt-4">
```

**Vertical space saved: ~32 px**  
**What stays**: All content, 4-cell strip, paragraph, fraction, border.  
**What's removed**: Only excess padding.

### Change 2 — Remove first sentence from summary paragraph

**File**: [SummaryStrip.tsx](file:///H:/Work%20projects/Prism/Prism.Web/src/components/matrix/SummaryStrip.tsx)

Currently the paragraph starts with "This paper makes N empirical claims." which repeats the 4-cell strip's "CLAIMS N". Remove the first sentence; start with the support breakdown.

```diff
  const sentences: string[] = [
-   total === 1 ? "This paper makes 1 empirical claim." : `This paper makes ${total} empirical claims.`,
  ];
```

**Vertical space saved: ~26 px** (one fewer line of text at `text-base leading-relaxed`)  
**What stays**: Support/partial/refused sentences — the actual audit insight.  
**What's removed**: A sentence whose information is fully redundant with the 4-cell strip.

### Change 3 — Remove count pill from section heading

**File**: [MatrixView.tsx](file:///H:/Work%20projects/Prism/Prism.Web/src/components/MatrixView.tsx)

"Claims `9 claims`" → just "Claims". The count is in the 4-cell strip 16 px above.

```diff
  <div className="flex items-center gap-3">
    <h2 className="font-display text-lg font-semibold text-ink">Claims</h2>
-   <span className="inline-flex h-6 items-center rounded-full bg-surface-sunken px-2 text-xs font-medium tabular-nums text-ink-muted">
-     {derivedSummary.total} claims
-   </span>
  </div>
```

**Vertical space saved: 0 px** (same row height driven by sort dropdown).  
**What stays**: "Claims" heading, sort dropdown.  
**What's removed**: Redundant count pill; reduces cognitive noise.

### Change 4 — Reduce gap between PaperHeader and SummaryStrip

**File**: [MatrixView.tsx](file:///H:/Work%20projects/Prism/Prism.Web/src/components/MatrixView.tsx)

```diff
- <div className="mt-6">
+ <div className="mt-4">
```

**Vertical space saved: 8 px**

### Change 5 — Reduce container top padding

**File**: [MatrixView.tsx](file:///H:/Work%20projects/Prism/Prism.Web/src/components/MatrixView.tsx)

```diff
- <div className="shrink-0 px-8 pt-6">
+ <div className="shrink-0 px-8 pt-4">
```

**Vertical space saved: 8 px**

### Change 6 — Compact chat strip empty state (see §6 below)

**File**: [PaperChatStrip.tsx](file:///H:/Work%20projects/Prism/Prism.Web/src/components/matrix/PaperChatStrip.tsx)

Replace stacked empty state with inline chips beside input. Remove the "Ask Prism…" paragraph entirely (the placeholder already says "Ask about this paper…").

```diff
  {turns.length === 0 ? (
-   <div className="flex flex-col items-center gap-3 px-6 py-6">
-     <p className="text-center text-sm text-ink-muted">
-       Ask Prism about this paper&rsquo;s claims, evidence, or audit.
-     </p>
-     <div className="flex max-w-lg flex-wrap justify-center gap-2">
-       {SUGGESTED_PROMPTS.map((prompt) => ( ... ))}
-     </div>
-   </div>
+   <div className="flex items-center gap-2 px-6 pt-3">
+     {SUGGESTED_PROMPTS.slice(0, 2).map((prompt) => (
+       <button key={prompt} type="button" onClick={() => sendMessage(prompt)}
+         className="shrink-0 rounded-full border border-border bg-surface px-3 py-1 text-xs text-ink-muted transition-all hover:border-border-strong hover:bg-surface-sunken"
+       >
+         {prompt}
+       </button>
+     ))}
+   </div>
  ) : ( /* ... */ )}
```

And tighten ChatInput bottom padding:
```diff
- <div className="px-6 pb-6">
+ <div className="px-6 pb-3">
```

**Vertical space saved: ~147 px** (from ~217 px to ~70 px)  
**What stays**: Input, submit button, 2 suggestion chips.  
**What's removed**: Explanatory paragraph, 2 of 4 chips, excess padding.

### Summary of all changes

| Change | Saved | Cumulative |
|---|---|---|
| 1. SummaryStrip tighten | 32 px | 32 px |
| 2. Remove first sentence | 26 px | 58 px |
| 3. Remove count pill | 0 px (noise reduction) | 58 px |
| 4. Reduce header→summary gap | 8 px | 66 px |
| 5. Reduce top padding | 8 px | 74 px |
| 6. Compact chat strip | 147 px | **221 px** |

**New chrome total ≈ 598 − 221 = ~377 px** → content area grows from 302 px to **523 px** → approximately **4 claim rows** visible on 900 px viewport (up from ~2.5).

---

## 6. Chat Strip Default State Proposal

### Option A: Input + 2 chips inline ✅ **Recommended**

```
┌─────────────────────────────────────────────────────────────────────┐
│  [Main claims?]  [Strongest refusals]  │ Ask about this paper... [→]│
└─────────────────────────────────────────────────────────────────────┘
```

- Chips sit to the left of (or above on narrow viewports) the input.
- Total height: **~70 px** (12 px top pad + 44 px input row + 12 px bottom pad + 1 px border).
- The two chosen prompts are the most common entry points: overview ("main claims") and critical audit ("strongest refusals").
- The remaining two prompts ("Explain the grounding methodology", "Which claims are only partially supported?") can appear as follow-up suggestions after the first turn — exactly where they're more contextually useful.

### Option B: Input only, no chips

- Height: ~56 px.
- Disadvantage: Zero discoverability of what users can ask. New users may not engage with the chat at all.

### Option C: Collapsible strip (click to expand)

- Collapsed: just the input bar (~56 px). Expand chevron reveals 4 chips.
- Disadvantage: Adds interaction complexity; the expand/collapse is a new pattern not in the design system.

### Recommendation: **Option A**

Rationale:
1. Matches the mockup's layout (input + chips on one row ≈ 70 px).
2. Preserves discoverability without stacking.
3. Saves **~150 px** over current implementation.
4. Two chips is the sweet spot — enough to suggest capabilities, not so many that they wrap.

---

## 7. Terminology Cleanup Proposal

| # | Current text | Location | Action | Rationale |
|---|---|---|---|---|
| 1 | "This paper makes N empirical claims." | SummaryStrip paragraph | **Remove** | Redundant with CLAIMS N in 4-cell strip |
| 2 | "Claims supported" | SummaryStrip right column | **Keep** | Labels the prominent fraction — load-bearing |
| 3 | "CLAIMS" (4-cell label) | SummaryStrip 4-cell strip | **Rename to "TOTAL"** | In context of the 4-cell row (Total / Supported / Partially / Not Supported), "Total" reads better and avoids repeating "claims" near the heading below |
| 4a | "Claims" (h2 heading) | MatrixView section header | **Keep** | Section label — clear and necessary |
| 4b | "`9 claims`" (count pill) | MatrixView section header | **Remove** | Count is in the 4-cell strip immediately above |
| 5 | "…this paper's claims, evidence, or audit." | PaperChatStrip empty state | **Remove** (per compact chat strip) | The input placeholder already conveys this |
| 6 | "What are the main claims…" / "Which claims…" | Chip text | **Keep / shorten** | Shorten to "Main claims?" and "Partially supported?" — still clear, less wordy |
| 7 | Follow-up suggestion text with "claims" | PaperChatStrip follow-ups | **Keep** | Only shown after interaction; contextually appropriate |

**Net effect**: The word "claims" goes from **6 visible occurrences on initial load** (occurrences 1–6) to **3** (the right-column label, the section heading, and one chip). The nearby cluster of 4 adjacent "claims" becomes a single "Claims" heading.

---

## 8. Priority Ranking

### By impact-per-effort

| Rank | Change | Space freed | Noise reduced | Effort | Risk |
|---|---|---|---|---|---|
| 🥇 | **6. Compact chat strip** | **147 px** (largest single gain) | Medium | ~30 min | Low — chat strip is self-contained; only touches PaperChatStrip.tsx |
| 🥈 | **1. SummaryStrip padding** | **32 px** | Low | ~10 min | Very low — padding-only change |
| 🥉 | **3. Remove count pill** | **0 px** | **High** (eliminates "Claims 9 claims" tautology) | ~5 min | Very low — delete 3 lines |
| 4 | **2. Remove first sentence** | **26 px** | Medium | ~5 min | Low — but verify remaining sentences still read well standalone |
| 5 | **7. Rename CLAIMS→TOTAL** | **0 px** | Medium | ~2 min | Very low |
| 6 | **4+5. Reduce gaps/padding** | **16 px** | Low | ~5 min | Very low |

### Single-metric answers

- **Most viewport space freed**: Change 6 (compact chat strip) — **147 px**
- **Most cognitive noise reduced**: Change 3 (remove count pill) — eliminates the most visually jarring redundancy ("Claims 9 claims")
- **Quickest to implement**: Change 7 (rename label) — single string edit, ~2 minutes
- **Riskiest**: Change 6 (compact chat strip) — it changes the onboarding UX for new users and removes 2 suggested prompts from the initial view. However, risk is mitigated because the mockup already validates this layout, and the removed prompts reappear as follow-up suggestions.

---

> [!TIP]
> **Suggested implementation order**: 6 → 3 → 1 → 2 → 7 → 4+5. This front-loads the largest visual improvement (chat strip compaction + count pill removal) and finishes with low-risk padding tweaks.
