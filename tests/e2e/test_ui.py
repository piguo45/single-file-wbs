"""編集UI: 保存状態の遷移（未保存→保存済→再描画後も維持）・列拡幅・クリックターゲット寸法"""
from playwright.sync_api import sync_playwright
from common import VIEWER, check, finish, leaf, granted_handle_init

DATA = {"projects": [{"name": "P1", "milestones": [],
        "tasks": [{"id": "1", "name": "工程", "children":
                   [leaf("1.1", "作業A", ps="2026-06-01", pe="2026-06-05")]}]}]}

errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1500, "height": 400})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.add_init_script(granted_handle_init(DATA))
    pg.goto(VIEWER)
    pg.click("#openBtn"); pg.wait_for_timeout(150)
    pg.click("#editBtn"); pg.wait_for_timeout(200)

    w = pg.evaluate("()=>document.querySelector('#leftRows .lrow .c.name').style.width")
    check(w == "272px", f"編集時は作業項目列が拡幅 -> {w}")
    h = pg.evaluate("()=>Math.round(document.querySelector('#leftRows .nm-wrap .clk.caret').getBoundingClientRect().height)")
    check(h >= 24, f"行caretのヒット領域が行高相当 ({h}px)")
    bw, bh = pg.evaluate("()=>{const r=document.querySelector('.acts button').getBoundingClientRect();return [Math.round(r.width),Math.round(r.height)];}")
    check(bw >= 20 and bh >= 20, f"操作ボタンの寸法 ({bw}x{bh}px)")

    # #78: 編集モードで数量/時間の列を3桁見える幅(52px)に拡幅
    qw = pg.evaluate("()=>{const i=document.querySelector('input[data-field=\"qty\"]');return i?i.closest('.c').style.width:null;}")
    hw = pg.evaluate("()=>{const i=document.querySelector('input[data-field=\"hours\"]');return i?i.closest('.c').style.width:null;}")
    check(qw == "52px" and hw == "52px", f"編集時は数量/時間が52px ({qw}/{hw})")

    # #49: アイコンは単色インラインSVG（emoji/テキスト回帰の検知）。操作ボタンとヘッダ指標の両方
    nsvg = pg.eval_on_selector_all(".acts button svg", "e=>e.length")
    check(nsvg > 0, f"操作ボタンにSVGアイコンがある ({nsvg}個)")
    check(pg.eval_on_selector_all("#stat svg", "e=>e.length") > 0, "ヘッダ指標(ファイル/本日/更新)にSVGアイコンがある")

    pg.fill('input[data-field="assignee"]', "X")
    pg.dispatch_event('input[data-field="assignee"]', "change")
    check("未保存" in pg.inner_text("#saveMsg"), "change直後は『未保存の変更あり』")
    pg.wait_for_timeout(800)
    check(":" in pg.inner_text("#saveMsg"), "書込後は『保存済 HH:MM:SS』")
    pg.evaluate("()=>document.activeElement.blur()")
    pg.wait_for_timeout(900)
    pg.click("#allCaret"); pg.wait_for_timeout(100)   # 再描画を挟む
    check(":" in pg.inner_text("#saveMsg"), "再描画後も保存状態が維持")
    b.close()
finish(errors)
