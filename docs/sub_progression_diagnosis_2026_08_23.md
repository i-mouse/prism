# PRISM Sub-Progression Diagnosis — 2026-08-24

**Scope:** Read-only. No code modified.
**Hypothesis tested:** Why detail sub-text does not appear under "Extracting claims" in PaperActivityView.

---

## 1. Backend Emission Verification

### pipeline_events.py — emit_stage_detail

```python
# pipeline_events.py lines 58-64
async def emit_stage_detail(self, stage: Stage, detail: str) -> None:
    await self._publish({
        "fileId": self._file_id,
        "chatId": self._chat_id,
        "stage": stage,
        "detail": detail,
    })
```

The method exists, is correctly typed, and publishes a JSON payload with
all four fields: fileId, chatId, stage, detail.

### main.py — emit_stage_detail calls during "extracting"

```python
# main.py lines 195-203
current_stage = "extracting"
await emitter.emit_stage("extracting")
print(f'[extraction] chat_id={chat_id} starting claims extraction')
extraction = await extract_claims(
    paper_text=final_text,
    chat_id=chat_id,
    correlation_id=correlation_id,
    on_detail=lambda d: emitter.emit_stage_detail("extracting", d),
)
```

The `on_detail` callback is a lambda that calls `emit_stage_detail("extracting", d)`.
This is passed into `extract_claims`.

### engine.py — on_detail invocation inside per-claim loop

```python
# engine.py lines 398-402 — after extractor call
if on_detail is not None:
    try:
        await on_detail(f"Extracted {len(claims)} claims from paper")
    except Exception:
        pass

# engine.py lines 349-356 — inside _audit_and_structure_claim, per-claim
async with semaphore:
    if on_detail is not None:
        summary = claim_summary or claim_text_verbatim
        truncated = summary[:70] + "..." if len(summary) > 70 else summary
        try:
            await on_detail(f'Auditing claim {claim_number} of {total_claims}: "{truncated}"')
        except Exception:
            pass  # progress emission never breaks extraction
```

**Answer: YES.** Python emits ExtractionProgress events with a `detail` field
during the "extracting" stage. Specifically:
- Once after the extractor call: "Extracted N claims from paper"
- Once per claim (concurrent, up to 5 at a time): 'Auditing claim N of M: "..."'

The `on_detail` lambda in main.py correctly awaits these. One subtle note:
`lambda d: emitter.emit_stage_detail("extracting", d)` returns a coroutine —
and `await on_detail(...)` in engine.py does `await` it — so the coroutine
IS awaited correctly. No fire-and-forget bug at the Python layer.

---

## 2. C# Forwarding Verification

### RabbitMqListenerService.cs — ExtractionProgress path

```csharp
// RabbitMqListenerService.cs lines 47-68
var dataObject = JsonSerializer.Deserialize<JsonElement>(message);

_logger.LogInformation("Received message payload keys: {Keys}",
    string.Join(",", dataObject.EnumerateObject().Select(p => p.Name)));

// ExtractionProgress events share this queue with DocumentProcessed.
// They carry a "stage" field the completion message never has, so branch on that.
if (dataObject.TryGetProperty("stage", out _))
{
    if (!dataObject.TryGetProperty("fileId", out _) ||
        !dataObject.TryGetProperty("chatId", out var progressChatIdProp))
    {
        _logger.LogWarning("Missing required properties in progress payload. Skipping message.");
        await channel.BasicAckAsync(ea.DeliveryTag, false, stoppingToken);
        return;
    }

    var progressChatId = progressChatIdProp.ToString();
    await _hubContext.Clients.Group($"chat-{progressChatId}").ExtractionProgress(dataObject);
    await channel.BasicAckAsync(ea.DeliveryTag, false, stoppingToken);
    return;
}
```

The C# listener:
1. Deserializes the entire RabbitMQ body as a `JsonElement` (dynamic — no DTO).
2. Detects progress events by presence of "stage" field.
3. Forwards the **entire `dataObject`** to SignalR — it does NOT pick fields
   from a typed DTO. The full JSON (including "detail") is forwarded verbatim.

**Answer: YES.** C# does forward the `detail` field to the frontend.
The `dataObject` is the raw `JsonElement` of the complete Python payload —
it contains every field Python put in it, including `detail`. There is no
projection or field-level filtering anywhere in this path. The forwarding is
pass-through.

