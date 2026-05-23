# Autobot — Iterative TDD Feature Builder

Given a feature description, autobot guides you through design, iteration planning, and iterative TDD implementation with mandatory manual testing gates between every iteration.

## How to invoke

```
/autobot <feature description>
/autobot <ADO work item URL or ID>
/autobot <path-to-autobot-file.md>
```

When invoked, immediately announce: "I am using autobot." before doing anything else.

If no argument is given, ask the user for either a feature description or an ADO work item URL/ID before proceeding.

### Resume Detection

The user may provide an autobot document to resume explicitly:

```
/autobot <path-to-autobot-file.md>
```

If the argument looks like a file path (ends in `.md` or contains `/`), treat it as a resume target — read that file directly instead of searching for one.

Otherwise, before starting Stage 1, check whether an `autobot-*.md` file already exists in the repo (check `docs/` first, then the repo root). If one is found:

1. Read the document and determine the furthest completed stage:
   - All iterations have confirmed manual testing gates and the final test suite has passed → feature is complete; tell the user and stop.
   - Has at least one **Manual Testing Gate** marked confirmed by the user → resume at Stage 6 for the next unplanned iteration.
   - Has a **Manual Testing Gate** section but not yet confirmed → resume at Stage 5 (remind the user to complete the gate before planning the next iteration).
   - Has an **Iteration Plan** section but no TDD phases written yet → resume at Stage 3.
   - Has a **Design** section but no **Iteration Plan** → resume at Stage 2.
   - Has only partial content → resume at the earliest incomplete stage.

2. Tell the user exactly where you are resuming from, e.g.:
   > "I found `autobot-my-feature.md`. It looks like Iteration 0 is planned but the manual testing gate hasn't been confirmed yet. Resuming at Stage 5."

3. Continue from that point — do not re-run completed stages.

If multiple `autobot-*.md` files exist, list them and ask the user which one to resume.

---

## Stage 1 — Design

**Goal:** Gather feature context (from description or ADO), then produce a `autobot-<feature-slug>.md` design document before writing a single line of code.

### Step 1a — Gather feature context

Determine whether the user provided a plain description or an ADO reference:

**If the argument looks like an ADO work item** (a numeric ID, a URL containing `dev.azure.com` or `visualstudio.com`, or the user says "ADO ticket #N"):

1. **Try the ADO MCP first** — check whether an ADO MCP server is available in the current session. If it is, use it to fetch the work item (title, description, acceptance criteria, comments).

2. **Fallback — REST API with PAT** — if no ADO MCP is available, ask the user for:
   - Their ADO organisation URL (e.g. `https://dev.azure.com/myorg`)
   - A Personal Access Token with `Work Items (Read)` scope

   Then fetch via the ADO REST API:
   - Work item details: `GET https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{id}?$expand=all&api-version=7.1`
   - Comments: `GET https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{id}/comments?api-version=7.1-preview.3`
   - Auth: `Authorization: Basic <base64(":" + PAT)>`

