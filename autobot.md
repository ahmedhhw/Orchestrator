# Autobot — Iterative TDD Feature Builder

Given a feature description, autobot guides design → iteration planning → iterative TDD implementation, with a mandatory manual testing gate between every iteration.

When invoked, announce **"I am using autobot."** before anything else.

## How to invoke

```
/autobot <feature description>
/autobot <ADO work item URL or ID>
/autobot <path-to-autobot-file.md>     # resume an existing run
```

If no argument is given, ask for a feature description or an ADO work item URL/ID before proceeding.

---

## Conventions (apply everywhere)

- **Link existing repo references.** Any time you name an existing file, function, class, method, or call site — in prose, diagrams, scope bullets, or `Files touched` — link it with markdown **relative to the autobot document's own location**: `[path/from/root.ext](rel/path.ext)` for files, `[file.ext:42](rel/path.ext#L42)` for a line. Example: doc in `docs/`, file at `worktree_manager/cli.py` → `[worktree_manager/cli.py](../worktree_manager/cli.py)`. New files the feature introduces: name their intended path, do **not** link (they don't exist yet).
- **Strict TDD.** Never write production code before a failing test for it exists — regardless of which implementation mode the user picks.
- **Test names describe behaviour, never planning structure.** Never put `phase`, `iter`, `iteration`, or a number from the plan into a test or file name (no `test_phase_0_1`, `test_iter0`).
- **Complete code only.** Everything in a plan must be copy-pasteable — no pseudocode, no `// ...`.
- **Stored-data guardrail.** If a change writes to persisted/stored data (config files, DBs, caches, serialized state, on-disk formats, migrations), surface a before→after diff to the user and get acknowledgement before applying it. Never silently mutate stored data.
- **No silent exceptions.** Never `except X: pass` / swallow errors. Surface to the user or logs; fix the root cause.
- **Sign-off required.** Never advance a stage without explicit user approval.

---

## Document status block (read first, update on every transition)

The autobot document **starts with** a machine-readable status block. It is the single source of truth for where a run is — resume reads it first, before inspecting sections.

```
<!-- autobot-status
stage: 1            # current stage number
iteration: -        # current iteration number, or - before planning
gate: none          # none | pending | confirmed  (state of the current iteration's gate)
mode: -             # plan | contract | direct  (chosen implementation mode)
updated: <date>
-->
```

Update this block at every state change. The gate moves to `confirmed` **only** when you record the user's confirmation (see Stage 5).

---

## Resume

If the argument is a file path (ends `.md` or contains `/`), read that file as the resume target. Otherwise, before Stage 1, look for an `autobot-*.md` in `docs/` then the repo root.

When a document is found, **read its status block** and resume from `stage`/`iteration`/`gate`:

- `gate: confirmed` on the **last** planned iteration **and** final suite passed → feature complete; tell the user and stop.
- `gate: confirmed` (not the last iteration) → resume at **Stage 6** to plan the next iteration.
- `gate: pending` → resume at **Stage 5**; remind the user to complete and confirm the gate first.
- iteration plan exists, no gate yet → resume at **Stage 3**.
- design exists, no iteration plan → resume at **Stage 2**.

If a doc has no status block (older format), reconstruct state from its sections, **add a status block**, then continue. If multiple `autobot-*.md` exist, list them and ask which to resume. Tell the user exactly where you're resuming, e.g. *"Resuming `autobot-x.md` at Stage 5 — Iteration 1's gate is pending."* Never re-run completed stages.

---

## Stage 1 — Design

**Goal:** Gather context, then write `autobot-<feature-slug>.md` before any code.

### 1a — Gather context

**ADO work item** (numeric ID, a `dev.azure.com`/`visualstudio.com` URL, or "ADO ticket #N"):
1. Use the ADO MCP server if one is available in the session.
2. Otherwise, ask for the org URL and a PAT with `Work Items (Read)`, then fetch via REST:
   - Item: `GET https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{id}?$expand=all&api-version=7.1`
   - Comments: `GET .../workitems/{id}/comments?api-version=7.1-preview.3`
   - Auth: `Authorization: Basic <base64(":" + PAT)>`
3. Extract Title (`System.Title`), Description (`System.Description`), Acceptance Criteria (`Microsoft.VSTS.Common.AcceptanceCriteria`), Comments (each `text`) — strip HTML.
4. Show the extracted content and confirm it's correct before continuing.

