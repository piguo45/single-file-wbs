"""クローズの閉じ方「重複」：元の課題が必須・links への台帳追加・表示（→ 課題 #N）・存在しない番号は拒否。
   本日=CLOCK_PIN(2026-09-15)。単体版・統合版の両方で回る。"""
import json
from playwright.sync_api import sync_playwright
from common import (S, VIEWER, action, book, check, finish, granted_handle_init,
                    issue, issue_ref, new_page)

D = {"name": "重複テスト", "projects": [
    {"name": "案件A", "issues": [
        issue(1, "元の課題", actions=[action("2026-09-02", "調査", "", True)]),
        issue(2, "重複で閉じる相手"),
        issue(3, "すでに重複で閉じてある",
              closed={"at": "2026-09-07", "how": "duplicate", "note": "#1 と同じ"},
              links=[issue_ref(1)]),
        issue(4, "別案件の課題と重複",
              closed={"at": "2026-09-07", "how": "duplicate", "note": "向こうと同じ"},
              links=[issue_ref(5, "勤怠システム更改")])]},
    {"name": "勤怠システム更改", "issues": [issue(5, "向こうの課題")]}]}

with sync_playwright() as pw:
    b = pw.chromium.launch()
    errors, dlg = [], []
    pg = new_page(b, viewport={"width": 1500, "height": 1000})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("dialog", lambda d: (dlg.append(d.message), d.accept()))
    pg.add_init_script(granted_handle_init(D))
    pg.goto(VIEWER)
    saved = lambda: json.loads(pg.evaluate("()=>window.__file"))["projects"][0]["issues"]
    dtl = lambda n: pg.inner_text(S(f"#tbody tr:nth-child({n}) td.detail")).replace("\n", " ")
    pg.click(S("#openBtn")); pg.wait_for_timeout(350)

    # ===== 表示：完了：[重複] … → 課題 #1（押すと飛ぶ） =====
    check("[重複]" in dtl(3) and "→ 課題 #1" in dtl(3), f"同じ案件は「→ 課題 #1」 -> {dtl(3)!r}")
    check("→ 勤怠-5" in dtl(4), f"別案件は略称「→ 勤怠-5」 -> {dtl(4)!r}")
    ref = pg.eval_on_selector(S("#tbody tr:nth-child(4) .iref"), "e=>[e.textContent, e.title]")
    check(ref == ["勤怠-5", "勤怠システム更改 #5"], f"略称のツールチップに正式名 -> {ref}")
    check(pg.eval_on_selector(S("#tbody tr:nth-child(3) td.state"), "e=>e.innerText").replace("\n", "/")
          .startswith("完了/重複"), "状態列のサブ表示も「重複」")
    pg.click(S("#tbody tr:nth-child(3) .iref")); pg.wait_for_timeout(400)
    check(pg.eval_on_selector_all(S("#tbody tr.jump td.num"), "e=>e.map(x=>x.innerText)") == ["1"],
          "重複の元をクリックするとその課題へ飛ぶ")

    # ===== 編集：フォームで「重複」を選ぶと元の課題の指定が要る =====
    pg.click(S("#editBtn")); pg.wait_for_timeout(400)
    hows = pg.eval_on_selector_all(S('#tbody tr:nth-child(2) [data-act="close"]'), "e=>e.length")
    check(hows == 1, "クローズのボタンがある")
    pg.click(S('#tbody tr:nth-child(2) [data-act="close"]')); pg.wait_for_timeout(300)
    opts = pg.eval_on_selector_all('#isForm select[data-fm="how"] option', "e=>e.map(x=>x.textContent)")
    check(opts == ["解決", "不対応", "発生せず", "重複"], f"閉じ方に「重複」が増えた -> {opts}")
    check(pg.eval_on_selector('#isForm .fm-f[data-f="dup"]', "e=>e.hidden"),
          "「重複」以外では元の課題の欄は出さない")
    pg.select_option('#isForm select[data-fm="how"]', "duplicate"); pg.wait_for_timeout(200)
    check(not pg.eval_on_selector('#isForm .fm-f[data-f="dup"]', "e=>e.hidden"),
          "「重複」を選ぶと元の課題の欄が出る")
    n = len(dlg)
    pg.click("#isForm .fm-ok"); pg.wait_for_timeout(400)
    check(any("元の課題" in d for d in dlg[n:]), f"番号が空なら拒否する -> {dlg[n:]}")
    check(saved()[1]["closed"] is None, "拒否したときは閉じない")
    n = len(dlg)
    pg.fill('#isForm input[data-fm="dissue"]', "99")
    pg.click("#isForm .fm-ok"); pg.wait_for_timeout(400)
    check(any("見つかりません" in d for d in dlg[n:]), f"存在しない番号も拒否する -> {dlg[n:]}")
    check(saved()[1]["closed"] is None, "存在しない番号では閉じない")
    pg.fill('#isForm input[data-fm="dissue"]', "1")
    pg.fill('#isForm textarea[data-fm="note"]', "#1 と同じ話")
    pg.click("#isForm .fm-ok"); pg.wait_for_timeout(700)
    iss = saved()[1]
    check(iss["closed"] == {"at": "2026-09-15", "how": "duplicate", "note": "#1 と同じ話"},
          f"重複で閉じる -> {iss['closed']}")
    check(iss["links"][-1] == {"issue": 1}, f"元の課題は links に台帳として残る -> {iss.get('links')}")
    check("→ 課題 #1" in dtl(2), f"閉じた直後から表示に出る -> {dtl(2)!r}")

    # 別案件を選ぶと {project, issue} で入る
    pg.click(S('#tbody tr:nth-child(1) [data-act="close"]')); pg.wait_for_timeout(300)
    pg.select_option('#isForm select[data-fm="how"]', "duplicate"); pg.wait_for_timeout(200)
    pg.select_option('#isForm select[data-fm="dproj"]', "勤怠システム更改")
    pg.fill('#isForm input[data-fm="dissue"]', "5")
    pg.click("#isForm .fm-ok"); pg.wait_for_timeout(700)
    check(saved()[0]["links"][-1] == {"project": "勤怠システム更改", "issue": 5},
          f"別案件は project 付きで書く -> {saved()[0].get('links')}")
    raw = pg.evaluate("()=>window.__file")
    check("_calc" not in raw, "派生値 _calc は書かない")
    check(not errors, f"JS エラーが出ない -> {errors[:2]}")
    b.close()
finish(errors)
