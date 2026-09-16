# Lessons

- **Missing-abstraction bug pattern:** when the same class of bug (e.g. "forgot to attach auth header") shows up in more than one independent call site, the fix is a shared abstraction (piClient.ts), not patching each site — patching sites individually guarantees a future site will drift the same way.
- **Verify before acting:** AG2.0 audit findings should be verified against real evidence (an actual decoded token, an actual log line) before being acted on — this session had two audit claims that were plausible but unverified, and both turned out to need correction once checked against real data.
- **Restart != Restart:** A restart doesn't always mean a restart: config changes to ppsettings.json (or similar startup-read config) require a full process kill, not just a re-run, if a debugger or lingering process still holds the old binary.
- **Check dependencies before removal:** Before removing a UI element, confirm what ELSE currently depends on it (props, gating logic, other call paths) — this session found duplicate Re-run buttons genuinely called the same backend path, but only after checking, not assuming.
