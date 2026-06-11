# Autobot Beta — Iterative TDD Feature Builder (cost-optimized)

> **BETA.** Experimental, token-optimized variant of autobot. It differs from the stable skill only in [Model policy](#model-policy): the inline session runs Opus for design (Stage 1–2) then switches to Sonnet for building (Stage 3–7), and Reviewed-mode TDD plans are authored by an Opus subagent rather than inline. All other behavior is identical to autobot.

Given a feature description, autobot guides frontend design → backend design → iteration planning → iterative TDD implementation, with a mandatory manual testing gate between every iteration.

When invoked, announce **"I am using autobot-beta."** before anything else.

Immediately after the announcement, recommend the user run on **Opus High** for the design stages and wait for them to confirm before proceeding. At the Stage 2→3 boundary you will recommend switching the inline session to **Sonnet** for the build stages. See [Model policy](#model-policy).

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
- **Iteration context files are always generated.** Create every iteration's context file right after iteration titles are approved (Stage 2). It carries the iteration's full design and is the only context the implementer reads. See [Iteration context files](#iteration-context-files). The user is asked whether to delete each one after its iteration's gate is confirmed (Stage 5).

---

## File naming

All autobot files share one naming scheme. `<date>` is **always** today's date in `YYYY-MM-DD`, placed at the very end of the name. `<feature>` is a short kebab-case slug of the feature. `<iter-slug>` is a short kebab-case slug derived from the iteration's approved title (e.g. "Walking skeleton" → `walking-skeleton`).

| File | Pattern |
|------|---------|
| Main autobot document | `autobot-<feature>-<date>.md` |
| Iteration context file | `autobot-<feature>-ctx-iter-N-<iter-slug>-<date>.md` |
| Reviewed TDD plan file | `autobot-<feature>-plan-iter-N-<iter-slug>-<date>.md` |

- Capture `<date>` **once** when the main document is first created and reuse that same value for every file in the run — do not re-date later files to the day they happen to be written. This keeps a run's files grouped together.
- All three file types live in the same directory (`docs/` if it exists, else repo root), next to the main document.
- When this spec writes `autobot-<feature>-ctx-iter-N.md` or `...-plan-iter-N.md` in shorthand elsewhere, it means the full dated, slugged name above.

---

## Chat navigation footer

**After every interaction in an autobot run, end your message with a "📁 Autobot files" footer** linking the run's files so the user can jump to them instantly. Always include the main document; include the current iteration's context file (and plan file, if one exists) once they've been created. Use clickable markdown links relative to the workspace root.

```
---
📁 **Autobot files** · [main doc](<path-to-main>.md) · [iter N context](<path-to-ctx>.md) · [iter N plan](<path-to-plan>.md)
```

Omit links for files that don't exist yet (e.g. before Stage 2 there is only the main doc). This footer is required on every turn from the moment the main document exists until the run ends.

---

## Model policy

The inline model is **stage-aware** — Opus where design reasoning lives, Sonnet for the orchestration-heavy build tail. Every Opus-worthy build-time task is delegated to an Opus subagent, so the inline session never needs to be Opus after Stage 2.

| What | Model | Where |
|------|-------|-------|
| Stage 1–2 — design + iteration slicing | **Opus High** | inline |
| Stage 2→3 boundary | — | recommend switching inline to Sonnet (see below) |
| Stage 3–7 — orchestration, gates, commits | **Sonnet** | inline |
| Reviewed-mode TDD plan authoring | **Opus** | subagent (spawned by the Sonnet inline session) |
| Implementation (Reviewed phases & Autonomous) | **Sonnet** | subagent |

- **Stage 2→3 switch.** After the iteration plan is approved (`stage: 2`) and before building Iteration 0, recommend the user switch the inline session to **Sonnet** to save cost, and **wait for confirmation** before continuing. This is the one and only inline model switch in a run. Mirror the tone of the Opus recommendation at invocation.
- **Why this is safe.** No Opus-worthy work happens inline after Stage 2: design is done, plan authoring is delegated to an Opus subagent, and implementation is delegated to Sonnet subagents. The Sonnet inline session only orchestrates (spawns, copies ledgers, coordinates gates, applies small plan-review tweaks, writes commit messages).
- **Plan revisions.** When the user requests changes to a delegated Opus-authored plan after review, apply small tweaks **inline** (Sonnet) — only re-spawn an Opus subagent if the revision is a substantial re-design.

---

## Keeping context lean

Long autobot runs accumulate context. Apply these throughout:

- **Reviewed plans in separate files** — see the Conventions rule on plan files.
- **Iteration context files** — implementer agents read the lean context file for the current iteration instead of the full autobot doc. See [Iteration context files](#iteration-context-files).
- **Delegate implementation to Sonnet subagents** (see Model policy) — the heavy work happens in the subagent's context, not the inline session's.
- **Delegate Reviewed-mode plan authoring to an Opus subagent** (see Model policy) — the plan's full test + production code is written in the subagent's throwaway context and never accumulates in the inline session, which only sees "plan ready" and the file link.
- **Read narrowly.** When you only need one function, read its line range — not the whole file. Prefer search over speculative full-file reads.

---

## Iteration context files

A context file named `autobot-<feature>-ctx-iter-N-<iter-slug>-<date>.md` (see [File naming](#file-naming)) is created next to the autobot document for **every** iteration, immediately after iteration titles are approved (see [Stage 2 Step 2](#step-2--detail-each-iteration-after-title-approval)). This file is the **only context** the implementer needs — it must be fully self-contained, carrying the iteration's complete design.

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

## Design / pseudocode
<Per-file high-level pseudocode of what to build. No complete code. One block per file touched.>

#### `path/to/file.swift`
\`\`\`
<high-level pseudocode>
\`\`\`

## Diagrams
<Optional. Small mermaid diagrams — one concept each, 3–5 nodes. Only where a diagram adds something pseudocode cannot. Omit the section if none.>

## Relevant existing code
<Only the function signatures / type definitions this iteration actually calls or modifies. Paste snippets — do not ask the implementer to go hunt for them.>

## Constraints / invariants
<Any non-obvious rules from the backend design or prior iterations that apply here.>

## Done when (gate items)
- [ ] <exact gate item from the Manual Testing Gate for this iteration>
- [ ] ...

## TDD mode: <Reviewed | Autonomous>
<Set when the iteration is built (Stage 3/6), not at creation time.
Reviewed: "Implement phase by phase — Phase N.1, N.2, … See [plan file](autobot-<feature>-plan-iter-N-<iter-slug>-<date>.md)."
Autonomous: "TDD directly. Keep the ledger below as you go.">
```

Rules:
- Paste the relevant code snippets directly into the file — the implementer must not need to open other files just to understand the context.
- Link every existing file/function reference (relative to this context file's location).
- Keep it short. If a section is empty, omit it.
- The iteration's block in the main doc links to this file (added at Stage 2): `**Context file:** [Iteration N context](autobot-<feature>-ctx-iter-N-<iter-slug>-<date>.md)`

---

## Document status block

When you first create the main autobot document, name it `autobot-<feature>-<date>.md` (see [File naming](#file-naming)) in `docs/` if it exists, else the repo root. **Capture `<date>` (today, `YYYY-MM-DD`) now and reuse that exact value for every file in this run** — context files and plan files all carry the run's original date, not the date they happen to be written.

The autobot document starts with this block. It is the single source of truth for resume.

```
<!-- autobot-status
stage: 1
iteration: -
gate: none
updated: <date>
-->
```

Update it at every state change. `gate: confirmed` only when user confirmation is recorded.

**Mode is not tracked here.** Build mode (Reviewed/Autonomous) is chosen fresh for every iteration and recorded only in that iteration's context file `## TDD mode` line (see [Iteration context files](#iteration-context-files)). There is deliberately no global `mode:` field — the mode of one iteration must never carry over to the next.

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

The full design for each iteration lives in its **context file**, not inline in the main doc. As soon as titles are approved, **create every iteration's context file** (`autobot-<feature>-ctx-iter-N-<iter-slug>-<date>.md`, see [File naming](#file-naming)) per the [Iteration context files](#iteration-context-files) spec — carrying tests, files, design/pseudocode, diagrams, constraints, and the gate items. Leave the `## TDD mode` line as a placeholder; it's set when the iteration is built.

In the **main doc**, each iteration keeps only its title, a link to its context file, and its Manual Testing Gate (the gate is ticked here at Stage 5):

```
### Iteration N — <Title>
**Context file:** [Iteration N context](autobot-<feature>-ctx-iter-N-<iter-slug>-<date>.md)

## ✋ Manual Testing Gate — Iteration N

> STOP. Do not proceed to Iteration N+1 until every item is confirmed.

- [ ] <Exact action to take>
- [ ] <Exact thing to observe>
- [ ] <Edge / error / empty case>
- [ ] <Regression: prior iteration behaviour still works>   # required from Iteration 1 on

**Confirmed by user:** —
**How to confirm:** Check every box, then reply "Iteration N confirmed" or describe what failed.
```

Rules (apply to the context file's design content):
- Tests come first — they tell the user what this iteration proves before showing how.
- Pseudocode is high-level. No implementation detail, no complete code.
- Mermaid diagrams are small and focused. Many small ones, never one large one.
- In single-repo features, frontend and backend files are interleaved naturally with no sub-headings. In multi-repo features, group files under their repo name — but still interleave front/back within each repo group.
- Gate items must be specific, observable, and complete. From Iteration 1 on, derive regression items mechanically from prior gates' observable-result lines. The gate lives in the main doc and is mirrored into the context file's "Done when".

Before writing each context file, scan every file/function/class reference and confirm each existing one is linked (relative to the context file's location).

Present all the context files (and the main-doc gates) together after title approval. Stop and ask: *"Does this plan look right? Any changes before we start Iteration 0?"* If the user requests changes, edit the relevant context file directly.

Set `stage: 2, iteration: 0` on approval.

**Recommend the Stage 2→3 model switch now.** Design and slicing are done; everything from here is orchestration plus delegated subagent work. Tell the user: *"Design is locked. I recommend switching the inline session to **Sonnet** now to cut cost for the build stages — Opus-worthy work (plan authoring) is delegated to Opus subagents, so building stays high-quality. Switch when ready, then say 'continue'."* Wait for confirmation before starting Iteration 0. See [Model policy](#model-policy).

---

## Stage 3 — Build Iteration 0

Pick up here for Iteration 0. **Stage 6 is identical for Iteration N.**

### Choose a mode

**Always ask this for every iteration — never reuse the previous iteration's mode.** The mode chosen for Iteration N-1 has no bearing on Iteration N; prompt again every single time.

Ask the user:

> "How should I build this iteration?
> - **Reviewed** — I write the full TDD plan (tests + production code) to a separate plan file for your review, then implement phase by phase.
> - **Autonomous** — I TDD this directly without an upfront plan."

Record the answer in **this iteration's context file** (`autobot-<feature>-ctx-iter-N-<iter-slug>-<date>.md`) on its `## TDD mode` line — this is the only place mode is stored. Do not write it to the status block.

Before writing anything, detect the project's primary language and test framework from existing source.

---

### Mode: Reviewed

Write the plan to **its own file**, not the main autobot doc. Name it next to the autobot document: `autobot-<feature>-plan-iter-N-<iter-slug>-<date>.md` (see [File naming](#file-naming)). Then add a link to it under the iteration's existing block in the main doc (alongside its context-file link):

```
### Iteration N — <Title>
**Context file:** [Iteration N context](autobot-<feature>-ctx-iter-N-<iter-slug>-<date>.md)
**Reviewed plan:** [Iteration N plan](autobot-<feature>-plan-iter-N-<iter-slug>-<date>.md)
```

**Delegate plan authoring to an Opus subagent.** The Sonnet inline session does **not** write the plan itself — it spawns an Opus subagent that breaks the iteration into the smallest independently-testable phases and writes the full plan to the plan file. If the Agent tool is available (Claude Code), call it with these exact parameters — do NOT omit `model`:
```
Agent(
  description: "Author Reviewed TDD plan — Iteration N — <title>",
  model: "opus",
  prompt: "<the prompt below>"
)
```
Otherwise, spawn a subagent using whatever mechanism is available, preferring Opus if the model can be specified.

The plan-authoring subagent prompt is:
```
Read <path-to-ctx-iter-N.md> for full iteration context. Author a Reviewed-mode TDD plan and write it to <path-to-plan-iter-N.md> (create the file). Break the iteration into the smallest independently-testable phases. For each phase append this exact block:

### Phase N.M — <Name>
**What it covers:** One sentence.
**Files touched:** Bullets — link existing files with markdown relative to the plan file's location; name new files unlinked.
**Tests (Red):**
```
<complete test code for review>
```
**Production code (Green):**
```
<complete implementation for review>
```
**Done when:** Observable acceptance criteria.

Rules: strict TDD (a failing test must exist before its production code); test names are plain behavioural English with no phase/iteration numbers; high-level pseudocode is NOT enough here — write complete, reviewable test and production code. Before finishing, scan every file/function/class reference and confirm each existing one is linked relative to the plan file's location. Do not implement anything or run tests — only write the plan file. When done, report back: the plan file path and the list of phases with their names.
```

Do not include any other context in the spawn prompt — the context file is sufficient.

When the subagent returns, add the plan-file link to the iteration block in the main doc (the `**Reviewed plan:**` line above) if not already present, and tell the user the plan is ready for review at the plan file.

Show and stop — implement nothing until the user approves the plan. If the user requests small changes, apply them inline (Sonnet); only re-spawn an Opus subagent for a substantial re-design (see [Model policy](#model-policy)). Handoff happens at [Stage 4](#stage-4--hand-off-iteration-0); the user drives it one phase at a time.

**Spawning a phase** (Stage 4 directs you here when the user says "Implement Phase N.M"). If the Agent tool is available (Claude Code), call it with these exact parameters — do NOT omit `model`:
```
Agent(
  description: "Implement Phase N.M — <phase name>",
  model: "sonnet",
  prompt: "<the prompt below>"
)
```
Otherwise, spawn a subagent using whatever mechanism is available, preferring Sonnet 4.6 if the model can be specified.

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

Handoff happens at [Stage 4](#stage-4--hand-off-iteration-0), which spawns the subagent for the whole iteration in one shot.

**Spawning the iteration** (Stage 4 directs you here). If the Agent tool is available (Claude Code), call it with these exact parameters — do NOT omit `model`:
```
Agent(
  description: "TDD Iteration N — <title>",
  model: "sonnet",
  prompt: "<the prompt below>"
)
```
Otherwise, spawn a subagent using whatever mechanism is available, preferring Sonnet 4.6 if the model can be specified.

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

## Stage 4 — Hand off Iteration 0

1. Run the full test suite once to establish a clean baseline. Surface any failures and stop until resolved.
2. Set the iteration context file's `## TDD mode` line to the mode just chosen (the file already exists from Stage 2). If Reviewed, also link the plan file there.
3. Hand off by mode:
   - *Reviewed:* Tell the user "Say 'Implement Phase 0.1' (or whichever phase) and I'll spawn a subagent for it. One phase at a time." Stop and wait — do not spawn until the user names a phase. When they do, spawn per [Reviewed mode](#mode-reviewed).
   - *Autonomous:* Spawn the subagent immediately per [Autonomous mode](#mode-autonomous). No user action needed.
4. When the work returns, present the ledger and say: *"Complete the Manual Testing Gate and reply 'Iteration 0 confirmed', or describe what failed."*
5. Do not plan Iteration 1 until the gate is confirmed.

---

## Stage 5 — Gate review

When the user replies after a gate:

- **All confirmed:** tick boxes to `[x]`, set `**Confirmed by user:** <date>`, set `gate: confirmed`. Then:
  1. Ask: *"Delete this iteration's context file (name its actual `autobot-<feature>-ctx-iter-N-<iter-slug>-<date>.md`)? It's served its purpose."* Delete only if yes.
  2. If a Reviewed TDD plan file was generated for this iteration, separately ask: *"Delete the TDD plan file (name its actual `autobot-<feature>-plan-iter-N-<iter-slug>-<date>.md`) too?"* Delete only if yes.
  3. Propose a concise commit message (one imperative sentence, ≤72 chars, no title/body split) and ask: *"Commit this? I'll run `git commit -m \"<message>\"` for you."* Run it only if the user says yes. Proceed to Stage 6.
- **Any failed:** leave `gate: pending`, acknowledge, help fix, ask user to re-run and re-confirm.

This gate is mandatory. If the user tries to skip it, refuse and redirect. Never treat a gate as passed without writing it to the file.

---

## Stage 6 — Build Iteration N

After the previous gate is confirmed. Identical to Stage 3 + Stage 4: **ask mode again** (always re-prompt — never assume the previous iteration's mode carries over), set the `## TDD mode` line in this iteration's already-created context file, write any Reviewed plan, then hand off — Reviewed mode stops and waits, Autonomous mode spawns a subagent immediately. Repeat Stages 5–6 until every iteration is confirmed.

---

## Stage 7 — Feature complete

When the last iteration's gate is confirmed:
1. Run the full test suite — confirm no failures or regressions.
2. Set `stage: 7, gate: confirmed` and declare the feature done.
3. Context and TDD plan files are cleaned up per-iteration at Stage 5. If any remain (the user kept some), ask once whether to delete the leftovers now.
4. Propose a commit message and ask permission — same as Stage 5. Run it only if the user says yes.

---

## Suite-running policy

Run the full suite exactly twice: Stage 4 baseline and Stage 7 finish. Never run the full suite between iterations. During implementation, run only the current iteration's tests plus test files for any modules this iteration touched.