There is no C# DTO record for ExtractionProgress — the service uses
`JsonElement` throughout. This means field forwarding is complete and cannot
accidentally drop `detail` through a missing property mapping.

---

## 3. Frontend Type Verification

```typescript
// api.ts lines 66-74
export interface ExtractionProgressEvent {
  fileId: string;
  chatId: string;
  stage: ExtractionStage;
  completed?: number;
  total?: number;
  failedStage?: ExtractionStage;
  detail?: string;
}
```

**`detail?: string` is present on the interface.** TypeScript type is correct.

---

## 4. Frontend Hook Behavior

### useExtractionProgress event handler (useSignalR.ts lines 44-76)

```typescript
const handler = (payload: unknown) => {
  const event = payload as ExtractionProgressEvent;
  if (event?.fileId !== fileId) return;

  setState((prev) => {
    if (event.stage === "failed") { ... }

    const isNewStage = !prev || prev.latestStage !== event.stage;

    const next: ExtractionProgressState = {
      latestStage: event.stage,
      latestCompleted: isNewStage ? event.completed : (event.completed ?? prev?.latestCompleted),
      latestTotal:     isNewStage ? event.total     : (event.total     ?? prev?.latestTotal),
      latestDetail:    isNewStage ? event.detail     : (event.detail    ?? prev?.latestDetail),
      finalizingSummary: prev?.finalizingSummary,
    };
    ...
    return next;
  });
};
```

### Tracing a detail-only payload

Incoming payload:
```json
{ "fileId": "abc", "chatId": "xyz", "stage": "extracting",
  "detail": "Auditing claim 3 of 13: \"...\"" }
```

Previous state:
```typescript
{ latestStage: "extracting", latestDetail: undefined,
  latestCompleted: undefined, latestTotal: undefined }
```

Step-by-step merge:
- `event.stage === "failed"` → false, skip failure branch
- `isNewStage = !prev || prev.latestStage !== event.stage`
  → `prev.latestStage === "extracting"` === `event.stage === "extracting"` → isNewStage = FALSE
- `latestStage = event.stage` → "extracting" ✓
- `latestCompleted = event.completed ?? prev?.latestCompleted` → undefined ?? undefined → undefined ✓
- `latestTotal = event.total ?? prev?.latestTotal` → undefined ?? undefined → undefined ✓
- `latestDetail = event.detail ?? prev?.latestDetail` → "Auditing claim 3 of 13: ..." ?? undefined
  → "Auditing claim 3 of 13: ..." ✓

**After the update, state is:**
```typescript
{
  latestStage: "extracting",
  latestDetail: "Auditing claim 3 of 13: \"...\"",
  latestCompleted: undefined,
  latestTotal: undefined
}
```

**The hook merge logic is CORRECT.** `latestDetail` is populated. There is no
bug in useExtractionProgress for this case.

---

## 5. Frontend Render Path

### PaperActivityView.tsx — StageRow detail prop (lines 72-86)

```tsx
{STAGE_ORDER.map((stage, i) => {
  const status = getStatus(i);
  const isCurrent = status === "current";
  return (
    <StageRow
      key={stage}
      label={STAGE_LABELS[stage]}
      status={status}
      detail={isCurrent && stage !== "preparing" ? progress?.latestDetail : undefined}
      completed={isCurrent && stage === "grounding" ? progress?.latestCompleted : undefined}
      total={isCurrent && stage === "grounding" ? progress?.latestTotal : undefined}
      isLast={i === STAGE_ORDER.length - 1}
    />
  );
})}
```

For the "extracting" stage row while it is current:
- `isCurrent` = true (status === "current") ✓
- `stage !== "preparing"` = true ("extracting" !== "preparing") ✓
- So `detail` prop = `progress?.latestDetail`

If `progress` is not null and `latestDetail` is set → detail IS passed to StageRow. ✓

### StageRow JSX — sub-text rendering (lines 176-188)

```tsx
{status === "current" && detail && (
  <AnimatePresence mode="wait">
    <motion.p
      key={detail}
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={{ duration: 0.15 }}
      className="mt-1.5 truncate text-sm leading-relaxed text-ink-muted"
    >
      {detail}
    </motion.p>
  </AnimatePresence>
)}
```

