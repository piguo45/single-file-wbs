"""仕上げ第2弾（実機指摘）：カレンダーの位置・＋課題の置き場と自動スクロール・方針の履歴・リンクの追加削除。
   本日=CLOCK_PIN(2026-09-15)。単体版・統合版の両方で回る。"""
import json
from playwright.sync_api import sync_playwright
from common import (S, J, VIEWER, action, book, check, decision, finish,
                    granted_handle_init, issue, new_page)

DEC = [decision("はじめの方針", "2026-09-03", "2026-09-03", "そのまま進める")]
DATA = book([
    issue(1, "履歴とリンクの課題", decisions=DEC, due="2026-09-20",
          actions=[action("2026-09-03", "着手", "ぴぐお", True)],
          links=[{"wbs": "2.3"}, {"title": "仕様書", "url": "https://example.com/spec"}], note="備考の本文"),
    issue(2, "2件目", decisions=None),
], name="仕上げ2テスト")
DATA["projects"][0]["tasks"] = [{"id": "2", "name": "変換ツール", "children": [
    {"id": "2.3", "name": "文字コード変換", "qty": 1, "hours": 8, "assignee": "ぴぐお",
     "plan": {"start": "2026-09-14", "end": "2026-09-18"}, "actual": {"start": None, "end": None}, "note": ""}]}]

errors, dlg = [], []


