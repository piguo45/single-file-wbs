"""依存タブの動くモック（deps_mock.html・第3版＝案G′）の自動検証（headless Chromium）.

既存の e2e（tests/e2e・tests/e2e_issue）は触らない。モックの検証はここだけで完結させる。
作法は tests/e2e/common.py に合わせる（check/finish・本日固定・JSエラーの収集）。

見るもの（brief-deps v0.2 §3〜§5 の要点）:
  ① JS エラー 0 で開ける
  ② ○15・矢印12・◇1
  ③ 自動配置が決定的（タブを往復して描き直しても座標が同じ）
  ④ 全○が1マスおきの格子（偶数）の上にあり、どの2つも隣り合わない
  ⑤ 最長経路の日数が独立計算と一致し、赤の○／矢印がその経路
  ⑥ 違反の○ 1件＋前工程の実遅れで割れた○ 2件
  ⑦ ゴム線：○A→○B のクリックで矢印 +1・`_deps` に入る／循環は拒否
  ⑧ 矢印の ✕ で −1／Ctrl+Z で戻る
  ⑨ ドラッグで `_pos` が付く（吸着は偶数マス）／「整列＝全部」で `_pos` が消える
  ⑩ 「図に載せる」で外すと○ −1・キーも消える
  ⑪ 時間タブに戻すと左表・フィルタバーが復帰（JS エラー 0）
  ⑫ ズーム 50% で SVG の transform が変わり、○の数は不変

使い方:
    uv run python scripts/deps_mock/smoke.py
"""

import json
import pathlib
import subprocess
import sys
import tempfile

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "tests" / "e2e"))      # check/finish/new_page を借りる（作法を二重に持たない）
from common import check, finish, new_page        # noqa: E402

sys.path.append(str(ROOT / "scripts"))
import build_deps_mock                            # noqa: E402  （_deps の表と目印を二重に持たない）

MOCK = ROOT / "deps_mock.html"
DEPS = build_deps_mock.DEPS
N_DEPS = len(DEPS)
N_EDGES = sum(len(v) for v in DEPS.values())

NODES = "#depsSvg g.dnode"
EDGES = "#depsSvg g.dedge"


def longest_path():
    """最長経路（日数の和が最大の経路）を smoke 側で独立に計算する（差し込み層の式を借りない）."""
    data = json.loads((ROOT / "wbs_demo.json").read_bytes().decode("utf-8"))

    def leaves(ns):
        for n in ns or []:
            if isinstance(n, dict) and n.get("children"):
                yield from leaves(n["children"])
            elif isinstance(n, dict):
                yield n

    import datetime as dt
    days = {}
    for leaf in leaves(data["projects"][0]["tasks"]):
        key = str(leaf.get("id"))
        if key in DEPS:                            # 日数＝予定の期間（暦日）＝end − start + 1
            s = dt.date.fromisoformat(leaf["plan"]["start"])
            e = dt.date.fromisoformat(leaf["plan"]["end"])
            days[key] = (e - s).days + 1
    best = {}                                      # best[id] = (日数の和, 経路)
    def walk(key):
        if key in best:
            return best[key]
        up, path = 0, []
        for p in DEPS[key]:
            u, q = walk(p)
            if u > up or (u == up and not path):
                up, path = u, q
        best[key] = (up + days[key], path + [key])
        return best[key]
    return max((walk(k) for k in DEPS), key=lambda t: t[0])


# --- 生成物としての検査（ブラウザを開く前に済ませる） ---
with tempfile.TemporaryDirectory() as tmp:        # worktree の外に出す（git status を汚さない）
    again = pathlib.Path(tmp) / "deps_mock.html"
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_deps_mock.py"),
                        "-o", str(again)], capture_output=True)
    check(r.returncode == 0, f"build_deps_mock.py が正常終了 -> {r.stderr.decode('utf-8', 'replace')[:200]}")
    check(r.returncode == 0 and again.read_bytes() == MOCK.read_bytes(),
          "deps_mock.html は再生成しても同じバイト列（冪等）")

