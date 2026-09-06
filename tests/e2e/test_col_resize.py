"""列幅の変更（#100）：ヘッダ境界のドラッグで幅が変わる／localStorage に残り再読込後も効く／
ダブルクリックで既定幅に戻る／ドラッグ中は再描画しない（幅は CSS 変数 --cw-<key> だけを書き換える）。"""
from playwright.sync_api import sync_playwright
from common import VIEWER, check, finish, leaf, granted_handle_init, new_page

DATA = {"projects": [{"name": "P1", "milestones": [],
        "tasks": [{"id": "1", "name": "工程", "children": [
            leaf("1.1", "作業A", ps="2026-06-01", pe="2026-06-05", asg="ぴぐお"),
            leaf("1.2", "作業B", ps="2026-06-03", pe="2026-06-10", asg="佐藤")]}]}]}

# 宣言幅の単一ソース＝CSS変数（実測は罫線ぶんの端数shrinkが乗るのでこちらを見る）
CWVAR = "k=>parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--cw-'+k))"


def open_file(pg):
    pg.goto(VIEWER)
    pg.click("#openBtn")
    pg.wait_for_timeout(200)


def drag(pg, key, dx, steps=12):
    """担当列などのリサイザを掴んで dx だけ動かす（mousemove を steps 回発火させる）"""
    box = pg.locator(f"#leftHead [data-resize-col='{key}']").bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    pg.mouse.move(x, y)
    pg.mouse.down()
    pg.mouse.move(x + dx, y, steps=steps)
    pg.mouse.up()
    pg.wait_for_timeout(150)


errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_page(b, viewport={"width": 1500, "height": 400})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script(granted_handle_init(DATA))
    open_file(pg)

    check(pg.locator("#leftHead [data-resize-col]").count() == 13,
          f"全13列にリサイザが出る -> {pg.locator('#leftHead [data-resize-col]').count()}")

    # ① ドラッグで列幅が変わる（担当=既定64px を +80px）
    w0 = pg.evaluate(CWVAR, "asg")
    left0 = pg.evaluate("()=>document.getElementById('left').getBoundingClientRect().width")
    drag(pg, "asg", 80)
    w1 = pg.evaluate(CWVAR, "asg")
    check(abs(w1 - (w0 + 80)) <= 2, f"ドラッグで担当列が+80px ({w0}->{w1})")
    check(pg.evaluate("()=>Math.round(document.getElementById('left').getBoundingClientRect().width)")
          == round(left0 + 80), "左表の総幅もドラッグぶん広がる")
    check(len(errors) == 0, f"ドラッグでJSエラー無し -> {errors}")

    # 最小幅（COLS の min=54）より狭くはならない
    drag(pg, "asg", -400)
    check(pg.evaluate(CWVAR, "asg") == 54, f"最小幅54pxで止まる -> {pg.evaluate(CWVAR, 'asg')}")
    drag(pg, "asg", 60)   # 54+60=114 を保存値として次の再読込テストへ
    saved = pg.evaluate(CWVAR, "asg")

    # ② localStorage に保存され、再読込後も反映される
    ls = pg.evaluate("()=>JSON.parse(localStorage.getItem('wbsColWidths')||'{}')")
    check(ls.get("asg") == saved, f"wbsColWidths に保存 -> {ls}")
    pg.reload()                      # 同一ページ＝同一コンテキスト（localStorage が残る）
    pg.click("#openBtn"); pg.wait_for_timeout(250)
    check(pg.evaluate(CWVAR, "asg") == saved, f"再読込後も幅が復元 ({saved})")

    # ③ ダブルクリックで既定幅（COLS の w=64）に戻る
    pg.dblclick("#leftHead [data-resize-col='asg']")
    pg.wait_for_timeout(200)
    check(pg.evaluate(CWVAR, "asg") == 64, f"ダブルクリックで既定64pxに復帰 -> {pg.evaluate(CWVAR, 'asg')}")
    check(pg.evaluate("()=>!('asg' in JSON.parse(localStorage.getItem('wbsColWidths')||'{}'))"),
          "保存値も削除される（既定に戻す＝上書きを消す）")

    # ④ ドラッグ中は再描画しない：DOMノードの同一性で見る（render()は innerHTML を作り直す＝別ノードになる）
    pg.evaluate("()=>{window.__row=document.querySelector('#leftRows .lrow');"
                "window.__hd=document.querySelector('#leftHead .h');}")
    box = pg.locator("#leftHead [data-resize-col='asg']").bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    pg.mouse.move(x, y); pg.mouse.down()
    pg.mouse.move(x + 60, y, steps=20)          # 20回の mousemove
    same = pg.evaluate("()=>window.__row===document.querySelector('#leftRows .lrow')"
                       "&&window.__hd===document.querySelector('#leftHead .h')")
    grew = pg.evaluate(CWVAR, "asg") > 64
    pg.mouse.up(); pg.wait_for_timeout(200)
    check(same, "ドラッグ中は行/ヘッダのDOMが作り直されない（＝render()を呼んでいない）")
    check(grew, "それでもドラッグ中に幅は追従する（CSS変数の書き換えだけ）")
    check(pg.evaluate("()=>window.__row!==document.querySelector('#leftRows .lrow')"),
          "mouseup で1回だけ確定の再描画が走る")
    check(len(errors) == 0, f"最後までJSエラー無し -> {errors}")

    b.close()
finish(errors)