**Plain description:** use it directly.

### 1b — Write the design document

Place it in `docs/` if that folder exists at the repo root, else at the root. Start the file with the **status block** (`stage: 1`), then:

```
# <Feature Name>

## Overview
One paragraph: what this does and why.

## UI / Flow
ASCII mockup of every screen/state. Label each (Empty / Loaded / Error …).

## Architecture
Mermaid diagram(s): data flow (sequence if async, component if structural) and any new models/services/view-models and their relationships.

## API Surface          # include ONLY if the feature touches any API
List every external or internal API the feature calls: endpoint/method/signature, the exact params used, and a link to the official documentation for each.

## Open Questions
Bullet list of unresolved ambiguities/decisions.
```

### 1c — API verification gate (only if an API is involved)

If the feature touches **any** API (external service, library, or internal endpoint), before leaving Stage 1 you must:
1. **Verify every param against official documentation** — names, types, required/optional, defaults. Do not rely on memory; fetch and cite the docs. Correct anything that doesn't match.
2. **Prove the API behaves as expected** — write and run minimal tests/probes against the real (or sandbox) API confirming each call returns what the design assumes. Surface the results.

If no API is involved, skip this silently.

### 1d — Approve

Show the document and **stop**.
- If **Open Questions** is non-empty: ask each one, refuse to proceed until all are answered, then update the doc and remove the resolved questions.
- Only when Open Questions is empty (and the API gate, if any, passed), ask: *"Does this design look right? Any changes before Stage 2?"*

Do not enter Stage 2 until the user approves **and** there are no open questions **and** any API gate has passed. Set `stage: 2` on approval.

---

## Stage 2 — Iteration Plan

**Goal:** Slice the feature into Iteration 0 (walking skeleton) + as many iterations as the feature genuinely needs, each adding one layer of user-visible behaviour. No code.

1. **Iteration 0 — walking skeleton:** the minimum that can be built, run, and touched end-to-end by a human. If you can't describe what a person would click or observe to confirm it, it's too thin — thicken it.
2. **Iterations 1…N:** each adds exactly one cohesive layer of visible behaviour. Small features may need only **2–5 total** including the skeleton; large features can legitimately run **up to 15** — don't artificially cap a big feature. Plan as many as the feature genuinely needs and no more.
3. Append:

```
## Iteration Plan

### Iteration 0 — Walking Skeleton
**Delivers:** One sentence — what a human can see/touch after this.
**Scope:** Bullets (link existing references).
**Out of scope:** Bullets — what's deferred.

### Iteration N — <Short Name>
**Delivers:** One sentence.
**Scope:** Bullets.
**Builds on:** Iteration N-1.
```

4. Show the doc and **stop**: *"Does this plan look right? Is the skeleton thin enough to build fast but thick enough to actually run? Any changes before Iteration 0?"* Set `stage: 2, iteration: 0` and wait for approval.

---

## Stage 3 — Plan/Build Iteration 0

Pick up here for Iteration 0; **Stage 6 is identical for Iteration N** — both use the choices and shared blocks below.

### Choose an implementation mode

Ask the user (record the answer in `mode:`):

> "How should I build this iteration?
> - **Plan first** — I write the full TDD plan (tests + production code) to the doc, you review, then implement phase by phase.
> - **Behavioral contract** — I write **end-to-end behavioral tests** that assert observable behaviour (not implementation details), you review and approve them, then I implement freely to make them pass. The approved tests are the contract.
> - **Implement on your own** — I do strict TDD directly against the iteration scope, no upfront plan document."

**Regardless of mode, always append the Manual Testing Gate (below) to the doc before any implementation.** The gate is never skipped or omitted.

Before writing any plan, detect the project's primary language from existing source and use its conventions and test framework throughout.

### Mode: Plan first

Break the iteration into the **smallest independently-testable phases**. For each, append the **Phase block**:

```
### Phase N.M — <Short Phase Name>
**What it covers:** One sentence.
**Files touched:** Bullets — link existing files; name new files unlinked; link existing call sites with line anchors.
**Tests (Red) — write first:**
\`\`\`
<complete, copy-pasteable test code>
\`\`\`
**Production code (Green):**
\`\`\`
<complete, copy-pasteable implementation>
\`\`\`
**Done when:** Observable acceptance criteria (not "tests pass").
```

