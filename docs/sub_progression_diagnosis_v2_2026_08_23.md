# Sub-Progression Rendering Diagnosis — v2 (2026-08-23)

> **Scope:** Read-only second-pass diagnosis. No code was modified.  
> **Symptom:** After the `AnimatePresence mode="popLayout"` fix, sub-text under the  
> "Extracting claims" stage row is **still not visible** during a live upload.  
> Stage labels, marker circles, and check-off all work correctly.

---

## 1. Backend emission — quick confirm

**File:** `Prism.PythonService/extraction/pipeline_events.py` lines 58–64

```python
async def emit_stage_detail(self, stage: Stage, detail: str) -> None:
    await self._publish({
        "fileId": self._file_id,
        "chatId": self._chat_id,
        "stage": stage,
        "detail": detail,          # ← key is lowercase "detail"
    })
```

✅ The `"detail"` key is present in the dict. The Python `TypedDict` at line 30 also
declares `detail: Optional[str]`. Backend emission is correct; the field is
published to `document_processed_queue` as-is via `json.dumps()` (which preserves
Python key casing — all lowercase).

---

## 2. C# forwarding — DETAIL FIELD FOCUS

**File:** `Prism.ApiService/Services/RabbitMqListenerService.cs`

### Deserialization

The service does **not** use a typed DTO. It deserializes the raw JSON into a
`JsonElement` and forwards the entire element directly:

```csharp
// line 47
var dataObject = JsonSerializer.Deserialize<JsonElement>(message);

// lines 55-68 (ExtractionProgress branch)
if (dataObject.TryGetProperty("stage", out _))
{
    ...
    var progressChatId = progressChatIdProp.ToString();
    await _hubContext.Clients.Group($"chat-{progressChatId}").ExtractionProgress(dataObject);
    await channel.BasicAckAsync(ea.DeliveryTag, false, stoppingToken);
    return;
}
```

There is **no typed DTO** at all. The `JsonElement` tree is forwarded verbatim.

| Question | Answer |
|---|---|
| Does the DTO have a "Detail" property? | N/A — no DTO exists. A raw `JsonElement` is forwarded. |
| Is the `detail` field forwarded in the SignalR payload? | **Yes** — the entire `JsonElement` (all keys) is passed. |
| What casing are the keys? | **camelCase** (`detail`, `fileId`, `chatId`, `stage`) — inherited from Python's `json.dumps()`. |

**Interim verdict:** The C# layer is transparent; it neither strips nor renames any
fields. The `detail` key reaches the SignalR `SendAsync` call with its original
camelCase intact.

---

## 3. Frontend type

**File:** `Prism.Web/src/types/api.ts` lines 66–74

```typescript
export interface ExtractionProgressEvent {
  fileId: string;
  chatId: string;
  stage: ExtractionStage;
  completed?: number;
  total?: number;
  failedStage?: ExtractionStage;
  detail?: string;           // ← camelCase, optional
}
```

✅ The interface declares `detail?: string` in camelCase. This matches the Python
emission casing.

---

## 4. Frontend hook — trace with a concrete payload

### 4a. How SignalR JS delivers the payload

The C# side calls `ExtractionProgress(dataObject)` where `dataObject` is a
`System.Text.Json.JsonElement`. ASP.NET Core's default SignalR JSON protocol
serializes this through `System.Text.Json`, which uses its own serializer options.

**`Program.cs` line 56:**
```csharp
builder.Services.AddSignalR();
```

No custom `JsonSerializerOptions` are configured. With `AddSignalR()` using
`System.Text.Json` as the default protocol, `JsonElement` is serialized as a
transparent "pass-through" because it is already a parsed JSON value — keys are
reproduced verbatim from the original JSON text. Since the Python payload used
lowercase camelCase keys, the wire payload that reaches the browser is:

```json
{ "fileId": "abc", "chatId": "def", "stage": "extracting", "detail": "Auditing claim 3 of 13: '...'" }
```

The Microsoft SignalR JavaScript client deserializes this using standard
`JSON.parse()` semantics. It does **not** apply any camelCase or PascalCase
transformation — keys are delivered exactly as received.

### 4b. Hook handler trace

