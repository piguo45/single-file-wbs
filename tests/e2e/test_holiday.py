"""祝日設定（トップレベル data.holidays）。日付ヘッダの祝日を赤字＋名称ツールチップ、
土日/祝日の列をガント全高で薄ピンクに塗る（オーバーレイ矩形）。文字列形と {date,name} 形の両対応・graceful。"""
from playwright.sync_api import sync_playwright
from common import VIEWER, CLOCK_PIN, check, finish

# 本日2026-06-15固定。6/12(金)=文字列祝日, 6/22(月)=名称付き祝日, 6/13/14=土日, 不正日付=無視
DATA = {
    "holidays": ["2026-06-12", {"date": "2026-06-22", "name": "創立記念日"}, "2026-13-99"],
    "projects": [{
        "name": "P", "milestones": [],
        "tasks": [{"id": "1", "name": "作業", "qty": 1, "hours": 8, "assignee": "佐藤",
                   "plan": {"start": "2026-06-10", "end": "2026-06-24"},
                   "actual": {"start": "2026-06-10", "end": None}, "note": ""}]
    }]
}

errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 500})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script(CLOCK_PIN)
    pg.goto(VIEWER)
    pg.evaluate("(d)=>window.renderData(d)", DATA)
    pg.wait_for_timeout(250)

    cell = lambda d: pg.eval_on_selector_all(
        "#dates .d",
        "(els,target)=>{const i=els.findIndex(e=>e.querySelector('div')&&e.querySelector('div').textContent==target);"
        "return i<0?null:{cls:els[i].className,title:els[i].getAttribute('title'),"
        "color:getComputedStyle(els[i]).color};}", d)

    # 祝日（名称付き 6/22）＝.hol・赤字・title=名称
    c22 = cell("22")
    check(c22 is not None and "hol" in c22["cls"], "6/22ヘッダに hol クラス")
    check(c22 and c22["color"] == "rgb(220, 38, 38)", f"6/22が赤字(#dc2626) 実={c22 and c22['color']}")
    check(c22 and c22["title"] == "創立記念日", f"6/22にツールチップ名称 実={c22 and c22['title']}")

    # 祝日（文字列形 6/12・名称なし）＝.hol・赤字・title無し
    c12 = cell("12")
    check(c12 is not None and "hol" in c12["cls"], "6/12(文字列形)に hol クラス")
    check(c12 and not c12["title"], "6/12は名称なし＝title属性なし")

    # 土日（6/13土・6/14日）＝.sat/.sun（祝日ではない＝赤字でない）
    c13 = cell("13")
    check(c13 is not None and "sat" in c13["cls"] and "hol" not in c13["cls"], "6/13は土(sat・holでない)")

    # 不正日付の祝日は無視（クラッシュしない・holセルは2つだけ）
    holn = pg.eval_on_selector_all("#dates .d.hol", "e=>e.length")
    check(holn == 2, f"不正日付祝日は無視＝holセルは2つ 実={holn}")

    # ガント列の薄ピンク＝オーバーレイ矩形（土日+祝日ぶん）。全高（rowsH）で塗る
    rects = pg.eval_on_selector_all("#overlay rect",
        "els=>els.map(e=>({h:+e.getAttribute('height'),op:e.getAttribute('opacity'),fill:e.getAttribute('fill')}))")
    check(len(rects) >= 3, f"土日/祝日ぶんの列矩形がある 実={len(rects)}")
    check(all(r["fill"] == "#d94f72" and float(r["op"]) < 0.5 for r in rects), "列矩形は半透明ピンク")
    check(len(set(r["h"] for r in rects)) == 1 and rects[0]["h"] > 0, "全矩形が同じ全高(rowsH)")

    # #75: 残り営業日＝土日＋祝日を除外。本日6/15→終了6/24＝10日。土日(6/20,21)＋祝日(6/22)を除く＝7日
    import re
    stat = pg.eval_on_selector("#stat", "e=>e.innerText")
    m = re.search(r"残り：(\d+)日", stat)
    check(m is not None and m.group(1) == "7", f"残り営業日が土日+祝日除外で7日 実={m and m.group(1)} / {stat[:60]}")
    b.close()

finish(errors)
