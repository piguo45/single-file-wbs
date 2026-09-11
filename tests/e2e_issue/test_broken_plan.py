"""計画（tasks/milestones）の型崩れを「無視するが消さない」で扱うことの回帰。

  1. 型崩れたファイルを描いて保存しても、JSON は1バイトも変わらない（壊れた要素も残す）
  2. 壊れた要素が混じった tasks でも、編集が正しい葉に当たる（配列の添字がずれない）
  3. 旧フォーマット {project, milestones, tasks} を編集モードで変換しても、
     トップレベルの鍵（name・holidays・star・`_`キー）が消えない
本日=CLOCK_PIN(2026-09-15)。
"""
import json
from playwright.sync_api import sync_playwright
from common import S, VIEWER, check, finish, granted_handle_init, new_page

# 型崩れの見本（B1〜B7 相当を1ファイルに詰めたもの）
BROKEN = {
    "name": "ブック名", "holidays": ["2026-09-21"],
    "star": {"from": "2026-09-01", "to": "2026-09-07"},
    "_keep": "ユーザーのカスタムキー",
    "projects": [{
        "name": "p", "milestones": ["2026-09-20", None, 42], "tasks": [
            42,
            {"id": "1", "name": "親", "children": "壊れ"},
            {"id": "2", "name": "親2", "children": [42, {
                "id": "2.1", "name": "生きている葉", "qty": 1, "hours": 8, "assignee": "ぴぐお",
                "plan": {"start": "2026-09-01", "end": "2026-09-05"},
                "actual": {"start": None, "end": None}, "note": ""}]},
            {"id": "3", "name": {"a": 1}, "qty": 1, "hours": {"h": 8},
             "plan": {"start": "2026-09-01", "end": "2026-09-05"},
             "actual": {"start": None, "end": None}, "note": ""}],
        "issues": [{"id": 1, "title": "読めるはずの課題", "priority": "mid",
                    "opened": "2026-09-01", "due": "2026-09-30",
                    "ifIgnored": "放置すると困る", "ifDone": "", "closeWhen": "確かめられること",
                    "decisions": [], "pending": None, "closed": None,
                    "links": [], "actions": [], "note": ""}]}]}

# 旧フォーマット（トップレベルに name / holidays / `_`キーがある）
LEGACY = {
    "project": "旧フォーマットの案件", "name": "ブック名",
    "tasks": [{"id": "1", "name": "作業", "qty": 1, "hours": 8, "assignee": "ぴぐお",
               "plan": {"start": "2026-09-01", "end": "2026-09-05"},
               "actual": {"start": None, "end": None}, "note": ""}],
    "holidays": ["2026-09-02", "2026-09-03"],
    "_ai": {"tokens": 1200, "memo": "AIのメモ"}, "_keep": "ユーザーのカスタムキー"}

