# <img src="docs/logo.svg" width="26"> single-file-wbs

> A dependency-free, single-file viewer that runs **the plan (WBS) and the issues in one page**: a time-axis Gantt, an EVM-style progress-axis view, a Japanese *inazuma* (slip / progress) line — and, **since v2.0.0, an issue table** on the same screen. Just open the HTML in Chrome — no server, no libraries, no build step.
> Flip with **Plan｜Issues** in the toolbar; clicking a `WBS 2.3` or `Issue #3` link moves you **within the same page**.
> The on-screen application name is **WBS Viewer** (`single-file-wbs` is the distribution name — this repository).

**[日本語版 README はこちら / Japanese README](README.md)**

![screenshot](docs/screenshot.en.png)

Switch with the **Time / Progress tabs** (top right). Progress view (EVM-style completion — actual, planned, behind):

![progress view](docs/screenshot-progress.en.png)

Flip **Plan｜Issues** to the issues side and the same file's issue table appears:

![issues view](docs/screenshot-issues.en.png)

## Five minutes

**On the plan (WBS) side, the only thing you touch by hand is the actual dates.**
Effort, progress, the Gantt and the inazuma line are **all computed**, so they are never stored in the data.
Set `actual.start` when work begins and `actual.end` when it finishes (the row turns gray with a `✓`).
**To push a schedule back, don't retype the dates — use the leaf row's `↷` (reschedule)**, which appends one line to `_planLog` recording why (editing a date cell directly counts as a "correction" and is not logged).

**On the issue side there are only five verbs**, and each maps to a place on screen.