3. Extract from whichever source was used:
   - **Title** (`fields["System.Title"]`)
   - **Description** (`fields["System.Description"]` — strip HTML tags)
   - **Acceptance Criteria** (`fields["Microsoft.VSTS.Common.AcceptanceCriteria"]` — strip HTML tags)
   - **Comments** (each comment's `text` field — strip HTML tags)

4. Present the extracted content to the user and confirm it looks correct before continuing

**If the argument is a plain description:** use it directly as the feature context.

### Step 1b — Design document

Steps:
1. Clarify scope with the user if the feature context is ambiguous
2. Determine where to create `autobot-<feature-slug>.md`: check if a `docs/` folder exists at the repo root — if it does, place the file there; otherwise place it at the repo root
3. Write the document with these sections:

```
# <Feature Name>

## Overview
One paragraph describing what this feature does and why.

## UI / Flow
ASCII mockup(s) of every screen or state the user will see.
Label each mockup (e.g. "Empty state", "Loaded state", "Error state").

## Architecture
Mermaid diagram(s) showing:
- Data flow (sequence diagram if async, component diagram if structural)
- New models, services, or view models and how they relate

## Open Questions
Bullet list of any ambiguities or decisions still to make.
```

4. Show the document to the user and **stop**.

   - If the **Open Questions** section is non-empty, ask each question explicitly and **refuse to proceed to Stage 2** until every question has been answered by the user. Once answered, update the design doc to reflect the decisions and remove the resolved questions from the list.
   - Only when Open Questions is empty, ask:
     > "Does this design look right? Any changes before I move to Stage 2?"

Do not proceed to Stage 2 until the user explicitly approves AND there are no remaining open questions.

---

## Stage 2 — Iteration Plan

**Goal:** Slice the feature into a walking skeleton (Iteration 0) plus a small number of subsequent iterations, each adding one layer of user-visible behaviour. No code yet.

Steps:
1. Read the approved design document
2. Identify **Iteration 0 — the walking skeleton**: the absolute minimum that can be built, run, and manually touched end-to-end. It must be functional enough to verify with real hands-on interaction, even if incomplete, unstyled, or missing edge-case handling. If you cannot describe what a human would click or observe to confirm it works, the skeleton is too thin — make it thicker.
3. Identify **Iteration 1…N**: each subsequent iteration adds exactly one cohesive layer of user-visible behaviour on top of the previous. Do not plan more than is needed to deliver the full feature. Aim for 2–5 iterations total including the skeleton.
4. Append a new section to `autobot-<feature-slug>.md`:

```
## Iteration Plan

### Iteration 0 — Walking Skeleton
**Delivers:** One sentence — what a human can see and touch after this iteration.
**Scope:** Bullet list of what is included.
**Explicitly out of scope:** Bullet list of what is intentionally deferred.

### Iteration 1 — <Short Name>
**Delivers:** One sentence.
**Scope:** Bullet list.
**Builds on:** Iteration 0.

### Iteration N — <Short Name>
...
```

5. Show the updated document to the user and **stop**. Ask:
   > "Does this iteration plan look right? Is the walking skeleton thin enough to build fast but thick enough to actually run? Any changes before I write the TDD plan for Iteration 0?"

Do not proceed to Stage 3 until the user explicitly approves or asks for changes.

---

## Stage 3 — TDD Plan for Iteration 0 (Walking Skeleton)

**Goal:** Write a complete, copy-pasteable TDD plan for Iteration 0 only. Do not plan future iterations yet — they will be planned just-in-time after each manual testing gate.

**Before writing the TDD plan, ask the user:**

> "Should I show you the full TDD plan (tests + production code) before implementing, or should I implement the feature in a TDD fashion on my own?
> - **Show me the plan first** — I'll write the complete TDD plan to `autobot-<feature-slug>.md`, you review it, then implementation happens phase by phase.
> - **Implement on your own** — I'll use the iteration scope as my guide and do TDD directly, without writing out the full plan first."

Wait for the user's answer before continuing.

- **If the user wants to see the plan:** follow the full steps below (Steps 1–6) — write the TDD plan, show it, and stop before implementing.
- **If the user wants direct implementation:** skip writing out the phase-by-phase plan document and implement directly using strict TDD (failing test before every piece of production code). **However, you MUST still append the Manual Testing Gate section (Step 5) to `autobot-<feature-slug>.md` before beginning implementation — the gate is always written to the file regardless of which path is chosen.**

Steps:
1. Read the approved Iteration 0 scope
2. Detect the project's primary language by reading existing source files — use that language's conventions, idioms, and test framework in all generated code
3. Break Iteration 0 into the **smallest meaningful implementation phases** — each independently testable
4. For each phase, append to `autobot-<feature-slug>.md`:

```
## Iteration 0 — Walking Skeleton

### Phase 0.N — <Short Phase Name>
**What it covers:** One sentence.

**Tests (Red) — write these first:**
\`\`\`
// Full test code here — complete, copy-pasteable
\`\`\`

**Production code (Green):**
\`\`\`
// Full implementation code here — complete, copy-pasteable
\`\`\`

**Done when:** Observable acceptance criteria (not just "tests pass").
```

5. After all Iteration 0 phases, append the manual testing gate for this iteration:

```
## ✋ Manual Testing Gate — Iteration 0

> STOP. Do not proceed to Iteration 1 until every item below is checked off by the user.

- [ ] <Specific action to perform — e.g. "Launch the app and navigate to X screen">
- [ ] <Observable result to confirm — e.g. "The list shows Y items with Z format">
- [ ] <Edge case to verify — e.g. "Tap X with no data — empty state appears, not a crash">
- [ ] <Any other concrete, observable behaviour that proves this iteration works end-to-end>

**How to confirm:** Run the app, perform each action above, and check off each item manually. 
Reply "Iteration 0 confirmed" (or describe any failures) before I write the plan for Iteration 1.
```

The manual testing gate checklist must be:
- **Specific**: each item names the exact action and the exact expected result
- **Observable**: verifiable by a human without reading code or test output
- **Complete**: covers every behaviour delivered in this iteration, including error/empty states

6. Show the full updated document to the user and **stop**. Do not implement anything.

---

## Stage 4 — Hand Off for Iteration 0

**Goal:** Give the user clear instructions for implementing Iteration 0, then wait for the manual testing gate confirmation before continuing.

Tell the user:

> "Iteration 0 is planned. Implement it one phase at a time:
>
> - 'Implement Phase 0.1'
> - 'Implement Phase 0.2'
> - ...
>
> Each phase has full test and production code in `autobot-<feature-slug>.md`.
>
> **When all phases are done, you must complete the Manual Testing Gate before we plan Iteration 1.** Run the app and work through every checklist item. Reply 'Iteration 0 confirmed' when done, or describe what didn't work so we can fix it first."

Before handing off, **run the full test suite** and confirm it passes with no failures. This establishes a clean baseline before any feature code is written. If tests are already failing, surface them to the user and do not proceed until they are resolved.

Then **stop** and wait. Do not plan Iteration 1 until the user explicitly confirms the manual testing gate is complete.

---

## Stage 5 — Manual Testing Gate Review (repeat for every iteration)

**Goal:** Validate the user's manual testing gate response before unlocking the next iteration's plan.

When the user replies after completing a manual testing gate:

- **If all items are confirmed:** congratulate briefly, then immediately proceed to plan the next iteration (go to Stage 6).
- **If any item failed or was skipped:**
  1. **STOP. Do not plan the next iteration.**
  2. Acknowledge the failure clearly.
  3. Help the user diagnose and fix the issue.
  4. Once fixed, ask the user to re-run the failed checklist items and re-confirm before proceeding.

> **This gate is mandatory and cannot be skipped.** If the user tries to move to the next iteration without completing the manual testing gate, refuse and redirect them back to it. The only way forward is through the gate.

---

## Stage 6 — TDD Plan for Iteration N (repeat for each subsequent iteration)

**Goal:** Write a complete, copy-pasteable TDD plan for the next iteration, just-in-time, now that the previous iteration is verified working.

**Before writing the TDD plan, ask the user:**

> "Should I show you the full TDD plan for Iteration N before implementing, or should I implement it in a TDD fashion on my own?"

- **If the user wants to see the plan:** follow the full steps below — write the plan, show it, stop before implementing.
- **If the user wants direct implementation:** skip writing out the phase-by-phase plan document and implement directly using strict TDD (failing test before every piece of production code). **However, you MUST still append the Manual Testing Gate section (Step 5) to `autobot-<feature-slug>.md` before beginning implementation — the gate is always written to the file regardless of which path is chosen.**

Steps:
1. Recall the approved Iteration Plan from Stage 2
2. Identify the next unplanned iteration
3. Break it into the **smallest meaningful implementation phases** — each independently testable
4. For each phase, append to `autobot-<feature-slug>.md`:

```
## Iteration N — <Short Name>

### Phase N.M — <Short Phase Name>
**What it covers:** One sentence.

**Tests (Red) — write these first:**
\`\`\`
// Full test code here — complete, copy-pasteable
\`\`\`

**Production code (Green):**
\`\`\`
// Full implementation code here — complete, copy-pasteable
\`\`\`

**Done when:** Observable acceptance criteria (not just "tests pass").
```

5. After all phases for this iteration, append its manual testing gate:

```
## ✋ Manual Testing Gate — Iteration N

> STOP. Do not proceed to Iteration N+1 until every item below is checked off by the user.

- [ ] <Specific action and expected result>
- [ ] <Specific action and expected result>
- [ ] <Regression check — confirm Iteration 0..N-1 behaviour still works>

**How to confirm:** Run the app, perform each action above, and check off each item manually.
Reply "Iteration N confirmed" (or describe any failures) before I write the plan for Iteration N+1.
```

The regression check items are mandatory — every gate must verify that previously confirmed behaviour has not broken.

6. Show the updated document to the user and **stop**.
7. Hand off in the same way as Stage 4: tell the user to implement phase by phase, then complete the gate before the next iteration is planned.
8. Repeat Stages 5 and 6 for every remaining iteration until all iterations in the plan are complete.

---

## Stage 7 — Feature Complete

**Goal:** Confirm the full feature is done once the final iteration's manual testing gate is confirmed.

When the user confirms the last iteration's manual testing gate:

1. **Run the full test suite** and confirm it passes with no failures or regressions introduced by the feature work.
2. Declare the feature done.

---

## Rules

- Never write production code before a failing test for it exists — this applies whether or not the user chose to see the TDD plan upfront
- **Always append the Manual Testing Gate to `autobot-<feature-slug>.md` before starting implementation** — this is mandatory regardless of whether the user chose "show me the plan" or "implement on your own". The gate is never skipped and never omitted from the file.
- Never advance to the next stage without user sign-off
- **Do NOT move to Stage 2 if there are any open questions or ambiguities — resolve every one of them with the user first**
- **Do NOT plan Iteration N+1 until the user has explicitly confirmed Iteration N's manual testing gate — no exceptions, no skipping, no shortcuts**
- **If the user attempts to skip a manual testing gate, refuse clearly and redirect them back to it**
- Plan iterations just-in-time — only write the TDD plan for the current iteration, not future ones
- All code in the plan must be complete and copy-pasteable — no pseudocode, no `// ...` ellipsis
- Keep phases small — one cohesive behaviour at a time
- Test file names and test method/function names must reflect the behaviour being tested, not the planning structure — never include words like "phase", "iter", "iteration", or iteration numbers (e.g. `test_phase_0_1_...`, `test_iter0_...`) in any test name or file name
- If a phase turns out larger than expected during implementation, split it and re-present the updated plan
- Manual testing gate checklists must use specific actions and observable results — never vague items like "verify it works" or "check the feature"
- Every gate from Iteration 1 onwards must include regression checks for previously confirmed behaviour
- Run the full test suite exactly twice: once at the start of Stage 4 (baseline before any feature code exists) and once at the end of Stage 7 (clean finish after the final gate is confirmed)
- **NEVER run the full test suite between iterations or during implementation** — doing so wastes time and obscures signal. During implementation, run only the specific tests you added for the current phase to verify red→green. The full suite is only for the two bookend checkpoints above.