errors, dialogs = [], []
with sync_playwright() as p:
    b = p.chromium.launch()

    # ===== 1. 型崩れたまま往復する（正規化した結果を保存しない） =====
    ctx = b.new_context(viewport={"width": 1500, "height": 900})
    pg = new_page(ctx, issue_view=False)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
    pg.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    pg.add_init_script(granted_handle_init(BROKEN))
    pg.goto(VIEWER)
    n0 = len(errors)
    pg.click("#openBtn"); pg.wait_for_timeout(300)
    check(len(errors) == n0, f"型崩れた計画でも JS エラーを出さない -> {errors[n0:]}")
    check(pg.eval_on_selector_all("#leftRows .nm", "e=>e.map(x=>x.innerText)").count("生きている葉") == 1,
          "壊れた兄弟がいても、生きている葉は描かれる")
    check("[object Object]" not in pg.evaluate("()=>document.body.innerText"),
          "オブジェクトの name / hours を [object Object] と描かない")

    pg.click("#editBtn"); pg.wait_for_timeout(400)
    # 保存を1回起こす（生きている葉の name を書き換える）
    sel = "#leftRows input.nm-in[value='生きている葉']"
    check(pg.eval_on_selector_all(sel, "e=>e.length") == 1, "編集モードで生きている葉の入力欄が1つ")
    pg.fill(sel, "書き換えた葉")
    pg.dispatch_event(sel, "change"); pg.wait_for_timeout(700)
    saved = json.loads(pg.evaluate("()=>window.__file"))
    tasks = saved["projects"][0]["tasks"]
    # 2. 編集は「元配列の添字」で当たる＝壊れた要素があってもずれない
    check(tasks[0] == 42, f"壊れた要素 42 は保存で消えない -> {tasks[0]!r}")
    check(tasks[1] == {"id": "1", "name": "親", "children": "壊れ"},
          f'children:"壊れ" のタスクも無傷 -> {tasks[1]!r}')
    check(tasks[2]["children"][0] == 42, f"children の壊れ要素も無傷 -> {tasks[2]['children'][0]!r}")
    check(tasks[2]["children"][1]["name"] == "書き換えた葉",
          f"編集は正しい葉（tasks[2].children[1]）に当たる -> {tasks[2]['children'][1]['name']!r}")
    check(tasks[3]["name"] == {"a": 1} and tasks[3]["hours"] == {"h": 8},
          f"オブジェクトの name / hours も書き換えずに残す -> {tasks[3].get('name')!r}")
    check(saved["projects"][0]["milestones"] == ["2026-09-20", None, 42],
          f"壊れた milestones も無傷 -> {saved['projects'][0]['milestones']!r}")
    check(saved.get("name") == "ブック名" and saved.get("holidays") == ["2026-09-21"]
          and saved.get("_keep") == "ユーザーのカスタムキー",
          f"トップレベルの鍵は保存で残る -> {sorted(saved)}")
    check("_calc" not in pg.evaluate("()=>window.__file"), "保存 JSON に派生値は入らない")
    ctx.close()

    # ===== 3. 旧フォーマットの変換でトップレベルの鍵を落とさない =====
    ctx2 = b.new_context(viewport={"width": 1500, "height": 900})
    pg2 = new_page(ctx2, issue_view=False)
    pg2.on("pageerror", lambda e: errors.append(str(e)))
    pg2.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    pg2.add_init_script(granted_handle_init(LEGACY))
    pg2.goto(VIEWER)
    pg2.click("#openBtn"); pg2.wait_for_timeout(300)
    n = len(dialogs)
    pg2.click("#editBtn"); pg2.wait_for_timeout(400)
    check(len(dialogs) > n, f"旧フォーマットは変換の確認を出す -> {dialogs[n:]}")
    sel2 = "#leftRows input.nm-in[value='作業']"
    pg2.fill(sel2, "作業（改）")
    pg2.dispatch_event(sel2, "change"); pg2.wait_for_timeout(700)
    sv = json.loads(pg2.evaluate("()=>window.__file"))
    check(sv.get("name") == "ブック名", f"ブック名(name)が変換で消えない -> {sv.get('name')!r}")
    check(sv.get("holidays") == ["2026-09-02", "2026-09-03"],
          f"holidays が変換で消えない -> {sv.get('holidays')!r}")
    check(sv.get("_ai") == {"tokens": 1200, "memo": "AIのメモ"} and sv.get("_keep") == "ユーザーのカスタムキー",
          f"`_` キーが変換で消えない -> {sorted(sv)}")
    check("project" not in sv and "tasks" not in sv and "milestones" not in sv,
          f"畳んだ3つの旧キーはトップに残さない -> {sorted(sv)}")
    check(len(sv["projects"]) == 1 and sv["projects"][0]["name"] == "旧フォーマットの案件",
          f"project は projects[0].name になる -> {sv['projects'][0].get('name')!r}")
    check(sv["projects"][0]["tasks"][0]["name"] == "作業（改）", "変換後も編集が効く")
    ctx2.close()
    b.close()
finish(errors)
