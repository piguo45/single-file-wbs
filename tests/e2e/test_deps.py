"""依存タブ（構造の軸・#66）: 右ペインの3つ目のタブ。読む専用の view として検証する。

見るもの（docs/design/brief-deps.md v0.2 §3 画面・§5 計算）:
  ① `_deps` を持つ葉が○・依存が矢印・◇は案件の最遅マイルストーン
  ② 自動配置が決定的（タブを往復しても同じ座標）・1マスおきの格子・隣り合わない
  ③ 最長経路の日数と経路が独立計算と一致し、赤い○／太い赤矢印がその経路
  ④ 違反（予定で割れ／前工程の実遅れで割れ）の判定
  ⑤ ○のホバー（数字・備考の先頭2行・AI 推定の根拠・課題の印）とクリックの吹き出し
  ⑥ C1: `_deps` を持つ葉が無い JSON では図も計算も走らせない（案内だけ）
  ⑦ 時間タブへ戻すと左の情報表とフィルタバーが復帰（display:none を残さない）
  ⑧ ズーム 50/75/100%・EN 切替・ダブルクリックで時間タブのその行へ
  ⑨ `_deps`／`_pos` の round-trip（編集して保存しても消えない）と参照の追従（id 変更・削除・集計化）

本日は CLOCK_PIN（2026-06-15）固定。fixture は tests/正常_依存.json。
"""
import json
from playwright.sync_api import sync_playwright
from common import (ROOT, VIEWER, check, finish, granted_handle_init,
                    load_test_json, new_page)

DATA = load_test_json("正常_依存.json")
PROJ = DATA["projects"][0]
LEAVES = {n["id"]: n for n in PROJ["tasks"][0]["children"]}
DEPS = {i: n["_deps"] for i, n in LEAVES.items() if isinstance(n.get("_deps"), list)}
N_NODES = len(DEPS)
N_EDGES = sum(len(v) for v in DEPS.values())

NODES = ".dsvg g.dnode"
EDGES = ".dsvg g.dedge"


def longest_path():
    """最長経路（日数の和が最大の経路）をビューアの式を借りずに計算する."""
    import datetime as dt
    days = {}
    for key in DEPS:
        plan = LEAVES[key]["plan"]
        s = dt.date.fromisoformat(plan["start"])
        e = dt.date.fromisoformat(plan["end"])
        days[key] = (e - s).days + 1
    best: dict[str, tuple[int, list[str]]] = {}

    def walk(key):
        if key in best:
            return best[key]
        up, path = 0, []
        for pre in DEPS[key]:
            u, q = walk(pre)
            if u > up:
                up, path = u, q
        best[key] = (up + days[key], path + [key])
        return best[key]

    return max((walk(k) for k in DEPS), key=lambda t: t[0])


EXP_DAYS, EXP_PATH = longest_path()

errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_page(b, viewport={"width": 1500, "height": 900})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
    pg.on("dialog", lambda d: d.accept())
    pg.goto(VIEWER)
    pg.evaluate("d => window.renderData(d)", DATA)
    pg.wait_for_timeout(150)

    check(pg.locator('#rtabs .rtab[data-view="deps"]').count() == 1, "「依存」タブが1つ出ている")
    check(pg.locator(NODES).count() == 0, "時間タブでは依存の図を描かない（C1・描画パスに載せない）")

    pg.click('#rtabs .rtab[data-view="deps"]')
    pg.wait_for_selector(".dsvg")
    pg.wait_for_timeout(120)

    # ① 図の中身
    check(pg.locator(".dfig").count() == 1, "`_deps` を持つ案件だけ図を出す（もう1案件は出さない）")
    check(pg.locator(NODES).count() == N_NODES, f"○の数＝`_deps` を持つ葉の数（{N_NODES}）")
    check(pg.locator(EDGES).count() == N_EDGES, f"矢印の数＝依存の本数（{N_EDGES}）")
    check(pg.locator(".dsvg .dms").count() == 1, "◇（最遅マイルストーン）が1つ")
    check(pg.locator(".dsvg .dnum").count() == N_EDGES, "矢印の上に日数が出る（矢印と同数）")
    check(pg.eval_on_selector("#left", "el => getComputedStyle(el).display") == "none"
          and pg.eval_on_selector("#filterBar", "el => getComputedStyle(el).display") == "none",
          "依存タブでは左の情報表とフィルタバーが隠れる（図は全幅）")

    cells = "() => [...document.querySelectorAll('.dsvg g.dnode')].map(g => [g.dataset.id, +g.dataset.c, +g.dataset.r])"
    pos1 = pg.evaluate(cells)

    # ② 決定的・1マスおき・隣り合わない
    pg.click('#rtabs .rtab[data-view="time"]')
    pg.wait_for_selector("#ganttBg")
    pg.click('#rtabs .rtab[data-view="deps"]')
    pg.wait_for_selector(".dsvg")
    pg.wait_for_timeout(120)
    check(pg.evaluate(cells) == pos1, "描き直しても自動配置の座標が同じ（決定的）")
    check(all(c % 2 == 0 and r % 2 == 0 for _, c, r in pos1), "全○が偶数の列・行（1マスおき）にある")
    check(len({(c, r) for _, c, r in pos1}) == len(pos1), "同じマスに2つ置かれていない")
    near = [(a[0], b2[0]) for a in pos1 for b2 in pos1
            if a[0] < b2[0] and max(abs(a[1] - b2[1]), abs(a[2] - b2[2])) < 2]
    check(not near, f"隣り合う（周りの1マスに入る）○の組が無い -> {near[:3]}")
    check(["1.6", 12, 8] in pos1, f"`_pos` を書いた葉はその位置に置かれる（1.6 → [12,8]） -> {pos1}")

    # ③ 最長経路
    txt = pg.eval_on_selector(".dsvg", "el => el.textContent")   # SVG は inner_text が使えない
    check(f"最長経路 {EXP_DAYS} 日" in txt, f"右下に「最長経路 {EXP_DAYS} 日」が出る")
    check(" → ".join(EXP_PATH) in txt, f"経路の id 列が出る（{' → '.join(EXP_PATH)}）")
    red = pg.eval_on_selector_all(NODES + "[data-crit]", "els => els.map(e => e.dataset.id)")
    check(sorted(red) == sorted(EXP_PATH), f"赤い輪の○がその経路 -> {sorted(red)}")
    crit_edges = pg.locator(EDGES + ".dcrit").count()
    check(crit_edges == len(EXP_PATH) - 1, f"太い赤矢印が経路の本数（{crit_edges}）")

    # ④ 違反（予定で割れ＝1.6／前工程の実遅れで割れ＝1.8）
    viol = pg.eval_on_selector_all(NODES + "[data-viol]", "els => els.map(e => e.dataset.id)")
    late = pg.eval_on_selector_all(NODES + "[data-late]", "els => els.map(e => e.dataset.id)")
    check(viol == ["1.6"], f"予定だけで割れている○が 1.6 -> {viol}")
    check(late == ["1.8"], f"前工程の実遅れで割れた○が 1.8 -> {late}")

    # ⑤ ホバーの中身と吹き出し
    tip = pg.eval_on_selector('.dsvg g.dnode[data-id="1.6"] title', "el => el.textContent")
    for frag in ["1.6 帳票の差し替え", "開始 6/17 → 終了 6/20", "違反：前工程 1.3",
                 "この○を通る最長経路", "予定との差：◇まで", "前工程：1.3", "後続：なし",
                 "AI推定：依存 AI 推定", "課題 #1（未決・待ち）", "ダブルクリック＝時間タブで見る"]:
        check(frag in tip, f"ホバーに「{frag}」が出る")
    note_tip = pg.eval_on_selector('.dsvg g.dnode[data-id="1.3"] title', "el => el.textContent")
    check(note_tip.count("備考：") == 2 and "3行目はホバーに出さない" not in note_tip,
          "備考は先頭2行だけ出す")
    pg.click('.dsvg g.dnode[data-id="1.6"] .dcore')
    pg.wait_for_timeout(120)
    check(pg.is_visible("#depsPop"), "○のクリックで吹き出しが固定される")
    check("課題 #1（未決・待ち）" in pg.inner_text("#depsPop"), "吹き出しはホバーと同じ中身")
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(100)
    check(pg.locator("#depsPop").count() == 0, "Esc で吹き出しが閉じる")

    # ⑧ ズーム
    z1 = pg.eval_on_selector(".dzoomg", "el => el.getAttribute('transform')")
    pg.click('.dzoom[data-z="50"]')
    pg.wait_for_timeout(150)
    z2 = pg.eval_on_selector(".dzoomg", "el => el.getAttribute('transform')")
    check(z1 != z2 and "0.5" in z2, f"ズーム 50% で transform が変わる（{z1} → {z2}）")
    check(pg.locator(NODES).count() == N_NODES, "ズームしても○の数は変わらない")
    pg.click('.dzoom[data-z="100"]')
    pg.wait_for_timeout(150)

    # EN 切替（UI文言が ja/en 両方にある）
    pg.click("#langBtn")
    pg.wait_for_timeout(150)
    check(pg.inner_text('#rtabs .rtab[data-view="deps"]') == "Deps", "EN でタブ名が Deps")
    check(f"Longest path {EXP_DAYS} d" in pg.eval_on_selector(".dsvg", "el => el.textContent"),
          "EN で「Longest path N d」が出る")
    check("Predecessors: " in pg.eval_on_selector('.dsvg g.dnode[data-id="1.6"] title',
                                                  "el => el.textContent"), "EN でホバーも英語")
    pg.click("#langBtn")
    pg.wait_for_timeout(150)

    # ⑧ ダブルクリック＝時間タブのその行へ（表示中は左の情報表を隠しているので、飛ぶ前に時間タブへ戻す）
    pg.dblclick('.dsvg g.dnode[data-id="1.6"] .dcore')
    pg.wait_for_timeout(300)
    check(pg.locator('#rtabs .rtab[data-view="time"].on').count() == 1, "ダブルクリックで時間タブへ戻る")
    check(pg.locator("#leftRows .lrow.pmjump").is_visible(), "その行が見える形で強調される（既存の gotoWbs）")

    # 課題側の `WBS 1.6` リンクも同じ入口（gotoWbs）。依存タブを見たまま飛んでも行が見えること
    pg.click('#rtabs .rtab[data-view="deps"]')
    pg.wait_for_selector(".dsvg")
    pg.click('[data-pmv="issue"]')                               # 上の切替を「課題」へ
    pg.wait_for_timeout(250)
    pg.click('#isMain .lk [data-jw]')                             # 課題 #1 の `WBS 1.6` リンク
    pg.wait_for_timeout(450)
    check(pg.locator('#rtabs .rtab[data-view="time"].on').count() == 1,
          "課題の WBS リンクで飛ぶと時間タブへ戻る（依存タブのままだと左表が隠れていて行が見えない）")
    check(pg.locator("#leftRows .lrow.pmjump").is_visible(), "飛び先の行が見える形で強調される")

    # ⑦ 左の情報表とフィルタバーの復帰
    check(pg.eval_on_selector("#left", "el => getComputedStyle(el).display") != "none"
          and pg.eval_on_selector("#filterBar", "el => getComputedStyle(el).display") != "none",
          "時間タブに戻すと左の情報表とフィルタバーが復帰する")
    check("none" not in (pg.eval_on_selector("#left", "el => el.style.display")
                         + pg.eval_on_selector("#filterBar", "el => el.style.display")),
          "style に display:none を残さない")
    check(pg.locator(".dsvg").count() == 0, "依存タブの図は消えている")

    # ⑥ C1: `_deps` が1つも無い JSON では計算も図も走らせない（案内だけ）
    plain = {"projects": [{"name": "P", "milestones": [], "tasks": [
        {"id": "1", "name": "作業", "qty": 1, "hours": 8, "assignee": "",
         "plan": {"start": "2026-06-10", "end": "2026-06-12"},
         "actual": {"start": None, "end": None}, "note": ""}]}]}
    pg.evaluate("d => window.renderData(d)", plain)
    pg.wait_for_timeout(120)
    pg.click('#rtabs .rtab[data-view="deps"]')
    pg.wait_for_timeout(150)
    check(pg.locator(".dsvg").count() == 0 and pg.locator(".dempty").count() == 1,
          "`_deps` を持つ葉が無ければ図を描かない（案内だけ）")
    check("_deps" in pg.inner_text(".dempty"), "案内は `_deps` の書き方を示す")
    pg.click('#rtabs .rtab[data-view="time"]')
    pg.wait_for_timeout(120)
    check(not errors, f"ここまで JS エラー 0 -> {errors[:2]}")

    # 壊れた依存でも落ちない（循環・参照切れ・集計ノードの _deps・予定日なし）
    for name in ("異常_依存_循環.json", "異常_依存_壊れ.json"):
        before = len(errors)
        pg.evaluate("d => window.renderData(d)", load_test_json(name))
        pg.wait_for_timeout(120)
        pg.click('#rtabs .rtab[data-view="deps"]')
        pg.wait_for_timeout(200)
        body = pg.inner_text("#rightBody")
        check(len(errors) == before and "NaN" not in body, f"{name}: 落ちない・NaN 無し")
        pg.click('#rtabs .rtab[data-view="time"]')
        pg.wait_for_timeout(120)
    pg.evaluate("d => window.renderData(d)", load_test_json("異常_依存_壊れ.json"))
    pg.click('#rtabs .rtab[data-view="deps"]')
    pg.wait_for_timeout(200)
    check("図に出せない作業が 1 件" in pg.inner_text(".dfig .dcap"),
          "予定日が無くて図に出せなかった葉の件数を見出しで断る（黙って落とさない）")
    b.close()