src = MOCK.read_bytes().decode("utf-8")
i, j = src.find(build_deps_mock.BEGIN), src.find(build_deps_mock.END)
block = src[i:j + len(build_deps_mock.END)]
stripped = src.replace(build_deps_mock.HEADER + "\n", "", 1)
stripped = stripped[:stripped.find(build_deps_mock.BEGIN)] \
    + stripped[stripped.find(build_deps_mock.END) + len(build_deps_mock.END) + 1:]
check(stripped == (ROOT / "wbs_viewer.html").read_bytes().decode("utf-8"),
      "追記ブロックを除くと wbs_viewer.html とバイト一致（製品本体は無改変）")
check(block.count("</script") == 2, "追記ブロックの </script は2本ぶんだけ（埋め込みデータの早期終端なし）")

exp_days, exp_path = longest_path()

errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_page(b, viewport={"width": 1700, "height": 950})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
    dialogs = []

    def on_dialog(d):
        dialogs.append((d.type, d.message))
        d.accept("smoke")
    pg.on("dialog", on_dialog)

    pg.goto(MOCK.resolve().as_uri())
    pg.wait_for_selector("#leftRows .lrow")
    check(not errors, f"① 読み込みで JS エラー 0 -> {errors[:2]}")
    check(pg.locator('#rtabs .rtab[data-view="deps"]').count() == 1, "① 「依存」タブが1つ出ている")

    pg.click('#rtabs .rtab[data-view="deps"]')
    pg.wait_for_selector("#depsSvg")
    pg.wait_for_timeout(150)

    # ② 図の中身
    check(pg.locator(NODES).count() == N_DEPS, f"② ○の数＝_deps を持つ葉の数（{N_DEPS}）")
    check(pg.locator(EDGES).count() == N_EDGES, f"② 矢印の数＝依存の本数（{N_EDGES}）")
    check(pg.locator("#depsMs").count() == 1, "② ◇（最遅マイルストーン）が1つ")
    check(pg.locator("#depsSvg .dnum").count() == N_EDGES, "② 矢印の上に日数が出ている（矢印と同数）")
    check(pg.eval_on_selector("#left", "el => getComputedStyle(el).display") == "none"
          and pg.eval_on_selector("#filterBar", "el => getComputedStyle(el).display") == "none",
          "② 依存タブでは左の情報表とフィルタバーが隠れる（図は全幅）")

    cells = "() => [...document.querySelectorAll('#depsSvg g.dnode')]" \
            ".map(g => [g.dataset.id, +g.dataset.c, +g.dataset.r])"
    pos1 = pg.evaluate(cells)

    # ③ 自動配置が決定的（タブを往復＝描き直しても同じ絵）
    pg.click('#rtabs .rtab[data-view="time"]')
    pg.wait_for_selector("#ganttBg")
    pg.click('#rtabs .rtab[data-view="deps"]')
    pg.wait_for_selector("#depsSvg")
    pg.wait_for_timeout(150)
    check(pg.evaluate(cells) == pos1, "③ 描き直しても自動配置の座標が同じ（決定的）")

    # ④ 1マスおきの格子・どの2つも隣り合わない
    check(all(c % 2 == 0 and r % 2 == 0 for _, c, r in pos1), "④ 全○が偶数の列・行（1マスおき）にある")
    seen = {(c, r) for _, c, r in pos1}
    check(len(seen) == len(pos1), "④ 同じマスに2つ置かれていない")
    near = [(a[0], b2[0]) for a in pos1 for b2 in pos1
            if a[0] < b2[0] and max(abs(a[1] - b2[1]), abs(a[2] - b2[2])) < 2]
    check(not near, f"④ 隣り合う（周りの1マスに入る）○の組が無い -> {near[:3]}")

    # ⑤ 最長経路
    got = pg.evaluate("() => ({days: window.__DEPS.pathDays, path: window.__DEPS.path,"
                      " cross: window.__DEPS.crossings, msDays: window.__DEPS.msDays})")
    check(got["days"] == exp_days, f"⑤ 最長経路の日数が独立計算と一致（{got['days']} == {exp_days}）")
    check(got["path"] == exp_path, f"⑤ 経路そのものも一致（{' → '.join(got['path'])}）")
    red_nodes = pg.eval_on_selector_all(NODES + "[data-crit]", "els => els.map(e => e.dataset.id)")
    check(sorted(red_nodes) == sorted(exp_path), f"⑤ 赤い○がその経路（{sorted(red_nodes)}）")
    red_edges = pg.eval_on_selector_all(EDGES + ".dcrit", "els => els.map(e => e.dataset.from + '>' + e.dataset.to)")
    check(len(red_edges) == len(exp_path) - 1, f"⑤ 太い赤矢印が経路の本数（{len(red_edges)}）")
    txt = pg.eval_on_selector("#depsSvg", "el => el.textContent")   # SVG は inner_text が使えない
    check(("最長経路 " + str(exp_days)) in txt, f"⑤ 右下に「最長経路 {exp_days} 日」が出る")

    # ⑥ 違反
    check(pg.locator(NODES + "[data-viol]").count() == 1, "⑥ 違反の○が1件（予定だけで割れている）")
    check(pg.locator(NODES + "[data-late]").count() == 2, "⑥ 前工程の実遅れで割れた○が2件")

    # ⑦ ゴム線で結ぶ／循環は拒否
    e0 = pg.locator(EDGES).count()
    pg.click('#depsSvg g.dnode[data-id="2.1.2"] .dcore')      # 2.1.2 → 1.2 は循環（1.2→1.6→2.1.2）
    pg.click('#depsSvg g.dnode[data-id="1.2"] .dcore')
    pg.wait_for_timeout(200)
    check(pg.locator(EDGES).count() == e0, "⑦ 循環になる結びは拒否される（矢印は増えない）")
    check(any(d[0] == "alert" and "循環" in d[1] for d in dialogs), f"⑦ 循環は alert で断る -> {dialogs[-1:]}")
    pg.click('#depsSvg g.dnode[data-id="1.2"] .dcore')        # 1回目＝選択＋ゴム線
    check(pg.locator('#depsSvg g.dnode[data-id="1.2"] circle[stroke-dasharray]').count() == 1,
          "⑦ ○をクリックすると選択の破線が出る（ゴム線の始点）")
    pg.click('#depsSvg g.dnode[data-id="3.1"] .dcore')        # 2回目＝1.2 → 3.1 を結ぶ
    pg.wait_for_timeout(250)
    e1 = pg.locator(EDGES).count()
    check(e1 == e0 + 1, f"⑦ ○A→○B のクリックで矢印が1本増える（{e0} → {e1}）")
    read = """(id) => {
        const f=(o)=>o.flatMap(n=>n.children?f(n.children):[n]);
        const n=f(window.__PM.data().projects[0].tasks).find(x=>String(x.id)===id);
        return {deps:(n._deps||null), pos:(n._pos||null)}; }"""
    check("1.2" in (pg.evaluate(read, "3.1")["deps"] or []), "⑦ 3.1 の _deps に 1.2 が入った")

    # ⑧ 矢印の ✕ で外す → Ctrl+Z で戻る
    pg.locator('#depsSvg g.dedge[data-from="1.2"][data-to="3.1"] .dx circle').click(force=True)
    pg.wait_for_timeout(250)
    check(pg.locator(EDGES).count() == e0, f"⑧ 矢印の ✕ で依存が外れる（{e1} → {e0}）")
    pg.keyboard.press("Control+z")
    pg.wait_for_timeout(250)
    check(pg.locator(EDGES).count() == e1, f"⑧ Ctrl+Z で戻る（{e0} → {e1}）")
    pg.locator('#depsSvg g.dedge[data-from="1.2"][data-to="3.1"] .dx circle').click(force=True)
    pg.wait_for_timeout(250)                                   # 後の検査のため元の依存に戻しておく

    # ⑨ ドラッグで置く（_pos が付く・吸着は偶数マス）→ 整列＝全部で消える
    box = pg.locator('#depsSvg g.dnode[data-id="2.4.2"] .dcore').bounding_box()
    pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    pg.mouse.down()
    pg.mouse.move(box["x"] + box["width"] / 2 + 88, box["y"] + box["height"] / 2 + 88, steps=6)
    pg.mouse.up()
    pg.wait_for_timeout(300)
    pos = pg.evaluate(read, "2.4.2")["pos"]
    check(isinstance(pos, list) and len(pos) == 2, f"⑨ ドラッグした○に _pos が付く -> {pos}")
    check(bool(pos) and pos[0] % 2 == 0 and pos[1] % 2 == 0, f"⑨ 吸着先は偶数マス（1マスおき）-> {pos}")
    pg.keyboard.press("Control+z")
    pg.wait_for_timeout(250)
    check(pg.evaluate(read, "2.4.2")["pos"] is None, "⑨ Ctrl+Z で置き直しも戻る")
    pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    pg.mouse.down()
    pg.mouse.move(box["x"] + box["width"] / 2 + 88, box["y"] + box["height"] / 2 + 88, steps=6)
    pg.mouse.up()
    pg.wait_for_timeout(300)
    pg.click("#depsAlign > summary")
    pg.click("#depsAlignAll")
    pg.wait_for_timeout(300)
    check(pg.evaluate("""() => {
        const f=(o)=>o.flatMap(n=>n.children?f(n.children):[n]);
        return f(window.__PM.data().projects[0].tasks).every(n => !('_pos' in n)); }"""),
          "⑨ 「整列＝全部」で _pos が全部消える（自動配置に戻る）")
    check(pg.evaluate(cells) == pos1, "⑨ 整列後の配置は最初の自動配置と同じ")

    # ⑩ 図から外す
    pg.click("#depsPickBtn")
    pg.wait_for_timeout(200)
    check(pg.locator("#depsPick input.dpick").count() == 33, "⑩ 「図に載せる」に葉が33件ある")
    pg.locator('#depsPick input.dpick[data-id="2.4.2"]').uncheck()
    pg.wait_for_timeout(300)
    check(pg.locator(NODES).count() == N_DEPS - 1, f"⑩ 外すと○が減る（{N_DEPS} → {N_DEPS - 1}）")
    check(pg.evaluate(read, "2.4.2")["deps"] is None, "⑩ _deps キーそのものが消える")
    pg.keyboard.press("Escape")

    # ⑫ ズーム
    z1 = pg.eval_on_selector("#depsZoom", "el => el.getAttribute('transform')")
    pg.click('.depsZoomBtn[data-z="50"]')
    pg.wait_for_timeout(250)
    z2 = pg.eval_on_selector("#depsZoom", "el => el.getAttribute('transform')")
    check(z1 != z2 and "0.5" in z2, f"⑫ ズーム 50% で transform が変わる（{z1} → {z2}）")
    check(pg.locator(NODES).count() == N_DEPS - 1, "⑫ ズームしても○の数は変わらない")
    pg.click('.depsZoomBtn[data-z="100"]')
    pg.wait_for_timeout(200)

    # ⑪ 時間タブへ戻す
    pg.click('#rtabs .rtab[data-view="time"]')
    pg.wait_for_selector("#ganttBg")
    check(pg.locator("#grows .grow").count() > 0, "⑪ 時間タブに戻すと製品のガントが再描画される")
    check(pg.eval_on_selector("#left", "el => getComputedStyle(el).display") != "none"
          and pg.eval_on_selector("#filterBar", "el => getComputedStyle(el).display") != "none",
          "⑪ 左の情報表とフィルタバーが復帰する")
    check("display: none" not in (pg.eval_on_selector("#left", "el => el.getAttribute('style') || '' ")
                                  + pg.eval_on_selector("#filterBar", "el => el.getAttribute('style') || '' ")),
          "⑪ style に display:none を残さない（製品の指定に戻す）")
    check(pg.locator("#depsSvg").count() == 0, "⑪ 依存タブの図は消えている")
    check(not errors, f"⑪ ここまで JS エラー 0 -> {errors[:2]}")

    shots = ROOT / ".tmp_deps"                    # 目で見たい時のスクショ置き場（コミットしない）
    shots.mkdir(exist_ok=True)
    pg.click('#rtabs .rtab[data-view="deps"]')
    pg.wait_for_selector("#depsSvg")
    pg.screenshot(path=str(shots / "smoke_deps.png"), full_page=False)
    b.close()

finish(errors)
