# Autobot — Iterative TDD Feature Builder

Given a feature description, autobot guides frontend design → backend design → iteration planning → iterative TDD implementation, with a mandatory manual testing gate between every iteration.

When invoked, announce **"I am using autobot."** before anything else.

## How to invoke

```
/autobot <feature description>
/autobot <ADO work item URL or ID>
/autobot <path-to-autobot-file.md>     # resume an existing run
```

If no argument is given, ask for a feature description or ADO work item URL/ID before proceeding.

---

## Conventions (apply everywhere)

- **Link existing repo references.** Any time you name an existing file, function, class, or method — in prose, scope bullets, or file lists — link it with markdown relative to the autobot document's own location. New files: name their intended path, do not link.
- **Strict TDD.** Never write production code before a failing test exists for it.
- **Test names describe behaviour.** Plain readable English — no `phase`, `iter`, `iteration`, or numbers from the plan in test or file names.
- **No silent exceptions.** Never `except X: pass`. Surface errors to the user or logs.
- **Stored-data guardrail.** If a change writes to persisted data (config files, DBs, caches, on-disk formats), show a before→after diff and get acknowledgement before applying.
- **Sign-off required.** Never advance a stage without explicit user approval.
- **Small mermaid diagrams only.** Each diagram covers one concept, 3–5 nodes max. Use many small diagrams rather than one large one. Only use mermaid when it adds something pseudocode cannot.

---

## Document status block

The autobot document starts with this block. It is the single source of truth for resume.

```
<!-- autobot-status
stage: 1
iteration: -
gate: none
mode: -
updated: <date>
-->
```

Update it at every state change. `gate: confirmed` only when user confirmation is recorded.

---

## Resume

If the argument ends in `.md` or contains `/`, read it as the resume target. Otherwise look for `autobot-*.md` in `docs/` then repo root.

Read the status block and resume from `stage`/`iteration`/`gate`:

- `gate: confirmed` on the last iteration and final suite passed → feature complete, tell user and stop.
- `gate: confirmed` (not last iteration) → resume at Stage 6.
- `gate: pending` → resume at Stage 5; remind user to confirm the gate first.
- iteration plan exists, no gate → resume at Stage 3.
- backend design exists, no iteration plan → resume at Stage 2.
- frontend design exists, no backend design → resume at Stage 1 Part 2.
- no design → resume at Stage 1 Part 1.

If multiple `autobot-*.md` exist, list them and ask which to resume. Tell the user exactly where you're resuming. Never re-run completed stages.

---

## Stage 1 — Design

**Goal:** Agree on the experience before touching technology. Frontend design is locked before backend design begins.

### Gather context

**ADO work item** (numeric ID, `dev.azure.com` URL, or "ADO ticket #N"):
1. Use the ADO MCP server if available.
2. Otherwise ask for the org URL and a PAT with `Work Items (Read)`, then fetch:
   - `GET https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{id}?$expand=all&api-version=7.1`
   - `GET .../workitems/{id}/comments?api-version=7.1-preview.3`
   - Auth: `Authorization: Basic <base64(":" + PAT)>`
3. Extract Title, Description, Acceptance Criteria, Comments — strip HTML.
4. Show extracted content and confirm before continuing.

**Plain description:** use it directly.

---

### Stage 1a — Frontend Design

> "Start with the user experience, then work back to the technology." — Steve Jobs

**If the feature has no UI**, skip this silently and go straight to Stage 1b.

Draw ASCII mocks first (best-guess), then ask clarifying questions inline at the bottom. Keep descriptions minimal — the mocks are the communication.

Show every meaningful screen state: empty, loaded, error, edge cases.

Write to the autobot doc:

```
## Frontend Design

### <Screen Name>
<ASCII mock>

### <Screen Name — State Variant>
<ASCII mock>

...
```

Stop and ask: *"Does this look right? Any screens missing or wrong before we design the backend?"*

Do not proceed to Stage 1b until the user approves. Set `stage: 1` (part 2 pending) on approval.

---

### Stage 1b — Backend Design

Design the business logic that makes the frontend work. No UI logic here — only data, algorithms, and flow.

For each piece of business logic, write pseudocode and a small focused mermaid diagram where it helps. Use as many small diagrams as needed — one per concept (data model, sequence, state machine, etc.).

Write to the autobot doc:

```
## Backend Design

### <Concept Name>
<pseudocode>

<mermaid diagram if it adds clarity — one concept only, 3–5 nodes>

### <Concept Name>
...
```

### API verification (only if an external/internal API is involved)

1. Verify every param against official docs — fetch and cite, never rely on memory.
2. Run minimal probes against the real API confirming each call behaves as the design assumes. Surface results.

Stop and ask: *"Does this logic look right before we plan iterations?"*

Set `stage: 2` on approval.

---

## Stage 2 — Iteration Plan

**Goal:** Slice the feature into thin vertical iterations, each delivering one observable layer of behaviour.

### Step 1 — Propose titles only

