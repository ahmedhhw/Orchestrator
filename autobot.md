# Autobot — Iterative TDD Feature Builder

Given a feature description, autobot guides frontend design → backend design → iteration planning → iterative TDD implementation, with a mandatory manual testing gate between every iteration.

When invoked, announce **"I am using autobot."** before anything else.

Immediately after the announcement, recommend the user run on **Opus High** for the design and planning stages (it is the strongest agent for this work) and wait for them to confirm before proceeding. Later, at the implementation boundary (Stage 4 / first phase implementation), prompt the user to switch to **Sonnet** to use tokens efficiently and wait for confirmation — see [Model policy](#model-policy).

## How to invoke

```
/autobot <feature description>
/autobot <ADO work item URL or ID>
/autobot <path-to-autobot-file.md>     # resume an existing run
```

If no argument is given, ask for a feature description or ADO work item URL/ID before proceeding.

---

## Conventions (apply everywhere)

- **ALWAYS LINK EXISTING REPO REFERENCES — NO EXCEPTIONS.** Any time you name an existing file, function, class, or method — in prose, scope bullets, or file lists — you MUST link it with markdown relative to the autobot document's own location. Example: instead of `TodoViewModel.swift`, write `[TodoViewModel.swift](../TimeControl/ViewModels/TodoViewModel.swift)`. New files that do not yet exist: name their intended path only, do not link. **Before outputting any section, scan it and verify every existing reference is linked.**
- **Strict TDD.** Never write production code before a failing test exists for it.
- **Test names describe behaviour.** Plain readable English — no `phase`, `iter`, `iteration`, or numbers from the plan in test or file names.
- **No silent exceptions.** Never `except X: pass`. Surface errors to the user or logs.
- **Stored-data guardrail.** If a change writes to persisted data (config files, DBs, caches, on-disk formats), show a before→after diff and get acknowledgement before applying.
- **Sign-off required.** Never advance a stage without explicit user approval.
- **Small mermaid diagrams only.** Each diagram covers one concept, 3–5 nodes max. Use many small diagrams rather than one large one. Only use mermaid when it adds something pseudocode cannot.
- **Reviewed plans live in their own files.** Never write a Reviewed-mode TDD plan inline in the main autobot document. Write each plan to its own file (see [Reviewed mode](#mode-reviewed)) and link to it from the iteration. This keeps the main doc navigable and the context lean.
- **Iteration context files are always generated.** Before handing off any iteration to an implementer agent (both Reviewed and Autonomous modes), write a lean `autobot-<feature>-ctx-iter-N.md` file. See [Iteration context files](#iteration-context-files). These are deleted at Stage 7.

---

## Model policy

- **Design & planning (Stages 1–2):** Opus High. Recommend it at invocation and wait for confirmation.
- **Implementation (Stages 3–4 onward, once files are actually being modified):** prompt the user to switch to **Sonnet** for token efficiency, and wait for their confirmation before continuing. Do this once, at the first real implementation step (when leaving planning to touch production/test files) — not at every phase.
- If the user declines a switch, respect it and continue.

---

## Keeping context lean

Long autobot runs accumulate context. Apply these throughout:

- **Reviewed plans in separate files** — see the Conventions rule on plan files.
- **Iteration context files** — implementer agents read the lean context file for the current iteration instead of the full autobot doc. See [Iteration context files](#iteration-context-files).
- **Switch to Sonnet for implementation** (see Model policy).
- **Read narrowly.** When you only need one function, read its line range — not the whole file. Prefer search over speculative full-file reads.

---

## Iteration context files

Before handing off any iteration to an implementer agent, write a lean file named `autobot-<feature>-ctx-iter-N.md` next to the autobot document. This file is the **only context** the implementer needs — it must be self-contained.

Template:

```markdown
# Context: Iteration N — <Title>

## Goal
<1–3 sentences: what this iteration builds and why it matters to the feature>

## Tests to write
- <plain-English test name>: <one-line description of what it proves>
- ...

## Files to touch
- [existing-file.swift](../relative/path/to/file.swift) — <what changes here, one line>
- `NewFile.swift` (new) — <what goes in here, one line>

## Relevant existing code
<Only the function signatures / type definitions this iteration actually calls or modifies. Paste snippets — do not ask the implementer to go hunt for them.>

## Constraints / invariants
<Any non-obvious rules from the backend design or prior iterations that apply here.>

## Done when (gate items)
- [ ] <exact gate item from the Manual Testing Gate for this iteration>
- [ ] ...

## TDD mode: <Reviewed | Autonomous>
<Reviewed: "Implement phase by phase — Phase N.1, N.2, … See [plan file](autobot-<feature>-plan-iter-N.md)."
Autonomous: "TDD directly. Keep the ledger below as you go.">
```

Rules:
- Paste the relevant code snippets directly into the file — the implementer must not need to open other files just to understand the context.
- Link every existing file/function reference (relative to this context file's location).
- Keep it short. If a section is empty, omit it.
- After writing, add a link to it in the autobot doc under the iteration: `**Context file:** [Iteration N context](autobot-<feature>-ctx-iter-N.md)`

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

Before writing to the doc, scan every file/function/class reference in the section and confirm each existing one is linked.

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

Before writing to the doc, scan every file/function/class reference in the section and confirm each existing one is linked.

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

On approval, append the final agreed titles to the autobot doc before proceeding.

---

### Step 2 — Detail each iteration (after title approval)

For each iteration append full detail followed immediately by its Manual Testing Gate:

```
### Iteration N — <Title>

**Tests:**
- <plain English test name>
- <plain English test name>
...

**Files:**
- `repo-name/` (omit if single-repo)
  - `path/to/file.py` (new | existing)
  - ...
- `other-repo/` (omit if single-repo)
  - `path/to/file.py` (new | existing)
  - ...

---

#### `path/to/file.py`
\`\`\`
<high-level pseudocode>
\`\`\`

<mermaid diagram — one concept, 3–5 nodes, only if it adds clarity>

#### `path/to/other_file.py`
...

## ✋ Manual Testing Gate — Iteration N

> STOP. Do not proceed to Iteration N+1 until every item is confirmed.

- [ ] <Exact action to take>
- [ ] <Exact thing to observe>
- [ ] <Edge / error / empty case>
- [ ] <Regression: prior iteration behaviour still works>   # required from Iteration 1 on

**Confirmed by user:** —
**How to confirm:** Check every box, then reply "Iteration N confirmed" or describe what failed.
```

Rules:
- Tests section comes first — it tells the user what this iteration proves before showing how.
- Pseudocode is high-level. No implementation detail, no complete code.
- Mermaid diagrams are small and focused. Many small ones, never one large one.
- In single-repo features, frontend and backend files are interleaved naturally with no sub-headings. In multi-repo features, group files under their repo name — but still interleave front/back within each repo group.
- Gate items must be specific, observable, and complete. From Iteration 1 on, derive regression items mechanically from prior gates' observable-result lines.

Before writing to the doc, scan every file/function/class reference in the iteration details and confirm each existing one is linked.

Show all iteration details (with gates) at once after title approval. Stop and ask: *"Does this plan look right? Any changes before we start Iteration 0?"*

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

---

### Mode: Reviewed

Write the plan to **its own file**, not the main autobot doc. Name it next to the autobot document, e.g. `autobot-<feature>-plan-iter-N.md`. Then add a link to it under the iteration in the main doc:

```
### Iteration N — <Title>
**Reviewed plan:** [Iteration N plan](autobot-<feature>-plan-iter-N.md)
```

Break the iteration into the smallest independently-testable phases. In the **plan file**, for each phase append:

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

Before writing the phase plan to the file, scan every file/function/class reference and confirm each existing one is linked (relative to the plan file's location).

Show and stop — implement nothing until the user approves the plan. Once approved and the user is ready to implement, apply the [Model policy](#model-policy): prompt to switch to Sonnet before touching files.

When the user says **"Implement Phase N.M"**, spawn a subagent for that phase only.

**If the Agent tool is available (Claude Code):** call it with these exact parameters — do NOT omit `model`:
```
Agent(
  description: "Implement Phase N.M — <phase name>",
  model: "sonnet",
  prompt: "<the prompt below>"
)
```

**Otherwise:** spawn a subagent using whatever mechanism is available, preferring Sonnet 4.6 if the model can be specified.

The subagent prompt is:
```
Read <path-to-ctx-iter-N.md> for iteration context. Then read Phase N.M in <path-to-plan-iter-N.md>. Implement that phase only — write the tests (Red), make them pass (Green), refactor if needed. Run only this phase's test file (plus test files for any modules touched) after each step. When done, report back: every test written and its final pass/fail status.
```

Do not include any other context in the spawn prompt — the context file + plan file are sufficient.

When the subagent returns, append its results to the ledger in the autobot doc:

```
### Implementation Ledger — Iteration N
- Phase N.M — <Name>
  - <test name>: red → green ✓
```

Then wait for the user to say which phase to implement next. Never spawn the next phase automatically.

---

### Mode: Autonomous

Write the iteration context file (per [Iteration context files](#iteration-context-files)), then spawn a subagent to do the TDD work.

**If the Agent tool is available (Claude Code):** call it with these exact parameters — do NOT omit `model`:
```
Agent(
  description: "TDD Iteration N — <title>",
  model: "sonnet",
  prompt: "<the prompt below>"
)
```

**Otherwise:** spawn a subagent using whatever mechanism is available, preferring Sonnet 4.6 if the model can be specified.

The subagent prompt is:
```
Read <path-to-ctx-iter-N.md> for full context. TDD the iteration described there — strict red/green/refactor, one test at a time. Run only this iteration's tests (plus any test files for modules you touch) after each green. When all tests pass, report back a one-line summary of every test written and its final status.
```

Do not include any other context in the spawn prompt — the context file is sufficient.

When the subagent returns, copy its test ledger into the autobot doc:

```
### Implementation Ledger — Iteration N
- <test name>: red → green ✓
```

Then present the ledger to the user and ask them to complete the Manual Testing Gate.

---

---

## Stage 4 — Hand off Iteration 0

1. Run the full test suite once to establish a clean baseline. Surface any failures and stop until resolved.
2. Apply the [Model policy](#model-policy): this is the implementation boundary — prompt the user to switch to Sonnet for token efficiency and wait for confirmation (once per run).
3. **Write the iteration context file** — generate `autobot-<feature>-ctx-iter-0.md` per the [Iteration context files](#iteration-context-files) spec. Add the link to the autobot doc before handing off.
4. Proceed by mode:
   - *Reviewed:* Tell the user "Say 'Implement Phase 0.1' (or whichever phase) and I'll spawn a subagent for it. One phase at a time." Stop and wait — do not spawn until the user names a phase.
   - *Autonomous:* Spawn the subagent immediately per the [Autonomous mode](#mode-autonomous) spec. No user action needed — report back when done, then ask the user to complete the gate.
5. *"When done, complete the Manual Testing Gate and reply 'Iteration 0 confirmed', or describe what failed."*
6. Do not plan Iteration 1 until the gate is confirmed.

---

## Stage 5 — Gate review

When the user replies after a gate:

- **All confirmed:** tick boxes to `[x]`, set `**Confirmed by user:** <date>`, set `gate: confirmed`. Then propose a concise commit message (one imperative sentence, ≤72 chars, no title/body split) and ask: *"Commit this? I'll run `git commit -m \"<message>\"` for you."* Run it only if the user says yes. Proceed to Stage 6.
- **Any failed:** leave `gate: pending`, acknowledge, help fix, ask user to re-run and re-confirm.

This gate is mandatory. If the user tries to skip it, refuse and redirect. Never treat a gate as passed without writing it to the file.

---

## Stage 6 — Build Iteration N

After the previous gate is confirmed. Identical to Stage 3 + Stage 4: ask mode, write the context file, write any Reviewed plan, then hand off — Reviewed mode stops and waits, Autonomous mode spawns a subagent immediately. Repeat Stages 5–6 until every iteration is confirmed.

---

## Stage 7 — Feature complete

When the last iteration's gate is confirmed:
1. Run the full test suite — confirm no failures or regressions.
2. Set `stage: 7, gate: confirmed` and declare the feature done.
3. Delete all `autobot-<feature>-ctx-iter-*.md` files for this run — they were temporary scaffolding.
4. Propose a commit message and ask permission — same as Stage 5. Run it only if the user says yes.

---

## Suite-running policy

Run the full suite exactly twice: Stage 4 baseline and Stage 7 finish. Never run the full suite between iterations. During implementation, run only the current iteration's tests plus test files for any modules this iteration touched.