**File:** `Prism.Web/src/hooks/useSignalR.ts` lines 44–76

```typescript
const handler = (payload: unknown) => {
  const event = payload as ExtractionProgressEvent;
  if (event?.fileId !== fileId) return;          // fileId guard — passes ✅

  setState((prev) => {
    // event.stage === "extracting", prev is null → isNewStage = true
    const isNewStage = !prev || prev.latestStage !== event.stage;

    const next: ExtractionProgressState = {
      latestStage: event.stage,                           // "extracting"
      latestCompleted: isNewStage ? event.completed : ..., // undefined
      latestTotal:     isNewStage ? event.total     : ..., // undefined
      latestDetail:    isNewStage ? event.detail    : ..., // ← accesses event.detail
      finalizingSummary: prev?.finalizingSummary,
    };
    return next;
  });
};
```

- Key used: **`event.detail`** (camelCase, line 66) — matches wire key `"detail"` ✅
- `next.latestDetail` is populated correctly ✅

---

## 5. Frontend hook return shape

**File:** `Prism.Web/src/hooks/useSignalR.ts` line 82

```typescript
return state;
```

`useExtractionProgress` returns the full `ExtractionProgressState | null` object,
including `latestDetail?: string`. The consuming component receives it as `progress`.

---

## 6. Render trace — THE BUG IS HERE

**File:** `Prism.Web/src/components/matrix/PaperActivityView.tsx`

### 6a. Prop passing to StageRow

```typescript
// line 80
detail={isCurrent && stage !== "preparing" ? progress?.latestDetail : undefined}
```

- `isCurrent` = true for the "extracting" stage ✅  
- `stage !== "preparing"` = true for "extracting" ✅  
- Result: `progress?.latestDetail` = `"Auditing claim 3 of 13: '...'"` is passed ✅

### 6b. StageRow render gate

```typescript
// lines 176-188
{status === "current" && detail && (
  <AnimatePresence mode="popLayout" initial={false}>
    <motion.p
      key={detail}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.12 }}
      className="mt-1.5 truncate text-sm leading-relaxed text-ink-muted"
    >
      {detail}
    </motion.p>
  </AnimatePresence>
)}
```

- `status === "current"` → true ✅  
- `detail` → truthy string ✅  
- The `<AnimatePresence>` and `<motion.p>` mount.

### 6c. ⚠️ ROOT CAUSE: `initial={false}` freezes the entering element at `opacity: 0`

When the very first `detail` event arrives for an "extracting" stage row:

1. Before the event, `detail` was `undefined` → the `status === "current" && detail` gate was **false**.
2. The `<AnimatePresence initial={false}>` component was **not mounted** (the whole block didn't render).
3. The event fires → `detail` becomes truthy → the block renders for the **first time**.
4. At this point, `<AnimatePresence>` **mounts** and simultaneously receives its first child `<motion.p>`.

**This is where it breaks.** Framer Motion's `initial={false}` on `AnimatePresence` means:
> "Do not run the entry animation for children that are present when this `AnimatePresence` first mounts."

Because `initial={false}` is active, Framer Motion applies the child's `initial` value
(`opacity: 0`) **as a static style** and **skips the animate transition** entirely.
The `<motion.p>` renders at `opacity: 0` and never transitions to `opacity: 1`.

When subsequent `detail` strings arrive, the `key` on `<motion.p>` changes, triggering
an exit + enter cycle. **But `initial={false}` still suppresses the entry animation**
for each new entering `<motion.p>`. Every detail string is permanently rendered at
`opacity: 0`. The text is in the DOM but invisible.

**`initial={false}` is appropriate only on an `AnimatePresence` that is always mounted
from the start.** Here it is conditionally mounted, so the first child that enters
must be allowed to animate in.

### 6d. Tailwind class check

`className="mt-1.5 truncate text-sm leading-relaxed text-ink-muted"`

- `truncate` = `overflow:hidden; text-overflow:ellipsis; white-space:nowrap` — not a
  visibility issue; it clips overflowing text to an ellipsis, does not hide the element.
- `text-ink-muted` — a theme-defined color; assuming it contrasts with `bg-surface`, not
  an issue.
- No `hidden`, `opacity-0`, `sr-only`, or `w-0` classes present.

The CSS classes are not the problem. The invisibility is caused entirely by the
Framer Motion `opacity: 0` style that is never animated away.

---

## 7. Casing mismatch check

### `useSignalR.ts` — all occurrences of lowercase `"detail"` (case-sensitive)

| Line | Match |
|---|---|
| 33 | `// a detail-only or counter-only event doesn't` (comment) |
| 57 | `// A fresh stage resets detail/counter rather than...` (comment) |
| 59 | `// detail-only or counter-only event merges...` (comment) |
| 66 | `latestDetail: isNewStage ? event.detail : (event.detail ?? prev?.latestDetail),` |
| 70 | `if (event.stage === "finalizing" && event.detail?.includes("audited"))` |
| 71 | `next.finalizingSummary = event.detail;` |

All field accesses use lowercase `event.detail`. Wire payload also carries `"detail"` in
lowercase. ✅ **No casing mismatch.**

### C# files — grep results

- `"detail"` (lowercase): **0 matches** in all `.cs` files under `Prism.ApiService/`
- `"Detail"` (PascalCase): **0 matches** in all `.cs` files under `Prism.ApiService/`

The C# layer uses no typed DTO for `ExtractionProgress` — the `JsonElement` is forwarded
verbatim. No renaming or dropping of the `detail` field occurs.

**Verdict:** No casing mismatch anywhere in the chain. The casing hypothesis is ruled out.

---

## 8. Root cause

### The single root cause

**`initial={false}` on `<AnimatePresence>` at PaperActivityView.tsx line 177
prevents the entering `<motion.p>` from transitioning from `opacity: 0` to
`opacity: 1`, leaving the detail text permanently invisible in the DOM.**

Cite: [`PaperActivityView.tsx` line 177](file:///H:/Work%20projects/Prism/Prism.Web/src/components/matrix/PaperActivityView.tsx#L177)

```tsx
<AnimatePresence mode="popLayout" initial={false}>   ← BUG IS HERE
  <motion.p
    key={detail}
    initial={{ opacity: 0 }}                          ← frozen here, never animated away
    animate={{ opacity: 1 }}
    exit={{ opacity: 0 }}
    transition={{ duration: 0.12 }}
    className="mt-1.5 truncate text-sm leading-relaxed text-ink-muted"
  >
    {detail}
  </motion.p>
</AnimatePresence>
```

**`initial={false}` was applied by the prior Claude Code fix** (which swapped
`mode="wait"` → `mode="popLayout"` and added `initial={false}`). The intent was to
prevent a flash of the previous detail text when transitioning stages. However,
because the `<AnimatePresence>` is conditionally rendered (gated by
`status === "current" && detail`), it mounts for the first time together with its
first child. `initial={false}` instructs Framer Motion to skip entry animations for
children present at mount time — so the `<motion.p>` is stuck at `opacity: 0` forever.

All other links in the chain are confirmed healthy: backend emits correctly, C# passes
through verbatim, casing is consistent throughout, hook state updates correctly, prop
flows to `StageRow` correctly, render gate conditions are met.

---

## 9. Recommended fix

> **Do NOT apply — read-only diagnosis only.**

**File:** `Prism.Web/src/components/matrix/PaperActivityView.tsx`  
**Line:** 177  
**Change:** Remove `initial={false}` from `AnimatePresence`

```diff
-              <AnimatePresence mode="popLayout" initial={false}>
+              <AnimatePresence mode="popLayout">
```

**Why this is sufficient:**  
Without `initial={false}`, Framer Motion runs the `initial → animate` transition
(`opacity: 0 → 1`, 120 ms) whenever a `<motion.p>` enters. The `mode="popLayout"`
attribute is retained — it handles the exit of the outgoing element correctly using
the popLayout strategy, which is the right choice for this keyed-list pattern.

`initial={false}` is the correct choice only on `AnimatePresence` components that
are **always mounted** from page load (e.g., route wrappers), where you want to
prevent animating in content that was already visible. Here, the `AnimatePresence`
mounts mid-extraction and must animate its first child in.

**Estimated change:** 1 attribute removed, 0 logic changes.

---

*Diagnosis completed 2026-08-24. Read-only; no source files were modified.*