| Verb | When | On screen | What gets written |
|---|---|---|---|
| **Put it on the table** | You can say what harm ignoring it does, or what value doing it brings | **`＋Issue`** at the right end of the filter bar | `title`, `Harm:` or `Value:`, due date, close condition |
| **Mark an action done** | You did something | **done⇄not-done** on an action row | `actions[].done` (**this is what makes it "In progress"**) |
| **Decide** | Something needs settling, or it just got settled | `＋Decision` in the **"Decisions (open)" band**, or `Decide` at the head of a row | `decisions[]` (`decided: null` = open; a date = a decision) |
| **Wait / freeze** | You are waiting on someone, or parking it on purpose | **`Waiting`** (who / what / by when), **`Frozen`** (resume condition) | `pending` (`kind: "waiting"` or `"frozen"`) |
| **Close** | You confirmed the close condition, or decided not to do it | **`Close`** (resolved / won't fix / did not occur / duplicate) | `closed` (`how`, plus the fact you confirmed) |

**Reading an issue is just "three states plus six marks".**

- **State (one per row)**: **Not started** (nothing done yet) / **In progress** (some action is done) / **Closed**.
- **Marks (they stack)**: `Waiting`, `Frozen`, `Undecided N`, `⚠ Overdue`, `⚠ Nudge`, `★ Updated`.
- So "**in progress but two things still undecided**" and "**not started and waiting on someone**" both read off a single row. Squeeze the state into one box and those two disappear.
- **`⚠ Nudge` is the "you forgot to follow up" signal.** It fires on a wait past its deadline, an open question past its deadline, and a wait whose target issue has already closed.

The **legend (`?`)** in the issue toolbar lists what every state and mark means, so nothing has to be memorised.
The full shapes and formulas are in [`CLAUDE.en.md`](CLAUDE.en.md) — **one file covers both the plan and the issues**.

## Concept

**A local plan-and-issue desk for the AI-era manager (PL / tech lead) leading a small, elite team that includes AI.**
Humans edit via the GUI; AI edits via raw JSON and [`CLAUDE.md`](CLAUDE.md) — the same single page.

- **Target**: not the enterprise PM of huge projects, but a **manager leading a small elite team that includes AI** (the author is this persona — dogfooding)
- **Core differentiator — two first-class interfaces**: most PM tools assume a human at a GUI. Here, **AI is also a first-class user**, maintaining plan and issues via raw JSON plus the AI-readable `CLAUDE.md`
- **The plan and the issues are not split apart**: "when, who, how much" belongs to the plan (`tasks`); "what, why, and what makes it done" belongs to the issues (`issues`). They **sit in the same project**, so "which issues with open questions hang off a late task?" is answerable from one file
- **Three states, everything else is a mark**: an issue is **Not started / In progress / Closed** (is any action done, is it closed). **Waiting, frozen, undecided, overdue, nudge and ★ updated are marks** that stack on top of the state
- **No hand-typed state column**: plan progress and issue state are both **derived from facts**, so "closed but still showing in progress" cannot happen
- **A stall always carries its reason**: **Waiting** needs who / what / by when; **Frozen** needs a resume condition. **A wait past its `by when` automatically gets `⚠ Nudge`**
- Architecture and decisions → [`docs/`](docs/index.md) ([overview](docs/design/system-overview.md), [ADRs](docs/adr/))
- Background essays (Japanese) → [WBSという至高ツールで、このAI時代をサバイブする](https://zenn.dev/piguolabo/articles/99b5b30a028f80) / [課題管理とはなにか？](https://knowledge.piguo.org/notes/what-is-issue-management/)

## Start in 30 seconds

1. Download `wbs_viewer.html` from [Releases](https://github.com/piguo45/single-file-wbs/releases/latest)
2. Open it in Chrome (plain `file://` is fine)
3. Load a bundled data file via **Open file** (or drag & drop onto that same button)
   - **`wbs_sample.json`** — a plan-only fictional sample; the classic format reference
   - **`wbs_sample_issues.json`** — a **plan-and-issues** fictional sample (two projects; the first has a plan and issues living together, and the set covers all three states and all six marks)
   - **`wbs_roadmap.json`** — this tool's own source of truth (real data; **the development plan and the issues live together**, maintained by Claude Code)
4. Flip **Plan｜Issues** in the toolbar (with a plan-only or issues-only JSON, no switch is shown)

For your own data, copy `wbs_sample.json` (plan only) or `wbs_sample_issues.json` (plan + issues) as a template (name the file anything you like; `wbs.json` is the idiom and is gitignored). Edit and save, then press **Reload**.
Updating the tool means overwriting `wbs_viewer.html`; your `wbs.json` data is never touched.

## What it does

**The headline of v2.0.0 is issues living in the same page** (the Plan｜Issues switch, the link ledger, the reverse-lookup chips). See [Releases](https://github.com/piguo45/single-file-wbs/releases) for the full changelog.

### See (plan)

- **Inazuma line (progress line)** — it bulges **left of the today line when a task is behind**, making start delays and deadline overruns visible at a glance
- **Plan-vs-actual Gantt overlay** — the actual bar sits inside a plan outline. **Overrun = finish delay (red + N days); an empty gap on the left = a late start.** Done tasks are gray, and parent (aggregate) rows are thin summary bars, so state reads at a glance. Colors follow **color-universal design (CVD-aware)**
- **Progress-axis view (EVM-style)** — besides the time-axis Gantt, a **progress view whose axis is completion (0–100%)**, reachable via a tab. It shows **actual (EV), planned (PV), and how far behind** as horizontal bars (the two views are never mixed)
- **Header summary** — period, effort (person-months), and progress (EVM) stay on screen at all times. Even when ahead-work offsets the overall figure to 0%, a **badge counts the tasks that are individually behind**, so none slip through
- **Holidays and weekends at a glance** — a top-level `holidays` list renders **holidays in red** in the date header and shades **weekend and holiday columns faint pink, full height**. Remaining-business-days excludes both (2026 Japanese holidays ship with the sample data)
- **`Issue #3` chips on plan rows** — a task that issues link to carries a small chip; click it to jump to the issue. **Nothing is written on the plan side** (the chip is a reverse lookup over `links`)

### See (issues)

- **A tab per project, plus a Summary** — the same idea as Excel's "one workbook, many sheets". Keep the projects (`projects`) in a single file and **switch with tabs**. The leading **Summary** tab rolls up not started / in progress / closed / `Waiting` / `Frozen` / `Undecided` / `★ Updated` / `⚠ Overdue` / `⚠ Nudge` / next due per project, and clicking a row jumps to that project. **Only the open project is rendered**, so more projects do not slow it down
- **A link ledger to move around** — under each issue's title, its connections render **one per line**, small and faint (`WBS 2.3`, `Issue #1`, `Time-2`, `Spec`). **Clicking one moves you within the same page** (`WBS 2.3` flips to the plan and lands on that row). The URL gains a marker (`#wbs=…` / `#issue=…`), so the browser's **Back button returns you** and handing the URL to someone opens the same row. A target that no longer exists shows a faint strikethrough — a **broken link**
- **A plain list when collapsed, the Excel issue table when open** — columns are **No / Priority / Title / Detail / State / Due**. Expanded, the Detail column stacks summary, the two questions, close condition, decisions, done steps and planned steps — divided by **faint grey `Summary` / `Done` / `Planned` badges**; collapsed, only **the next move** remains, on one line
- **State is computed, not typed** — **Not started / In progress / Closed** are derived every render. **There is no field to hand-edit the state.** Waiting, frozen, undecided, overdue and nudge ride alongside as **marks**
- **How long it has sat is a number** — days since filing on a Not started row, days since the wait began on a waiting row, days unsettled on each open question. **The oldest can be picked off first**
- **★ Updated (what moved this time)** — anything that moved inside the **update period** (default: the last 7 days, or set `star`) gets a ★ — not only completed actions but also anything **decided, paused, or closed**. Any issue with a ★ shows **a ★ on its title**, so a collapsed list still tells you what moved this week
- **The weekly check-in falls out of it** — `★ Updated 3` and `⚠ Overdue 1` sit at the top right, with `Update period: 9/1–9/7` on the meta line. Read the starred issues from the top, report, then move `star.from` on to the next week
- **Owners live on the actions** — issues have neither an owner field nor an Owner column. Owners are written **per action** and render as `Owner: Piguo`. Collapsed, the Detail column becomes one line such as **`Not done 9/11 Draft the doc, internal review Owner: Piguo/A`**. "The issue is Tanaka's but Sato is up next" can no longer disagree
- **A warning on under-filled rows** — a faint mark appears when both of the two questions are empty, or the close condition is empty. **Never an error** (it must not block filing)

### Narrow down

- **Filter bar (plan)** — above the left table, four axes sit side by side: **state (to do / in progress / done), delayed-only, owner (multi-select), and period (today / this week / this month / all)**. Values inside one axis combine with OR; axes combine with AND. It is **display-only**: neither `wbs.json` nor the time axis changes
- **Filter bar (issues)** — four axes: state, priority, owner (multi-select), and **marks** (`Waiting`, `Frozen`, `Undecided`, `Overdue`, `Nudge`, `★ Updated`). Owners are collected from **everyone appearing in the actions**. Sort by No (data order), due, or priority
- **Column collapse** — **+/−** above the headers fold or unfold column groups (qty+hours, progress, status, owner, plan, actual, notes), freeing up room for the Gantt
- **Column resize** — drag a column header boundary to change its width; double-click resets it to the default (widths are remembered in the browser; the data is untouched)

### Edit

- **Three ways to edit** — in-browser editing (autosave), any text editor, or **AI chat** (`CLAUDE.md` ships with the tool, so Claude Code already understands the data format)
- **Reschedule history** — confirming a reschedule via the **↷ button** in edit mode updates the plan and **records the reason** in the same action (`_planLog`). The Gantt shows only the latest change, as a dotted **trail**; clicking a task's **↷N** opens a balloon with the full history and how far it has drifted from the original plan. A plain date-cell edit — a "correction" — is treated separately and leaves no history
- **One click writes the facts (issues)** — Decide (an approach) / Waiting / Frozen / Close write everything required together (dates, who, by when, resume condition, the fact you confirmed), structurally preventing the half-done records you get from hand-writing a single key

### Foundation

- **A single HTML file** — just open it in Chrome. No server, CDN, build step, or dependencies
- **Data is one JSON file of facts** — plan and actual dates, plus what was decided, paused and closed. Effort (qty × hours ÷ 8, person-days), progress, the inazuma line, issue state, overdue and ★ are all **computed automatically**, so there are no numbers to maintain by hand
- **A quiet screen** — each role gets exactly one form of emphasis: the `Summary` / `Done` / `Planned` badges use a grey fill, ★ is **black everywhere**, and done vs. not done is text weight (☑ / ☐). **Borders are reserved for the priority and state badges**
- Also: multiple projects as tabs, a collapsible tree, milestone lines, completed-task graying, auto-linked URLs in notes, custom keys starting with `_` preserved, a Japanese/English UI toggle

## Working the screen

- **Flip Plan｜Issues**: the two-way switch in the toolbar (shown only for files that carry both)
- **Switch views (plan)**: the **Time / Progress tabs** (top right) toggle between the Gantt (time axis) and the progress view (completion)
- **Narrow down**: the **filter bar** above the table. Only the display changes — the data never moves
- **Collapse rows**: on the plan, click a project or phase name, or `▼/▶` (the **`▼/▶` in the Task column header** expands or collapses everything; **Ctrl+Z** restores the previous view after a slip). On the issues, **click the Title cell** to toggle one line ⇄ full text
- **Collapse / resize columns**: the **+/−** above the headers; drag a column header boundary (double-click resets the width)
- **Gantt**: the day column under your mouse is **highlighted**, with its date emphasized in the header. **Hover a bar** to see the exact plan and actual dates
- **Notes**: an issue's note (`note`) is an aside, so it **stays hidden by default**. Hover the `Note` marker at the end of the link line under the title to see the full text, and **click to pin it as a popover** where the URLs inside are clickable
- **Language**: switch with **EN / 日本語** in the header (the data itself is never translated)

## In-browser editing (optional)

Turn the **Edit** button ON to edit directly on screen. Changes are **autosaved to `wbs.json` about 0.4 s later** (save status is always visible at the top right).

- **Plan**: in-place editing of each field — No., name, qty, hours, owner, dates, notes (**effort is auto-computed**, so it isn't editable). Dates accept shorthand like `611` or `6/11`, full `YYYY-MM-DD`, or the 📅 picker. You can add a row `＋`, delete one `✕` (with confirmation), reorder `⬆⬇`, **add a nested child task**, **edit a milestone** (`＋MS` on a project row), and **reschedule** (the **↷ button**)
- **Issues**: edit title, priority, due, the two questions, close condition and notes in place. Record stalls and completion with the **`Waiting` / `Frozen` / `Close`** buttons. Add links with **`＋Link`** and remove any with its `✕`. **`＋Issue` sits at the right end of the filter bar** (the view jumps to the new row). Add `＋` actions and edit their owner, date and text; toggle done, delete `✕`, reorder `▲▼`. Things to decide are added in the **"Decisions (open)" band** (`＋Decision`)
- **Projects**: `＋Project` adds one, double-clicking a tab renames it, and the tab's `✕` deletes it (with confirmation)
- Not supported (edit the JSON or ask the AI instead): drag-and-drop reordering, moving a task to a different parent, automatic renumbering, opening multiple files at once

### Recording why a plan changed

"Why did this slip?" is the first thing everyone forgets once a project drags on. Confirming a reschedule via the **↷ button** updates the plan and **records the reason** at the same time. The Gantt shows only the latest change as a subtle dotted trail — it never adds rows or extra ink. The full history is always one click away via **↷N**.

![reschedule history](docs/screenshot-history.en.png)

<details>
<summary>⚠ Enabling edit mode requires re-selecting the file (click for steps)</summary>

When you press **Edit**, a **file save dialog opens immediately**. This is not a bug: for security, Chrome only grants a page write access to a file when **the user picks that file in a save dialog** — an unavoidable constraint of `file://`-based tools.

1. Press the **Edit** button — a save dialog opens
2. Select **the same `wbs.json` you currently have open** and press Save
3. "Replace existing file?" → **Yes**
4. When the Edit button turns **green**, you're ready

What the page looks like right after pressing Edit (a yellow guidance bar appears; the save dialog opens on top of this):

![right after pressing Edit (yellow guidance bar)](docs/guide-edit-on.en.png)

You only do this **once per Chrome session** — not every time (required again after restarting Chrome).

</details>

![edit mode](docs/screenshot-edit.en.png)

## Maintaining via AI chat

The number-one reason WBS charts and issue tables die is **the cost of updating them**. This tool freezes the view logic (HTML) and treats the data (`wbs.json`) as the only thing that changes, so you can **delegate updates to Claude Code via chat**. The data is one plain JSON file, so no plugins or integrations are needed — bulk edits, workload aggregation, and analysis that crosses plan and issues are each one sentence away.

- "Mark the design review as completed today" → sets `actual.end` to today
- "Push every June task back a week" → a bulk change
- "File the migration-test errors as an issue — if ignored the production cutover fails" → one entry added, with the two questions and close condition filled in
- "Set #3 to waiting — the dev team's spec answer, by 9/12" → `pending` records **who, what and by when**, and past 9/12 a `⚠ Nudge` appears
- "Sweep up the open questions, longest-standing first" → the list to take to whoever can decide, with elapsed days, on the spot
- "List the issues with open questions that hang off a late task" → **one file, so one read answers it**

The bundled [`CLAUDE.md`](CLAUDE.md) ([English: `CLAUDE.en.md`](CLAUDE.en.md)) teaches the AI the data format, the editing rules, the four moves (put it on the table, decide, fold it in, close), and the shape of each request.

## Data format (wbs.json)

```json
{
  "name": "My board",
  "holidays": [ "2026-07-20", { "date": "2026-08-11", "name": "Mountain Day" } ],
  "star": { "from": "2026-09-01", "to": "2026-09-07" },
  "projects": [
    {
      "name": "Sales system migration",
      "milestones": [ { "date": "2026-10-20", "label": "Cutover", "color": "#cc79a7" } ],
      "tasks": [
        { "id": "2", "name": "Conversion tool", "children": [
          { "id": "2.3", "name": "Character encoding", "qty": 1, "hours": 16, "assignee": "Piguo",
            "plan":   { "start": "2026-09-14", "end": "2026-09-18" },
            "actual": { "start": null, "end": null }, "note": "",
            "_ai":    { "tokens": 70000, "minutes": 25, "model": "fable-5" } }
        ] }
      ],
      "issues": [
        {
          "id": 1,
          "title": "Migration test throws encoding errors in bulk",
          "priority": "high",
          "opened": "2026-09-05",
          "due": "2026-10-20",
          "ifIgnored": "The same errors hit the production cutover and the migration fails, on cutover day",
          "ifDone": "",
          "closeWhen": "A rehearsal runs the whole migration procedure with no errors",
          "decisions": [
            { "q": "Build the converter in-house or use an existing library",
              "since": "2026-09-07", "decided": null, "a": "" }
          ],
          "pending": null,
          "closed": null,
          "links": [
            { "wbs": "2.3" },
            { "issue": 3 },
            { "project": "Timecard system renewal", "issue": 2 },
            { "title": "Spec", "url": "https://example.com/spec" }
          ],
          "actions": [
            { "date": "2026-09-05", "text": "Incident observed", "assignee": "", "done": true },
            { "date": null, "text": "Meet the dev team about the encoding spec", "assignee": "", "done": false }
          ],
          "note": "Related links live in links; the note is just an aside"
        }
      ]
    }
  ]
}
```

- **`projects` is an array of projects.** One project holds **both a plan (`tasks`) and its issues (`issues`)** — plan-only, issues-only and both are all valid. An issue `id` only needs to be unique **within its project**
- **Plan (`tasks`)**: tasks nest up to 3 levels. A node with `children` is a summary node; without one, it's a leaf that carries effort. **`qty` is a repeat count** (e.g. 5 screens × `hours` 4h each); leave it at `1` for one-off work
- `holidays` (optional, top-level) is shared across all projects. A plain string means no name; `{ date, name }` shows the name as a tooltip. **Holidays render red in the date header and shade columns pink alongside weekends**, and are excluded from the remaining-business-days count
- **`links` is the link ledger.** Only four forms: `{ "wbs": "2.3" }` (a plan task in the same project) / `{ "issue": 1 }` (an issue in the same project) / `{ "project": "…", "issue": 2 }` (another project) / `{ "title": "…", "url": "https://…" }` (external URL). **Connections are written on the issue side only** — never on the plan
- **`decisions[]` holds what to decide and what was decided.** `{ q, since, decided, a }`: `decided: null` is **an open question** (listed in the "Decisions (open)" band as `14 days open (since 8/26)`); a date makes it **a decision**. **An issue may hold any number**
- **`pending` has two shapes.** **Waiting** `{ kind: "waiting", since, who, until, what }` / **Frozen** `{ kind: "frozen", since, resumeWhen, detail }`. A wait past its `until` gets `⚠ Nudge`
- **It holds facts only.** Effort, progress, the inazuma line, issue state, the marks, and the collapsed Detail column (the next-move line) are never written; they follow from the dates and from `decisions`, `pending`, `closed` and `actions`. The exception is `star` (the **update period** ★ marks) — a **setting**, not a derived value
- `ifIgnored` (**if ignored, when and what happens**) and `ifDone` (**if done, when and what you gain**) are **either-or**; only file what answers one of them (on screen they appear under `Harm:` and `Value:`). `due` = **the day the harm or the value shows up** — not when the assignee plans to work on it
- **Keys starting with `_` are custom keys** you can add freely (`_ai` = AI effort above; `_money` and `_links` work the same way — any structure). The viewer ignores them, and in-browser editing preserves them
- **Legacy shapes still read fine**: a plan-only `{ "projects": [{ name, milestones, tasks }] }` and the single-project `{ "project", "milestones", "tasks" }`. **A file with no `issues` renders the plan alone and shows no switch**
- To confirm nothing is broken, run the bundled checker: `uv run python scripts/check.py wbs.json` — or `python3 scripts/check.py wbs.json` where uv is not installed (dependency-free; it resolves link targets and checks duplicate numbers, dates and enums, reporting as `<project> / #<number> / <field>`)
- For exact formulas, operations, and edge-case handling, see [`CLAUDE.en.md`](CLAUDE.en.md) — the single source of truth for the spec

## Requirements

**Google Chrome (latest) recommended.** It uses the File System Access API, so a **Chromium-based browser is required**; opening directly via `file://` works fine.

- **Microsoft Edge** and other Chromium-based browsers work too (same engine; development testing is done on Chrome)
- On corporate-managed browsers, the File System Access API may be disabled by policy — viewing still works, but **editing won't** (check `edge://policy`)
- Firefox and Safari are **not supported** (no File System Access API)

## Tests and known limitations

`tests/` bundles normal-case and broken-input sample JSONs plus e2e tests (see [`tests/INDEX.md`](tests/INDEX.md)). Design policy: graceful degradation — broken input must never crash the viewer.

Known limitations: initial rendering slows down with thousands of rows (mitigate by collapsing). Projects with identical names — and duplicate `id`s — share collapse state. Issues carry no dependencies on each other. Renaming a project breaks the links that point at it by name (check with `scripts/check.py`). There's no keyboard navigation or screen-reader support (a mouse-first personal tool).

## License

[MIT](LICENSE)
