"""フィルタバー：状態3・優先度3・担当ドロップダウン・印6（待ち/凍結/未決/期限超過/催促/★更新）。
   軸内OR／軸間AND・印どうしもAND・サマリ不変・localStorage記憶。
   表示専用＝行を間引くだけでデータは変えない。本日=CLOCK_PIN(2026-09-15)。"""
from playwright.sync_api import sync_playwright
from common import S, VIEWER, check, finish, load_test_json, new_page, reload

DATA = load_test_json("正常_全機能.json")

errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1500, "height": 900})
    pg = new_page(ctx)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(VIEWER)
    pg.evaluate("d=>window.renderData(d)", DATA)
    pg.wait_for_timeout(200)

    ids = lambda: pg.eval_on_selector_all(S("#tbody td.num"), "e=>e.map(x=>x.innerText)")
    counts = lambda: pg.inner_text(S("#counts"))

    check(pg.is_visible(S("#filterBar")), "データ読込でフィルタバーが表示される")
    n_state = pg.eval_on_selector_all(S("#filterBar .sf-btn[data-state]"), "e=>e.length")
    n_prio = pg.eval_on_selector_all(S("#filterBar .sf-btn[data-prio]"), "e=>e.length")
    n_mark = pg.eval_on_selector_all(S("#filterBar .sf-btn[data-mark]"), "e=>e.length")
    check((n_state, n_prio, n_mark) == (3, 3, 6), f"状態3・優先度3・印6 -> {(n_state, n_prio, n_mark)}")
    labels = pg.eval_on_selector_all(S("#filterBar .sf-btn[data-mark]"), "e=>e.map(x=>x.innerText)")
    check(labels == ["待ち", "凍結", "未決", "期限超過", "催促", "★ 更新"],
          f"印のピルは印の名前だけ（「のみ」は付けない） -> {labels}")
    tips = pg.eval_on_selector_all(S("#filterBar .sf-btn[data-mark]"), "e=>[...new Set(e.map(x=>x.title))]")
    check(tips == ["この印がある課題だけ表示（表示専用）"],
          f"押した時の意味はツールチップで言う -> {tips}")
    check(ids() == ["1", "2", "3", "4", "5", "6", "7", "8"], f"既定は全ON -> {ids()}")
    base = counts()

    # 状態：完了OFF（軸内OR＝残り3状態のいずれか）
    pg.click(S('.sf-btn[data-state="closed"]')); pg.wait_for_timeout(150)
    check(ids() == ["1", "2", "3", "4", "5"], f"完了OFF -> {ids()}")
    check(counts() == base, "件数サマリは絞り込みで不変（完了込み）")
    check(pg.eval_on_selector(S('.sf-btn[data-state="closed"]'), "e=>e.classList.contains('on')") is False,
          "OFFのピルは on クラスが外れる")
    # 軸間AND：状態(未着手/対応中) × 優先度(高のみ)
    pg.click(S('.sf-btn[data-prio="mid"]')); pg.click(S('.sf-btn[data-prio="low"]')); pg.wait_for_timeout(150)
    check(ids() == ["1", "4"], f"状態AND優先度 -> {ids()}")
    check(counts() == base, "軸を重ねてもサマリ不変")
    pg.click(S('.sf-btn[data-state="wip"]')); pg.wait_for_timeout(150)
    check(ids() == [], f"対応中も切れば0件（未着手は0件） -> {ids()}")
    pg.click(S('.sf-btn[data-state="wip"]')); pg.wait_for_timeout(150)

    # 全部戻す
    for k in ("closed",):
        pg.click(S(f'.sf-btn[data-state="{k}"]'))
    for k in ("mid", "low"):
        pg.click(S(f'.sf-btn[data-prio="{k}"]'))
    pg.wait_for_timeout(150)
    check(len(ids()) == 8, "全ONに戻る")

    # 担当ドロップダウン（候補＝全課題の actions[].assignee のユニーク集合・複数選択・全選択/全解除）
    opts = pg.eval_on_selector_all(S("#filterBar .asg-cb"), "e=>e.map(x=>x.getAttribute('data-asg'))")
    check(sorted(opts) == sorted(["", "Aさん", "ぴぐお", "ぴぐお/Aさん", "佐藤"]),
          f"候補は行動の担当のユニーク集合（複数表記は1文字列） -> {opts}")
    pg.click(S("#filterBar .asg-dd > summary")); pg.wait_for_timeout(100)   # details を開く（開閉状態は再描画で保持される）
    check(pg.is_visible(S("#filterBar .asg-list")), "ドロップダウンが開く")
    pg.click(S("#filterBar .asg-none")); pg.wait_for_timeout(150)
    check(ids() == [], f"全解除で0件（graceful） -> {ids()}")
    pg.click(S("#filterBar .asg-all")); pg.wait_for_timeout(150)
    check(len(ids()) == 8, "全選択で全件に戻る")

    # 軸内OR：課題は「その課題の行動の担当のどれかが表示ONなら表示」
    pg.uncheck(S('#filterBar .asg-cb[data-asg="ぴぐお"]')); pg.wait_for_timeout(150)
    check(ids() == ["1", "2", "3", "5", "7", "8"],
          f"ぴぐお を外しても #1 は他の担当(空/ぴぐお/Aさん)の行動があるので残る -> {ids()}")
    check(counts() == base, "担当で絞ってもサマリ不変")

    def only(asg):
        pg.click(S("#filterBar .asg-none")); pg.wait_for_timeout(120)
        pg.check(S(f'#filterBar .asg-cb[data-asg="{asg}"]')); pg.wait_for_timeout(150)
        return ids()

    # 複数の行動に別々の担当がいる課題(#1)は、そのどちらの担当で絞っても出る
    check(only("ぴぐお") == ["1", "4", "6"], f"担当=ぴぐお -> {only('ぴぐお')}")
    check(only("ぴぐお/Aさん") == ["1"], f"担当=ぴぐお/Aさん（#1 は両方で出る） -> {only('ぴぐお/Aさん')}")
    check(only("佐藤") == ["5", "8"], f"担当=佐藤 -> {only('佐藤')}")
    check(only("") == ["1", "3"], f"担当=(未割当)＝担当が空の行動を持つ課題 -> {only('')}")
    pg.click(S("#filterBar .asg-all")); pg.wait_for_timeout(150)
    check(len(ids()) == 8, "担当を全選択で全件に戻る")

    # 印（それぞれ単独トグル）
    def mark_only(k):
        pg.click(S(f'.sf-btn[data-mark="{k}"]')); pg.wait_for_timeout(150)
        out = ids()
        pg.click(S(f'.sf-btn[data-mark="{k}"]')); pg.wait_for_timeout(150)
        return out
    check(mark_only("wait") == ["3", "4"], "待ちの印だけ表示")
    check(mark_only("frozen") == ["5"], "凍結の印だけ表示")
    check(mark_only("open") == ["1", "2"], "未決の印だけ表示")
    check(mark_only("ovd") == ["1", "4"], "期限超過の印だけ表示")
    check(mark_only("nudge") == ["4"], "催促の印だけ表示")
    st_ids = mark_only("star")
    check(st_ids == ["1", "2", "3", "6"], f"★更新の印だけ表示（★は完了にも付くので #6 も出る） -> {st_ids}")
    # 印どうしを重ねると AND
    pg.click(S('.sf-btn[data-mark="wait"]')); pg.click(S('.sf-btn[data-mark="nudge"]')); pg.wait_for_timeout(150)
    check(ids() == ["4"], f"待ち AND 催促 -> {ids()}")
    check(counts() == base, "印で絞ってもサマリ不変")
    pg.click(S('.sf-btn[data-mark="wait"]')); pg.wait_for_timeout(150)
    check(ids() == ["4"], f"催促だけ残す -> {ids()}")
    pg.click(S('.sf-btn[data-prio="high"]')); pg.wait_for_timeout(150)
    check(ids() == [], f"印 AND 優先度(高OFF) -> {ids()}")
    pg.click(S('.sf-btn[data-prio="high"]')); pg.wait_for_timeout(150)

    # localStorage 記憶（リロードしても復元）
    pg.click(S('.sf-btn[data-state="todo"]')); pg.wait_for_timeout(150)
    reload(pg); pg.wait_for_timeout(150)
    pg.evaluate("d=>window.renderData(d)", DATA); pg.wait_for_timeout(200)
    check(pg.eval_on_selector(S('.sf-btn[data-mark="nudge"]'), "e=>e.classList.contains('on')"),
          "リロード後も 催促 の絞り込みを記憶")
    check(pg.eval_on_selector(S('.sf-btn[data-state="todo"]'), "e=>e.classList.contains('on')") is False,
          "リロード後も 未着手OFF を記憶")
    check(ids() == ["4"], f"リロード後の絞り込み結果 -> {ids()}")

    # 表示専用＝トグルを元に戻せば元の並び・件数に完全に戻る（データを削っていない証拠）
    pg.click(S('.sf-btn[data-state="todo"]')); pg.click(S('.sf-btn[data-mark="nudge"]')); pg.wait_for_timeout(200)
    check(ids() == ["1", "2", "3", "4", "5", "6", "7", "8"], f"全ONに戻すと全件が戻る -> {ids()}")
    check(counts() == base, "最後までサマリは不変")
    b.close()
finish(errors)