List iteration titles and nothing else. Wait for approval before adding detail.

```
## Iteration Plan

- Iteration 0 — <title>
- Iteration 1 — <title>
- ...
```

Iteration 0 is always the walking skeleton — the minimum a human can run and touch end-to-end. Use as many iterations as the feature genuinely needs — no more, no less.

If the feature has both frontend and backend, interleave them within each iteration — a thin slice of UI and the backend it needs, together.

Ask: *"Does this slice look right? You can ask me to add, remove, combine, or split iterations — or propose your own set entirely."* Wait for approval or changes before Step 2.

---

### Step 2 — Detail each iteration (after title approval)

For each iteration append:

```
### Iteration N — <Title>

**Tests:**
- <plain English test name>
- <plain English test name>
...

**Files:**
- `path/to/file.py` (new | existing)
...

---

#### `path/to/file.py`
\`\`\`
<high-level pseudocode>
\`\`\`

<mermaid diagram — one concept, 3–5 nodes, only if it adds clarity>

#### `path/to/other_file.py`
...
```

Rules:
- Tests section comes first — it tells the user what this iteration proves before showing how.
- Pseudocode is high-level. No implementation detail, no complete code.
- Mermaid diagrams are small and focused. Many small ones, never one large one.
- Frontend and backend files interleaved naturally — no sub-headings separating them.

Show all iteration details at once after title approval. Stop and ask: *"Does this plan look right? Any changes before we start Iteration 0?"*

Set `stage: 2, iteration: 0` on approval.

---

## Stage 3 — Build Iteration 0

Pick up here for Iteration 0. **Stage 6 is identical for Iteration N.**

### Choose a mode

Ask the user:

> "How should I build this iteration?
> - **Reviewed** — I write the full TDD plan (tests + production code) to the doc for your review, then implement phase by phase.
> - **Autonomous** — I TDD this directly without an upfront plan."

Record the answer in `mode:`.

Before writing anything, detect the project's primary language and test framework from existing source.

**Always append the Manual Testing Gate before any implementation begins.**

---

### Mode: Reviewed

Break the iteration into the smallest independently-testable phases. For each append:

```
### Phase N.M — <Name>
**What it covers:** One sentence.
**Files touched:** Bullets — link existing; name new unlinked.
**Tests (Red):**
\`\`\`
<complete test code for review>
\`\`\`
**Production code (Green):**
\`\`\`
<complete implementation for review>
\`\`\`
**Done when:** Observable acceptance criteria.
```

Show and stop — implement nothing until the user approves the plan.

---

### Mode: Autonomous

Implement directly with strict TDD. Keep a ledger in the doc as evidence:

```
### Implementation Ledger — Iteration N
- <test name>: red → green ✓
```

---

### Manual Testing Gate (append for every iteration, every mode)

```
## ✋ Manual Testing Gate — Iteration N

> STOP. Do not proceed to Iteration N+1 until every item is confirmed.

- [ ] <Exact action to take>
- [ ] <Exact thing to observe>
- [ ] <Edge / error / empty case>
- [ ] <Regression: prior iteration behaviour still works>   # required from Iteration 1 on

**Confirmed by user:** —
**How to confirm:** Check every box, then reply "Iteration N confirmed" or describe what failed.
```

Gate items must be specific, observable, and complete. From Iteration 1 on, derive regression items mechanically from prior gates' observable-result lines.

---

## Stage 4 — Hand off Iteration 0

1. Run the full test suite once to establish a clean baseline. Surface any failures and stop until resolved.
2. Tell the user how to proceed:
   - *Reviewed:* "Implement one phase at a time — say 'Implement Phase 0.1', etc."
   - *Autonomous:* "I'll TDD this directly."
3. *"When done, complete the Manual Testing Gate and reply 'Iteration 0 confirmed', or describe what failed."*
4. Stop and wait. Do not plan Iteration 1 until the gate is confirmed.

---

## Stage 5 — Gate review

When the user replies after a gate:

- **All confirmed:** tick boxes to `[x]`, set `**Confirmed by user:** <date>`, set `gate: confirmed`. Proceed to Stage 6.
- **Any failed:** leave `gate: pending`, acknowledge, help fix, ask user to re-run and re-confirm.

This gate is mandatory. If the user tries to skip it, refuse and redirect. Never treat a gate as passed without writing it to the file.

---

## Stage 6 — Build Iteration N

After the previous gate is confirmed. Identical to Stage 3: ask mode, write the chosen artifact, append the Manual Testing Gate with derived regression items, show, stop, hand off. Repeat Stages 5–6 until every iteration is confirmed.

---

## Stage 7 — Feature complete

When the last iteration's gate is confirmed:
1. Run the full test suite — confirm no failures or regressions.
2. Set `stage: 7, gate: confirmed` and declare the feature done.

---

## Suite-running policy

Run the full suite exactly twice: Stage 4 baseline and Stage 7 finish. Never run the full suite between iterations. During implementation, run only the current iteration's tests plus test files for any modules this iteration touched.
