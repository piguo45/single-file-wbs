# WBS Tool - CLAUDE.en.md

> **English translation of [`CLAUDE.md`](CLAUDE.md) (the Japanese original is the primary spec).**
> **Sync rule: whenever the spec changes, update `CLAUDE.md` and `CLAUDE.en.md` in the same commit.**

A text (JSON) driven WBS / Gantt + inazuma-line tool.
`wbs.json` (data) is the single source of truth; the self-contained single HTML `wbs_viewer.html` renders it.

---

## Product vision & design principles (#67)

> **A local WBS for the AI-era manager (PL / tech lead) leading a small, elite team that includes AI. Humans edit via the GUI; AI edits via raw JSON and `CLAUDE.md` — the same plan.**

- **Target user**: not the enterprise PM of huge projects, but a **manager (PL / tech lead) leading a ~10-person elite team that includes AI**. The author is this persona (dogfooding).
- **Vision (a bet, owned as such)**: as AI rises, small elite teams wielding AI become the norm, and **everyone becomes a PL/TL**. This tool is for that lead (human **and** PL/TL agent) to manage the plan. It is a bet on the future, but hedged — even if it misses, it already helps today's leads.
- **Core differentiator = two first-class interfaces**: human = GUI / AI = raw JSON + the AI-readable `CLAUDE.md`. **Both are first-class.** Every feature works via both the GUI path and the AI/JSON path (custom keys preserved, round-trip).
- **`CLAUDE.md` is not "documentation" but "the AI's API spec"**: because AI depends on the format, **the schema is kept almost frozen**.
- **Build**: AI-native (progress assessment, dependency inference) / honest views (true state, not vanity) / load by assignee (human vs AI) / cost (`_ai` tokens, `_money`).
- **Don't build**: enterprise PM (portfolios, complex permissions) / large-scale real-time collaboration / heavy workflow engines / approval flows.
- Background essay (Japanese) → [WBSという至高ツールで、このAI時代をサバイブする](https://zenn.dev/piguolabo/articles/99b5b30a028f80)

---

## Handling principles (important)

- **Do not touch `wbs_viewer.html` (the viewer) as a rule.** The view logic is complete.
- **Changes mean editing `wbs.json` (data) only.** When asking an AI to do work, it should edit the JSON.
  - Touch the HTML only when the display spec itself must change (and only on explicit request).

## Archiving (pruning past tasks)

To keep the file from growing forever, **move old completed tasks out of the current file**:

- **Trigger**: when completed tasks from past months (e.g., May 2026 and earlier) have scrolled into the past on the Gantt.
- **Steps**:
  1. **Create a backup in the same folder** (e.g., collect the moved tasks into `wbs-archive-2026-05.json`).
  2. **Delete those completed tasks** from `wbs.json`.
- → The current `wbs.json` stays focused on "now and the future"; history is preserved in archive JSONs.
- Scale is managed in two layers: **collapsing (display) + this archiving (data)**.

---

## Requirements
- **Google Chrome (latest) recommended**. **Chromium-based browsers (e.g., Edge) work too** (testing is done on Chrome). Firefox/Safari are not supported (no File System Access API).
- On corporate-managed browsers, editing is unavailable if File System Access is disabled by policy (viewing still works).
- No HTTP server, no external libraries / CDN. Open `wbs_viewer.html` **directly via file://**.

## Opening / reloading
1. Open `wbs_viewer.html` in Chrome.
2. Pick `wbs.json` via **Open file** (or **drag & drop** onto that same button).
3. Edit `wbs.json` and save → press **Reload** to re-read and re-render (no re-selection needed / File System Access API).
4. Collapsing: click a **◆project / L1 / L2 `▼/▶`–name**.
   The **`▼/▶` in the Task column header** expands/collapses everything (▼ = all open → click collapses all; ▶ = something closed → click expands all).
   An accidental header action can be **restored with Ctrl+Z** (inactive while an input has focus).
5. Scroll position is **preserved across collapsing and reloads**; **only loading a new file re-centers on today and resets collapse state**.

## In-browser editing (edit mode)
In addition to text / AI editing, `wbs.json` can be **edited directly on screen** (optional feature).
- The **Edit button** toggles ON/OFF (green = ON). When ON, the left table becomes inputs + action buttons.
- Supported: **inline editing of every field** (No.=id / task name / qty / hours / assignee / plan & actual dates / notes),
  **progress input** (the leaf's `◀ N% ▶` stepper changes `_progress` by ±10%; setting ≥10% auto-sets `actual.start` to today / returning to 0% keeps the start date),
  **adding leaves** (row `＋` = sibling below; project row `+Task`; ids are minted collision-free; adding to a collapsed project auto-expands it),
  **nesting (add a child task)** (row `＋子`/`+sub`: on a leaf it **becomes a summary node** carrying its values into child 1 = effort/progress unchanged; on a summary it appends a blank child; child id = parent id + suffix; **not shown on the 3rd level** = no 4th level),
  **deletion** (`✕`, with confirmation, including children; **deleting the last child of a summary returns that child's values to the parent and demotes it to a leaf** = effort is never lost), **reordering among siblings** (`▲▼`).
- **Autosave**: changes are written back to `wbs.json` after a ~0.4 s debounce (File System Access API).
  Writes are serialized through a single queue. Only the internal derived values `_calc`/`_leaf` are stripped (**user keys starting with `_` are preserved**).
  Save status (Unsaved changes… / Saved HH:MM:SS / Save failed) is **always visible at the top right**.
- **External-change detection**: before each write the file's mtime is checked; if it changed outside the tool (e.g., AI editing), an **overwrite confirmation** is shown.
  When asking an AI to edit, it is safest to turn edit mode OFF first.
- **Auto-retry on interference**: when a sync client (OneDrive, etc.) or antivirus touches the file at the same instant as a save, the browser may reject the
  write with `InvalidStateError` ("state had changed since it was read from disk"). In that case the tool **waits a beat and retries the save once**
  (the retry's `getFile()` refreshes the browser's internal snapshot, which almost always recovers). The write is rejected *before* touching disk, so **the
  original file stays intact**. If the retry also fails, it shows "Save failed" and **keeps the dirty flag** (re-saved on the next edit or on tab close;
  it does not auto-retry in a loop, to avoid alert spam).
- Prerequisites: saving requires **write permission**. Only files opened with a handle (Open file or D&D) are editable.
  **file:// pages cannot show write-permission prompts**, so when turning Edit ON you **re-select the same wbs.json in a save dialog** (the selection itself grants permission).
  ⚠ Chrome **truncates the file the moment it is picked**, so the current data is **written immediately after selection** (never left empty — #29).
  If told to "press Edit again", do so (browser gesture limitation; the second click opens the dialog directly).
  The permission is **session-scoped** (after restarting Chrome, re-select once per Edit ON).
  **Loading a new file automatically turns edit mode OFF** (turn it ON again to grant permission for the new file). On a failed load the handle is not replaced (prevents overwriting the wrong file).
- **Legacy format** (`{project,tasks}`): on Edit ON, after confirmation it is **converted to the `projects[]` format** before editing.
- **Date cells are `YYYY-MM-DD` text inputs plus a 📅 calendar button**. `2026/07/01`-style input is accepted and normalized to `-`.
  (The display format of `input type=date` follows the browser UI language and cannot be controlled, so the display is fixed to ISO — #33.)
- Input guards: dates are **valid only within 1900–2099** (out-of-range / partial input is ignored, not saved). Qty / hours accept decimals (`step="any"`).
  Mouse-wheel changes on number inputs are disabled (prevents accidental edits). Closing the tab with unsaved changes prompts for confirmation.
- Out of scope (by design): drag-and-drop reordering / moving across parents / automatic renumbering / adding projects. Use JSON or AI editing for those.
  (leaf↔summary conversion is now handled in the GUI via `＋子`/deleting the last child = #70)
- Effort / progress / inazuma line recompute automatically as before (re-rendering is deferred while an input has focus).

## Data (wbs.json)
- **Multi-project**. Top level is `projects: [{ name, milestones, tasks }]`.
  - The legacy format (single `{ project, milestones, tasks }`) is **still readable** (backward compatible).
- Each project's `tasks` nest parent-child (max 3 levels). With `children` = summary node; without = leaf (carries effort).
- Leaf fields:
  ```
  id, name, qty, hours (per unit), assignee,
  plan:   { start, end }        planned, "YYYY-MM-DD"
  actual: { start, end }        actual (null if undecided)
  note
  _anyName                      "_"-prefixed = custom key (optional, ignored by viewer, preserved on save)
  ```
- **Effort and progress are not stored in the data** (all derived; computed by the JS in the HTML).
- **Keys starting with `_` may be added freely** (ignored by the viewer by default, preserved by edit-mode saves).
  Use them for metadata (e.g., `_ai` in `wbs_roadmap.json` = recorded AI effort in tokens; entirely optional. `wbs_sample.json` is the minimal example without custom keys).
- **Exception: `_progress` (0/10/…/100) is read by the viewer** as the progress value (EV), alongside `_progressAt` (assessment time, ISO) and
  `_progressBy` (`"manual"` or a model name). Asking an AI: "assess task X's progress to the nearest 10% from the deliverable and requirements"
  → it writes `_progress`/`_progressAt`/`_progressBy` on the leaf. If unset, progress falls back to time-based (backward compatible).
- `milestones: [{ date, label, color }]` is optional per project.

## Adding / updating data (how-to)

Edit `wbs.json` only. Save → press **Reload** in the viewer.

### ① Status updates (daily operation — most important)
Progress, effort, and the inazuma line are **computed automatically**. You only touch the **actual dates**:
- **Work started** → set `actual.start` on the leaf (→ the Actual-End column shows "active"; reflected in the inazuma line)
- **Work finished** → set `actual.end` (→ row turns gray with `✓`; the inazuma point sits on the today line)
- **Plan changed** → fix `plan.start` / `plan.end`

### ② Adding a task
Append a leaf to a summary node's `children`.
**Keep `name` a concise label (guideline: ~14 full-width chars; put details and context in `note`)** —
long names don't break anything but get truncated in the task column (full text on hover).
```json
{ "id": "2.1.3", "name": "New task", "qty": 1, "hours": 16, "assignee": "piguo",
  "plan":   { "start": "2026-07-01", "end": "2026-07-05" },
  "actual": { "start": null, "end": null }, "note": "" }
```
- To add an intermediate phase, add a **summary node** with `children` and put leaves under it (max 3 levels).

### ③ Adding a project
Append to the `projects` array:
```json
{ "name": "New project", "milestones": [],
  "tasks": [ { "id": "1", "name": "Phase 1", "children": [ /* leaves… */ ] } ] }
```

### ④ Adding a milestone
Append to the project's `milestones`:
```json
{ "date": "2026-09-30", "label": "Release", "color": "#ef4444" }
```

### ⑤ Example requests to an AI (have it edit the JSON)
- "Mark the design review as **completed today**" → set `actual.end` of that leaf to today
- "Component placement has **started**" → set `actual.start`
- "**Add** a testing phase" → append a summary node + leaves
- "**Archive** everything completed before May" → archiving procedure above (backup + delete)
- "**Assess** the progress of task X" → see "AI progress assessment" below (deliverable + requirements → nearest 10% into `_progress`)

### ⑥ AI progress-assessment workflow (this tool's core = AI-native)
Hand the fuzzy "roughly what %" to an AI. The steps are deterministic:
1. **Read the leaf's requirements** (issue URL / acceptance criteria in `note`, related commits/deliverables).
2. **Compare deliverable vs. requirements** and estimate completion, **quantized to the nearest 10% (0/10/…/100)** (don't over-credit; don't count unverified work).
3. Write three keys on the leaf: `_progress` (the value) / `_progressAt` (assessment time, ISO) / `_progressBy` (the assessing model's name, or `"manual"` for a human).
4. **Done is separate**: when actually finished, set `actual.end` (= 100%) rather than `_progress`. `_progress` is only an in-progress earned-value estimate.
- Example: "Assess #63's progress from the deliverable (impl/tests/docs) and acceptance criteria, to the nearest 10%."
- Note: an assessment is a **recorded fact** (a person/AI judgment at that moment); it is not recomputed, hence a `_`-key — consistent with "no derived values in data."

## Computation (deterministic, in the HTML)
- **Effort (person-days) = `qty × hours ÷ 8`**. Parent = sum of descendant leaves.
- Parent plan/actual period = min start – max end of descendant leaves.
- Progress (EV = earned value / reference date = today):
  - Not started (no actual.start) = 0% / Completed (actual.end set) = 100%
  - Active = **if `_progress` (0/10/…/100) is present, quantize to the nearest 10% and use it**; otherwise fall back to the
    time-based `clamp((today − actual.start) ÷ (plan.end − plan.start) × 100, 0, 100)` (backward compatible).
  - Parent = effort-weighted average of descendant leaves' (progress × effort) (continuous; not snapped).
- **EVM values**: EV = actual progress / **PV = planned** = what should be done by today `clamp((today−plan.start)/(plan.end−plan.start)×100,0,100)` (linear; parents weighted) /
  **slip = behind = max(PV−EV,0)** (≈ EVM SV). S-curve, non-linear PV, and a cost axis are out of scope (not done).
- **Header summary (right, #71)**: **Period** (earliest start–latest end / weekdays left, excl. weekends) / **Effort**
  (person-months = person-days ÷ 20 working days / remaining) / **Progress** (actual EV% / planned PV% / behind = max(PV−EV,0)%),
  in three rows plus a meta line (📄 filename · N projects · 📅 today · 🔄 refreshed · 💾 saved). Each row has a hover tooltip.
- **Delay badges (4th summary line "Behind:")**: the overall behind% is textbook EVM (ahead-work offsets it, so it can read 0%);
  to avoid missing slippage, the **count of tasks behind** is shown as badges (**Due** = past planned end & not done / **EV** = PV>EV).
  A badge whose count is 0 is hidden; if both are 0 the whole line is hidden.
- **Progress column = `◀ N% ▶` stepper** (10% steps; editable on leaves only / parents show the auto-aggregate read-only, continuous). `_progress` is not a derived value but
  "a person's/AI's judgment at a point in time", so it is stored as a `_` key (never recomputed) — consistent with the "no derived values in data" rule.
- **Status column = behind / actual / planned** (slip / EV / PV, %). Behind=red, actual=blue, planned=black. **On-track rows show actual only** (quiet). No mental math (the delay is pre-computed).
- **Planned-end turns red** when today > plan end and not done (deadline overrun; done rows are not reddened). Same "red = behind" as the time tab's Gantt/inazuma.
- **The right pane toggles between "Time / Progress" tabs** (default = Time). Time = the Gantt (unchanged) / Progress = horizontal completion bars (blue=actual / red=shortfall to plan, whose right edge = planned PV / thick=leaf, thin=parent summary, same sizes as the time view).
  Only the active view is injected into the DOM (render cost = one view). The tab choice is remembered in localStorage.
- **Telling the Progress view apart from Time**: (1) **square-cornered bars** (Time = rounded; distinguished by shape, CUD-safe) (2) a **blue-grey unfilled track** (`#eef1f7`, 0–100%) (3) **ruler-style ticks** =
  major (full-height dotted at 20/40/60/80%, `#555`) + minor (short solid from the top edge down ~60%, every 10%, same `#555`, drawn in front of the bars). Axis labels are 0/20/40/60/80/100%.

## Display
- **UI is Japanese/English switchable** (the "EN / 日本語" toolbar button). Default Japanese; the choice is stored in localStorage.
- **Plain-branding toggle (#79)**: clicking the **title (logo / "WBS Viewer") at the top-left** hides the logo, version, "Viewer" and the tab title, leaving just **"WBS"** (click again to restore; remembered in localStorage). It strips the product look so the tool can pass as "self-made" on locked-down client sites. No tooltip is added (to keep it undiscoverable).
  All UI strings live in the `I18N` table inside the HTML (data = the contents of wbs.json is never translated). **When adding a UI string, add it to both ja and en.**
- Column headers are centered. The left info table (No.–Notes) is fixed; **only the Gantt scrolls horizontally**.
- **Column collapse (outline-style, #64)**: a thin row above the column headers holds **+/−** toggles per **collapsible unit** —
  `qty+hours` (the breakdown of effort), Effort, Progress, Status, Assignee, Plan, Actual, Notes (**No. and Task name are always shown**).
  Collapsed columns are **removed at 0 width (no leftover gap stub)**, the + sits at the boundary (absolute). State is
  saved in localStorage; scroll/tree-collapse are preserved; collapsing widens the Gantt. Implemented via the `COL_CG` map + `effCols()` filter (draw cost = column count, not row-dependent).
- **Plan/Actual date columns have a two-level header**: "Plan" / "Actual" on top, "Start / End" beneath (adjacent columns grouped by the `group` property in `COLS`).
- Row layer colors: **◆project (with separators) > L1 > L2 > L3**.
- Gantt: date + weekday (year-month header), weekends shaded; active tasks extend the actual bar to today.
  **Plan = unfilled outline (front, 4 sides) / actual = filled bar (behind), overlaid in the same lane** (#65):
  the actual sticking past the outline's right = **finish delay = red bar + "+N"** (number only; always placed at the bar tip; exact value in the tooltip "Finish delay +N d"),
  empty space at the outline's left = **start delay** (actual start is right of the outline's left) — shown by the gap, no dedicated color.
  Because delays are color-coded (red = finish delay, gray = done), the outline + fill is not misread as a progress bar.
- **Parent (aggregate) = thin summary bar**: both plan outline and actual are thin (parent vs leaf by shape, not extra color = CUD-safe, keeps all info when collapsed).
  The actual's fill ratio matches leaves. **Bar color is identical across all levels** (parent vs leaf distinguished by bar thickness/shape, not hue or lightness).
- **Colors (CUD-aware, #35)**: actual = blue / plan = blue outline / finish delay & inazuma = red (vivid while active / muted when done) / done = gray bar.
  Start delay uses no color — just the empty outline. Following the Okabe-Ito principle we avoid "blue vs purple" (milestone default = mauve `#cc79a7`) and never rely on color alone (shape, position, labels add redundancy).
  Verified by `tests/e2e/test_color_audit.py` (add the pair and re-run whenever you add/change a color).
- Date columns show `5/11` style. Initial view centers near today.
- **Completed tasks**: darker gray row + strikethrough + leading `✓`. The gantt actual bar is **gray** too (blue = active / gray = done at a glance).
- **URLs inside notes are auto-linked** (`http(s)://` only, opens in a new tab). Put plain URLs in `note` to jump to issues or specs.
- Overlay (SVG):
  - **Inazuma line** (red, **one line across all projects**). Each terminal row's point is placed as follows (**bulging left = behind schedule**):
    - Completed = on the today line
    - **Deadline overrun** (started, unfinished, today > `plan.end`) = at the **planned end date** (overrun takes priority)
    - **Start delay** (not started, today > `plan.start`) = at the **planned start date**
    - Active (within deadline) = on the today line (start drift is not shown)
    - Everything else (not started, not yet due, etc.) = on the today line
    - A collapsed node contributes a single aggregated point. No explicit today line is drawn (today is the reference).
  - **Milestone lines** (per-project `milestones`, arbitrary color; **default = Okabe-Ito mauve `#cc79a7`**).

## Broken input (graceful degradation)

**Policy: broken input must never crash the viewer.** Invalid values render as ignored / 0 / empty.
Avoid the following when entering data (nothing crashes, but display degrades).

| Input (anomaly) | Viewer behavior |
|---|---|
| Invalid date (not `"YYYY-MM-DD"`, or **outside 1900–2099**) | **Ignored** (plan/actual/milestones alike). Date cell shows `—` |
| Milestone without `label` | **Rendered with an empty label** (no crash) |
| Active but `plan.end` missing | Progress **0%** (avoids NaN) |
| End < start (inverted period) | Bar not drawn / looks odd |
| Actual start in the future | Progress 0 |
| `qty` / `hours` missing or 0 | Effort 0 (shown empty) |
| Decimal `qty` (e.g., 0.5) | Decimal person-days (1.5 etc.) |
| Nesting beyond 4 levels | Colors stop at **L3** (no breakage) |
| Out-of-range / colorless / invalid-date milestones | **Not drawn** (ignored) |
| Milestone `color` not `#hex` | **Ignored, default color** (prevents attribute injection) |
| **Duplicate ids** within one project | Collapse keys collide (same ids open/close together) |
| `projects: []` / `tasks: []` (empty) | Empty view (no crash) |
| Top level `null` / number / non-object | Empty view (no crash) |
| Invalid JSON (D&D / file picker / reload) | Alert shown (no silent failure) |

- Verification data lives in **`tests/異常_*.json`** (broken) and **`tests/正常_*.json`** (normal); see `tests/INDEX.md`.
- "Never crashes" is verified by loading every test file in headless Chromium and asserting **no JS errors and no `NaN`**.

## Known limitations
- **Initial rendering slows with thousands of rows** (full innerHTML rebuild each render). Mitigation = collapsing + archiving. Virtualization only if it ever truly hurts.
- **Identically-named projects share collapse state** (they open/close together). Keep project names unique.
- **`null` elements inside arrays** (null tasks/projects) are unsupported (a non-object top level degrades to an empty view).
- **No keyboard navigation / screen-reader support** (mouse-first personal tool).
- **Renaming a project or editing an id in edit mode resets its collapse state** (collapse keys derive from name/id).
- **Multi-line `note` values get flattened to one line** when touched in edit mode (inputs cannot hold line breaks).

## Notes
- Chromium-based browsers (Chrome recommended), file:// based (uses the File System Access API).
- Your own `wbs.json` is **gitignored by default** (prevents accidental commits). `wbs-archive-*.json` is ignored too. Sample = `wbs_sample.json`; development plan = `wbs_roadmap.json`.

## Dev workflow: the `/pm` skill (Issue × WBS maintenance)

A skill that keeps GitHub Issues and the WBS roadmap consistent. **The Japanese `CLAUDE.md` holds the full reference** (this is the single source; `~/.claude/CLAUDE-single-file-wbs.md` symlinks to it). Summary:
- **Split of truth**: Issue = problem / challenge / done-criteria; WBS (`wbs_roadmap.json`) = the work breakdown needed. Linked by `#N`. The WBS format itself is the "data" sections above.
- **4 modes (AI picks from context)**: file (discuss → issue + WBS) / start (`actual.start`) / done (auto-verify → close + `actual.end`) / auto-file on test failure (dedup + threshold).
- **Done is auto-verified** (don't close on "should be fixed"): machine-checkable criteria are run (e2e green — command in the private `.claude/rules/` as it has a local path; PII grep); visual / save-path smoke is human-confirmed.
- **repo** `piguo45/single-file-wbs`; **versioning** features=MINOR / fixes=PATCH / breaking=MAJOR (once); a different altitude or artifact is a separate tool (#72).
