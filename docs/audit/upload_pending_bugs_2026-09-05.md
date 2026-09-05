# Audit Report: Prism File Upload & Processing Bugs
**Date:** 2026-09-05

This report investigates two bugs in the Prism file upload and processing pipeline:
1. Failed extractions stuck in a never-ending retry loop (MAX_ATTEMPTS bypassed).
2. The sidebar erroneously showing "Ready" for failed uploads.

---

## 1. Bug 1 — Retry loop root cause

The root cause of the infinite retry loop is a bug in how `attempt` is calculated when transient errors occur. 

When a transient error is caught in `main.py` (`except Exception as e:`), the worker intentionally sleeps for 5 seconds and then **republishes a new message** with an incremented `x-attempt` header, instead of NACK-ing the current message:
```python
# main.py
new_headers = dict(message.headers or {})
new_headers["x-attempt"] = attempt + 1
await channel.default_exchange.publish(...)
await message.ack() 
```
However, the function that parses the attempt count prioritizes RabbitMQ's built-in `x-delivery-count` over the custom `x-attempt` header:
```python
# main.py
def _get_attempt_count(message) -> int:
    headers = message.headers or {}
    delivery_count = headers.get("x-delivery-count")
    if delivery_count is not None:
        return int(delivery_count) + 1  # 0-indexed -> 1-indexed
    # Fallback: our own portable counter
    return int(headers.get("x-attempt", 1))
```
Because the worker is publishing a brand-new message to RabbitMQ rather than requeuing the old one, RabbitMQ assigns the new message an `x-delivery-count` of `0`. 
Therefore, `_get_attempt_count` always evaluates to `0 + 1 = 1`. The `x-attempt` header is successfully incremented, but completely ignored. As a result, `attempt >= MAX_ATTEMPTS` is never reached, and the 7-second retry loop (5s sleep + ~2s parsing) continues indefinitely.

## 2. Bug 1 — What terminal-failure state SHOULD do

According to `decisions.md` (RabbitMQ topology), when a paper permanently fails (e.g., `fitz.FileDataError` or `attempt >= MAX_ATTEMPTS`), it should:
1. Publish an explicit error message to the `document_processed_queue`.
2. Reject the message without requeueing (`requeue=False`), which routes it to the Dead Letter Queue (DLQ).

The code accurately reflects this intent:
```python
# main.py
if attempt >= MAX_ATTEMPTS:
    error_message = {
        "fileId": file_id,
        "fileName": file_name,
        "connectionId": connection_id,
        "chatId": chat_id,
        "status": "Error",
        "summary": f"Processing failed after {MAX_ATTEMPTS} attempts: {str(e)}"
    }
    await channel.default_exchange.publish(
        aio_pika.Message(body=json.dumps(error_message).encode()),
        routing_key='document_processed_queue',
    )
    await message.reject(requeue=False)  # -> DLQ
```
The backend `RabbitMqListenerService` consumes this, writes the error string into the database, and emits the `DocumentProcessed` SignalR event, leaving the paper permanently failed.

## 3. Bug 2 — Sidebar state derivation

In the UI (`PaperListItem.tsx`), the "Ready" vs "Analyzing" vs "Failed" badge is driven strictly by `chat.extractionStatus`:
```tsx
// PaperListItem.tsx
{chat.extractionStatus === "Completed" ? (
   // Shows "Ready"
) : chat.extractionStatus === "Failed" ? (
   // Shows "Failed"
) : (
   // Shows "Analyzing..."
)}
```
However, the backend does not store an explicit extraction status. Instead, the `useChats` fetch (`/api/chats/{userId}`) derives `ExtractionStatus` via a SQL `CASE` statement based on whether the `summary` column is null:
```sql
CASE
    WHEN (
        SELECT f1.summary
        FROM file_records AS f1
        WHERE f1.chat_id = p.chat_id
        ORDER BY f1.uploaded_at DESC
        LIMIT 1) IS NOT NULL THEN 'Completed'
    ELSE 'In progress'
END AS "ExtractionStatus"
```
The sidebar is hydrated by a direct database query via REST, not by cached SignalR events.

## 4. Bug 2 — Why "Ready" surfaces on failed papers