Show the doc and **stop** — implement nothing yet.

### Mode: Behavioral contract

1. Write **end-to-end behavioral tests** for the iteration — each asserts an observable, user-facing behaviour from the outside (inputs → observable outputs/state), **never** internal structure. Append them under:

```
### Behavioral Contract — Iteration N
\`\`\`
<complete, copy-pasteable end-to-end behavioral tests>
\`\`\`
```

2. Show them and **stop**: *"These behavioral tests are the contract for this iteration. Approve them and I'll implement freely to make them pass."*
3. Once approved, the contract is **locked** — implement freely to satisfy it, but if implementation reveals a test must change, **stop and get re-approval** before editing it. Never silently weaken the contract.

### Mode: Implement on your own

Implement directly with strict TDD (failing test before every piece of production code). Keep a one-line-per-phase ledger in the doc so the discipline leaves evidence:

```
### Implementation Ledger — Iteration N
- <behavioral test name>: red → green ✓
```

### Manual Testing Gate (append for every iteration, all modes)

```
## ✋ Manual Testing Gate — Iteration N

> STOP. Do not proceed to Iteration N+1 until every item is confirmed by the user.

- [ ] <Specific action — exact thing to do>
- [ ] <Observable result — exact thing to see>
- [ ] <Edge/error/empty case to verify>
- [ ] <Regression: confirm Iteration 0..N-1 behaviour still works>   # required from Iteration 1 on

**Confirmed by user:** —
**How to confirm:** Perform each action, check each box. Reply "Iteration N confirmed" (or describe failures) before I plan the next iteration.
```

Gate items must be **specific** (exact action + exact result), **observable** (no reading code/test output), and **complete** (every behaviour delivered, including error/empty states). From Iteration 1 on, **derive regression items from the prior gates' observable-result lines** so coverage is mechanical, not re-invented.

---

## Stage 4 — Hand off Iteration 0

1. **Run the full test suite once** to establish a clean baseline. If anything fails, surface it and stop until resolved.
2. Tell the user how to proceed by mode:
   - *Plan first:* "Implement one phase at a time — 'Implement Phase 0.1', etc. Full code is in the doc."
   - *Behavioral contract:* "Tests are approved; I'll implement to satisfy them."
   - *Implement on your own:* "I'll TDD this directly."
3. In all cases: *"When implementation is done, complete the Manual Testing Gate and reply 'Iteration 0 confirmed', or describe what failed."*
4. **Stop and wait.** Do not plan Iteration 1 until the gate is confirmed.

---

## Stage 5 — Gate review (every iteration)

When the user replies after a gate:

- **All items confirmed:** edit the doc — tick the gate's boxes to `[x]`, set `**Confirmed by user:** <date>`, and set `gate: confirmed` in the status block. **Then** proceed to Stage 6.
- **Any item failed/skipped:**
  1. **STOP — do not plan the next iteration.** Leave `gate: pending`.
  2. Acknowledge the failure; help diagnose and fix.
  3. Ask the user to re-run the failed items and re-confirm.

**This gate is mandatory.** If the user tries to skip it, refuse and redirect. Recording the confirmation in the file (boxes + date + `gate: confirmed`) is what makes resume reliable — never treat a gate as passed without writing it.

---

## Stage 6 — Plan/Build Iteration N

Just-in-time, after the previous gate is confirmed. Identical to Stage 3: choose a mode, write the chosen artifact (Phase blocks / Behavioral Contract / Ledger), append the Manual Testing Gate (with derived regression items), show, **stop**, then hand off as in Stage 4. Repeat Stages 5–6 until every planned iteration is confirmed.

---

## Stage 7 — Feature complete

When the last iteration's gate is confirmed:
1. **Run the full test suite once** — confirm no failures or regressions.
2. Set `stage: 7, gate: confirmed`; declare the feature done.

---

## Suite-running policy

Run the **full** suite exactly twice: the Stage 4 baseline and the Stage 7 finish. **Never** run the full suite between iterations or mid-implementation. During implementation, before each gate, run only the **current iteration's tests plus the test files for any modules this iteration touched** — enough to catch a broken sibling, not the whole suite. (The API verification probes in Stage 1c are separate and expected.)
