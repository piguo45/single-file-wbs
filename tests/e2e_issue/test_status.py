"""導出状態は3つ（未着手／対応中／完了）＋横断の印（待ち・凍結・未決・期限超過・催促・★）。
   優先順位・期限超過の赤字・警告⚠・件数サマリ。本日=CLOCK_PIN(2026-09-15)固定。
   異常系（enum不正）ではサブ表示なしに落ちることも確認する。"""
from playwright.sync_api import sync_playwright
from common import S, VIEWER, check, finish, load_test_json, new_page

errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_page(b, viewport={"width": 1500, "height": 900})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(VIEWER)
    pg.evaluate("d=>window.renderData(d)", load_test_json("正常_全機能.json"))
    pg.wait_for_timeout(200)

    st = pg.eval_on_selector_all(S("#tbody td.state"),
        "e=>e.map(x=>[x.querySelector('.bdg').className, x.querySelector('.bdg').innerText, (x.querySelector('.sub')||{}).innerText||''])")
    want = [["bdg s-wip", "対応中", ""], ["bdg s-wip", "対応中", ""], ["bdg s-wip", "対応中", ""],
            ["bdg s-wip", "対応中", ""], ["bdg s-wip", "対応中", ""],
            ["bdg s-closed", "完了", "解決"],
            ["bdg s-closed", "完了", "不対応"],
            ["bdg s-closed", "完了", "発生せず"]]
    check(st == want, f"状態は3つだけ（済んだ行動が1つでもあれば対応中・閉じたら完了）\n     得 {st}")
    # 待ち・凍結・未決は状態ではなく「印」＝状態バッジの下に小さく並ぶ
    mk = pg.eval_on_selector_all(S("#tbody tr"),
        "e=>e.map(x=>[x.querySelector('td.num').innerText, [...x.querySelectorAll('td.state .mk')].map(m=>m.innerText)])")
    drop = lambda ms: [m for m in ms if not (m.startswith("未着手 ") or m.startswith("待ち ") and m.endswith("日"))]
    mk = [[n, drop(ms)] for n, ms in mk]     # 経過日数（未着手N日／待ちN日）はここでは見ない
    check(mk == [["1", ["未決 1"]], ["2", ["未決 2"]], ["3", ["待ち 企画部"]],
                 ["4", ["待ち 開発部（9/5）", "⚠ 催促"]], ["5", ["凍結 移行が完了したら"]],
                 ["6", []], ["7", []], ["8", []]],
          f"印＝待ち／凍結／未決／催促。完了(#6-8)には付けない\n     得 {mk}")
    # 完了は pending より優先（#4 は pending も closed も無いが、#6 は closed のみ）
    over = pg.eval_on_selector_all(S("#tbody tr"),
        "e=>e.map(x=>[x.querySelector('td.num').innerText, !!x.querySelector('td.due.overdue')])")
    check([o[0] for o in over if o[1]] == ["1", "4"],
          f"期限超過（赤字）は未完了の #1(9/10)・#4(9/1) だけ -> {over}")
    check(not any(o[1] for o in over if o[0] in ("6", "8")),
          "期限が過ぎていても完了行は赤にしない（#6=9/5・#8=8/20）")
    col = pg.eval_on_selector(S("#tbody td.due.overdue"), "e=>getComputedStyle(e).color")
    check(col == "rgb(192, 57, 43)", f"期限超過は赤字 -> {col}")

    warns = pg.eval_on_selector_all(S("#tbody tr"),
        "e=>e.map(x=>[x.querySelector('td.num').innerText, !!x.querySelector('.warn')])")
    check([w[0] for w in warns if w[1]] == ["2", "3"],
          f"未回答警告⚠は #2(完了条件が空)・#3(二つの問い両方空) -> {warns}")
    tip = pg.eval_on_selector(S("#tbody .warn"), "e=>e.getAttribute('title')")
    check(tip and "空" in tip, f"⚠ にはツールチップが付く -> {tip!r}")

    cnts = pg.eval_on_selector_all(S("#counts .cnt"), "e=>e.map(x=>x.innerText.replace(/\\s+/g,' ').trim())")
    check(cnts == ["未着手 0", "対応中 5", "完了 3",
                   "待ち 2", "凍結 1", "未決 2", "⚠ 期限超過 2", "⚠ 催促 1", "★ 更新 4"],
          f"件数＝状態3つ ｜ 印はすべて課題数（0 の印は並べない・★は完了も数える） -> {cnts}")
    check(pg.eval_on_selector_all(S("#counts .cnt-sep"), "e=>e.length") == 1,
          "状態と印のあいだに区切りを1つ入れる")

    # 担当列は無い。たたんだ時の詳細＝次の一手1行（未の最初の行動・完了した課題は空）
    check(pg.eval_on_selector_all(S("#tbody td.asg"), "e=>e.length") == 0, "担当列は存在しない")
    tag = lambda: pg.eval_on_selector_all(S("#tbody td.detail"),
        "e=>e.map(x=>x.innerText.replace(/\\n/g,' ').trim())")
    pg.click(S("#allCaret")); pg.wait_for_timeout(200)                            # 全たたみ
    want_next = ["未 9/11 資料作成、内部Rv 担当：ぴぐお/Aさん",   # #1 対応中：未の最初
                 "未 (調整中) チューニング方針を決める 担当：Aさん",  # #2 未決
                 "",                                                 # #3 保留：未の行動が無い
                 "未 (調整中) 受領後に検証を再開 担当：ぴぐお",     # #4 保留でも次の一手は出す
                 "",                                                 # #5 保留：未の行動が無い
                 "", "", ""]                                         # #6/#7/#8 完了＝空
    check(tag() == want_next, f"たたんだ詳細＝次の一手1行\n     得 {tag()}")
    check(pg.eval_on_selector_all(S("#tbody tr.st-closed td.detail *"), "e=>e.length") == 0,
          "完了の課題の詳細は空（閉じた課題に「次の一手」は無い）")
    pg.click(S("#allCaret")); pg.wait_for_timeout(200)                            # 全展開（次の fixture に持ち越さない）

    # 異常系：enum が既知値以外 → バッジ無し（保留/完了のまま落ちない）
    pg.evaluate("d=>window.renderData(d)", load_test_json("異常_enum不正.json"))
    pg.wait_for_timeout(150)
    st2 = pg.eval_on_selector_all(S("#tbody td.state"),
        "e=>e.map(x=>[x.querySelector('.bdg').innerText, (x.querySelector('.sub')||{}).innerText||''])")
    check(st2 == [["未着手", ""], ["未着手", ""], ["未着手", ""], ["完了", ""]],
          f"how が不正ならサブ表示なし・kind が不正でも状態は落ちない -> {st2}")
    mk2 = pg.eval_on_selector_all(S("#tbody tr:nth-child(3) td.state .mk"), "e=>e.map(x=>x.innerText)")
    check([m for m in mk2 if not m.endswith("日")] == ["待ち"],
          f"kind が既知値でなければ「待ち」に寄せる（相手が空なら添え字なし） -> {mk2}")
    pr = pg.eval_on_selector_all(S("#tbody td.prio .bdg"), "e=>e.map(x=>[x.className, x.innerText])")
    check(pr[0] == ["bdg p-mid", "中"] and pr[1] == ["bdg p-mid", "中"],
          f"priority が3値以外 / 数値 → mid 扱い -> {pr}")
    b.close()
finish(errors)