def on_dialog(d):
    dlg.append(d.message)
    if "対応方針" in d.message:
        d.accept("あたらしい方針")
    elif "理由" in d.message or "Why" in d.message:
        d.accept("状況が変わったため")
    else:
        d.accept()


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_page(b, viewport={"width": 1500, "height": 900})
    pg.on("pageerror", lambda e: errors.append(str(e)[:120]))
    pg.on("console", lambda m: errors.append("console:" + m.text[:120]) if m.type == "error" else None)
    pg.on("dialog", on_dialog)
    pg.add_init_script(granted_handle_init(DATA))
    pg.goto(VIEWER)
    pg.evaluate("()=>{window.__xss=false;}")  # alert は潰さない（不正 URL の警告に使うため）
    saved = lambda: json.loads(pg.evaluate("()=>window.__file"))["projects"][0]["issues"]
    pg.click(S("#openBtn")); pg.wait_for_timeout(300)
    pg.click(S("#editBtn")); pg.wait_for_timeout(400)

    # ===== #3 カレンダーは 📅 の直下に開く（位置がばらばらだった） =====
    cal = pg.eval_on_selector(S("#tbody .date-wrap"), J("""e=>{
        const bb=e.querySelector('.cal-btn').getBoundingClientRect();
        const x=e.querySelector('.cal-proxy').getBoundingClientRect();
        return [Math.round(x.left-bb.left), Math.round(x.top-bb.bottom),
                Math.round(x.width), getComputedStyle(e).position,
                getComputedStyle(e.querySelector('.cal-proxy')).display,
                Math.round(e.getBoundingClientRect().width)];}"""))
    check(cal[3] == "relative", f".date-wrap が位置の基準になっている -> {cal[3]}")
    check(0 <= cal[0] <= 24 and -4 <= cal[1] <= 4,
          f".cal-proxy が 📅 ボタンの直下（±4px） -> dx={cal[0]} dy={cal[1]}")
    # Chrome は input[type=date] の幅に 8px 程度の下限を持つ（width:1px でもそこで止まる）。
    # 狙いは「#tbl input{width:100%} に負けて入力欄いっぱいに伸びていない」こと。
    check(cal[2] <= 10 and cal[2] * 4 < cal[5],
          f".cal-proxy は極小幅（入力欄の 100% に引き伸ばされていない） -> {cal[2]}px / 欄 {cal[5]}px")
    check(cal[4] != "none", "display:none にはしない（showPicker が効かなくなるため）")
    # 全部の日付欄で同じ（ばらばらでない）
    allc = pg.eval_on_selector_all(S("#tbody .date-wrap"), J("""e=>e.map(w=>{
        const bb=w.querySelector('.cal-btn').getBoundingClientRect();
        const x=w.querySelector('.cal-proxy').getBoundingClientRect();
        return [Math.round(x.left-bb.left), Math.round(x.top-bb.bottom)];})"""))
    check(all(0 <= dx <= 24 and -4 <= dy <= 4 for dx, dy in allc),
          f"どの日付欄でも 📅 の直下に揃う（{len(allc)}箇所） -> {allc[:3]}")

    # ===== #4 ＋課題は絞り込みバーの右端。押すとその行へ飛んで書き始められる =====
    check(pg.eval_on_selector_all(S("#filterBar .addissue"), "e=>e.length") == 1, "＋課題は絞り込みバーにある")
    check(pg.eval_on_selector_all(S("#addRow"), "e=>e.length") == 0, "表の下の ＋課題 は撤去された")
    n0 = len(saved())
    pg.click(S("#filterBar .addissue")); pg.wait_for_timeout(700)
    iss = saved()
    check(len(iss) == n0 + 1 and iss[-1]["id"] == 3, f"末尾に id=最大+1 で追加 -> {iss[-1]['id']}")
    focused = pg.evaluate(J("""()=>{const a=document.activeElement;
        return a && a.tagName==='INPUT' && a.getAttribute('data-field')==='title'
               ? a.closest('tr').getAttribute('data-key') : null;}"""))
    check(focused == "仕上げ2テスト|3", f"追加した行のタイトル欄にフォーカスが入る -> {focused}")
    check(pg.eval_on_selector_all(S("#tbody tr.jump"), "e=>e.map(x=>x.getAttribute('data-key'))") == ["仕上げ2テスト|3"],
          "追加した行が強調される")
    check(pg.eval_on_selector_all(J("#tbody tr[data-key='仕上げ2テスト|3'] td.detail .body"), "e=>e.length") == 1,
          "追加した行は開いた状態で出る")

    # ===== #5 方針は decisions[] へ設計変更（2026-09-09）＝断言は test_decisions.py へ移した =====

    # ===== #8 リンクの追加・削除 =====
    lk = lambda: pg.eval_on_selector_all(S("#tbody tr:nth-child(1) .lk .lk-i"), "e=>e.map(x=>x.textContent.trim())")
    check(pg.eval_on_selector_all(S("#tbody tr:nth-child(1) .lk-add"), "e=>e.length") == 1, "編集モードで ＋リンク が出る")
    n_lk = len(saved()[0]["links"])
    # (1) WBS：同じ案件の tasks から選ぶ
    pg.click(S("#tbody tr:nth-child(1) .lk-add")); pg.wait_for_timeout(300)
    check(pg.eval_on_selector_all("#isForm select[data-lk='wbs'] option", "e=>e.map(x=>x.textContent)")
          == ["2 変換ツール", "2.3 文字コード変換"], "WBS は同じ案件の tasks を再帰した一覧から選ぶ")
    pg.select_option("#isForm select[data-lk='wbs']", "2.3")
    pg.click("#isForm .fm-ok"); pg.wait_for_timeout(700)
    check(saved()[0]["links"][-1] == {"wbs": "2.3"}, f"WBS リンクが追加される -> {saved()[0]['links'][-1]}")
    # (2) 課題
    pg.click(S("#tbody tr:nth-child(1) .lk-add")); pg.wait_for_timeout(300)
    pg.select_option("#isForm select[data-lk='kind']", "issue"); pg.wait_for_timeout(150)
    pg.fill("#isForm input[data-lk='issue']", "2")
    pg.click("#isForm .fm-ok"); pg.wait_for_timeout(700)
    check(saved()[0]["links"][-1] == {"issue": 2}, f"課題リンクが追加される -> {saved()[0]['links'][-1]}")
    # (3) URL（不正は拒否）
    pg.click(S("#tbody tr:nth-child(1) .lk-add")); pg.wait_for_timeout(300)
    pg.select_option("#isForm select[data-lk='kind']", "url"); pg.wait_for_timeout(150)
    XSS = '<img src=x onerror="window.__xss=true">'
    pg.fill("#isForm input[data-lk='title']", XSS)
    pg.fill("#isForm input[data-lk='url']", "javascript:alert(1)")
    m = len(dlg)
    pg.click("#isForm .fm-ok"); pg.wait_for_timeout(400)
    check(any("http" in d for d in dlg[m:]), f"http(s) 以外の URL は拒否する -> {dlg[m:]}")
    check(len(saved()[0]["links"]) == n_lk + 2, "拒否された URL は追加されない")
    pg.fill("#isForm input[data-lk='url']", "https://example.com/a?x=1&y=2")
    pg.click("#isForm .fm-ok"); pg.wait_for_timeout(700)
    check(saved()[0]["links"][-1] == {"title": XSS, "url": "https://example.com/a?x=1&y=2"},
          f"URL リンクが追加される -> {saved()[0]['links'][-1]}")
    check(pg.eval_on_selector_all(S("#tbody img,#tbody script"), "e=>e.length") == 0, "表示名に入れた文字が生DOMにならない")
    check(not pg.evaluate("()=>window.__xss"), "仕込んだスクリプトが動かない")
    # 削除
    before = len(saved()[0]["links"])
    pg.click(S("#tbody tr:nth-child(1) .lk .lkdel")); pg.wait_for_timeout(700)
    check(len(saved()[0]["links"]) == before - 1, f"✕ でリンクを削除できる -> {len(saved()[0]['links'])}")
    check(saved()[0]["links"][0] == {"title": "仕様書", "url": "https://example.com/spec"},
          f"消えたのは先頭の1件だけ -> {saved()[0]['links'][0]}")
    # 編集モードを抜けると ✕ と ＋リンク は出ない
    pg.click(S("#editBtn")); pg.wait_for_timeout(400)
    check(pg.eval_on_selector_all(S("#tbody .lkdel,#tbody .lk-add"), "e=>e.length") == 0,
          "表示モードでは ✕ と ＋リンク を出さない")
    check("備考" in " ".join(lk()), f"備考はリンク行に並ぶ -> {lk()}")
    check(pg.eval_on_selector(S("#tbody .lk .lk-i"), "e=>getComputedStyle(e).display") == "block",
          "リンクは1行1件（縦並び）")
    b.close()
finish(errors)