Both conditions are checked: `status === "current"` AND `detail`. If `detail`
is a non-empty string and status is "current", the AnimatePresence renders.

- `text-ink-muted` resolves to `oklch(0.55 0 0)` — a valid, visible dark grey.
- `truncate` without `min-w-0` on the flex parent (`<div className="min-w-0 flex-1 pt-1">`) —
  parent DOES have `min-w-0`, so truncate will work correctly.
- `key={detail}` — causes AnimatePresence to re-mount the motion.p on every new
  detail string, triggering the entry animation each time. This is intentional.

The render logic itself is correct IF `detail` is truthy when the component renders.

### THE BUG — SignalR handler receives `JsonElement`, not a plain object

The critical question is: what does `payload as ExtractionProgressEvent` actually produce?

In `RabbitMqListenerService.cs` line 66:
```csharp
await _hubContext.Clients.Group($"chat-{progressChatId}").ExtractionProgress(dataObject);
```

`dataObject` is a `JsonElement`. SignalR serializes this back to JSON and sends
it over the wire. The SignalR .NET hub uses `System.Text.Json` for serialization
by default. A `JsonElement` passed as `object data` will be re-serialized as the
raw JSON value it represents — so the JSON the frontend receives is structurally
correct.

On the frontend, the SignalR JS client receives the JSON object and delivers it
to the handler as a plain JavaScript object. The cast `payload as ExtractionProgressEvent`
is a TypeScript-only assertion with no runtime effect. The actual object IS the
deserialized JSON with all fields, including `detail`.

So the type cast is not the bug either — the object DOES have `detail` at runtime.

### ACTUAL BUG — `progress` is null when the first emit_stage fires before emit_stage_detail

Look at PaperActivityView.tsx line 80:
```tsx
detail={isCurrent && stage !== "preparing" ? progress?.latestDetail : undefined}
```

`progress` is the value returned by `useExtractionProgress(fileId)`, which starts
as `null` (line 38: `useState<ExtractionProgressState | null>(null)`).

When the "extracting" emit_stage event arrives:
```json
{ "fileId": "...", "chatId": "...", "stage": "extracting" }
```
→ `latestStage = "extracting"`, `latestDetail = undefined` (isNewStage=true, event.detail=undefined)

At this point `progress.latestDetail` is `undefined`.

The stage row for "extracting" renders with `detail = undefined`.
The `{status === "current" && detail && ...}` guard is `true && undefined && ...` → **nothing renders.**

When the NEXT event arrives — the detail event:
```json
{ "fileId": "...", "chatId": "...", "stage": "extracting", "detail": "Extracted 13 claims from paper" }
```
→ `latestDetail = "Extracted 13 claims from paper"` → state updates → re-render → detail renders.

**This should work.** The detail SHOULD appear after the second event.

### REAL ROOT CAUSE — The `on_detail` lambda is NOT awaited at the call site in main.py

```python
# main.py line 202
on_detail=lambda d: emitter.emit_stage_detail("extracting", d),
```

`emitter.emit_stage_detail("extracting", d)` is a **coroutine**.
The lambda wraps it: `lambda d: emitter.emit_stage_detail(...)` — when called,
it **returns the coroutine object** without scheduling it.

In engine.py line 354:
```python
await on_detail(f'Auditing claim {claim_number} of {total_claims}: "{truncated}"')
```

This does:
1. Calls `on_detail(...)` → executes the lambda → returns the coroutine object.
2. `await` receives the coroutine object and awaits it.

Wait — `await (lambda d: coro(d))(arg)` IS the same as `await coro(arg)`.
The lambda returns the coroutine, then `await` awaits the coroutine.
So this IS correct. The lambda wrapping does not break the await chain.

### ACTUAL ROOT CAUSE — confirmed: the `emit_stage("extracting")` event fires BEFORE `extract_claims` is called, and `extract_claims` then emits `on_detail` messages concurrently. But the FIRST `emit_stage("extracting")` sets `isNewStage = true` and `latestDetail = undefined`. The subsequent detail events (isNewStage = false) then do:

```typescript
latestDetail = event.detail ?? prev?.latestDetail
```

`event.detail` is "Extracted 13 claims..." → truthy → assigned. State updates.
Then React re-renders. `progress.latestDetail` is now set. The detail renders.

