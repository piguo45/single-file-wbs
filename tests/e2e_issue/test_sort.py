"""並び替えセグメント: No（データ順）／期限（null は末尾）／優先度（高→低・同順位はデータ順）。表示専用・localStorage記憶。"""
from playwright.sync_api import sync_playwright
from common import J, S, VIEWER, check, finish, load_test_json, new_page, reload

DATA = load_test_json("正常_全機能.json")

errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1500, "height": 900})
    pg = new_page(ctx)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(VIEWER)
    pg.evaluate("d=>window.renderData(d)", DATA); pg.wait_for_timeout(200)
    ids = lambda: pg.eval_on_selector_all(S("#tbody td.num"), "e=>e.map(x=>x.innerText)")

    segs = pg.eval_on_selector_all(S("#filterBar .seg-btn"), "e=>e.map(x=>[x.getAttribute('data-sort'), x.innerText])")
    check(segs == [["no", "No"], ["due", "期限"], ["prio", "優先度"]], f"3セグメント -> {segs}")
    check(ids() == ["1", "2", "3", "4", "5", "6", "7", "8"], "既定は No（データ順）")

    pg.click(S('.seg-btn[data-sort="due"]')); pg.wait_for_timeout(150)
    # 期限: 8=8/20, 4=9/1, 6=9/5, 1=9/10, 2=10/20, 5=12/1, null=3,7（データ順で末尾）
    check(ids() == ["8", "4", "6", "1", "2", "5", "3", "7"], f"期限昇順・nullは末尾 -> {ids()}")

    pg.click(S('.seg-btn[data-sort="prio"]')); pg.wait_for_timeout(150)
    # 高=1,4,6 / 中=2,5,8 / 低=3,7（同順位はデータ順）
    check(ids() == ["1", "4", "6", "2", "5", "8", "3", "7"], f"優先度 高→低・同順位はデータ順 -> {ids()}")
    check(pg.eval_on_selector(S('.seg-btn[data-sort="prio"]'), "e=>e.classList.contains('on')"), "選択中セグメントが塗られる")

    reload(pg)
    try:   # 記憶した並びが読み込まれるのを条件で待つ（固定待ちだと負荷時に取りこぼす）
        pg.wait_for_function(J("()=>!!document.querySelector('.seg-btn[data-sort=\"prio\"].on')"), timeout=5000)
    except Exception:
        pass
    pg.evaluate("d=>window.renderData(d)", DATA)
    try:
        pg.wait_for_function(J("()=>document.querySelectorAll('#tbody td.num').length===8"), timeout=5000)
    except Exception:
        pass
    check(ids() == ["1", "4", "6", "2", "5", "8", "3", "7"], f"リロード後も並び順を記憶 -> {ids()}")

    pg.click(S('.seg-btn[data-sort="no"]')); pg.wait_for_timeout(150)
    check(ids() == ["1", "2", "3", "4", "5", "6", "7", "8"], "No に戻すとデータ順")
    b.close()
finish(errors)
