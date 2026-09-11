# Plan & Issue Tracking Tool (WBS Viewer) - CLAUDE.en.md

> **English translation of [`CLAUDE.md`](CLAUDE.md) (the Japanese original is the primary spec).**
> **Sync rule: whenever the spec changes, update `CLAUDE.md` and `CLAUDE.en.md` in the same commit.**

A text (JSON) driven management tool. **The plan (WBS) and the issues run in one HTML page and one JSON.**
The data is one JSON in which **each project (`projects[]`) holds both a plan (`tasks`) and its issues (`issues`)**.
Connections are written **only in the issue's `links[]`**; the view builds the reverse lookup and jumps both ways in one click.

| File | What it is |
|---|---|
| **`wbs_viewer.html`** | **The product entry point — open this.** A two-way Plan｜Issues switch flips between the views (one HTML file, zero dependencies) |
| `wbs.json` | The single source of truth. Both the plan and the issues live here (any filename works; `wbs.json` is the idiom) |

**This one file is complete for both the plan (`tasks`) and the issues (`issues`).**
**The effort formulas, the Gantt, the inazuma line, progress assessment, filing and closing issues are all written here** (the manual is never split across files — one read is enough for an AI).
**A plan-only `wbs.json` (a file with no `issues`) still opens exactly as before** (→ "The backward-compatibility promise").

**Suggested reading order**: shared (vision, principles, requirements, screen, editing, data) → the plan (computation, adding & updating) → the issues (derived values, the four moves, example requests) → broken input and limits → dev workflow.

---

## Product vision & design principles

> **A local plan plus issue table for the AI-era manager (PL / tech lead) leading a small, elite team that includes AI. Humans edit via the GUI; AI edits via raw JSON and `CLAUDE.md` — the same single sheet.**