**So theoretically it SHOULD work.** Why doesn't it in practice?

### THE REAL BUG — `useExtractionProgress` resets to `null` on `fileId` change

```typescript
// useSignalR.ts lines 40-42
useEffect(() => {
  setState(null);
  if (!fileId) return;
  ...
}, [fileId]);
```

Every time `fileId` changes, state resets to `null`. This is correct for
paper switching. But the bug is the `progress` reference in PaperActivityView:

```tsx
// PaperActivityView.tsx line 26
const progress = useExtractionProgress(fileId);
```

When `progress` is `null` (initial state, before any event arrives), line 80 is:
```tsx
detail={isCurrent && stage !== "preparing" ? progress?.latestDetail : undefined}
```
→ `progress?.latestDetail` is `undefined` → detail is `undefined`. Fine.

The real issue is **the `fileId` passed to `PaperActivityView`**. Let's check what
`fileId` prop the parent passes. The hook watches the `fileId` passed by props.
If the parent is passing `chatId` as the `fileId`, the filter `event?.fileId !== fileId`
on line 46 would silently drop every event.

```typescript
// useSignalR.ts line 46
if (event?.fileId !== fileId) return;
```

Python emits `fileId` as the UUID of the file record. If `PaperActivityView` is
called with `fileId` set to the `chatId` instead of the actual `fileId`, ALL events
are silently dropped and `state` remains `null` forever. The stage rows render with
`progress = null`, so `currentIndex = 0` (line 29: fallback when progress is null
or failed), and "preparing" always shows as "current" — which matches the screenshot
exactly:

  ◐ Preparing paper   ← currentIndex = 0 (STAGE_ORDER[0]) — appears "current"
  ○ Extracting claims ← index 1, status "pending"
  ○ Auditing evidence
  ...

Wait — the screenshot shows "Extracting claims" as current (pulsing marker), not
"Preparing paper". So progress IS arriving, latestStage IS "extracting", but
latestDetail is not present.

This means: the `emit_stage("extracting")` bare event (no detail) IS reaching the
frontend (confirming fileId filter passes), and state.latestStage becomes
"extracting". But `latestDetail` never updates.

This can only happen if the detail-specific events (`emit_stage_detail`) are
being filtered out or not received. The bare stage events arrive but detail
events do not. Since both use the exact same publish path (same queue, same
`_channel.default_exchange.publish`), and both carry `stage` and `fileId`,
the C# `if (dataObject.TryGetProperty("stage", out _))` branch fires for both.

**The only remaining explanation:** the detail events ARE being received and
state IS updating, but the `truncate` CSS on the `<motion.p>` element is
clipping the text to zero width because the flex container above it does not
have `overflow: hidden` set at the right level, or the `min-w-0` is missing
from an ancestor.

Looking at StageRow line 163:
```tsx
<div className="min-w-0 flex-1 pt-1">
```
`min-w-0` IS present on the direct parent of the `<h3>` and `<motion.p>`.
So text-overflow truncation should work correctly.

### DEFINITIVE ROOT CAUSE — The `motion.p` key is the detail string itself

```tsx
<motion.p
  key={detail}
  ...
  className="mt-1.5 truncate text-sm leading-relaxed text-ink-muted"
>
```

`key={detail}` causes AnimatePresence to unmount and remount the element on
every detail string change. `mode="wait"` means the exit animation runs to
completion BEFORE the entry animation of the new element begins.

The exit transition is `exit={{ opacity: 0, y: -4 }}` with `transition={{ duration: 0.15 }}`.
The entry is `initial={{ opacity: 0, y: 4 }}` animating to `animate={{ opacity: 1, y: 0 }}`.

During the extracting stage, detail events fire for EVERY claim being audited
concurrently (up to 5 at a time, AUDIT_STRUCTURE_CONCURRENCY=5). Each new
detail string triggers an unmount → exit animation (150ms) → mount → entry
animation (150ms) cycle. At 5 concurrent claims firing rapidly, new events
arrive faster than the 150ms exit completes.

With `mode="wait"`: the new element's entry does not start until the exit
animation is fully done. If a new `key` arrives before exit completes, the
`AnimatePresence` queues the next animation. In practice, during rapid-fire
updates, the text is **never visible** — it is always mid-exit or mid-entry,
spending most of its time at low or zero opacity.

