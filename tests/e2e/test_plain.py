"""#79 簡素表示トグル：ロゴ/版/"Viewer"/タブ名を隠し「WBS」だけにする
（現場で“自作”と言える逃げ道）。クリックで切替・localStorage記憶・再読込で保持。"""
from playwright.sync_api import sync_playwright
from common import VIEWER, check, finish

errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(VIEWER)

    disp = lambda sel: pg.eval_on_selector(sel, "e=>getComputedStyle(e).display")
    is_plain = lambda: pg.eval_on_selector("body", "b=>b.classList.contains('plain')")

    # 既定=フル表示
    check(not is_plain(), "既定はフル表示")
    check(disp("#brandTitle .logo") != "none", "既定でロゴ表示")
    check(pg.title() == "WBS Viewer", "既定タブ名=WBS Viewer")

    # クリック→簡素モード
    pg.click("#brandTitle"); pg.wait_for_timeout(50)
    check(is_plain(), "クリックで簡素モード")
    check(disp("#brandTitle .logo") == "none", "簡素=ロゴ非表示")
    check(disp("#brandTitle .brand-x") == "none", "簡素=“Viewer”非表示")
    check(disp("#brandTitle .ver") == "none", "簡素=バージョン非表示")
    check(pg.title() == "WBS", "簡素タブ名=WBS")
    check(pg.inner_text("#brandTitle").strip() == "WBS", "簡素で表記は「WBS」のみ")

    # 再読込で保持（localStorage）
    pg.goto(VIEWER); pg.wait_for_timeout(50)
    check(is_plain(), "再読込でも簡素を保持")
    check(pg.title() == "WBS", "再読込でもタブ名=WBS")

    # 再クリックでフルに戻る
    pg.click("#brandTitle"); pg.wait_for_timeout(50)
    check(not is_plain(), "再クリックでフル表示に戻る")
    check(pg.title() == "WBS Viewer", "戻すとタブ名=WBS Viewer")
    b.close()

finish(errors)