- **Target user**: not the enterprise PM of huge projects, but a **manager (PL / tech lead) leading a ~10-person elite team that includes AI**. The author is this persona (dogfooding).
- **Vision (a bet, owned as such)**: as AI rises, small elite teams wielding AI become the norm, and **everyone becomes a PL/TL**. This tool is for that lead (human **and** PL/TL agent) to manage the plan and the issues. It is a bet on the future, but hedged — even if it misses, it already helps today's leads.
- **Core differentiator = two first-class interfaces**: human = GUI / AI = raw JSON + the AI-readable `CLAUDE.md`. **Both are first-class.** Every feature works via both the GUI path and the AI/JSON path (custom keys preserved, round-trip).
- **`CLAUDE.md` is not "documentation" but "the AI's API spec"**: because AI depends on the format, **the schema is kept almost frozen**. When it must change, keep readers backward compatible and update `CLAUDE.md` / `CLAUDE.en.md` together.
- **One entry point, complete**: an AI cannot read another repo's manual. **Both the plan and the issues are documented in this one file**, and cross-references stay inside the document.
- **Source-of-truth rule: declare it per repository, one per repository.** Pick exactly one home for issues in each repo and declare it. Never mix GitHub Issues and this table (you lose track of which one is real). The declaration goes in that repo's `CLAUDE.md` (this repo's is the final section below).
- **Build**: data that holds only facts (state is derived) / fields that support the filing discipline (the two questions, the close condition) / a "waiting" and a "frozen" mark that always carry their reason / AI-native (progress assessment, dependency inference) / load by assignee (human vs AI) / cost (`_ai` tokens, `_money`) / honest views (true state, not vanity).
- **Don't build**: enterprise ticketing / enterprise PM (portfolios, complex permissions) / workflow and approval engines / large-scale real-time collaboration / notifications and outbound requests / automated reporting.
- Source of the semantics → [課題管理とはなにか？ / What is issue management?](https://knowledge.piguo.org/notes/what-is-issue-management/) (Japanese)
- Background essay for the plan side → [WBSという至高ツールで、このAI時代をサバイブする](https://zenn.dev/piguolabo/articles/99b5b30a028f80) (Japanese)

---

## Handling principles (important)

- **Do not touch the viewer (`wbs_viewer.html`) as a rule.** The view logic is complete.
- **Changes mean editing `wbs.json` (data) only.** When asking an AI to do work, it should edit the JSON.
  - Touch the HTML only when the display spec itself must change (and only on explicit request).
- **Never write derived values into the data.** State, overdue, ★ (which rows get one), effort and progress are computed by the viewer. Do not add keys like `status` or `overdue`.
  - **There are exactly three exceptions** (none of them derived — each is either a **setting** or **a fact recorded at a moment in time**):
    1. **`star`** (the reporting period that ★ marks) = a **setting**. It lives in the JSON so the person reporting, the people reading, and the AI all see the same ★.
    2. **`_progress` / `_progressAt` / `_progressBy`** (the plan's earned-value assessment) = **a person/AI judgment at that moment, recorded as fact**. It is never recomputed, hence a `_` key (→ "Plan (`tasks`) field definitions").
    3. **`_planLog`** (the history of schedule changes) = **the fact of when and why something slipped**. Append-only (→ same section).
- **Write on the issue side and the plan side separately.** Day to day, an issue request rewrites only `issues` and the `links` inside them. **The plan side may be rewritten in exactly three cases**:
  - **"Folding in"**: when no matching leaf exists yet, you may add **exactly one leaf**. Number the `id` so it **does not collide within the project**, set `name` to the issue title, and **ask the user** for `qty` / `hours` / `plan` (never invent them). If the project has no `tasks`, create `tasks: []` and add the leaf there. Whenever you add a leaf, **always add `{ "wbs": "<the new id>" }` to the issue's `links`** — never leave the leaf unreferenced. → example ⑦-4
  - **Recording that a plan task finished or started**: write `actual.end` (and `actual.start` if it is empty). → example ⑯ and "Plan (`tasks`) — adding and updating ①"
  - **Requests about the plan itself** (add a task, reschedule, assess progress, milestones, archiving): → "Plan (`tasks`) — adding and updating"
- **Connections are written on the issue side only.** Never add "Issue #3" to a plan task — the view derives that chip from `links`.
- **Never write the same thing on both sides** (the split is detailed at the end of "The four moves of issue management ⇄ JSON operations").

---

## Rules that keep an AI from guessing

**Read this table before editing the JSON from this file.**

| Where people go wrong | The rule |
|---|---|
| Duplicating an action as a WBS child task | **A WBS leaf = one issue** (plan, actual and effort live there). **An issue's actions = the steps inside that issue** (never create children in the WBS for them) |
| Which kind of number | WBS ids are strings like `"2.3"` (key `wbs`); issue ids are integers like `3` (key `issue`). **The key name tells them apart** |
| Referring across projects | Same project: `{ "issue": 3 }`. Another project: `{ "project": "…", "issue": 3 }` |
| `null` vs. absent | They mean the same thing. **When an AI writes, write `null` explicitly** |
| Order | **Array order = display order = chronological.** Append at the end; never re-sort |
| Owners | Free text (`Piguo/A`). If asked to tally them, match strings and say so |
| Only one approach? | **An issue may hold several** (`decisions[]`). Anything not settled yet sits there as an **open question** (`decided: null`). **You never need to split the issue for it** |
| Naming the state | The states are **Not started / In progress / Closed** — those three only. **"Undecided", "waiting" and "frozen" are marks, not states** (they can sit on the same issue) |
| Why it is stuck | **Waiting on a person or a thing = waiting** (`kind: "waiting"`; who / what / by when). **Deliberately parked = frozen** (`kind: "frozen"`; a resume condition). **Waiting on someone to decide is neither — it is an open question in `decisions`** |

**Check after editing**: `uv run python scripts/check.py wbs.json` — or `python3 scripts/check.py wbs.json` where uv is not installed (dependency-free; it looks at duplicate numbers, dates, enums, whether link targets exist, and leftover legacy keys).

---

## What to do when a request is vague or self-contradictory (for AI)

**When in doubt, ask instead of editing.** The situations below are the ones an AI actually got wrong — or decided without any basis in this file — during an AI check (an AI given only this document, fed sloppy requests in the voice of a user).

1. **A request names only a number, and that number exists in several projects** → **ask which project** (unless the conversation just before it already fixed one).
   Example: "#1 is stuck, waiting on the dev team" → "There is a #1 in Migration project and a #1 in Timesheet system replacement. Which one?"
2. **A phrase (part of a title) matches several issues** → list the candidates and ask. Proceed only with a **clear reason** for narrowing it to one, and **state that reason in your reply**.
   Example: "add a line to the encoding one" → if two match, offer both; if #3 was the subject a moment ago, say "the previous turn was about #3, so I added it there".
3. **Colloquial, no number at all** → offer the candidates and ask **"close the issue, or mark one action done?"**
   Example: "the timesheet thing is done" → "Do you mean #2 in Timesheet system replacement? Close the issue, or mark one action as done?"
4. **The number and the content of the request disagree** → **do not edit**; show the mismatch and ask. **Never write a false record.**
   Example: "close #2 as resolved — the rehearsal had zero errors" → if #2 is the paper-forms issue, "#2 is about paper forms; the rehearsal sounds like #1?"
5. **A completed action (`done: true`) — its date, text and owner — is a record of fact** → **never rewrite it.** Change it only when the user explicitly says **"correction"**.
   Example: "set the owner on #1 to Sato for all of them" → apply it to the **outstanding actions only**, and reply "the two completed ones are records, so I left them alone".
6. **The same request contradicts itself** → do not let the later half silently win; ask.
   Example: "add the next action with owner A. Also set every owner on #1 to Sato" → "Should the action I am adding stay with A, or become Sato too?"
7. **Filing an issue with no close condition or stated impact** → **ask first, then file.** The viewer will display an empty `closeWhen`, but **an AI must never file one empty** (see "Checklist when filing").
   Example: "the forms came out garbled. Production is 10/20. Put it on the table" → first ask "if ignored, when and what happens? / what state lets us close it?" **If a similar issue already exists, also ask "file a new one, or add an action to #N?"**
8. **Which project a new issue belongs to is unclear** (two or more projects exist) → ask. With only one project, do not ask.
9. **New actions are appended at the end.** A dated action may follow one that is still being scheduled (`date: null`). **Never re-sort** (array order is the chronological record).
10. **The update period includes both `from` and `to`.** "Move it to next week" means `from` = **the day after the current `to`**, and `to` = **`from` + 6 days** (see example ⑩).
11. **Read-only requests** (report / list / what moved / is anything broken) **must not change the JSON.** Say **"no changes"** in your reply.
12. **The verb is clear but the number you need is missing** (e.g. "fold it in" with no WBS number) → **state the default move and confirm it**. If a matching leaf exists, "I will link it to `2.3`"; if not, "I will add one leaf named after the issue". **Ask for values you cannot know** (planned dates, effort) — never fill in a placeholder.
13. **A joint owner** (`Piguo/A`) told to "set them all to X" → **replacing the whole string is the default** (`Sato`). **Ask when it looks like only one name is meant to change** ("just drop A").
14. **"Close it" is explicit but the substance is unfinished** (outstanding actions or open questions remain) → **show the mismatch and ask before closing.** A clear number is not permission to close quietly.
    Example: "close #1 as resolved" → "#1 still has 2 outstanding actions and 2 open questions. **Close anyway** (is the close condition met), or **settle the open questions first**?"
15. **A progress note on a wait** ("#3, still no answer") → **change nothing on your own; offer three options.** ① **Within the deadline, no data changes** ("it is due 9/12, so three days left — leave it?") ② **Extend the deadline** (a new `pending.until`) ③ **Record that you nudged** (one line in `actions`).
    "Still nothing" is usually **a status update, not an instruction**. **When you change nothing, say "no changes".**

16. **Never invent a reason in `what` or `q`.** Do not add causation the user never stated ("because…", "due to…") — **stay a paraphrase of what was said**.
    Example: "#3, still nothing back from the dev team" → `what` is "the dev team's answer". **Do not write "because the dev team is swamped"** — you were not told that. If the background matters, ask, or put it in `note` marked as the user's own words.
17. **Fix how "next week" is counted** (the same for `decisions[].until`, `pending.until` and `due`).
    **"next week" = Monday–Sunday of the week after the day it was said** / **"next Friday" = the Friday of that following week** / **"this week" = the week containing the day it was said (Monday–Sunday)**.
    When the phrasing leaves the day open ("sometime next week"), **ask whether that means the Friday or the Sunday** — never pick one. Write the settled date as `YYYY-MM-DD`.
18. **Asked to assess progress, but no deliverable was pointed at — or the leaf has not started** (`actual.start` empty) → **do not write `_progress`.** Answer that the work has not started yet, and ask **what to assess it against** (implementation, tests, docs, commits…).
    **Never write 0% and call it assessed** (`_progress: 0` records "I looked and it is at 0%", which is not the same as "I have not looked"). A leaf that has not started is already 0% automatically, so there is nothing to write.
19. **When an AI writes `_planLog` or `_progress`, `by` / `_progressBy` is its model name** (e.g. `"claude-sonnet-5"`), never `"manual"`. `"manual"` is **only for a human editing by hand**. Without a record of whose judgment it was, the assessment cannot be revisited later.
20. **On a read-only request that spans the plan** ("what is due this month", "what is late", "assess the progress"), **if a project has no `tasks`, say so in one line: "no plan (WBS), so this cannot be judged"** (never silently omit it).
    When nothing matches, **state it explicitly** ("there are no late tasks"). These are read-only requests, so **never change the JSON** (→ 11).
21. **A request that moves an `until` / `due` that is already set, in bulk** ("push all the open questions to next week", "add a week to every due date") → **list the targets and confirm before overwriting.**
    Extending a deadline is **changing a promise**, not tidying a record. In particular, **anything currently overdue** loses its nudge mark the moment you push it, so **count how many are overdue**, list them, and then ask a two-way question: "move all of them, or hold the overdue ones and move only the rest?" (recommend the latter).
    Example: "push every open question to next Friday" → "That is 5 entries, 2 of them already overdue (9/4 and 9/8). I would **hold those two** and move the other 3 to 9/18 — or shall I move all 5?"
22. **A request to move a plan date (`plan`) splits in two, on whether a reason came with it.**
    **With a reason it is a reschedule** — update `plan` to the new dates and **append one entry to `_planLog`** (when, from → to, ±N days, reason, `by`).
    **With no reason it is a correction** — just fix `plan` and **record no history** (piling history onto typo fixes makes "why did this slip?" unreadable later).
    **If it is unclear which, ask** ("give me one line of reason and I will log it as a reschedule; if it is a typo I will correct it with no history"). The shape of `_planLog` and the value of `by` are governed by 19 and "Plan (`tasks`) field definitions".
**When in doubt, ask instead of editing. Offer two or three options and name the one you recommend.**

---

## Requirements
- **Google Chrome (latest) recommended.** Other **Chromium-based** browsers such as Edge work too (testing is done on Chrome). Firefox / Safari are not supported (no File System Access API).
- On corporate-managed browsers, editing is unavailable if File System Access is disabled by policy (viewing still works).
- No HTTP server, no external libraries or CDN. Open **`wbs_viewer.html` directly via `file://`**.

## Opening / reloading
1. Open **`wbs_viewer.html`** in Chrome.
   The toolbar carries a **two-way Plan｜Issues switch** (the same idiom as the plan side's Time / Progress tabs — one side filled).
   **The switch appears whenever issues could be shown**: any JSON that has `issues` (with or without `tasks`), and **before any file is loaded** (both sides are live). **A JSON with only `tasks` shows no switch** (the plan alone). **A JSON with only `issues` does show the switch, but the Plan side is disabled** (not clickable). With both, it defaults to **whichever side you were last on** (remembered in localStorage).
2. Load `wbs.json` via **Open file** (drag & drop onto that same button also works).
3. Edit and save `wbs.json`, then press **Reload** to re-read and re-render (no re-picking needed; File System Access API).
4. Scroll position is **preserved across collapsing and reloads**; **only loading a new file re-centers on today and resets collapse state** (plan side).

How to read the screen (columns, tabs, collapsing, filters, links) is collected in the "Display" section below.

---

## Display

### Shared
- **UI is Japanese/English switchable** (the "EN / 日本語" toolbar button). Default Japanese; the choice is stored in localStorage.
  All UI strings live in the `I18N` table inside the HTML (data = the contents of `wbs.json` is never translated). **When adding a UI string, add it to both ja and en.**
- **Plain-branding toggle**: clicking the **title (logo / "WBS Viewer") at the top-left** hides the logo, version, "Viewer" and the tab title, leaving just **"WBS"** (click again to restore; remembered in localStorage). It strips the product look so the tool can pass as "self-made" on locked-down client sites. No tooltip is added (to keep it undiscoverable).
- The browser tab title reads "`name` – WBS Viewer".
- Filtering shares the same rules on both sides: **OR within an axis, AND across axes, default = no filtering** (a full-column Excel-style filter is deliberately not built — to stay lightweight and honest).
- **Filters are display-only — `wbs.json` (the data) never changes.** They thin the rows; neither the time axis nor the counts move (hiding is a blindfold, not a delete).

### The plan (`tasks`) screen
- **State filter**: three pill toggles in the **"filter bar" (a full-width band just above the left info table)** ("State: To do / In progress / Done") **show/hide rows by state** (default all-ON; remembered in localStorage `wbsStateFilter`; i18n ja/en). It lets you focus on unfinished work when completed tasks pile up. **Display-only — it merely thins the rows; neither `wbs.json` (data) nor the horizontal axis (time range) changes**: the axis is fixed from the full data, so the remaining bars don't move a single pixel (hiding is a blindfold, not a delete). State is the exclusive 3-way split of the existing progress logic (To do = no `actual.start` / In progress = start set, no end / Done = `actual.end` set), evaluated via a `STATES` table. **Parent-retention**: a parent stays if at least one descendant remains visible; otherwise the parent (and project) is hidden too. **The top-right summary (effort/progress/delay) stays unchanged, counting completed work** (honest view). A hidden pill shows a **strike-through** so it reads without relying on color (CUD redundancy).
- **Delay filter**: a "Delayed only" toggle in the same filter bar (default OFF; remembered in localStorage `wbsDelayOnly`). When ON, only **delayed leaves** are shown = `slip>0` (behind schedule) or **past due** (today > plan end and not done). Delay is a separate axis from state, so it **AND-combines** with the state filter (e.g., In progress AND delayed). Display-only, axis fixed, summary unchanged, and parent-retention are shared with the state filter. The ON pill is **red-tinted** (meaning color: delay = red); being a single toggle it has no strike-through.
- **Assignee filter**: assignees are variable and many, so instead of pills this is a **dropdown (`details/summary`, a browser standard) + checklist**. Assignee values are **collected dynamically** from `wbs.json` (unique, empty = "(none)", sorted). **Multi-select (OR within the axis)** = only checked owners are shown; **Select all / Clear all**; default = all shown. The badge reads All / a count `(N)` / the name when only one. It uses an **off-set approach** (owners you hid are stored in localStorage `wbsAsgOff`, so new owners are shown by default = robust). It **AND-combines** with the other axes (e.g., Tanaka AND Done). Display-only, axis fixed, summary unchanged, and parent-retention are shared. The dropdown **stays open** while you check items.
- **Period filter**: a **single-select segment** of **Today / This week / This month / All** (default All; remembered in localStorage `wbsPeriod`). When set, only leaves whose **plan or actual period overlaps the target range** are shown (this week = Mon–Sun containing today; this month = the **calendar month** containing today, the 1st through the last day — fiscal months or a custom start day are out of scope). **The axis doesn't move — only rows are filtered** (bars don't shift a pixel). AND-combines with the other axes; summary unchanged and parent-retention shared. The selected segment is filled to signal single-select.
- Collapsing: click a **◆project / L1 / L2 `▼/▶`–name**. The **`▼/▶` in the Task column header** expands/collapses everything (▼ = all open → click collapses all; ▶ = something closed → click expands all). An accidental header action can be **restored with Ctrl+Z** (inactive while an input has focus).
- Column headers are centered. The left info table (No.–Notes) is fixed; **only the Gantt scrolls horizontally**.
- **Column collapse (outline-style)**: a thin row above the column headers holds **+/−** toggles per **collapsible unit** — there are **8 groups**:
  `qty+hours` (the breakdown of effort), Effort, Progress, Status, Assignee, Plan, Actual, Notes (**No. and Task name are always shown**).
  Collapsed columns are **removed at 0 width (no leftover gap stub)**, the + sits at the boundary (absolute). State is
  saved in localStorage; scroll/tree-collapse are preserved; collapsing widens the Gantt. Implemented via the `COL_CG` map + `effCols` filter (draw cost = column count, not row-dependent).
- **Column resize**: **drag a column header boundary** to change its width (a thin blue line on hover marks the grip);
  **double-click resets it to the default** (the Excel convention). Widths are remembered in localStorage
  (`wbsColWidths`, key→px; default = `w` in `COLS`, floor = `min` in `COLS`). **Independent of column collapse** (a collapsed
  column keeps its width and returns to it when expanded). **View-only — `wbs.json` (the data) never changes.** Edit-mode
  width needs (84px floor for dates, 52px for qty/hours, +72px for the Task name) still take precedence as before.
  Widths live in the CSS variables `--cw-<column key>`, so a drag **only rewrites the variable** (no re-render, no extra
  row×column work); the single confirming re-render happens on mouseup.
  **Capped so the left pane never exceeds `window width − 200px`** (the Gantt always keeps 200px), which stops a column
  from being widened until the grips on its right go off-screen. The same check runs at startup, so **saved widths that
  no longer fit the screen are reset to the defaults** (no dead end when widths saved on a large monitor are opened on a small one).
- **Plan/Actual date columns have a two-level header**: "Plan" / "Actual" on top, "Start / End" beneath (adjacent columns grouped by the `group` property in `COLS`).
- Row layer colors: **◆project (with separators) > L1 > L2 > L3**.
- Gantt: date + weekday (year-month header), **weekend + holiday (`holidays`) columns shaded faint pink full-height** (`--weekend` / a translucent overlay drawn above the rows; bars/inazuma/today-line stay in front for legibility); active tasks extend the actual bar to today.
  **Holidays render red in the date header** (Sat = blue / Sun = red convention kept). The holiday name shows as the date cell's tooltip.
  **Plan = unfilled outline (front, 4 sides) / actual = filled bar (behind), overlaid in the same lane**:
  the actual sticking past the outline's right = **finish delay = red bar + "+N"** (number only; always placed at the bar tip; exact value in the tooltip "Finish delay +N d"),
  empty space at the outline's left = **start delay** (actual start is right of the outline's left) — shown by the gap, no dedicated color.
  Because delays are color-coded (red = finish delay, gray = done), the outline + fill is not misread as a progress bar.
- **Parent (aggregate) = thin summary bar**: both plan outline and actual are thin (parent vs leaf by shape, not extra color = CUD-safe, keeps all info when collapsed).
  The actual's fill ratio matches leaves. **Bar color is identical across all levels** (parent vs leaf distinguished by bar thickness/shape, not hue or lightness).
- **Colors (CUD-aware)**: actual = blue / plan = blue outline / finish delay & inazuma = red (vivid while active / muted when done) / done = gray bar.
  **Only the Progress tab uses dedicated bar colors** (`--actual-soft` / `--short-soft` — same hue and lightness as the Time tab, 50% less chroma): the semantics stay shared while the area's visual pressure drops.
  Start delay uses no color — just the empty outline. Following the Okabe-Ito principle we avoid "blue vs purple" (milestone default = mauve `#cc79a7`) and never rely on color alone (shape, position, labels add redundancy).
  Verified by `tests/e2e/test_color_audit.py` (and `tests/e2e_issue/test_color_audit_issue.py` for the issue side); add the pair and re-run whenever you add/change a color.
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

- **The right pane toggles between "Time / Progress" tabs** (default = Time). Time = the Gantt (unchanged) / Progress = horizontal completion bars (blue=actual / red=shortfall to plan, whose right edge = planned PV / leaf=10px, parent summary=6px — **thinner than the time view (14px/8px)** to shrink the colored area).
  Only the active view is injected into the DOM (render cost = one view). The tab choice is remembered in localStorage.
- **Telling the Progress view apart from Time**: (1) **square-cornered bars** (Time = rounded; distinguished by shape, CUD-safe) (2) a **blue-grey unfilled track** (`#eef1f7`, 0–100%) (3) **ruler-style ticks** =
  major (full-height dotted at 20/40/60/80%, `#555`) + minor (short solid from the top edge down ~60%, every 10%, same `#555`, drawn in front of the bars). Axis labels are 0/20/40/60/80/100%.
  (4) **dedicated colors and thinner bars** = actual `--actual-soft` `#6872b1` / shortfall `--short-soft` `#b15a5d`. **Same hue and same lightness (L\*) as the Time tab's `#2f6fed` / `#e11d48`, with only chroma (C\*) lowered by 50%**.
  Every row in the Progress tab is a full-width 0-100% bar, so the colored area is several times that of the Time tab and pure hues make the screen heavy. The pressure comes from **both chroma and area**, so the bars are also slimmed from 14/8px to **10/6px** (the `.ptrack` backing and the minor ticks follow). **Lightness is never raised** (washing the colors out would also weaken the sense of delay) — the semantic colors stay identical, only the visual pressure drops.

### The issues (`issues`) screen
- Projects (tabs): with two or more `projects`, a **tab bar** sits above the table (a leading **Summary** tab plus one per project; each tab name carries `★N ⚠N`).
  **Summary** is a per-project roll-up (project name / **Not started** / **In progress** / **Closed** / `Waiting` / `Frozen` / `Undecided` / **★ Updated** / **⚠ Overdue** / next due, plus a totals row). Clicking a row jumps to that project.
  **Only the open project is rendered**, so adding projects does not slow things down.
- Columns are **No / Priority / Title / Detail / State / Due** (left = **what it is about**, middle = **how it is going**, right = **where it stands and by when**).
  **The Detail column holds the body only**: Summary (**Harm** / **Value** / close condition / decision / waiting or frozen / closed) → Done → Planned. The title lives in the Title column and is never repeated in the detail.
  **The note (`note`) is not shown by default** — it is an aside, not the substance of the issue. Its marker sits **at the end of the link line under the title** (not at the end of the detail); **hovering shows the full text as a tooltip** and **clicking pins it as a popover** so the URLs inside are clickable (click outside or press `Esc` to close). Because it rides the link line, **it stays readable while collapsed.**
  The dividers are **`Summary` / `Done` / `Planned` badges — a grey fill, no border**; no `■`-style glyphs and no rules.
  **Inside the detail, each role gets exactly one form of emphasis**: badges = fill / ★ = **a black glyph** / done vs. not done = **text weight** (☑ bold dark grey, ☐ light grey; the Japanese UI uses `済` / `未`). The note marker uses a **fainter fill than the badges**.
  **★ is black everywhere** — on action rows, on titles, on tabs, and in the `★ Updated N` count at the top right. It never carries a colour.
  **Borders are reserved for the priority and state badges.** Nothing inside the detail uses a fill, a border, strikethrough, or a size difference.
  Owners on action rows are written as **`Owner: Piguo`** (when empty, the label is dropped too).
- Collapsing: **click the Title cell** to collapse or expand (the `▼/▶` and the unanswered `⚠` also live in the **Title column**).
  **Collapsing shrinks the Detail column to a single "next move" line** (e.g. `Not done 9/11 Draft the doc, internal review Owner: Piguo/A`). It is the first action with `done: false`; if there is none the cell is **empty** (closed issues are always empty).
  The **`▼/▶` in the Title column header** expands or collapses everything.
- Filtering: the **filter bar** above the table (state / priority / owner / **marks**).
  **Six mark pills**: `Waiting` / `Frozen` / `Undecided` / `Overdue` / `Nudge` / `★ Updated`. **No "only" suffix** (`Overdue`, never `Overdue only`) — a pill being on already says "show just these". **The pills, the counts, the derived-values table and the request examples all use these same six names** — never a synonym.
 Owners are collected from **everyone appearing in the actions** (OR within the axis: an issue shows if any of its action owners is on). There is no Owner column, but filtering still works off the action owners. It is **display-only — `wbs.json` never changes**. Sorting: `No (data order) / due / priority`.
  The state, priority and mark filters and the sort order are **shared across the book**; the owner candidates and the collapse state are **per project**. The counts at the top right are for **the open project**.
- Following a link (**issue → plan**): click an entry on the link line under the title (**one link per line** — `WBS 2.3`, `Issue #1`, `Time-2`, `Spec` stacked vertically).
  **Every jump happens inside the same page** (no new tabs). Clicking `WBS 2.3` **flips to the plan**, selects the project, expands that row, scrolls to it and highlights it for about two seconds; `Issue #1` does the same within the issues view.
  The URL gains **`#wbs=<project name>/2.3`** or **`#issue=<project name>/<number>`** at the end, so the browser's **Back button returns you to where you were**. Hand that URL to someone and they land on the same row once they open the file (if nothing is loaded yet, they get "open the JSON to see …").
  Only external URLs (`{ title, url }`) open in a new tab. The link line shows **one link per line**, with **the `Note` marker at its end**.
- Back-reference chips (**plan → issue**): a plan task that issues link to carries a small **`Issue #3`** chip (`Issue #3 #7` for several).
  **Nothing is written on the plan side** — the reverse lookup is rebuilt from `links` on every render. Clicking a task name toggles collapse, so **the chip is the click target**.
  A target that does not exist (missing task, issue or project) renders with **a faint strikethrough plus a tooltip** (no crash, the data is never removed).

---

## In-browser editing (edit mode)

Besides text and AI editing, you can **edit `wbs.json` directly on screen** (optional).
Toggle the **Edit** button (green when on). Changes are auto-saved to `wbs.json` after a short delay (save status is always shown at the top right).

### What you can do on the plan (`tasks`)
- **Inline editing of every field** (No.=id / task name / qty / hours / assignee / plan & actual dates / notes).
- **Progress input**: the leaf's `◀ N% ▶` stepper changes `_progress` by ±10%; setting ≥10% auto-sets `actual.start` to today (returning to 0% keeps the start date).
- **Adding leaves**: row `＋` = sibling below; project row `+Task`. Ids are minted collision-free (adding to a collapsed project auto-expands it).
- **Nesting (add a child task)**: row `＋子`/`+sub`. On a leaf it **becomes a summary node** carrying its values into child 1 = effort/progress unchanged; on a summary it appends a blank child; child id = parent id + suffix. **Not shown on the 3rd level** = no 4th level.
- **Deletion**: `✕` (with confirmation, including children). **Deleting the last child of a summary returns that child's values to the parent and demotes it to a leaf** = effort is never lost.
- **Reordering among siblings**: `▲▼`.
- **Milestone editing**: `＋MS` on the project row / an edit row below it with **date (📅) · name · color · ✕ delete**. Color is **chosen from 5 CUD-safe Okabe-Ito presets** — the GUI uses a picker, not free hex; JSON/AI can still set any `#hex`.
- **Reschedule**: the leaf row's `↷` records the plan change into `_planLog` and auto-updates the plan (form = new start / new end / optional reason → **Confirm reschedule** appends to `_planLog`, updates `plan` and autosaves in one click). **Editing a date cell directly is a "correction" and is not logged** (reschedule and correction are kept apart). See `_planLog` under "Plan (`tasks`) field definitions".
- **Out of scope (by design)**: drag-and-drop reordering / moving across parents / automatic renumbering. Use JSON or AI editing for those.
- Effort / progress / inazuma line recompute automatically as before (re-rendering is deferred while an input has focus).

### What you can do on the issues (`issues`)

| Target | Operation |
|---|---|
| Title | Edit in place in the **Title column** |
| Note | In edit mode a **textarea appears at the end of the Detail column** (replacing the read-mode marker and popover; newlines preserved). **Issues have no owner field** — owners are edited on each action in the detail |
| Priority | High / Mid / Low dropdown |
| Due (`due`) | `YYYY-MM-DD` text input plus 📅. Shorthand like `611` / `6/11` also accepted |
| The two questions, close condition | Edit `ifIgnored` / `ifDone` / `closeWhen` as multi-line text (newlines preserved) |
| Actions (`actions`) | `＋` add / done⇄not-done checkbox / edit date, text, owner / `✕` delete / `▲▼` reorder / edit the `WBS` tag |
| Things to decide (`decisions`) | **`＋Decision`** adds one entry. The edit row is a **single line**: from the left, **a `Decide` button / `q` (the question) / a deadline field / `✕`**. The deadline field's placeholder is **`by MM-DD`** (matching the `(by 9/16)` shown in read mode; empty means `until` stays `null`). Pressing **`Decide`** at the head of the row opens **the answer form**; writing `a` there stamps `decided` with today. **The old separate decide button is gone** — `Decide` lives at the head of the row. **`✕`** removes that row |
| Waiting / Frozen / release | **`Waiting`** → enter who (`who`), what (`what`) and by when (`until`), which sets `pending = { kind: "waiting", … }`. **`Frozen`** → enter the resume condition (`resumeWhen`) and the reason (`detail`) for `pending = { kind: "frozen", … }`. Releasing sets `pending = null` |
| Close / reopen | Button (labelled **`Close`**) → pick one of 3 close types, plus the fact you confirmed, which sets `closed` (**and resets `pending` to `null`** — the same as example ③); reopening sets `closed = null` only |
| Update period (`star`) | Edit `from` / `to` from the `Update period: 9/1–9/7` meta line in the header (leave `to` empty for "up to today") |
| Links (`links`) | **`＋Link`** → pick one of the four forms and fill it in (`wbs` / `issue` / another project / external URL). **`✕`** on any link removes it. The link line shows **one link per line** |
| Add / delete an issue | **`＋Issue` sits at the right end of the filter bar** (only while edit mode is on). `id` = current max + 1, `opened` = today, `priority` = mid; **the view jumps to the new row automatically**. Delete with `✕` (with confirmation, in the **Title column**) |

### What you can do on projects (`projects[]`)

| Target | Operation |
|---|---|
| Add a project | `＋Project` → type a name. **A legacy-shape file (`{ project, tasks }` and the like) is converted to `projects` the moment you press it** |
| Rename a project | **Double-click** the tab. **Cross-project links point at the name**, so fix the pointing side too (`scripts/check.py` will tell you) |
| Delete a project | `✕` on the tab (with confirmation — **its issues and plan go with it**) |

**What you cannot do** (edit the JSON or ask an AI)

- Drag & drop reordering / automatic `id` renumbering / opening multiple files at once / notifications and outbound requests.

**Saving and permissions (shared)**

- **Autosave**: changes are written back to `wbs.json` after a ~0.4 s debounce (File System Access API). Writes are serialized through a single queue. **Only internal derived values are stripped** (`_calc`/`_leaf` etc.) — **user keys starting with `_` are preserved**. Save status (Unsaved changes… / Saved HH:MM:SS / Save failed) is **always visible at the top right**.
- **External-change detection**: before each write the file's mtime is checked; if it changed outside the tool (e.g., AI editing), an **overwrite confirmation** is shown. When asking an AI to edit, it is safest to turn edit mode OFF first.
  - **If you cancel that confirmation and then press Reload, the edits made on screen are discarded** (the file wins). **A confirmation is shown before Reload takes effect**, so if you want to keep the on-screen version, cancel it and either save a copy under another name first or fold the AI's change in by hand.
- **Auto-retry on interference**: when a sync client (OneDrive, etc.) or antivirus touches the file at the same instant as a save, the browser may reject the write with `InvalidStateError` ("state had changed since it was read from disk"). In that case the tool **waits a beat and retries the save once** (the retry's `getFile()` refreshes the browser's internal snapshot, which almost always recovers). The write is rejected *before* touching disk, so **the original file stays intact**. If the retry also fails, it shows "Save failed" and **keeps the dirty flag** (re-saved on the next edit or on tab close; it does not auto-retry in a loop, to avoid alert spam).
- **Permissions**: saving requires **write permission**. Only files opened with a handle (Open file or D&D) are editable. **`file://` pages cannot show write-permission prompts**, so when turning Edit ON you **re-select the same `wbs.json` in a save dialog** (the selection itself grants permission). ⚠ Chrome **truncates the file the moment it is picked**, so the current data is **written immediately after selection** (never left empty). If told to "press Edit again", do so (browser gesture limitation; the second click opens the dialog directly). The permission is **session-scoped** (after restarting Chrome, re-select once per Edit ON). **Loading a new file automatically turns edit mode OFF** (turn it ON again to grant permission for the new file). On a failed load the handle is not replaced (prevents overwriting the wrong file).
- **Legacy formats** (the plan-only single-project shape `{ project, tasks }`): on Edit ON, after confirmation they are **converted to the `projects[]` format** before editing.
- **Date cells are `YYYY-MM-DD` text inputs plus a 📅 calendar button**. `2026/07/01`-style input is accepted and normalized to `-` (the display format of `input type=date` follows the browser UI language and cannot be controlled, so the display is fixed to ISO).
- Input guards: dates are **valid only within 1900–2099** (out-of-range / partial input is ignored, not saved). Qty / hours accept decimals (`step="any"`). Mouse-wheel changes on number inputs are disabled (prevents accidental edits). Closing the tab with unsaved changes prompts for confirmation.
- State transitions **write all the required facts with one button** (structurally preventing half-done records). Writing `closed` by hand alone can leave an open item in `decisions`.

---

## Data (wbs.json)

### Shape

```json
{
  "name": "My issue table",
  "star": { "from": "2026-09-01", "to": "2026-09-07" },
  "projects": [
    {
      "name": "Migration project",
      "milestones": [
        { "date": "2026-10-20", "label": "Cutover", "color": "#cc79a7" }
      ],
      "tasks": [
        {
          "id": "2",
          "name": "Conversion tool",
          "children": [
            { "id": "2.3", "name": "Encoding conversion", "qty": 1, "hours": 16,
              "assignee": "Piguo",
              "plan": { "start": "2026-09-14", "end": "2026-09-18" },
              "actual": { "start": null, "end": null }, "note": "" }
          ]
        }
      ],
      "issues": [
        {
          "id": 1,
          "title": "Mass character-encoding errors in the migration test",
          "priority": "high",
          "opened": "2026-09-05",
          "due": "2026-10-20",
          "ifIgnored": "The same errors will hit the production cutover and the migration will fail. The impact lands on cutover day",
          "ifDone": "",
          "closeWhen": "A full rehearsal of the migration procedure runs with zero errors",
          "decisions": [
            { "q": "Approach", "since": "2026-09-05",
              "decided": "2026-09-07", "a": "Investigate the cause and fix the conversion step" },
            { "q": "Build the converter in-house or use an existing library", "since": "2026-09-07",
              "decided": null, "a": "" }
          ],
          "pending": null,
          "closed": null,
          "links": [
            { "wbs": "2.3" },
            { "issue": 3 },
            { "project": "Timesheet system replacement", "issue": 2 },
            { "title": "Spec", "url": "https://example.com/spec" }
          ],
          "actions": [
            { "date": "2026-09-05", "text": "Incident occurred", "assignee": "", "done": true },
            { "date": "2026-09-07", "text": "Decide approach, assess impact", "assignee": "Piguo", "done": true },
            { "date": null, "text": "Meet dev team about the encoding spec", "assignee": "", "done": false }
          ],
          "note": "Related links live in `links`; the note is just an aside",
          "_ai": { "tokens": 1200, "model": "claude-fable-5-1", "memo": "filed by AI draft" }
        }
      ]
    }
  ]
}
```

**A project is one element of `projects[]`.** The plan (`tasks`) and the issues (`issues`) sit **inside the same project**.
A project may hold only `tasks` (plan only), only `issues` (issues only), or both — all three are valid.
`star` (the update period) and `holidays` are **shared by the book** (top level); `milestones` are per project.

### Field definitions

| Key | Type | Required | Meaning (in plain words) |
|---|---|---|---|
| `name` | string | optional | Book name (shown on screen and in the browser tab) |
| `holidays` | array | optional | Public holidays (book-wide, top level). Shape: `["YYYY-MM-DD", { date, name }]`. Used when drawing the plan (→ "Plan (`tasks`) field definitions") |
| `star` | `{ from, to }` / `null` | optional | The **update period** (the reporting period) — the range ★ marks (top level, alongside `name`). `from` = start, `to` = end (**omit for today**). Absent means the default: **the last 7 days** (today included). **A setting, not a derived value** (see "Reporting" below) |
| `projects[]` | array | required | The **projects**. One project = `{ name, milestones?, tasks?, issues? }`. Tab order = array order |
| `projects[].name` | string | required | Project name (shown on the tab). **Cross-project links point at this string**, so keep it **unique within the book** |
| `projects[].milestones` | array | optional | That project's milestones (`{ date, label, color }`). Used on the plan side |
| `projects[].tasks` | array | optional | The **plan (WBS)**. String `id` like `"2.3"`, nested children (max 3 levels), `plan` / `actual`. Shape → "Plan (`tasks`) field definitions"; formulas → "Computation". An issue request normally only **reads** it (to resolve links and show back-reference chips); the three cases where writing is allowed are listed under "Handling principles" |
| `projects[].issues` | array | optional | That project's **issues**. **Array order = display order** |
| `id` | number (integer) | required | No. Unique **within its project** (different projects may reuse a number). Gaps are fine. **Never renumber** |
| `title` | string | required | Headline (aim for ~30 full-width chars; details go in other fields) |
| `priority` | `"high"` / `"mid"` / `"low"` | optional (default `mid`) | Priority = size of impact × nearness of the due date. Shown as High / Mid / Low |
| `opened` | `YYYY-MM-DD` | optional | The day it was put on the table |
| `due` | `YYYY-MM-DD` / `null` | optional | **The day the harm or the value shows up** (the day `ifIgnored`'s harm lands, or the day you want `ifDone`'s value — not when the assignee plans to work on it) |
| `ifIgnored` | string | one of the two | **If ignored, when and what happens** (the blocking side). Example: "on the 10/20 cutover the forms become unreadable". **On screen the label is `Harm:`** (the key name never changes) |
| `ifDone` | string | one of the two | **If done, when and what you gain** (the accelerating side). Example: "from November, the monthly close takes half a day". **On screen the label is `Value:`** (the key name never changes) |
| `decisions[]` | array | optional | **The things to decide and the things decided.** One issue may hold **several**. Each element is `{ q, since, until, decided, a }`: `q` = **the question to settle** / `since` = **since when it has been open** / `until` = **by when you want it settled** (optional, may be `null`; past it you get **⚠ Nudge**) / `decided` = **the day it was settled** (`null` means **undecided**) / `a` = **the approach** (filled once decided). **Array order = display order**; append at the end |
| `closeWhen` | string | required (may be empty; empty shows a warning) | **The close condition** — the state in which you can confirm the harm did not happen or the value was realized. Note: "may be empty" is **what the viewer tolerates** (so broken input never crashes it). **An AI must never file one empty** (see "Checklist when filing" and rule 7 of "What to do when a request is vague") |
| `pending` | `{ kind, … }` / `null` | optional | Why it cannot proceed — **exactly two shapes**. **Waiting**: `{ kind: "waiting", since, who, until, what }` (`what` = what for, `until` = by when — `null` if none). **Frozen**: `{ kind: "frozen", since, resumeWhen, detail }` |
| `pending.who` | string / `{ issue }` / `{ project, issue }` | required on a wait | **A person is a string** (`"Dev team"`); **waiting on another issue is an issue reference** (`{ "issue": 2 }`, or `{ "project": "…", "issue": 2 }` across projects). With a reference, **closing that issue raises ⚠ Nudge** — the reason to wait is gone but the wait was never released |
| `closed` | `{ at, how, note }` / `null` | optional | **Close**. `at` = the day closed, `how` = one of the 3 values below, `note` = **the fact you confirmed** (write it against `closeWhen`) |
| `links[]` | array | optional | The **link ledger** — everything this issue connects to. Each element is one of four forms (**the key names pick the form; you may not mix them**): `{ "wbs": "2.3" }` = a plan task in the same project / `{ "issue": 1 }` = an issue in the same project / `{ "project": "Timesheet system replacement", "issue": 2 }` (a `"wbs"` variant also works) = another project / `{ "title": "Spec", "url": "https://…" }` = an external URL (**`title` required, `http(s)` only**). **Connections are written on the issue side only** — never on the plan |
| `actions[]` | array | optional | Done and planned steps (the Done / Planned bands of the Excel sheet). **Array order = chronological display order.** On screen they are split under the `Done` (completed) and `Planned` (outstanding) badges |
| `actions[].date` | `YYYY-MM-DD` / `null` | optional | Date. **`null` = being scheduled (TBD)** |
| `actions[].text` | string | required | What was or will be done |
| `actions[].assignee` | string | optional | Owner of that step (free text, e.g. `"Piguo/A"`). **This is the only place owners live** (there is neither an issue-level owner field nor an Owner column). It shows on each action row in the detail as **`Owner: Piguo`** (when empty, the label is dropped too), and the same form appears in the single next-move line a collapsed row shows |
| `actions[].done` | boolean | optional (default `false`) | Done / not done. On screen the two are told apart **by text weight alone** — **☑ in bold dark grey / ☐ in light grey** (the Japanese UI uses `済` / `未`). No fills, borders, strikethrough, or size differences |
| `note` | string | optional | Free notes (an aside). **Never displayed inline**: read it from the `Note` marker at the end of the detail, as a **tooltip (hover)** or a **pinned popover (click)**. `http(s)://` is auto-linked and **clickable inside the popover** |
| `_anyName` | any | optional | Custom key (ignored by the viewer, preserved on save) |

**`pending.kind` (why it is stuck — two kinds)**

| Value | In plain words | Shape | The move that unsticks it |
|---|---|---|---|
| `"waiting"` | **Waiting** (on someone's answer, a thing, or a date) | `{ kind, since, who, until, what }` | Nudge them (past `until` it becomes **⚠ Nudge**) |
| `"frozen"` | **Frozen** (parked on purpose) | `{ kind, since, resumeWhen, detail }` | Write a resume condition and let it sleep |

**A wait with nobody and nothing recorded is a wait nobody ever follows up on**, so never leave `who` or `what` empty. The same goes for a freeze's `resumeWhen`.

The article's **three reasons for pending** split like this in this tool (**the moves stay the article's**).

| The article's reason | How this tool writes it | The move |
|---|---|---|
| Nobody has decided | **An open question in `decisions[]`** (`decided: null`) — not a pending at all | Take it to whoever can decide |
| Something isn't available (people, things, information, timing) | **Waiting** `{ kind: "waiting", since, who, until, what }` | Nudge them (past `until` it becomes **⚠ Nudge**) |
| Deliberately parked | **Frozen** `{ kind: "frozen", since, resumeWhen, detail }` | Write a resume condition and let it sleep |

**`closed.how` (how it was closed)**

| Value | In plain words | When to use it |
|---|---|---|
| `"resolved"` | Resolved | You confirmed the close condition (`closeWhen`) was met |
| `"wontfix"` | Won't fix | You decided not to do it (close it the moment you decide) |
| `"not_occurred"` | Did not occur | The due date passed and the harm you wrote never happened (**keep the row**) |
| `"duplicate"` | Duplicate | The same thing is already on another issue. **A `links` entry pointing at it (`{ issue }` or `{ project, issue }`) is required.** Follow it there from now on |

### Plan (`tasks`) field definitions

- Each project's `tasks` nest parent-child (**max 3 levels**). With `children` = **summary node**; without = **leaf** (carries effort).
- Leaf fields:
  ```
  id, name, qty, hours (per unit), assignee,
  plan:   { start, end }        planned, "YYYY-MM-DD"
  actual: { start, end }        actual (null if undecided)
  note
  _anyName                      "_"-prefixed = custom key (optional, ignored by viewer, preserved on save)
  ```
  - **`id` is a string** (`"2.3"`); an issue number is an integer (`3`), and the key name (`wbs` / `issue`) tells them apart. Keep it **unique within the project**.
  - **Keep `name` a short label** (about 14 full-width characters; put detail and history in `note`) — longer values do not break anything but get clipped in the Task column (the full text shows on hover).
- **Effort and progress are not stored in the data** (all derived; computed by the viewer → "Computation").
- **Holidays (optional, top-level)**: `holidays: ["YYYY-MM-DD", { date, name }]` (string form = no name / object form = `name` as tooltip).
  Shared across all projects. Holiday dates render **red in the date header**, and **weekend + holiday columns are shaded faint pink full-height** in the Gantt. If omitted, only weekends are pink (backward compatible).
  e.g. `"holidays": [{ "date": "2026-07-20", "name": "Marine Day" }]`.
- **`milestones: [{ date, label, color }]`** is optional per project (drawn as vertical lines on the plan side).
- **Exception: `_progress` (0/10/…/100) is read by the viewer** as the progress value (EV), alongside `_progressAt` (assessment time, ISO) and
  `_progressBy` (**who assessed it**). Asking an AI: "assess task X's progress to the nearest 10% from the deliverable and requirements"
  → it writes `_progress`/`_progressAt`/`_progressBy` on the leaf (→ "Plan (`tasks`) — adding and updating ⑥"). If unset, progress falls back to time-based (backward compatible).
  An assessment is a **recorded fact** (a person/AI judgment at that moment); it is not recomputed, hence a `_` key — consistent with "no derived values in data".
  **When an AI writes `_progressBy`, it writes its model name** (e.g. `"claude-sonnet-5"`). **`"manual"` is only for a human editing by hand** (the on-screen stepper and the like) — never write `"manual"` from an AI edit.
- **`_planLog` (schedule-change history)**: a `_` key that records **as fact** why a successor was pushed back by a delay (same idea as `_progress`/`_ai` — not derived; the viewer preserves it by default).
  Append one entry per reschedule (append-only). **The first entry's `from` is effectively the baseline (the original plan)**:
  ```json
  "_planLog": [
    { "at": "2026-06-10T09:00:00Z",
      "from": { "start": "2026-06-01", "end": "2026-06-05" },
      "to":   { "start": "2026-06-15", "end": "2026-06-19" },
      "by": "manual", "reason": "pushed back by the delay in #504" }
  ]
  ```
  - `at` = change timestamp (ISO) / `from`·`to` = `plan` before·after / `by` = **who changed it** / `reason` = why (e.g. the upstream `#N`).
    **When an AI writes `by`, it writes its model name** (e.g. `"claude-sonnet-5"`). **`"manual"` is only for a human editing by hand** (the `↷` button in edit mode and the like) — never write `"manual"` from an AI edit.
  - **AI-native**: "push B back by a week and record the reason = delay in #504" → the AI updates `plan` and appends one line to `_planLog`.
  - **GUI path (edit mode)**: the leaf row's **↷ button → form (new start / new end / optional reason) → "Confirm"** = appending to `_planLog` + **auto-updating `plan`** + autosave, all in one click (structurally prevents half-done updates). **Editing a date cell directly is a "correction" = not recorded** (intent is separated from rescheduling). No-change confirms are not recorded. There is no GUI deletion of history (fix via JSON if needed).
  - **Display**: only the **latest change** gets a **trail** (dotted gray; bottom lane = start moved, top lane = end moved — the lane tells the change type). The task name gets **↷N** (count of valid entries). **Click ↷N or a rescheduled plan bar** to open a balloon = full history (when, from → to, ±N days, reason) plus vs-baseline. Click outside / Esc closes. No extra rows; gantt ink stays constant no matter how many reschedules. Trail origins are automatically included in the time-axis range. Broken entries are ignored (graceful; `tests/異常_リスケ履歴.json`).
  - Scope: recording is **limited to changes of `plan`** (no full-field audit log).

### `_` keys (custom keys)

- **Keys starting with `_` may be added freely.** The viewer ignores them as a rule and in-browser editing preserves them (round-trip).
- Use them for metadata (e.g. `_ai` for AI token records, `_money` for cost). The structure is up to you; they work on issues and on plan leaves alike.
- **As a rule they are not a place for derived values.** State, overdue, ★ (which rows get one), effort and progress must not be written even under a `_` key (the ★ **period** lives in the top-level `star`).
- **The viewer reads exactly three `_` keys** (none of them derived — each is **a fact recorded at a moment in time**, so it is fine to store):
  - **`_progress`** (0/10/…/100) = the earned-value assessment, alongside **`_progressAt`** (assessment time, ISO) and **`_progressBy`** (`"manual"` or a model name).
  - **`_planLog`** = the history of schedule changes (append-only).
  - Both shapes are specified under "Plan (`tasks`) field definitions".
- **`_calc` and `_leaf` are reserved internal names.** The viewer rebuilds them on every render, and they are **stripped on save at any depth** (project, task or issue). **Never use them as your own keys** — whatever you write there is discarded.

### Backward-compatibility promise

- **Never change the meaning of an existing key.** Add keys, but do not delete, rename, or change types.
- **New keys are always optional.** An old `wbs.json` must keep reading correctly.
- When the schema changes, update `CLAUDE.md` and `CLAUDE.en.md` **in the same commit**.
- Keep your own information in a `_` key **first**. Promote it to an official key only once it turns out to be needed in other repos too.

**How older files are read (the reader's responsibility)**

| Input | Handling |
|---|---|
| The v2.0.0 shape `{ name?, holidays?, star?, projects: [{ name, milestones?, tasks?, issues? }] }` | As is |
| A plan-only file `{ projects: [{ name, milestones, tasks }] }` (existing single-file-wbs data) | Opens as is; the issue view is empty |
| The plan-side legacy shape `{ project, milestones, tasks }` (single project) | Converted to the `projects[]` shape on load (a confirmation is shown when turning Edit ON) |
| An existing file carrying `_progress` / `_progressAt` / `_progressBy` / `_planLog` | **Read as is** (the three `_` keys the viewer reads → "`_` keys (custom keys)") |
| A file carrying `_` keys the viewer does not know | **Ignored but preserved** (never stripped on save = round-trip) |

**There is no legacy shape on the issue side.** Issues first shipped in v2.0.0, so `sheets`, a bare top-level `issues`, `actions[].wbs`, an issue-level `assignee`, `decision`, `decisionLog` and `pending.reason` are **not read or mapped** — they were removed before release, so no mixed file exists.
**An AI writes the new shape only.** Any of those keys left behind is an **error** in the checker.

---

---

## Computation (plan side — deterministic, in the viewer)
- **Effort (person-days) = `qty × hours ÷ 8`**. Parent = sum of descendant leaves.
- Parent plan/actual period = min start – max end of descendant leaves.
- Progress (EV = earned value / reference date = today):
  - Not started (no actual.start) = 0% / Completed (actual.end set) = 100%
  - Active = **if `_progress` (0/10/…/100) is present, quantize to the nearest 10% and use it**; otherwise fall back to the
    time-based `clamp((today − actual.start) ÷ (plan.end − plan.start) × 100, 0, 100)` (backward compatible).
  - Parent = effort-weighted average of descendant leaves' (progress × effort) (continuous; not snapped).
- **EVM values**: EV = actual progress / **PV = planned** = what should be done by today `clamp((today−plan.start)/(plan.end−plan.start)×100,0,100)` (linear; parents weighted) /
  **slip = behind = max(PV−EV,0)** (≈ EVM SV). S-curve, non-linear PV, and a cost axis are out of scope (not done).
- **Header summary (right, plan side)**: **Period** (earliest start–latest end / business days left, **excl. weekends & holidays (`holidays`)** ) / **Effort**
  (person-months = person-days ÷ 20 working days / remaining) / **Progress** (actual EV% / planned PV% / behind = max(PV−EV,0)%),
  in three rows plus a meta line (📄 filename · N projects · 📅 today · 🔄 refreshed · 💾 saved). Each row has a hover tooltip.
- **Delay badges (4th summary line "Behind:")**: the overall behind% is textbook EVM (ahead-work offsets it, so it can read 0%);
  to avoid missing slippage, the **count of tasks behind** is shown as badges (**Due** = past planned end & not done / **EV** = PV>EV).
  A badge whose count is 0 is hidden; if both are 0 the whole line is hidden.
- **Progress column = `◀ N% ▶` stepper** (10% steps; editable on leaves only / parents show the auto-aggregate read-only, continuous). `_progress` is not a derived value but
  "a person's/AI's judgment at a point in time", so it is stored as a `_` key (never recomputed) — consistent with the "no derived values in data" rule.
- **Status column = behind / actual / planned** (slip / EV / PV, %). Behind=red, actual=blue, planned=black. **On-track rows show actual only** (quiet). No mental math (the delay is pre-computed).
- **Planned-end turns red** when today > plan end and not done (deadline overrun; done rows are not reddened). Same "red = behind" as the time tab's Gantt/inazuma.

---

## Plan (`tasks`) — adding and updating (how-to)

Edit `wbs.json` only. Save → press **Reload** in the viewer.
Requests about the issues (`issues`) are under "Example requests to an AI (issue side — have it edit the JSON)".

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
- **When the leaf belongs to an issue**, do not leave it unreferenced — add `{ "wbs": "<the new id>" }` to that issue's `links` (→ "Example requests to an AI (issue side — have it edit the JSON)" ⑦-4). **One WBS leaf = one issue**, so never turn the steps inside an issue into child tasks (those live in the issue's `actions[]`).

### ③ Adding a project
Append to the `projects` array (for the issue-side conventions see "Example requests to an AI (issue side — have it edit the JSON)" ⑪; the name must be **unique within the book**):
```json
{ "name": "New project", "milestones": [],
  "tasks": [ { "id": "1", "name": "Phase 1", "children": [ /* leaves… */ ] } ] }
```

### ④ Adding a milestone
Append to the project's `milestones`:
```json
{ "date": "2026-09-30", "label": "Release", "color": "#ef4444" }
```

### ⑤ Example requests to an AI (plan side)
- "Mark the design review as **completed today**" → set `actual.end` of that leaf to today
- "Component placement has **started**" → set `actual.start`
- "**Add** a testing phase" → append a summary node + leaves
- "**Archive** everything completed before May" → → "Archiving" (backup + delete)
- "**Assess** the progress of task X" → see ⑥ "AI progress-assessment workflow" below (deliverable + requirements → nearest 10% into `_progress`)
- "Push **B** back by a week, reason = delay in #504" → update `plan` and append one line to `_planLog` (→ "Plan (`tasks`) field definitions")

### ⑥ AI progress-assessment workflow (this tool's core = AI-native)
Hand the fuzzy "roughly what %" to an AI. The steps are deterministic:
1. **Read the leaf's requirements** (the linked issue's `closeWhen`, URLs / acceptance criteria in `note`, related commits/deliverables). The reverse lookup is: whichever issue's `links[].wbs` points at this leaf.
2. **Compare deliverable vs. requirements** and estimate completion, **quantized to the nearest 10% (0/10/…/100)** (don't over-credit; don't count unverified work).
3. Write three keys on the leaf: `_progress` (the value) / `_progressAt` (assessment time, ISO) / `_progressBy` (the assessing model's name, or `"manual"` for a human).
4. **Done is separate**: when actually finished, set `actual.end` (= 100%) rather than `_progress`. `_progress` is only an in-progress earned-value estimate.
- Example: "Assess `2.3`'s progress from the deliverable (impl/tests/docs) and the close condition, to the nearest 10%."
- Note: an assessment is a **recorded fact** (a person/AI judgment at that moment); it is not recomputed, hence a `_`-key — consistent with "no derived values in data."

---

## Derived values (issue side — computed by the viewer, never stored in JSON)

| Derived value | Rule |
|---|---|
| **State (three, exclusive)** | `closed` present → **Closed** (sub-label from `how`: resolved / won't fix / did not occur) / else **any completed action** (`done: true`) → **In progress** / else → **Not started**. **Holds and open questions are not states** (see the marks below) |
| **Marks (six, orthogonal to state)** | ① **Waiting** (`pending.kind === "waiting"`, with `who` beside it) ② **Frozen** (`pending.kind === "frozen"`) ③ **Undecided N** (how many `decisions` entries have `decided: null`) ④ **⚠ Overdue** (today > `due`) ⑤ **⚠ Nudge** (any of three: **a wait past `pending.until`** / **an open question past `decisions[].until`** / **a wait whose `who` is an issue that is now closed** — the "⚠ Nudge" row below is authoritative) ⑥ **★ Updated** (moved during the reporting period). **Closed rows show none of ①–⑤** (nothing left to nudge). **Only ★ also appears on closed rows** — "we closed this one this week" is the substance of a report |
| **⚠ Nudge** | Raised by any of: ① a **waiting** (`kind: "waiting"`) where **today > `pending.until`**; ② an **open question** (`decided: null`) where **today > `decisions[].until`**; ③ a wait **whose `who` is an issue reference and that issue is closed** (the reason to wait is gone but nothing was released). With `until: null`, ① and ② never fire. **Counts and filters include both waits and open questions** |
| **Elapsed days** | A **Not started** row shows the days since `opened`; a **waiting** row the days since `pending.since`; each **open question** the days since its `decisions[].since`, small. The wording depends on where it sits. **The marks in the State column read `Not started Nd` / `Waiting Nd`** (no start date on screen — the tooltip supplies it). **Only the rows in the "Decisions (open)" band use `N days open (since M/D)`** (e.g. `14 days open (since 8/26)`), whose tooltip spells it out: `N days since it was added on M/D`. Both are **the same in read mode and edit mode**. **How long something has sat is a number**, so the oldest can be picked off first |
| **Decision lines** (inside Summary) | Every `decisions` entry that **has a `decided` date** renders as "**Decision: a (M/D)**", **one per line** (several are fine, in array order). **In read mode an entry with an empty `a` (or `q`) is not rendered**; **in edit mode it is**, so a broken entry can still be fixed from the screen |
| **The "Decisions (open)" band** | Every `decisions` entry with **`decided: null`** is listed in a band under `Summary`, **bulleted with "·"**, each showing **how many days since `since`** as `N days open (since M/D)` (e.g. `· Build the converter in-house or use a library 14 days open (since 8/26)`). With none open, the band is not drawn at all |
| **Overdue** | today > `due` and not closed → `due` in red plus a `⚠` mark (closed rows are never red and carry no mark) |
| **★ Updated** (moved during the reporting period) | ★ on any action **completed** in the period (`done: true` with a `date` inside it; `date: null` never gets one), and on anything **decided** (`decisions[].decided`), **paused** (`pending.since` — waiting or frozen), or **closed** (`closed.at`) in the period. An issue with any ★ gets **a ★ on its title** (visible even when collapsed). The period comes from `star` (default: the last 7 days) and **includes both `from` and `to`** (activity on the `from` day and on the `to` day counts). On screen this is called "**Updated**" (tabs, titles and action rows show the bare ★ with an "Updated…" tooltip) |
| **Next move** | The first action with `done: false` (used in the summary and tooltips) |
| **The Detail column when collapsed** | The **next move** (the first action with `done: false`) on one line: `Not done 9/11 Draft the doc, internal review Owner: Piguo/A`. If no action is outstanding the cell is **empty** (closed issues are always empty). **Never stored in JSON** (issues have no owner field, and there is no separate Owner column) |
| **Link line** | `links[]` renders **under the title**, small and faint, **one link per line** (`WBS 2.3`, `Issue #1`, `Time-2`, `Spec` each on their own line). **An issue in another project shows as the first two characters of the project name plus its number** (Timesheet system replacement #2 → `Time-2`). **The data never changes** — only the display shrinks (an AI still writes "Timesheet system replacement #2" in full), with **the `Note` marker at the end** when `note` is set. The hierarchy is **title > links** (weakened by weight and size; **no borders, no chips** — borders belong to the badges). **Shown even when collapsed.** Hover underlines and darkens it. A target that does not exist (missing task, issue or project) renders with **a faint strikethrough plus a tooltip explaining why** (no crash, **the data is never removed**) |
| **Back-reference chips on the plan** (after the merge) | A plan task that issues link to gets a small `Issue #3` chip (`Issue #3 #7` for several). **Nothing is written on the plan side** — the reverse lookup is rebuilt from `links` on every render. Clicking a task name toggles collapse, so **the chip is the click target** for jumping to the issue |
| **Unanswered warning** | Both `ifIgnored` and `ifDone` empty, or `closeWhen` empty → a faint warning mark on the row (**never an error**) |
| **Counts summary** | The top right has **two rows**. Upper = **states** (`Not started N` / `In progress N` / `Closed N`); lower = **marks** (`Waiting N` / `Frozen N` / `Undecided N` / `⚠ Overdue N` / `⚠ Nudge N` / `★ Updated N`). **Every mark on the lower row counts issues**: `Undecided N` is **the number of issues that have an open question** (an issue with three open questions still counts as 1). **Only the row badge `Undecided N` counts the questions themselves** (the summary column and the tab badge also count issues). **Marks with a count of 0 are dropped** — that applies to the five (`Waiting` / `Frozen` / `Undecided` / `⚠ Overdue` / `⚠ Nudge`); **`★ Updated` is always shown, even at 0** ("nothing moved this period" is itself part of a report). **Only the upper row (the three states) is invariant** — it includes closed rows; marks ①–⑤ never appear on closed rows, so the lower row shrinks as you close things. The meta line shows **`Update period: 9/1–9/7`** (or `Update period last 7 days` when defaulted) |

**Three states, exclusive** (the first matching rule wins). They say **only how far the work has moved**.

**Waiting, frozen and open questions are marks, not states** (cross-cutting facts). So an issue can be **in progress with three open questions**, or **not started and waiting**, at the same time.
Forcing such a table into a single "undecided" or "on hold" box hides whether anything is actually moving.

**The "close when the work finishes" type needs no decision at all**:
there is **no rule** saying "write a `decision` the moment you file it". An empty `decisions` simply means **zero open questions**,
and the state follows from whether any action is done — **Not started** or **In progress**. Nothing is forced to look "decided".

---

## The four moves of issue management ⇄ JSON operations

Managing issues is four moves, repeated: **put it on the table → decide → fold it in → close**.

| Move | What you do | Keys you write |
|---|---|---|
| **Put it on the table** | Answer one of the two questions, set the due date and close condition, then file it. **Anything still to settle goes into `decisions` as an open question** (you never have to decide before filing) | Append one entry to `issues[]`: `id` / `title` / `ifIgnored` **or** `ifDone` / `due` / `closeWhen` / `priority` / `opened` (owners go in `actions[].assignee`) |
| **Decide** | Are we doing it, or not? **There may be several things to settle** | Append to `decisions[]`. Not settled yet = `{ q, since: today, decided: null, a: "" }` (an open question). Settled = fill that entry's `decided` (the day) and `a` (the approach). If the decision is "won't fix", **also** write `closed = { at, how: "wontfix", note }` |
| **Fold it in** | Put it on the plan (WBS). **A WBS leaf = this one issue** (plan, actual and effort live there); the steps inside the issue stay in `actions[]` | Add `{ "wbs": "2.3" }` to the issue's `links[]`. **Do not use `actions[].wbs`** (retired) |
| **Close** | **Confirm** the close condition is met, then close | `closed = { at, how, note }`. `note` holds **the fact you confirmed**, matching `closeWhen` |

**Wording**: "put on the table / decide / fold in / close" are **the article's words**. **The on-screen buttons are `Decide` and `Close`** (`方針を決める` / `クローズ` in Japanese). They name the same moves.

**When it gets stuck** — cross-cutting; it can happen during any of the four moves:

| Situation (the article's three reasons) | How this tool writes it | Write alongside |
|---|---|---|
| Waiting on someone who can decide | **An open question in `decisions[]`** (`decided: null`) — never a pending | Name them in `q` ("(HR to decide)") |
| Information, people, things, or timing not available | **Waiting** `pending = { kind: "waiting", … }` | `who` = who / `what` = what for / `until` = by when (**past `until` it becomes ⚠ Nudge**) |
| Deliberately parked | **Frozen** `pending = { kind: "frozen", … }` | `resumeWhen` = **the resume condition (effectively required)** / `detail` = why it is parked |

To release either, set `pending = null` (no history is kept). **A row cannot be waiting and frozen at once** (`pending` holds one).

**Division of labour between the issue table and the WBS**: the issue table holds **what and why** (`title`, the two questions, `closeWhen`).
The WBS holds **when, who, and how** (effort, dates, progress). **Never write the same thing in both.**
The link between them is the issue's **`links[]`** (`{ "wbs": "2.3" }`). **Nothing is written on the plan side** — the view derives the chip by reverse lookup.

**A note on closing**: an issue does not close automatically when all its action items are done.
Confirm `closeWhen` first. A row whose due date passed with nothing happening is closed with `how: "not_occurred"`. **Do not delete it** — "it did not happen" is itself a record.

**What does not go on the table**: risks (file them **once they happen**) and improvements (file them **once you decide to pursue them**).

---

## Reporting (the weekly check-in and ★ Updated)

★ is the mark for telling people **what moved since last time** at the weekly check-in. On screen it is called "**Updated**" (`★ Updated 3` at the top right, `★ Updated` as the Summary column header).
It is not a measure of progress — it is a mark of a **period**, the "**update period**" (`star`).

> "Updated" was chosen because one word covers **all four kinds** — completed, decided, paused, closed — and it reads as the counterpart of `⚠ Overdue`.

- **Set the update period**: the top-level `star` (e.g. `{ "from": "2026-09-01", "to": "2026-09-07" }`). Omit `to` for **up to today**. With no `star` at all, the default is **the last 7 days**.
  - **Both ends are included**: the `from` day and the `to` day are inside the period (in the example, anything that moved on 9/1 or on 9/7 gets a ★).
- **What gets a ★** (decided by the viewer, never stored in JSON):
  - Any action **completed** in the period (`done: true` with a `date` inside it; rows with `date: null` never get one)
  - Anything **decided** (`decisions[].decided`), **paused** (`pending.since` — waiting or frozen), or **closed** (`closed.at`) in the period
  - An issue with any ★ gets **a ★ on its title**, so a collapsed list still reads
- **How the check-in goes**:
  1. Before the meeting, **read the starred issues from the top** (`★ Updated 3` at the top right for the count, the `Update period: 9/1–9/7` meta line for the period).
  2. Report (you can ask an AI: "summarise this period's ★ as bullets" — example ⑨).
  3. When the meeting is over, **move `star.from` forward** (example ⑩). Next week only what moved since then is starred.
- No ★ means **nothing moved in that period**. That is not automatically bad (a deliberately frozen row, say), but an issue that goes unstarred week after week is a signal to revisit its due date and its `pending`.

---

## Checklist when filing (the discipline of putting it on the table)

Before adding an issue, check these three. **If you cannot answer even one, don't file it yet.**

1. **Can you answer one of the two questions?**
   - `ifIgnored` (shown as `Harm:`): **if ignored, when and what happens**
     Example: "on the 10/20 cutover the forms become unreadable"
   - `ifDone` (shown as `Value:`): **if done, when and what you gain**
     Example: "from November, the monthly close takes half a day"
   - These are the **"impact / benefit" columns** of a conventional issue sheet. Here the ignore-side is called **Harm** and the do-side **Value**, so the name itself says which way the column points.
   - Something that answers neither is not an issue (it's a note or a passing thought).
2. **Is the due date "the day the harm or the value shows up"?**
   - `due` is **not** when the assignee plans to work on it. Use the "when" from your answer above.
   - Example: "the production cutover will fail" → `due` is the cutover day.
3. **Did you write the close condition?**
   - Write `closeWhen` as **a state you can confirm**, not as "the work is finished".
   - Bad: "build the conversion tool". Good: "a full rehearsal of the procedure runs with zero errors".

4. **Is it already on the table?**
   - If the same project already holds an issue with **the same due date and the same wording** (e.g. "encoding"), ask the user whether to **file a new one or add an action to the existing one**.
   - **The test is whether the close condition matches.** Similar words with **a different state to confirm means a separate issue** — file it and relate the two with `links`.
   - Duplicate filings split one conversation across two rows, and both end up half-done.
   - **If you only notice after filing**, close the newer one with **`closed.how: "duplicate"`** and point at the original in `links` (see example ⑥-2).

Priority comes from **size of impact × nearness of that day** (it is stored in `priority` as a human/AI judgement; no formula is stored).

---

## Archiving (pruning old completed work)

To keep the file from growing forever, **move old completed work (plan tasks and closed issues) out of the current file**:

- **Trigger**: when completed tasks from past months (e.g., May 2026 and earlier) have scrolled into the past on the Gantt. On the issue side, when closed rows make up most of the list.
- **Steps**:
  1. **Create a backup in the same folder** (e.g., collect the moved rows into `wbs-archive-2026-05.json`; `wbs-archive-*.json` is gitignored).
  2. **Delete those completed tasks** — and issues closed long ago (`closed` set) — from `wbs.json`.
- → The current `wbs.json` stays focused on "now and the future"; history is preserved in archive JSONs.
- Scale is managed in two layers: **collapsing (display) + this archiving (data)**.
- **Before deleting a closed issue, check nothing still points at it** (another issue's `links` / `pending.who`). Deleting a referenced issue leaves a **broken link** (`scripts/check.py` catches it).

---

## Pull it out with jq first (never read the whole file)

Once issues and the plan pile up in one file, the source-of-truth JSON runs to hundreds of KB.
**For a read-only request, pull just the part you need with `jq` first — open the file only when you are going to write** (→ "What to do when a request is vague or self-contradictory", item 11).
The examples use this repo's own source of truth, `wbs_roadmap.json`. **Nothing prints when nothing matches**, so answer "0" rather than going quiet.

**① List the issues** (project, number, title, closed or not)

```bash
jq -r '.projects[] | .name as $p | .issues[]? | "\($p)\t#\(.id)\t\(.title)\t\(if .closed then "closed" else "open" end)"' wbs_roadmap.json
```

**② One issue by number** (narrow by project name first — numbers are unique only within a project)

```bash
jq '.projects[] | select(.name=="single-file-wbs 開発") | .issues[] | select(.id==37)' wbs_roadmap.json
```

**③ List the open questions** (entries with `decided: null`, and since when)

```bash
jq -r '.projects[] | .name as $p | .issues[]? | select(.closed==null) | .id as $i
       | (.decisions//[])[] | select(.decided==null) | "\($p)\t#\($i)\t\(.q)\t\(.since)"' wbs_roadmap.json
```

**④ List the waits** (who, what, until)

```bash
jq -r '.projects[] | .name as $p | .issues[]? | select(.pending.kind=="waiting")
       | "\($p)\t#\(.id)\t\(.pending.who|tostring)\t\(.pending.what)\t\(.pending.until//"no deadline")"' wbs_roadmap.json
```

**⑤ The plan leaf an issue links to** (look the `links[].wbs` id up recursively in `tasks` — you never need to know the nesting depth)

```bash
# which issue links to which leaf
jq -r '.projects[] | .issues[]? | select((.links//[])|any(.wbs)) | "#\(.id) \((.links[]|select(.wbs)|.wbs))"' wbs_roadmap.json
# pull that one leaf
jq -r --arg w "4.14" '.projects[] | select(.name=="single-file-wbs 開発")
       | [.tasks[]? | .. | objects | select(.id==$w)] | .[]
       | "\(.id)\t\(.name)\tplan \(.plan.start//"—")–\(.plan.end//"—")\tactual \(.actual.start//"—")–\(.actual.end//"—")"' wbs_roadmap.json
```

**⑥ Plan leaves that have not started** (a leaf is anything with `plan`; `actual.start` is empty)

```bash
jq -r '.projects[] | .name as $p
       | (.tasks[]? | .. | objects | select(has("plan") and (.actual.start//null)==null) | "\($p)\t\(.id)\t\(.name)")' wbs_roadmap.json
```

- The **`?`** in `.issues[]?` / `.tasks[]?` means "skip projects that lack the key". A book mixing plan-only and issues-only projects will not blow up.
- `.. | objects` walks **every object at any depth** — the same expression works no matter how deep the WBS nests.
- **A leaf is identified by `has("plan")`** (objects with `plan` are leaves; those without are roll-up nodes).
- **jq is for reading only.** Never overwrite the file with jq output (key order and custom keys get mangled). **To write, open the JSON and edit just the spot that changes.**

---

## Example requests to an AI (issue side — have it edit the JSON)

> Requests about the plan (`tasks`) are under "Plan (`tasks`) — adding and updating". The before/after below are **fragments showing only the keys that change**. The ids match `wbs_sample_issues.json` (`#1` = the in-progress migration errors, `#2` = the paper forms with an open question, `#3` = the waiting spec request, `#4` = the row closed as did-not-occur, `#6` = the frozen nightly-batch issue, `#9` = the row closed as a duplicate). `#3`, `#4`, `#6` and `#9` ship in the sample **as the result of** these requests.

### ① Filing a new issue

> "The migration test threw a pile of character-encoding errors. If we ignore it the production cutover will hit the same thing and the migration fails. Close condition: a rehearsal with zero errors."

Append one entry to `issues[]` (`id` = current max + 1):

```json
{
  "id": 10,
  "title": "Mass character-encoding errors in the migration test",
  "priority": "high",
  "opened": "2026-09-05",
  "due": "2026-10-20",
  "ifIgnored": "The same errors will hit the production cutover and the migration will fail. The impact lands on cutover day",
  "ifDone": "",
  "closeWhen": "A full rehearsal of the migration procedure runs with zero errors",
  "decisions": [],
  "pending": null,
  "closed": null,
  "links": [],
  "actions": [ { "date": "2026-09-05", "text": "Incident occurred", "assignee": "", "done": true } ],
  "note": ""
}
```

- If neither of the two questions has an answer, **don't file it — ask back**. Ask it as "**if ignored, when and what happens?**" (e.g. "on the 10/20 cutover the forms become unreadable") and "**if done, when and what do we gain?**" (e.g. "from November, the monthly close takes half a day").
- `due` is the day the harm or the value shows up. If you don't know it, ask (never invent a date).

### ② Set it to waiting (you are waiting on a person or a thing)

> "Set #3 to waiting. The dev team's spec answer, by 9/12."

before → after (`pending` only):

```json
"pending": null
```
```json
"pending": {
  "kind": "waiting",
  "since": "2026-09-06",
  "who": "Dev team",
  "until": "2026-09-12",
  "what": "the encoding-conversion spec (how gaiji and platform-specific characters are handled)"
}
```

- **Never leave `who` or `what` empty.** A wait nobody can name is a wait nobody ever follows up on.
- **`until` is what produces the nudge**: once today passes it, the row gets a `⚠ Nudge` mark. `null` is fine when no deadline was agreed, but then no nudge appears.
- **"Waiting on whoever can decide" is not a wait** → make it an open question in `decisions[]` (`decided: null`; see example ④-2).
- Leave `decisions` alone. An approach can be settled and the work still stall on a thing or an answer.
- To release, set `"pending": null`.

### ②-2 Freeze it (parked on purpose)

> "Freeze #6. Resume once the production cutover is done — migration comes first."

```json
"pending": null
```
```json
"pending": {
  "kind": "frozen",
  "since": "2026-08-27",
  "resumeWhen": "resume once the production cutover is complete",
  "detail": "parked on purpose so the migration work takes priority"
}
```

- **Never leave `resumeWhen` empty.** A freeze without one is simply forgotten.
- A freeze has no `until` — **there is nobody to nudge**, since you parked it yourself.
- To release, set `"pending": null`.

### ②-3 Wait for another issue to finish

> "#5 waits until the timesheet project's #2 is done"

When what you are waiting on is **an issue rather than a person**, put an **issue reference** in `who` (never the name as a string):

```json
"pending": null
```
```json
"pending": {
  "kind": "waiting",
  "since": "2026-09-09",
  "who": { "project": "Timesheet system replacement", "issue": 2 },
  "until": null,
  "what": "parallel verification cannot start until the cross-midnight conversion is settled"
}
```

- **Same project: `{ "issue": 2 }`**; another project: `{ "project": "…", "issue": 2 }` — the same shape as `links`.
- **When that issue closes, `⚠ Nudge` appears.** It means "the reason to wait is gone but this is still waiting", so release it and add the next action.
- `until` can be left out (the other issue's own due date already applies). Add one and an overdue nudge fires too.
- **Never repeat the same target in `links`.** The wait line itself renders as a link, so adding the same issue to `links` puts **the same destination on screen twice**. `links` is for relationships other than the wait (related, duplicate-of, WBS, external URL).
- Pointing at an issue that does not exist renders as a **broken link** with a faint strikethrough (an error in the checker).

### ②-4 List everything that needs nudging (waits and open questions)

> "List everything that needs nudging"

**Read only** — change nothing. Collect **both waits and open questions** (`⚠ Nudge` is one mark):

```
Waiting
  Timesheet system replacement #2 Cross-midnight punches break in the data migration
    Dev vendor owes "the revised date-boundary spec" by 9/8 (1 day past)
Open questions
  Migration project #2 Whether to migrate the legacy paper forms (business team to decide)
    wanted settled by 9/4 (5 days past; open for 16 days)
```

- Three triggers: **a wait past `pending.until`**, **an open question past `decisions[].until`**, and **a wait whose target issue has closed**.
- Anything with `until: null` is out of scope; adding "N waits and N open questions with no deadline" as a count is still helpful.
- Closed issues are left out (nothing left to nudge).
- **If nothing matched, say "nothing needs nudging"** — never return an empty answer silently.

### ③ Closing as resolved

> "Close #1 as resolved — the rehearsal had zero errors."

before → after (`closed` only):

```json
"closed": null
```
```json
"closed": {
  "at": "2026-09-20",
  "how": "resolved",
  "note": "Ran all steps in the first rehearsal and confirmed zero conversion errors"
}
```

- Write `note` **against `closeWhen`**. If `closeWhen` says "no errors", `note` records **the confirmed fact** — "confirmed zero errors". "We worked on it" is not grounds to close.
- If `pending` is still set, reset it to `null`.

### ④ Decide "won't fix" and close (two places to write)

> "Decide #2 as 'won't fix' and close it — the business side will change their process for the paper forms."

**Settle the open question and close in the same move** (with only one of them, the reason for not doing it is lost):

```json
"decisions": [
  { "q": "Whether to migrate the legacy paper forms (business team to decide)", "since": "2026-08-24",
    "decided": null, "a": "" }
],
"closed": null
```
```json
"decisions": [
  { "q": "Whether to migrate the legacy paper forms (business team to decide)", "since": "2026-08-24",
    "decided": "2026-09-09", "a": "Won't fix. The business side will change their process for paper forms" }
],
"closed": { "at": "2026-09-09", "how": "wontfix", "note": "Agreed with the business team; removed from the migration scope list" }
```

- **If an open question already covers it, settle that one** — never stack the same question twice.
- With no open question, append one entry (`q` = what was settled, `since` = today, `decided` = today, `a` = the approach).

### ④-2 Stack something still to be decided

> "Add 'build the converter in-house or use an existing library' to #1 as an open question, to settle by 9/16"

Append one entry with **`decided: null`** to `decisions[]`:

```json
"decisions": [
  { "q": "Approach", "since": "2026-09-05",
    "decided": "2026-09-07", "a": "Investigate the cause and fix the conversion step" }
]
```
```json
"decisions": [
  { "q": "Approach", "since": "2026-09-05",
    "decided": "2026-09-07", "a": "Investigate the cause and fix the conversion step" },
  { "q": "Build the converter in-house or use an existing library", "since": "2026-09-09",
    "until": "2026-09-16", "decided": null, "a": "" }
]
```

- **When a deadline is given** ("by 9/16"), **put it in `until`**. Past it the row gets `⚠ Nudge` (see example ②-4). With none given, leave `until` out (`null`).
- `since` is **today** — the clock that measures how long it has been open (the screen shows the elapsed days).
- **Never fill `a` before it is settled.** That happens only when `decided` goes in.
- **You never split the issue for this.** Three things to settle means three entries, not three issues.
- **The state does not change** (an open question is a mark, not a state).

### ④-3 An open question got settled

> "#1's 'in-house or existing library' is settled — we're using the existing library"

Put **`decided` (the day) and `a` (the approach)** into that entry. Never add another:

```json
{ "q": "Build the converter in-house or use an existing library", "since": "2026-09-09",
  "decided": null, "a": "" }
```
```json
{ "q": "Build the converter in-house or use an existing library", "since": "2026-09-09",
  "decided": "2026-09-09", "a": "Use the existing conversion library (no in-house build)" }
```

- **Never rewrite `q` or `since`** — they record how long it stood open.
- Once settled it leaves the band and joins the summary as **`Decision: Use the existing conversion library (9/9)`**.
- **If the decided day falls in the update period, it earns a ★** (see "Reporting").
- To **change** an approach later, rewrite that entry's `a` and give `decided` the new day. Add a line in `note` if you want the previous one on record (there is no history key).

### ④-4 Sweep up the open questions

> "Sweep up the open questions, longest-standing first"

**Read only** — change nothing. Gather every `decisions` entry with **`decided: null`** across all projects and sort by **days since `since`, longest first**:

```
20d Timesheet system replacement #1 Keep the current rounding rule or move to the statutory one (HR to decide)
16d Migration project #2 Whether to migrate the legacy paper forms (business team to decide)
12d Migration project #5 Whether to provision a second verification environment (PL to decide)
 2d Migration project #1 Build the converter in-house or use an existing library
 2d Migration project #1 Substitute characters for the legacy gaiji, or handle them case by case
 2d Timesheet system replacement #4 Round the carry-over as before, or to the statutory rule
```

- Count **entries**, not issues (one issue may hold several).
- Leave out open questions on closed issues (nothing left to nudge).
- **Longest-standing on top.** The list exists to take things to whoever can decide, so a `q` that names them ("(HR to decide)") tells you where to take it.

### ⑤ Adding the next action

> "Add the next action on #1 for 9/21 — review the rehearsal results, owner A."

Append one entry to `actions[]`:

```json
{ "date": "2026-09-21", "text": "Review the rehearsal results", "assignee": "A", "done": false }
```

- If the date isn't settled, use `"date": null` (= being scheduled). **Never fill in a made-up date.**
- Mark it done with `"done": true`. If its date falls **inside the reporting period (`star`)**, that row automatically gets a ★ (never write ★ by hand).

### ⑥ Closing as "did not occur"

> "#4 passed its due date and nothing happened — close it as did-not-occur."

```json
"closed": null
```
```json
"closed": {
  "at": "2026-08-31",
  "how": "not_occurred",
  "note": "The 8/31 month-end batch finished on schedule and never overlapped the rehearsal slot"
}
```

- **Keep the row.** "We worried and it didn't happen" is worth recording.
- If the due date merely passed and the impact can't be judged yet, don't close it — revisit `due`.

### ⑥-2 Close as a duplicate

> "#9 is the same thing as #1 — close it as a duplicate"

**Write `closed` and `links` together** (without the pointer, the closed row is a dead end):

```json
"closed": null,
"links": []
```
```json
"closed": { "at": "2026-09-09", "how": "duplicate", "note": "Same encoding issue as #1; followed there from now on" },
"links": [ { "issue": 1 } ]
```

- **What makes it a duplicate is the close condition (`closeWhen`) being the same.** Sharing a word in the title (e.g. "encoding") is not enough — **if the state you want to confirm differs, they are separate issues**. Then do not close as a duplicate; just **relate them** with `{ "issue": N }` in `links`.
- **`links` is required** (`{ "issue": N }`, or `{ "project": "…", "issue": N }` across projects). Without it the checker reports an error.
- **Keep the one that has moved, not the one filed most recently** — whichever has the actions and decisions on it survives; the other closes as a duplicate.
- If the one being closed carries useful actions or open questions, **move them across first**; never drop them.
- **Check whether anything points at the issue you are closing**: if another issue's `links` or `pending.who` refers to it, **repoint them at the surviving issue before closing** (otherwise something is left waiting on a dead end). The checker cannot catch this — the reference itself is still valid — so **look for the pointers before you close**.
- This is where rule 4 of "Checklist when filing" (**is it already on the table?**) lands: notice before filing and you never file; notice after and you close it this way.

### ⑦ Record that it went into the plan (WBS)

> "Link #3 to WBS 2.3"

Append one entry to the issue's `links[]` (**never use `actions[].wbs` — it is retired**):

```json
"links": [ { "issue": 1 } ]
```
```json
"links": [ { "issue": 1 }, { "wbs": "2.3" } ]
```

- The target is an id in **the same project's `tasks`**. An id that does not exist renders as a **broken link** (faint strikethrough).
- **A WBS leaf = this one issue.** Effort, plan and actual live on the plan side and are never copied into the issue. The steps inside the issue stay in `actions[]`.
- Nothing is written on the plan side. The `Issue #3` chip that appears on a plan row is built by **reverse lookup** from `links`.

### ⑦-2 Link to another issue

> "Link the timesheet project's #2 to #3 as a related issue"

Add a **cross-project** entry to `#3`'s `links[]` (the issue in the project you are in):

```json
"links": [ { "wbs": "2.3" } ]
```
```json
"links": [ { "wbs": "2.3" }, { "project": "Timesheet system replacement", "issue": 2 } ]
```

- **Same project: `{ "issue": 2 }`.** Another project: `{ "project": "…", "issue": 2 }`. The key names tell them apart.
- **One side is enough.** The view does not mirror links automatically — that would duplicate the data. Add it on the other side only when you actually want to walk it both ways.
- **If you rename a project, fix every link that points at that name** (the name is the only handle).

### ⑦-3 Check for broken links

> "Check whether any links are broken"

Reading alone will not tell you — run the bundled checker:

```
uv run python scripts/check.py wbs.json
# where uv is not installed
python3 scripts/check.py wbs.json
```

- What it looks at: whether link targets exist (project name, issue number, task id) / the shape of `links` / duplicate numbers / dates and enums / waits with nobody recorded and freezes with no resume condition / leftover legacy keys (`sheets`, issue-level `assignee`, `actions[].wbs`).
- **Exit code 1 when there are errors.** `--quiet` prints only the counts.
- Findings are reported as **`<project> / #<number> / <field>`** rather than line numbers, so you can go straight to the fix.

### ⑦-4 When the leaf to fold into does not exist yet

> "Fold #2 in" (no matching WBS leaf yet)

**Add one leaf to the plan, then tie it to the issue with `links`.** Ask the user for `qty` / `hours` / `plan` first — never invent them.

Add a single leaf to the project's `tasks` (number the `id` so it **does not collide within the project**; `name` is the issue title):

```json
{ "id": "2", "name": "Conversion tool", "children": [
  { "id": "2.3", "name": "Encoding conversion", "qty": 1, "hours": 16, "assignee": "Piguo",
    "plan": { "start": "2026-09-14", "end": "2026-09-18" },
    "actual": { "start": null, "end": null }, "note": "" }
] }
```
```json
{ "id": "2", "name": "Conversion tool", "children": [
  { "id": "2.3", "name": "Encoding conversion", "qty": 1, "hours": 16, "assignee": "Piguo",
    "plan": { "start": "2026-09-14", "end": "2026-09-18" },
    "actual": { "start": null, "end": null }, "note": "" },
  { "id": "2.5", "name": "Whether to migrate the legacy paper forms", "qty": 1, "hours": 8,
    "assignee": "Sato",
    "plan": { "start": "2026-09-24", "end": "2026-09-25" },
    "actual": { "start": null, "end": null }, "note": "" }
] }
```

Then **add it to issue `#2`'s `links`** — never leave the new leaf unreferenced:

```json
"links": []
```
```json
"links": [ { "wbs": "2.5" } ]
```

- **If the project has no `tasks`**, create `tasks: []` and **put the leaf straight in** (no parent needed; number the `id` from `"1"`).
- Add **one leaf only.** The steps inside the issue stay in `actions[]`; never create WBS children for them.
- **`qty` defaults to 1** (most work has no quantity to reason about), so the only things you actually need to ask for are **`hours` and `plan`**.
- The leaf's **`name` can be the issue title verbatim.** Exceeding the plan side's "about 14 full-width characters" guideline is fine — it only truncates in the list, and the full text shows on hover. Shorten it if you prefer and reach the detail through the issue.
- **Never fill in placeholder numbers** for `hours` / `plan` (see rule 12 of "What to do when a request is vague").

### ⑧ Revisiting priorities

> "Revisit the priorities by size of impact × nearness of the due date."

Read each issue's `ifIgnored` / `ifDone` (size of impact) and `due` (nearness), then rewrite `priority`:

```json
"priority": "mid"
```
```json
"priority": "high"
```

- Rewrite only the value of `priority`. **Do not store a formula or a score in a new key** (`priority` is a human/AI judgement).
- Put the reasoning in `note` as one line, or just say it in the conversation.
- Leave closed issues (`closed` set) alone.

### ⑨ Report this period's ★

> "Summarise this period's ★ as bullets"

**Read only** — change nothing. Take the period from `star` (or the last 7 days) and collect the issues matching the ★ rules, grouped per issue:

```
#1 Mass character-encoding errors in the migration test
   9/5 incident → 9/7 decided the approach (investigate the cause, fix the conversion step)
#3 Encoding-conversion spec still unanswered by the dev team
   9/5 sent the questionnaire, decided the approach → 9/6 set to waiting (dev team's answer, by 9/12)
#7 Make the migration tool's log searchable on screen
   9/5 decided "won't fix" and closed it
```

- To avoid missing anything, look **not only at actions but also at `decisions[].decided`, `pending.since`, and `closed.at`**.
- Leave out anything outside the period. Issues with no ★ do not go in the report (answer separately if asked).
- **If nothing matched, say "no issues moved in this period"** — never return an empty answer silently.
- **Close with one to three lines of "watch out"**: `⚠ Nudge` (waits and open questions), `⚠ Overdue`, and long-standing open questions. ★ means "moved", so **what has not moved but needs a nudge never shows up in it**. For example:

```
Watch out
  Nudge 2 (Timesheet #2 spec 1 day past / Migration #2 open question 5 days past)
  Overdue 2 (Migration #2, Timesheet #1)
  1 open question standing 20 days (Timesheet #1, rounding rule)
```

### ⑩ Move the update period forward

> "The check-in is over — move the update period to 9/8–9/14"

Rewrite the top-level `star`:

```json
"star": { "from": "2026-09-01", "to": "2026-09-07" }
```
```json
"star": { "from": "2026-09-08", "to": "2026-09-14" }
```

- **When asked to "move it to next week"**: set `from` to **the day after the current `to`** (9/7 → 9/8) and `to` to **`from` + 6 days** (9/8 → 9/14). Because both ends are included, that is a full seven days.
- Omit `to` for **up to today** (`{ "from": "2026-09-08" }`) — useful for watching progress before the next check-in.
- `star` is the only thing you may rewrite. **★ itself (which rows get one) is never stored in the data.**

### ⑪ Add a project

> "Add a project for the timesheet system replacement"

Append one entry to the `projects` array (it may start empty):

```json
{ "name": "Timesheet system replacement", "issues": [] }
```

- **Keep project names unique within the book** — cross-project links point at the name.
- A project separates **bodies of work**, not kinds (incident / reminder / improvement) — those belong mixed in one table.
- If the reporting unit differs (you want separate update periods), split the **file**, not the project.
- A project may hold only `tasks`, only `issues`, or both — all valid.

### ⑫ Read the summary and report

> "Look at the summary and tell me which projects moved this week"

**Read only** — change nothing. Count `★ Updated` and `⚠ Overdue` per project:

```
Timesheet system replacement   ★ Updated 1 (#2 cross-midnight conversion, decided 9/2) / ⚠ Overdue 1 (#1 still has 1 open question, past 9/3)
Migration project              ★ Updated 3 (#1 investigation, #3 set to waiting, #7 closed as won't fix) / ⚠ Overdue 1
```

- "This week" comes from the **update period** (`star`, or the last 7 days). Count **across projects**.
- Say so when a project has no ★ — "nothing moved this week" — rather than omitting it.
- **With no late tasks, write "no tasks are running late"**; **with no `tasks` in a project, write "no plan (WBS), so lateness cannot be judged"**. Never leave either out silently.
- **Close with the same "watch out"** as ⑨: `⚠ Nudge`, `⚠ Overdue` and long-standing open questions across all projects. Never end a report on what moved alone.

### ⑬ Move an issue to another project

> "Move #3 to the timesheet system replacement project"

Remove it from the source project's `issues` and append it to the destination's. **Renumber `id` for the destination** (`id` is unique per project):

```json
"id": 3
```
```json
"id": 4
```

- Renumber only when moving. **Never renumber within a project** — minutes and chat threads refer to those numbers.
- **Fix the links that pointed at it**: a same-project `{ "issue": 3 }` becomes `{ "project": "Timesheet system replacement", "issue": 4 }`. Drop any `{ "wbs": … }` the moved issue carries if the destination project has no such task.
- When you are done, run `uv run python scripts/check.py` (or `python3 scripts/check.py`) to confirm nothing is broken.
- Leaving a line in `note` ("moved from the migration project") makes the number change traceable.

### ⑭ Show the plan behind an issue

> "Show me the plan for #3 (WBS 2.3)"

**Read only** — change nothing. Take `{ "wbs": … }` from the issue's `links`, walk **the same project's `tasks`**, and read that leaf's `plan` / `actual`:

```
#3 Encoding-conversion spec still unanswered by the dev team
  WBS 2.3 Encoding conversion (owner Piguo, 16h)
    Planned 2026-09-14 – 2026-09-18
    Actual  not started
```

- Read the **plan-side values** (`plan.start` / `plan.end` / `actual.start` / `actual.end` / `qty` / `hours` / `assignee`). **Never copy them onto the issue.**
- Effort formulas and progress are specified under "Computation". Do not invent a calculation here.
- With no `{ "wbs": … }` in `links`, answer "it is not on the plan yet" — do not fold it in unasked (see example ⑦-4).

### ⑮ List issues with open questions linked to late tasks

> "List the issues with open questions that are linked to tasks running late"

**Read only.** Collect in two passes:

1. **Decide lateness on the plan side.** The rule is under "Computation" (deadline slip = **today > `plan.end` and not finished** — no `actual.end`; progress slip = `PV > EV`). Do not re-derive a rule here.
2. Match the late leaves' `id`s against each issue's `links` entries, and keep only the issues that **still have an open question** (some `decisions` entry has `decided: null`).

Reading `wbs_sample_issues.json` as of 2026-09-07, no leaf is late, so the answer is **nothing matched**:

```
No tasks are running late (Migration project plans end 9/18, 10/2 and 10/20 — none reached yet).
Timesheet system replacement: no plan (WBS), so lateness cannot be judged.

For reference — issues past their due date with an open question, not linked to the plan:
  Migration project              #2 Whether to migrate the legacy paper forms (due 9/4)
  Timesheet system replacement   #1 Whether to keep the current punch-rounding rule (due 9/3)
```

- **The numbers above are specific to the sample.** With real data, **always recompute against today's date** — never copy the example.
- **With nothing matching, write "no tasks are running late"**; **with no `tasks` in a project, write "no plan (WBS), so lateness cannot be judged"**. Never leave either out silently.
- **"Undecided" is a mark, not a state.** One `decisions` entry with `decided: null` is enough (the state is still Not started / In progress / Closed).
- **This takes a single read because the plan and the issues live in one JSON** — no crossing files.
- If asked with different state conditions ("include the ones waiting"), follow them. **Change nothing in the JSON** (see rule 11 of "What to do when a request is vague").

### ⑯ Record that a plan task finished

> "2.4 is done"

**Write the actual on the plan side** (the second exception where this tool edits `tasks`). The default date is **today**:

```json
{ "id": "2.4", "name": "Migration rehearsal", "qty": 1, "hours": 24, "assignee": "Piguo/A",
  "plan": { "start": "2026-09-24", "end": "2026-10-02" },
  "actual": { "start": null, "end": null }, "note": "" }
```
```json
{ "id": "2.4", "name": "Migration rehearsal", "qty": 1, "hours": 24, "assignee": "Piguo/A",
  "plan": { "start": "2026-09-24", "end": "2026-10-02" },
  "actual": { "start": "2026-09-07", "end": "2026-09-07" }, "note": "" }
```

- **`actual.end` = today.** **If `actual.start` is empty, set it to today as well** (the same behaviour as the plan side's done toggle — never leave a finished row with no start date).
- **Do not stop when it lands before the planned start.** Say "recorded as finishing ahead of the plan (start 9/24)" and **carry on**.
- **If the user gives you the real start date, use it** ("we actually started on 9/2" → `actual.start` = `2026-09-02`).
- Only `actual` changes. **Never move `plan`** — rescheduling is a separate request; append one line to `_planLog` (→ "Plan (`tasks`) field definitions").
- Progress, effort and the inazuma line are **computed**, so leave them alone (the formulas are under "Computation").

### Other common requests

- "List the issues past their due date that still have an open question" → **read only** (some `decisions` entry has `decided: null`, `due` < today, `closed: null`). Change nothing.
- "Find waits with nobody recorded" → rows where `pending.kind` is `"waiting"` and `who` or `what` is empty.
- "List the waits that need nudging" → **read only** (`kind: "waiting"` and `until` < today). Name who, what, and how many days past.
- "Reopen this issue" → set `"closed": null`.
- "Change the owner of the next action on #1 to Sato" → rewrite that `actions[].assignee`. **Issues have no owner field**, so the `Owner:` in the collapsed row's next-move line follows automatically.

---

## Broken input (graceful degradation)

**Policy: broken input must never crash the viewer.** Invalid values render as ignored / 0 / empty.
Avoid the following when entering data (nothing crashes, but display degrades).

**Shared**

| Input (broken) | What the viewer does |
|---|---|
| Invalid date (not `YYYY-MM-DD`, or **outside 1900–2099**) | **Ignored** (`plan` / `actual` / `due` / milestones / holidays alike). The date cell shows `—` |
| `projects` not an array, empty, or elements not objects | **Only the plan-only legacy shape `{ project, tasks }` is converted.** The **issues-only legacy shapes (`sheets`, a top-level `issues`) are not read** (see "The backward-compatibility promise"), so such a file renders as an **empty view** |
| `projects[].name` missing or duplicated | Rendered as an unnamed tab. **Duplicates make links unresolvable**, so the checker reports them as errors |
| **Duplicate `id`** within one project | Collapse keys collide (rows with the same id open and close together) |
| Top level `null`, a number, or otherwise not an object | Empty view (no crash) |
| Invalid JSON (drag & drop / file pick / reload) | An alert (never a silent failure) |
| Strings containing `<script>` etc. | Escaped on render (raw values never reach attributes) |
| `holidays` not an array, or an element with an invalid date | **Ignored** (no red text / no pink column; no crash) |
| Out-of-range / colorless / invalid-date milestones | **Not drawn** (ignored) |
| Milestone without `label` | **Rendered with an empty label** (no crash) |
| Milestone `color` not `#hex` | **Ignored, default color** (prevents attribute injection) |

**The plan (`tasks`)**

| Input (broken) | What the viewer does |
|---|---|
| `tasks: []` (empty) | Empty view (no crash) |
| Active but `plan.end` missing | Progress **0%** (avoids NaN) |
| End < start (inverted period) | Bar not drawn / looks odd |
| Actual start in the future | Progress 0 |
| `qty` / `hours` missing or 0 | Effort 0 (shown empty) |
| Decimal `qty` (e.g., 0.5) | Decimal person-days (1.5 etc.) |
| Nesting beyond 4 levels | Colors stop at **L3** (no breakage) |
| `_progress` not a number | **Ignored** (falls back to time-based progress). A number is rounded to the nearest 10% and **clamped to 0–100** |
| A broken element inside `_planLog` | That element alone is **ignored** (the rest of the history still renders) |

**The issues (`issues`)**

| Input (broken) | What the viewer does |
|---|---|
| `issues` empty | Empty view (no crash) |
| `priority` outside the 3 values | Treated as `"mid"` |
| `pending.kind` outside the known values | No mark at all (`pending` is drawn as absent). The checker reports it as an error |
| An invalid `pending.until` | Treated as **a wait with no deadline** (no nudge mark) |
| `closed.how` outside the known values | "Closed" with no sub-label |
| Issue-level `assignee` (legacy data) | **Never read, ignored** (owners live only in `actions[].assignee`; there is no Owner column). Not stripped on save |
| `decisions` not an array, or an element that is not an object | That element alone is **ignored** (the rest still render). The checker reports it as an error |
| An empty `decisions[].q` | **In read mode** it is rendered nowhere — neither in the band nor as a decision line (an entry with no question means nothing). **In edit mode it is shown**, so a blank entry added with `+ Decision` can be filled in on the spot. **The `Undecided N` count is unaffected** (facts are counted as they are) |
| An invalid `decisions[].decided` date | **Treated as undecided** (the date shows as `—`) |
| `links` not an array, or an element in none of the four forms | That element alone is **ignored** (the others still render). The checker reports it as an error |
| A `links` target that does not exist (task, issue, project) | **Faint strikethrough plus a tooltip.** Never removed, never a crash |
| A `links` `url` that is not `http(s)` | **Rendered as a broken link** (faint strikethrough plus a tooltip, **not clickable**). Raw values never reach attributes |
| `star` malformed (not an object, bad dates, `from` > `to`) | **Ignored — falls back to the default last 7 days** (today included) |
| `actions` not an array, or elements not objects | **Ignored** |

- Fixtures: **plan side** = `tests/正常_*.json` / `tests/異常_*.json` (index: `tests/INDEX.md`); **issue side** = `tests/issue/正常_*.json` / `tests/issue/異常_*.json` (index: `tests/issue/INDEX.md`).
- "Never crashes" is verified by loading every test file in headless Chromium and asserting **no JS errors and no `NaN`**.

---

## Known limitations

- **Initial rendering slows with thousands of rows** (everything is rebuilt at once). Mitigation = collapsing + archiving into a separate file. Virtualization only if it ever truly hurts.
- **Duplicate `id`s share collapse state** (they open and close together). Keep `id` unique within a project. **Identically-named projects** collide the same way, so keep project names unique too.
- **`null` elements inside arrays** (null tasks/projects) are unsupported (a non-object top level degrades to an empty view).
- **No history of waits or freezes.** `pending` holds only the current one; how often or how long it was stuck is not kept (write it in a `_` key if you need it). **The schedule-change history (`_planLog`) exists on the plan side only.**
- **No dependencies between issues** ("#1 can't move until #3 finishes" goes in `note`). The plan side has no predecessor/successor links either.
- **Issue → plan and issue → issue are both in-page moves** (writing `#wbs=` / `#issue=` into the URL). **Only external URLs (`{ title, url }`) open a new tab.**
- **Links are one-way.** Writing `{ "issue": 2 }` does not make this issue appear on the other one; add it on both sides if you want to walk it both ways. **Plan → issue is the exception**: the view derives the chip from `links` (the data stays one-way).
- **Renaming a project breaks the links that point at that name** (there is no immutable key). Run `scripts/check.py` after a rename. **Renaming a project or editing an id in edit mode also resets collapse state** (collapse keys derive from name/id).
- **Multi-line `note` values get flattened to one line** when touched in the plan side's edit mode (inputs cannot hold line breaks). The issue side's `note` is a textarea and keeps newlines.
- **No keyboard navigation or screen-reader support** (a mouse-first personal tool).

## Notes

- Chromium-based browsers (Chrome recommended), `file://` assumed (it uses the File System Access API).
- Your own real data `wbs.json` is **gitignored by default** (to prevent accidental commits), as is `wbs-archive-*.json`.
- Two samples: **`wbs_sample.json`** = the plan (`tasks`) only, the classic sample; **`wbs_sample_issues.json`** = plan and issues (fictional, **a two-project book**; the first project shows **a plan (`tasks`) and issues living together**, and the set covers all three states and all six marks). This repository's own source of truth is in the final section, "The source of truth for this repo".
- This is a public repo: samples and screenshots use **fictional names only**. No real company names, project names, personal data, or rates.

---

## Dev workflow: the `/pm` skill (issues × plan maintenance) — full reference

A skill that keeps this tool's own development artefacts consistent with AI. **This section is the single source**
(the user's own `~/.claude/commands/pm.md` reads this section, and locally `~/.claude/CLAUDE-single-file-wbs.md` is a symlink to this file; this repo gitignores `.claude/`, so no command definition is checked in).
Pick the mode **from the context of the conversation** (no need to type `/pm` explicitly). The human judges; the skill drives and records.

**The source of truth is the JSON this merged viewer reads** (`projects[].issues` and `projects[].tasks`).
Issues and the development plan live in the same file, and are **never duplicated into GitHub Issues** (you would lose track of which one is real).
Which file is the source of truth is decided **once per repository** and declared in that repo's `CLAUDE.md`.

### Split of truth
- **An issue (`issues[]`) = what, why, and when it is done**; **a plan leaf (a `tasks` leaf) = when, who, how much**. The connecting key is the issue's **`links[].wbs`** (the authoritative statement is at the end of "The four moves of issue management ⇄ JSON operations").
- **One issue = one leaf.** The steps inside an issue go in the issue's **`actions[]`**; **never create child tasks in the WBS** (→ the first row of "Rules that keep an AI from guessing").
- The formats are specified by the "Data (`wbs.json`)", "Plan (`tasks`) — adding and updating" and "Computation" sections above.

### 4 modes (the AI picks from context)

1. **File** ("make this an issue", "put it on the table", or agreement after a discussion):
   - Discussion frame: is it worth putting on the table / **altitude × artifact** (a different altitude or a different artifact means a different tool) / which version and stage.
   - It is settled when the human says "**put it on the table**".
   - **Run the filing checklist** (→ "Checklist when filing"): can you answer one of the two questions / is `due` the day the harm or value appears / did you write `closeWhen`. **If even one has no answer, do not file — ask.**
   - **Dedup is judged by "is the close condition (`closeWhen`) the same"** (→ "Checklist when filing", item 4). Even with the same words in the title, a different state to confirm is a different issue. If one already exists, ask whether to **file a new one or add an action to the existing one**. If you notice afterwards, close the new one with `closed.how: "duplicate"` and point `links` at the original (→ example ⑥-2).
   - **Add one issue**: append to `issues[]` with `id` (current max + 1), `title`, `priority`, `opened`, `due`, `ifIgnored` **or** `ifDone`, `closeWhen`, `decisions`, `pending: null`, `closed: null`, `links`, `actions`.
   - **AI starter memo (optional)**: write only **pointers that do not rot** into the issue's `note` (or `_ai`) so a later session starts fast — entry files, verification commands, constraints (what not to touch), out of scope. **Never write a step-by-step plan** (the HOW is assembled from the actual code at start time; prompts rot the moment they are written, problems and close conditions do not).
   - **When transcribing from a GitHub Issue, always read the comments too**, not just the body (`gh issue view <N> --comments`). **Acceptance criteria, decisions and rejections the author added later usually live in the comments**, so copying the body alone leaves `closeWhen` stale. What was settled in comments goes into `decisions` (`decided` and `a`); acceptance criteria go into `closeWhen`.
   - **Take `priority` from the value stated in the body** (never re-estimate it yourself). **For a range such as `mid–high`, take the upper end** (= `high`). If the body states no priority, use the default `mid` and add one line to your reply: "the body states no priority, so I used mid".
   - **Reflect into the plan**: if needed add **exactly one leaf** to `tasks` and write `{ "wbs": "<the new id>" }` into the issue's `links` (→ example ⑦-4). **Ask the user** for `qty` / `hours` / `plan` (never put in placeholder numbers).
2. **Start** ("started it"): set **`actual.start` on the matching leaf to today** (→ "Plan (`tasks`) — adding and updating ①"). If no leaf exists yet, do ⑦-4 first. **Find which leaf with `jq`** (→ "Pull it out with jq first", recipe ⑤).
   - **Do not also record the start in the issue's `actions[]`** (never keep the same fact on both the plan and the issue side — the last bullet of "Handling principles"). That work started is visible from the plan's Actual column and its back-reference chip. `actions[]` is only for **steps inside the issue** ("held the meeting", "sent the questionnaire").
3. **Done** ("finished", "close it"): **check what is still open (unfinished actions, open questions, waits) with `jq` before closing** (→ "Pull it out with jq first", recipes ②③④). **Auto-verify** (never close on "should be fixed") → **`actual.end` on the leaf** (and `actual.start` too if empty) ＋ **close the issue** (`at` / `how` / `note` = **the fact you confirmed**, matching `closeWhen`). Reset `pending` to `null` if it is still set. **If unfinished actions or open questions remain, show the discrepancy and ask before closing** (→ "What to do when a request is vague or self-contradictory", item 14).
4. **Auto-file on failure** (test / CI failure): **dedup** (search existing unclosed issues by the error signature; judged by the same close condition) ＋ **threshold** (file only after N consecutive failures, to reject flakes) → append one issue to `issues[]` (repro / log / expectation = `closeWhen`). Add a leaf plus `links` if needed. ※ For a client-only tool (no telemetry), this covers **test failures only**.

### Done is auto-verified
Machine-checkable close conditions are **run** (never report or close on "should be fixed"):

- **The regression nets are GREEN**: the merged viewer's e2e and the plan-side e2e it was built from, both passing.
- **`uv run python scripts/check.py <the source-of-truth JSON>`** with zero errors (duplicate numbers, dates, enums, link targets, leftover legacy keys).
- PII grep / specific behaviours.
- Anything needing human eyes (**the save-path smoke test on a real browser**, look and feel, UX) is **human-confirmed**.
- **This repository's concrete commands are collected in the final section, "The source of truth for this repo".** Procedures containing absolute paths or internal names never go in a public file (→ Guardrails).

### Compatibility path for repos still using GitHub Issues (pre-migration)
**If you are starting fresh, use the JSON issue management above.** Repos that still keep GitHub Issues as their source of truth may continue as before — this is the compatibility path until they migrate.

- **Split of truth**: Issue = problem / challenge / done-criteria (WHAT / WHY / DONE); WBS = the work breakdown needed (HOW / WHEN). Linked by `#N`. **1 issue → N work items** (the WBS parent node = the issue title, children = the breakdown, `#N: URL` in the parent's `note`).
- **Dedup**: `gh issue list --state all --search "<keywords> in:title,body"`. If one exists, append to it.
- **Creating an issue**: background / problem / proposal / open points / done-criteria (acceptance criteria as checkboxes) / priority / related (#).
- **Start** = `actual.start` on the matching WBS leaf; **Done** = auto-verify → close the issue (with a summary comment of the verification) ＋ `actual.end`.
- **Where the two rules disagree, the JSON side wins.** The GitHub Issue path is a pre-migration compatibility route, not a second co-equal rule.

### Settings (decided per repository)
- **The source-of-truth filename** (issues and the development plan both live there).
- **Issue title convention**: a category prefix such as `【表示】`/`【編集】` is welcome (aim for ~30 full-width characters).
- **Versioning**: backward-compatible features = MINOR / bug fixes = PATCH / breaking or identity changes = MAJOR (once). Example: **adding issue management is MAJOR (`v1.4` → `v2.0`)** — it changes what the product is, so it spends the "once" allowance.

### Guardrails (every time)
- **PII grep before push** (usernames, e-mail, absolute paths, real names, internal names) / commit e-mail = **GitHub noreply** / `git push --force` is forbidden.
- Samples and screenshots use **fictional names only**. Secrets such as `.env` are never edited by the AI — ask the user.
- **Real data carries the same rule** (including `wbs_roadmap.json`). The source-of-truth JSON is committed to a public repo, so it needs the same discipline as the samples: never write an employer or customer name, an internal system name, a machine name, a username or an absolute path into an issue's `title`, `note`, `actions[].text` or `_ai`. Anything like that belongs in your local `wbs.json` (already gitignored).
- **Never report or close on "should be fixed"** (always run the auto-verification). Keep the output short and **leave one line explaining the judgment**.
- **When in doubt, don't edit — ask** (→ "What to do when a request is vague or self-contradictory"). Offer two or three options with one recommendation.

---
## The source of truth for this repo

**This repo's source of truth is `wbs_roadmap.json`** — `projects[0]` holds **both the development plan (`tasks`) and the issues (`issues`)**. (repo: `piguo45/single-file-wbs`)

- Every issue, TODO and open question for single-file-wbs goes into that file's `issues[]`; the development plan (when, who, how much) goes into the same project's `tasks`. **Never copy effort or dates onto the issue side** (the plan is the plan; issues carry the what and why).
- **GitHub Issues are not used for new work** (never keep the source of truth in two places). On 2026-09-11 the 26 open issues were moved into `issues[]`.
- **GitHub Issues remain as an inbox from outside** (this is a public repo, so anyone can file one). When one arrives, **copy its content into `issues[]`** and add `{ "title": "GitHub #N", "url": "…" }` to `links`. From then on it is tracked in the JSON.
- The rule is: **declare it per repository, one per repository.** Other repos may well use GitHub Issues as their source of truth — follow the declaration in each repo's `CLAUDE.md` (→ the compatibility path in "Dev workflow: the `/pm` skill").
- Your own real data in `wbs.json` is gitignored (it is not the source of truth — it is your local scratch file).

**This repo's auto-verification (the concrete commands behind `/pm`'s "Done is auto-verified")**

```
uv run python tests/e2e/run_all.py         # plan-side regression net (golden + pixel)
uv run python tests/e2e_issue/run_all.py   # issue-side e2e
uv run python scripts/check.py wbs_roadmap.json wbs_sample_issues.json
```

## Where the merge stands (v2.0.0 — done)

**The plan (WBS) and the issues are merged into one HTML page, one JSON and one `CLAUDE.md`** (2026-09-11, `v2.0.0`).
Adding issue management **changes what the product is**, so the MAJOR version was raised (`v1.4` → `v2.0.0`; author's decision).

- The data shape and the issue renderer were settled first in the sister repo single-file-issue (a private repo) as v0.1–v0.2 and then **moved here**. That repo is **frozen as the design record** (the primary records are [`docs/design/brief-v0.1.md`](docs/design/brief-v0.1.md), [`docs/design/brief-v0.2-unified.md`](docs/design/brief-v0.2-unified.md) and [`docs/design/unified-touchpoints.md`](docs/design/unified-touchpoints.md), all Japanese; the decisions are ADR 0008–0011 in [`docs/adr/`](docs/adr/)).
- **The issues-only viewer (`issue_viewer.html`) has retired.** The product is the single `wbs_viewer.html`.
- **A plan-only `wbs.json` keeps working as before** (with no `issues` the viewer shows the plan alone and no switch).
- **Issue numbers are not aligned to WBS numbering (1.1.1).** Insertions would shift them, and issues that never reach the WBS could not have one. Numbers stay per-project counters; the WBS id is derived from `links` and shown next to the issue.