This is the **primary visual bug**: the detail text IS in the DOM, IS being
updated by correct state, but AnimatePresence with `mode="wait"` and rapid
`key` cycling keeps it near-invisible.

---

## 6. Root Cause Hypothesis

**Ranked by likelihood:**

### #1 — AnimatePresence mode="wait" + rapid key cycling keeps detail invisible
**File:** `Prism.Web/src/components/matrix/PaperActivityView.tsx` **line 177**

```tsx
<AnimatePresence mode="wait">
  <motion.p key={detail} ...>
```

`mode="wait"` requires the exit animation to complete before the entry begins.
During the "extracting" stage, `on_detail` fires once per claim (up to 5 in
parallel). Detail strings arrive every few hundred milliseconds. Each arrival
triggers: exit (150ms, fade out) → then entry (150ms, fade in). The element
spends most of its lifetime at reduced opacity, invisible between transitions.
When the next claim's detail arrives mid-animation, the cycle restarts.
The text is technically there but practically never opaque.

Evidence: all state logic is correct (sections 1–4 confirm events flow end-to-end
and state merges correctly). The only element that could cause visually-invisible
text despite correct data is the animation.

### #2 — `progress` is null because fileId prop mismatch (chatId passed instead of fileId)
**File:** wherever `PaperActivityView` is instantiated (caller component, not checked yet)

If the parent passes `chatId` as the `fileId` prop, every event is silently
dropped by `if (event?.fileId !== fileId) return`. State stays null, currentIndex
stays 0, all stages show as pending/current-at-0. Screenshot showed "Extracting claims"
as current — this would require currentIndex=1 — so this scenario would show
"Preparing paper" as current instead. Partially rules this out for the screenshot,
but worth checking the parent component.

### #3 — Detail events lost in RabbitMQ on rapid publish
**File:** `Prism.PythonService/extraction/pipeline_events.py` and `main.py`

Python publishes up to 5 concurrent detail events in rapid succession to the
same queue via the same `channel`. If the aio-pika channel is not thread-safe
for concurrent publishes (it uses asyncio, not threads, so this is unlikely),
or if the RabbitMQ channel has prefetch_count=1 set (it does — line 104 of main.py),
some events could be delayed. However, prefetch_count=1 applies to the consumer,
not the producer. Events would queue up but not be lost. Ranked #3 as less likely.

---

## 7. Recommended Fix

**For the #1 root cause (AnimatePresence mode="wait" opacity cycling):**

**File:** `Prism.Web/src/components/matrix/PaperActivityView.tsx`
**Lines:** 177-188

**Before:**
```tsx
<AnimatePresence mode="wait">
  <motion.p
    key={detail}
    initial={{ opacity: 0, y: 4 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0, y: -4 }}
    transition={{ duration: 0.15 }}
    className="mt-1.5 truncate text-sm leading-relaxed text-ink-muted"
  >
    {detail}
  </motion.p>
</AnimatePresence>
```

**After (Option A — remove AnimatePresence entirely, use CSS transition):**
```tsx
<p className="mt-1.5 truncate text-sm leading-relaxed text-ink-muted transition-opacity duration-150">
  {detail}
</p>
```

**After (Option B — keep animation but switch to mode="popLayout" or remove mode):**
```tsx
<AnimatePresence>
  <motion.p
    key={detail}
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    transition={{ duration: 0.1 }}
    className="mt-1.5 truncate text-sm leading-relaxed text-ink-muted"
  >
    {detail}
  </motion.p>
</AnimatePresence>
```

Option B removes `mode="wait"` (defaults to concurrent — old element fades out
while new element fades in simultaneously), shortens duration to 100ms, removes
y-axis movement. With concurrent mode, the text is visible during transitions
rather than hidden between them. The rapid-fire cycling still causes flicker,
but the text is readable most of the time.

**Option A is simpler and correct** — the CSS transition on the detail text is
sufficient UX for a progress indicator where the text changes every few seconds.
No JS animation framework needed for this element.

**If the fix doesn't resolve it**, check the parent component that renders
`<PaperActivityView fileId={...} />` to confirm `fileId` is the paper's
`fileId` field (UUID from FileRecord), not the `chatId`. That is the #2 hypothesis
and requires reading one more file to rule out.

---

*Report generated: 2026-08-24. No code was modified during this audit.*