The false "Ready" state is caused by **conflating a populated summary column with a successful extraction**. (Option A: Backend writes "Ready" prematurely).

When a paper reaches terminal failure, `main.py` populates the `summary` payload with an error string (e.g., `"Could not process document. The file may be corrupted."`). 
The `RabbitMqListenerService` blindly writes this error string into the `FileRecords.Summary` column in Postgres. 

Because `Summary` is no longer NULL, the SQL query strictly evaluates it as `'Completed'`. The REST API serves `"extractionStatus": "Completed"`, and `PaperListItem.tsx` renders it as "Ready".

## 5. Polling pattern

There is no intentional `setInterval` polling within `useChats.ts` or `usePaperClaims.ts`. The React hooks correctly memoize their `fetch` calls.

The rapid, repeated network fetches ("every few seconds") observed in the network tab are a side-effect of `AppShell.tsx`'s SignalR subscription:
```tsx
// AppShell.tsx
useEffect(() => {
  const handleDocumentProcessed = (data: unknown) => {
    refetchChats();
    // ... refetchClaims();
  };
  on("DocumentProcessed", handleDocumentProcessed);
  return () => off("DocumentProcessed", handleDocumentProcessed);
}, [on, off, activeChatId, refetchChats, refetchClaims]);
```
Because the `useSignalR` hook returns newly bound `on` and `off` function references on every render, this `useEffect` constantly tears down and rebuilds its event listeners. While SignalR's internal referential checks prevent duplicate listeners, any external event that rapidly forces an AppShell render (such as `useExtractionProgress` emitting state updates every 7 seconds during the infinite retry loop) could theoretically destabilize the component tree or cause cascaded refetches if the backend mistakenly emits `DocumentProcessed` concurrently. 

*Note: Statically, the Python pipeline emits `ExtractionProgress` during transient failures, not `DocumentProcessed`. If fetches are truly firing every few seconds, it indicates either a React Router remount loop (switching between `<Route path="/paper/:paperId">` and `/`) or an unhandled exception in the C# `RabbitMqListenerService` causing RabbitMQ to infinitely redeliver and re-broadcast.*

## 6. Interaction between Bug 1 and Bug 2

These bugs are independent but interact pathologically. 
Because Bug 1 prevents transient errors from ever reaching terminal failure, their `summary` remains NULL, so they correctly display as "Analyzing..." in the sidebar while stuck in the loop.
However, if a paper hits a *terminal* error (like the 3 older `react.pdf` uploads hitting `fitz.FileDataError`), they bypass the retry loop, immediately write their error string to `summary`, and trigger Bug 2, falsely appearing as "Ready".

**Critical Note:** If Bug 1 is fixed without fixing Bug 2, transient errors will finally reach `MAX_ATTEMPTS`, write their error string to the database, and **they too will incorrectly show as "Ready" in the sidebar.**

## 7. Ranked recommendations

### 1. Fix Bug 1 (Retry Loop) - Effort: Trivial
* **Action:** Update `_get_attempt_count` in `Prism.PythonService/main.py` to prioritize `headers.get("x-attempt")` over `x-delivery-count`, or simply remove the `x-delivery-count` logic entirely since the republish pattern renders it useless. 
* **Decisions.md:** No update needed.

### 2. Fix Bug 2 (False "Ready" State) - Effort: Medium
* **Action:** Stop deriving pipeline status from `Summary IS NOT NULL`. Add an explicit `ExtractionStatus` or `Status` column to the `file_records` table (e.g., Pending, Completed, Failed). Update `RabbitMqListenerService.cs` to write to this column, and update the SQL query to read from it directly.
* **Decisions.md:** Requires a new entry explaining the migration from the derived summary status to an explicit status column.

### 3. Stabilize SignalR Hooks (Debt) - Effort: Low
* **Action:** Wrap the `on`, `off`, and `joinChat` functions in `Prism.Web/src/hooks/useSignalR.ts` with `useCallback`. This will prevent `AppShell.tsx` from needlessly tearing down and re-registering WebSocket listeners on every render, mitigating any potential cascading re-render loops.
* **Decisions.md:** No update needed.
