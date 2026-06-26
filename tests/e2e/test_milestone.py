"""マイルストーンのGUI編集（追加/ラベル編集/削除）。従来はAI/JSONのみだった経路をGUIに追加。"""
import json
from playwright.sync_api import sync_playwright
from common import VIEWER, granted_handle_init, check, finish

DATA = {"projects": [{
    "name": "P",
    "milestones": [{"date": "2026-06-20", "label": "レビュー", "color": "#ef4444"}],
    "tasks": [{"id": "1", "name": "作業", "qty": 1, "hours": 8, "assignee": "佐藤",
               "plan": {"start": "2026-06-01", "end": "2026-06-10"},
               "actual": {"start": None, "end": None}, "note": ""}]
}]}

errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 600})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.add_init_script(granted_handle_init(DATA))
    pg.goto(VIEWER)
    pg.click("#openBtn"); pg.wait_for_timeout(150)
    pg.click("#editBtn"); pg.wait_for_timeout(200)

    def saved():
        pg.wait_for_timeout(550)
        return json.loads(pg.evaluate("()=>window.__file"))
    msrows = lambda: pg.eval_on_selector_all(".msrow .ms-edit", "els=>els.length")

    check("on" in (pg.get_attribute("#editBtn", "class") or ""), "編集ON")
    check(msrows() == 1, "既存MSが1件、編集行で表示される")
    check(pg.query_selector('button[data-act="addms"][data-proj="0"]') is not None, "＋MSボタンがある")

    # 追加
    pg.click('button[data-act="addms"][data-proj="0"]'); pg.wait_for_timeout(250)
    check(msrows() == 2, "＋MSで編集行が2件に")
    d = saved()
    check(len(d["projects"][0]["milestones"]) == 2, "MSが2件保存される")
    check(bool(d["projects"][0]["milestones"][1].get("date")), "追加MSに既定日付(本日)が入る")

    # ラベル編集（既存MS=index0）
    inp = pg.query_selector('input[data-mpath="0/0"][data-mfield="label"]')
    inp.fill("中間レビュー"); inp.dispatch_event("change"); pg.wait_for_timeout(50)
    d = saved()
    check(d["projects"][0]["milestones"][0]["label"] == "中間レビュー", "ラベル編集が保存される")

    # 色＝5プリセット＋「現在色」インジケータ（プリセット外の既存色も選択中として先頭に表示）
    check(pg.eval_on_selector_all('.ms-sw[data-mpath="0/0"]', "e=>e.length") == 6, "現在色(プリセット外#ef4444)＋5プリセット=6スウォッチ")
    check(pg.eval_on_selector('.ms-sw[data-mpath="0/0"].on', "e=>e.getAttribute('data-color')") == "#ef4444", "現在色が選択中(.on)で表示される")
    pg.click('button.ms-sw[data-mpath="0/0"][data-color="#e69f00"]'); pg.wait_for_timeout(250)
    d = saved()
    check(d["projects"][0]["milestones"][0]["color"] == "#e69f00", "プリセット選択が保存される")
    check(pg.eval_on_selector_all('.ms-sw[data-mpath="0/0"]', "e=>e.length") == 5, "プリセット選択後は5スウォッチ(現在色がプリセット内)")

    # 削除（追加した index1 を消す）
    pg.click('button[data-act="delms"][data-mpath="0/1"]'); pg.wait_for_timeout(250)
    d = saved()
    check(len(d["projects"][0]["milestones"]) == 1, "delmsで1件に戻る")
    check(d["projects"][0]["milestones"][0]["label"] == "中間レビュー", "残ったMSの内容は保持")
    b.close()

finish(errors)
