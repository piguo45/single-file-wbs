# <img src="docs/logo.svg" width="26"> single-file-wbs

> A dependency-free, single-file WBS / Gantt viewer: a time-axis Gantt **plus an EVM-style progress-axis view** and a Japanese *inazuma* (slip / progress) line. Just open the HTML in Chrome — no server, no libraries, no build step.
> The on-screen application name is **WBS Viewer** (`single-file-wbs` is the distribution name = this repository).

**[日本語版 README はこちら / Japanese README](README.md)**

![screenshot](docs/screenshot.en.png)

Switch with the **Time / Progress tabs** (top right). Progress view (EVM-style completion: actual / planned / behind):

![progress view](docs/screenshot-progress.en.png)

## Concept

**A local WBS for the AI-era manager (PL / tech lead) leading a small, elite team that includes AI.**
Humans edit via the GUI; AI edits via raw JSON and [`CLAUDE.md`](CLAUDE.md) — the same plan.

- **Target**: not the enterprise PM of huge projects, but a **manager leading a small elite team that includes AI** (the author is this persona — dogfooding)
- **Core differentiator = two first-class interfaces**: most PM tools assume a human (GUI). Here, **AI is also a first-class user** — it maintains the plan via raw JSON + the AI-readable `CLAUDE.md`
- Architecture & decisions → [`docs/`](docs/index.md) ([overview](docs/design/system-overview.md) · [ADRs](docs/adr/))
- Background essay (Japanese) → [WBSという至高ツールで、このAI時代をサバイブする](https://zenn.dev/piguolabo/articles/99b5b30a028f80)

## Start in 30 seconds

1. Download `wbs_viewer.html` from [Releases](https://github.com/piguo45/single-file-wbs/releases/latest)
2. Open it in Chrome (plain `file://` is fine)
3. Load a bundled data file via **Open file** (or drag & drop onto that same button)
   - **`wbs_sample.json`** — fictional sample, format reference
   - **`wbs_roadmap.json`** — this tool's own development plan (real data, linked to GitHub issues and maintained by Claude Code)

For your own WBS, copy `wbs_sample.json` as a template (name the file anything you like). Edit and save → press **Reload**.
Updating the tool = overwriting `wbs_viewer.html`; your `wbs.json` data is never touched.

## Features

- **Single HTML file** — just open it in Chrome. No server, CDN, build, or dependencies
- **Inazuma line (progress line)** — bulging **left of the today line = behind schedule**; start delays and deadline overruns at a glance
- **Plan-vs-actual Gantt overlay** — the actual bar sits inside a plan outline; **overrun = finish delay (red + N days), empty left = late start**. Done tasks are gray, parents (aggregates) are thin summary bars — state at a glance. Colors are **Color-Universal-Design (CVD) aware**
- **Progress-axis view (EVM-style)** — besides the time-axis Gantt, a **progress view whose axis is completion (0–100%)**, switched via **tabs**. Shows **actual (EV) / planned (PV) / behind** as horizontal bars (the two views are never mixed)
- **Header summary** — period, effort (person-months), and progress (EVM) always on screen; even when the overall figure is 0% (ahead-work offsets it), a **badge counts the tasks that are individually behind**
- **Column collapse (outline-style)** — **+/−** above the headers collapse/expand column groups (qty+hours, progress, status, owner, plan, actual, notes) to widen the Gantt
- **Data is one JSON of facts only** — it holds nothing but plan and actual dates. Effort (qty × hours ÷ 8, person-days), progress, and the inazuma line are all **computed automatically** — no numbers to maintain by hand
- **Three ways to edit** — in-browser editing (autosave) / any text editor / **AI chat** (ships with `CLAUDE.md` so Claude Code already understands the data format)
- **Holidays & weekends at a glance** — a top-level `holidays` list renders **holidays in red** in the date header and shades **weekend + holiday columns faint pink full-height**. Remaining-business-days also excludes weekends & holidays (2026 Japanese holidays ship with the sample data)
- Plus: multiple projects, collapsible tree, milestone lines, completed-task graying with ✓, auto-linked URLs in notes, Japanese/English UI

> **Main additions in v1.3** (the fruits of the v1.2 maintenance period): (1) **add nested child tasks** in edit mode; (2) **edit milestones in the GUI** (date, name, 5-color presets); (3) **plain display that hides the logo/version** (toggle by clicking the title); (4) **holiday settings + pink weekend/holiday columns** (remaining business days exclude holidays too); (5) icon cleanup, tooltips, and edit-column-width polish.

## Working the screen

- **Switch views**: the **Time / Progress tabs** (top right) toggle between the Gantt (time axis) and the progress view (completion)
- **Collapse rows**: click a project / phase name or `▼/▶`. The **`▼/▶` in the Task column header** expands / collapses everything (**Ctrl+Z** restores the previous view after a slip)
- **Collapse columns**: the **+/−** above the headers fold/unfold column groups (qty+hours, progress, status, owner, plan, actual, notes)
- **Gantt**: the day column under your mouse is **highlighted** with its date emphasized in the header; **hover a bar** to see the exact plan / actual dates

## In-browser editing (optional)

Turn the **Edit** button ON to edit directly on screen. Changes are **autosaved to `wbs.json` ~0.4 s later** (save status always visible at the top right).

- Available: in-place editing of each field (No./name/qty/hours/owner/dates/notes — **effort is auto-computed**, not editable). Dates accept shorthand like `611`/`6/11`, `YYYY-MM-DD`, or the 📅 picker (this year shows `MM-DD`); add `＋`, delete `✕` (with confirmation), reorder `⬆⬇`; **add nested child tasks** (a leaf is promoted to a summary node and the child hangs under it, effort preserved); **edit milestones** (`＋MS` on a project row — date, name, 5-color presets)
- Not supported (edit the JSON or ask the AI): drag-and-drop reordering / moving to a different parent / automatic renumbering

<details>
<summary>⚠ Enabling edit mode requires re-selecting the file (click for steps)</summary>

When you press **Edit**, a **file save dialog opens immediately**. This is not a bug: for security, Chrome only grants a page write access to a file when **the user picks that file in a save dialog** (an unavoidable constraint of `file://`-based tools).

1. Press the **Edit** button → a save dialog opens
2. Select **the same `wbs.json` you currently have open** and press Save
3. "Replace existing file?" → **Yes**
4. When the Edit button turns **green**, you're ready

What the page looks like right after pressing **Edit** (a yellow guidance bar appears; the save dialog opens on top of this):

![right after pressing Edit (yellow guidance bar)](docs/guide-edit-on.en.png)

You do **not** do this every time — only **once after starting Chrome** (required again after restarting Chrome).

</details>

![edit mode](docs/screenshot-edit.en.png)

## Maintaining via AI chat

The number-one reason WBS charts die is **the cost of updating them**. This tool freezes the view logic (HTML) and treats the data (`wbs.json`) as the only thing that changes — so you can **delegate updates to Claude Code via chat**. The data is one plain JSON file, so no plugins or integrations are needed; bulk edits, workload aggregation, and cross-file analysis are each one sentence.

- "Mark the design review as completed today" → sets `actual.end` to today
- "Push every June task back a week" → bulk change
- "Total workload by owner" → analyses the viewer itself doesn't have
- "Archive everything completed before May" → backup + cleanup

The bundled [`CLAUDE.md`](CLAUDE.md) ([English: `CLAUDE.en.md`](CLAUDE.en.md)) teaches the AI the data format, editing rules, and conventions.

## Data format (wbs.json)

```json
{
  "holidays": [ "2026-07-20", { "date": "2026-08-11", "name": "Mountain Day" } ],
  "projects": [
    {
      "name": "Project name",
      "milestones": [ { "date": "2026-09-30", "label": "Release", "color": "#ef4444" } ],
      "tasks": [
        { "id": "1", "name": "Phase 1", "children": [
          { "id": "1.1", "name": "Task", "qty": 1, "hours": 16, "assignee": "Owner",
            "plan":   { "start": "2026-07-01", "end": "2026-07-05" },
            "actual": { "start": null, "end": null }, "note": "",
            "_ai":    { "tokens": 70000, "minutes": 25, "model": "fable-5" },
            "_money": { "outsource": 50000, "currency": "JPY" },
            "_links": ["https://example.com/spec.md"] }
        ] }
      ]
    }
  ]
}
```

- Tasks nest up to 3 levels. A node with `children` is a summary node; without it, a leaf (carries effort)
- `holidays` (optional, top-level) is shared across all projects. String form = no name / `{ date, name }` form = name shown as a tooltip. **Holidays render red in the date header and shade columns pink with weekends**, and are excluded from the remaining-business-days count
- **Keys starting with `_` are custom keys** you can add freely (`_ai` = AI effort, `_money` = outsourcing cost, `_links` = reference links above; any structure works). The viewer ignores them and in-browser editing preserves them. URLs you want to click belong in `note` (auto-linked)
- The legacy single-project format `{ "project", "milestones", "tasks" }` is still readable (backward compatible)
- For exact formulas, operations, and edge-case handling, see [`CLAUDE.en.md`](CLAUDE.en.md) (single source of truth for the spec)

## Requirements

**Google Chrome (latest) recommended**. Uses the File System Access API, so a **Chromium-based browser is required**; works when opened directly via `file://`.

- **Microsoft Edge** and other Chromium-based browsers work as well (same engine; development testing is done on Chrome)
- On corporate-managed browsers, the File System Access API may be disabled by policy — viewing still works but **editing won't** (check `edge://policy`)
- Firefox / Safari are **not supported** (no File System Access API)

## Tests & known limitations

`tests/` contains normal-case and broken-input sample JSONs plus e2e tests (see [`tests/INDEX.md`](tests/INDEX.md)). Design policy: graceful degradation — broken input must never crash the viewer.

Known limitations: initial rendering slows down with thousands of rows (mitigate by collapsing) / projects with identical names share collapse state / no keyboard navigation or screen-reader support (mouse-first personal tool).

## License

[MIT](LICENSE)