# ⑨ round-trip と参照の追従（編集モード＝別セッション。保存は既存の自動保存パスに任せる）
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_page(b, viewport={"width": 1500, "height": 900})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.add_init_script(granted_handle_init(DATA))
    pg.goto(VIEWER)
    pg.click("#openBtn"); pg.wait_for_timeout(200)
    pg.click("#editBtn"); pg.wait_for_timeout(250)

    def saved():
        d = json.loads(pg.evaluate("()=>window.__file"))
        out = {}
        def walk(ns):
            for n in ns:
                if n.get("children"):
                    walk(n["children"])
                else:
                    out[str(n["id"])] = n
        walk(d["projects"][0]["tasks"])
        return out

    def path_of(tid):
        """その id の行の data-path（行の並びに依存しない指し方）."""
        return pg.evaluate("""(id) => {
            const i = [...document.querySelectorAll('#leftRows input[data-field="id"]')]
              .find(x => x.value === id);
            return i ? i.getAttribute('data-path') : null; }""", tid)

    def field(tid, f):
        return f'#leftRows input[data-field="{f}"][data-path="{path_of(tid)}"]'

    pg.fill(field("1.6", "note"), "備考を書き換えた")
    pg.dispatch_event(field("1.6", "note"), "change")
    pg.wait_for_timeout(600)
    s = saved()
    check(s["1.6"]["_deps"] == ["1.3"] and s["1.6"]["_pos"] == [12, 8],
          f"編集して保存しても `_deps`／`_pos` が残る（round-trip） -> {s['1.6'].get('_deps')}")
    check(s["1.1"]["_deps"] == [], "`_deps: []`（前工程なし）も空配列のまま残る")

    # id 変更 → 指していた矢印が付け替わる
    sel = field("1.1", "id")
    pg.fill(sel, "1.1x")
    pg.dispatch_event(sel, "change")
    pg.wait_for_timeout(600)
    s = saved()
    check(s["1.2"]["_deps"] == ["1.1x"] and s["1.4"]["_deps"] == ["1.1x"],
          f"id を変えると他の葉の `_deps` も付け替わる -> {s['1.2']['_deps']}")

    # 葉の削除 → 指していた矢印が外れる
    pg.click(f'#leftRows button[data-act="del"][data-path="{path_of("1.4")}"]')   # 1.4（データ移送）
    pg.wait_for_timeout(600)
    s = saved()
    check("1.4" not in s, "葉が消えている")
    check(s["1.5"]["_deps"] == ["1.3"] and s["1.8"]["_deps"] == [],
          f"消えた葉を指していた参照が外れる -> {s['1.5']['_deps']} / {s['1.8']['_deps']}")

    # ＋子で集計ノード化 → `_deps`/`_pos` は子1へ移り、指していた矢印も子1へ
    pg.click(f'#leftRows button[data-act="addchild"][data-path="{path_of("1.3")}"]')   # 1.3（実装）
    pg.wait_for_timeout(600)
    s = saved()
    check(s.get("1.3.1", {}).get("_deps") == ["1.2"],
          f"集計ノード化で `_deps` は子1へ移る -> {s.get('1.3.1', {}).get('_deps')}")
    check(s["1.5"]["_deps"] == ["1.3.1"] and s["1.6"]["_deps"] == ["1.3.1"],
          f"集計ノードを指していた矢印は子1へ付け替わる -> {s['1.5']['_deps']}")
    b.close()

finish(errors)
