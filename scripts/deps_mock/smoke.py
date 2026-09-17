"""依存タブの動くモック（deps_mock.html）の自動検証（headless Chromium）.

既存の e2e（tests/e2e・tests/e2e_issue）は触らない。モックの検証はここだけで完結させる。
作法は tests/e2e/common.py に合わせる（check/finish・本日固定・JSエラーの収集）。

見るもの（8つ）:
  ① JS エラー 0 で開ける
  ② 「依存」タブで SVG が出て、○の数＝`_deps` を持つ葉の数
  ③ 余裕0の○（赤い輪）が1つ以上
  ④ わざとの違反の○が1つ
  ⑤ ○A → ○B のクリックで矢印が1本増える（⑤' 矢印クリックで外れる）
  ⑥ 線の目盛りクリックで plan.start が変わり `_planLog` が1件増える
  ⑦ 「時間」タブに戻すと製品のガントが再描画される（JS エラー 0）
  ⑧ チェックを外すと○が消える
  ⑨ ガードレール：循環は結べない／違反になる結びは確認のうえ後続ごとずらす

使い方:
    uv run python scripts/deps_mock/smoke.py
"""

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
N_DEPS = len(build_deps_mock.DEPS)                # ○を置いた葉の数（= 15）

# --- 生成物としての検査（ブラウザを開く前に） ---
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

NODES = "#depsSvg g.dnode"
EDGES = "#depsSvg g.dedge"

errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_page(b, viewport={"width": 1600, "height": 900})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
    # confirm は OK、prompt は理由つきで確定（既定のままだと自動キャンセル＝操作が中断する）
    dialogs = []
    def on_dialog(d):
        dialogs.append((d.type, d.message))
        d.accept("smoke: 依存タブから変更")
    pg.on("dialog", on_dialog)

    pg.goto(MOCK.resolve().as_uri())
    pg.wait_for_selector("#leftRows .lrow")
    check(not errors, f"① 読み込みで JS エラー 0 -> {errors[:2]}")
    check(pg.locator('#rtabs .rtab[data-view="deps"]').count() == 1, "① 「依存」タブが1つ出ている")

    # ② タブを押すと図が出る
    pg.click('#rtabs .rtab[data-view="deps"]')
    pg.wait_for_selector("#depsSvg")
    n = pg.locator(NODES).count()
    check(n == N_DEPS, f"② ○の数＝_deps を持つ葉の数（{n} == {N_DEPS}）")
    check(pg.locator('#rtabs .rtab[data-view="deps"].on').count() == 1, "② 「依存」タブが選択の見た目になる")
    check(pg.locator("#depsPick input.dpick").count() == 33, "② チェックリストに葉が33件ある")

    # ③ 余裕0（赤い輪）／④ 違反
    crit = pg.locator(NODES + "[data-crit]").count()
    viol = pg.locator(NODES + "[data-viol]").count()
    late = pg.locator(NODES + "[data-late]").count()
    check(crit >= 1, f"③ 余裕0の○（赤い輪）が1つ以上（{crit}件）")
    check(viol == 1, f"④ わざとの違反の○が1つ（{viol}件）")
    check(late >= 1, f"④' 前工程の実遅れで線からはみ出した○がある（{late}件）")

    # ⑨ ガードレール：循環は結べない（1.2 → 1.6 → 2.1.2 の逆を結ぶ）
    e_before = pg.locator(EDGES).count()
    pg.click('#depsSvg g.dnode[data-id="2.1.2"] circle')
    pg.click('#depsSvg g.dnode[data-id="1.2"] circle')
    pg.wait_for_timeout(200)
    check(pg.locator(EDGES).count() == e_before, "⑨ 循環になる結びは拒否される（矢印は増えない）")
    check(any(d[0] == "alert" and "循環" in d[1] for d in dialogs), f"⑨ 循環は alert で断る -> {dialogs[-1:]}")
    pg.keyboard.press("Escape")

    # ⑤ ○A → ○B で依存を結ぶ（1.2 の終了 8/1 < 3.1 の開始 9/1 なのでずらしは起きない）
    e0 = pg.locator(EDGES).count()
    pg.click('#depsSvg g.dnode[data-id="1.2"] circle')
    pg.click('#depsSvg g.dnode[data-id="3.1"] circle')
    pg.wait_for_timeout(200)
    e1 = pg.locator(EDGES).count()
    check(e1 == e0 + 1, f"⑤ ○A→○B のクリックで矢印が1本増える（{e0} → {e1}）")
    check(pg.evaluate("""() => {
        const f=(t,o)=>o.flatMap(n=>n.children?f(t,n.children):[n]);
        const ts=window.__PM.data().projects[0].tasks;
        const n=f(0,ts).find(x=>String(x.id)==="3.1");
        return !!n && (n._deps||[]).indexOf("1.2")>=0; }"""),
          "⑤ 3.1 の _deps に 1.2 が入った（データ側も更新されている）")

    # ⑤' 矢印をクリック＝依存を外す（確認ダイアログは OK）
    # 曲線は bbox の中心が線の上に無い。パスを少しずつ辿り、「右ペインの見えている範囲にあって、
    # そこをクリックすればこの矢印に当たる点」を探してから実際にクリックする（当たり判定ごと検証する）。
    pg.evaluate("() => document.getElementById('right').scrollTo(0, 0)")
    at = pg.evaluate("""() => {
        const g = document.querySelector('#depsSvg g.dedge[data-from="1.2"][data-to="3.1"]');
        const p = g.querySelector('path'), L = p.getTotalLength();
        const r = document.getElementById('depsSvg').getBoundingClientRect();
        const box = document.getElementById('right').getBoundingClientRect();
        const pick = document.getElementById('depsPick').getBoundingClientRect();
        for(let f = 0.12; f <= 0.88; f += 0.02){
          const pt = p.getPointAtLength(L * f), x = r.left + pt.x, y = r.top + pt.y;
          if(x < Math.max(box.left, pick.right) + 2 || x > box.right - 2)continue;
          if(y < box.top + 2 || y > box.bottom - 2)continue;
          const stack = document.elementsFromPoint(x, y);
          if(stack.some(el => el.closest && el.closest('g.dedge') === g))return { x: x, y: y };
        }
        return null; }""")
    check(at is not None, "⑤' 矢印の上でクリックできる点が見つかる")
    if at:
        pg.mouse.click(at["x"], at["y"])
        pg.wait_for_timeout(250)
    e2 = pg.locator(EDGES).count()
    check(e2 == e0, f"⑤' 矢印をクリックすると依存が外れる（{e1} → {e2}）")

    # ⑥ 線の目盛りクリック＝○を動かす（期間は維持・_planLog に1件）
    read = """(id) => {
        const f=(o)=>o.flatMap(n=>n.children?f(n.children):[n]);
        const n=f(window.__PM.data().projects[0].tasks).find(x=>String(x.id)===id);
        return {s:n.plan.start,e:n.plan.end,log:(n._planLog||[]).length}; }"""
    before = pg.evaluate(read, "2.4.2")
    pg.click('#depsSvg g.dnode[data-id="2.4.2"] circle')
    pg.wait_for_timeout(150)
    day = pg.locator('#depsSvg rect.dtick[data-id="2.4.2"]').first.get_attribute("data-day")
    pg.locator('#depsSvg rect.dtick[data-id="2.4.2"]').first.click()
    pg.wait_for_timeout(250)
    after = pg.evaluate(read, "2.4.2")
    check(after["s"] == day and after["s"] != before["s"],
          f"⑥ 目盛りをクリックすると plan.start がその日になる（{before['s']} → {after['s']} = 目盛り {day}）")
    check(after["log"] == before["log"] + 1,
          f"⑥ _planLog が1件増える（{before['log']} → {after['log']}）")
    check(pg.evaluate("""() => {
        const f=(o)=>o.flatMap(n=>n.children?f(n.children):[n]);
        const n=f(window.__PM.data().projects[0].tasks).find(x=>String(x.id)==="2.4.2");
        const L=n._planLog[n._planLog.length-1];
        return L.by==="mock" && !!L.from.start && !!L.to.start; }"""),
          "⑥ 追記した _planLog は by:\"mock\" で from/to を持つ")

    # ⑧ チェックを外すと○が消える（依存が付いているので確認ダイアログ＝OK で進む）
    pg.locator('#depsPick input.dpick[data-id="2.4.2"]').uncheck()
    pg.wait_for_timeout(250)
    n2 = pg.locator(NODES).count()
    check(n2 == N_DEPS - 1, f"⑧ チェックを外すと○が消える（{n} → {n2}）")
    check(pg.evaluate("""() => {
        const f=(o)=>o.flatMap(n=>n.children?f(n.children):[n]);
        const n=f(window.__PM.data().projects[0].tasks).find(x=>String(x.id)==="2.4.2");
        return !("_deps" in n); }"""), "⑧ _deps キーそのものが消える")

    # ⑦ 「時間」タブに戻すと製品のガントが描き直される
    pg.click('#rtabs .rtab[data-view="time"]')
    pg.wait_for_selector("#ganttBg")
    check(pg.locator("#grows .grow").count() > 0, "⑦ 時間タブに戻すと製品のガントが再描画される")
    check(pg.locator("#depsSvg").count() == 0, "⑦ 依存タブの図は消えている")
    check(pg.locator('#rtabs .rtab[data-view="deps"]').count() == 1, "⑦ 「依存」タブは残っている")

    shots = ROOT / ".tmp_deps"                    # 目で見たい時のスクショ置き場（コミットしない）
    shots.mkdir(exist_ok=True)
    pg.screenshot(path=str(shots / "smoke_time.png"), full_page=False)
    pg.click('#rtabs .rtab[data-view="deps"]')
    pg.wait_for_selector("#depsSvg")
    pg.screenshot(path=str(shots / "smoke_deps.png"), full_page=False)

    # ⑨' 違反になる結び＝確認のうえ「B と後続」を同じ日数ずらす（3.1 の終了より前に始まる 1.8 に結ぶ）
    span = """(ids) => {
        const f=(o)=>o.flatMap(n=>n.children?f(n.children):[n]);
        const all=f(window.__PM.data().projects[0].tasks);
        return ids.map(id=>{const n=all.find(x=>String(x.id)===id);
          return [n.plan.start, n.plan.end, (n._planLog||[]).length];}); }"""
    b0 = pg.evaluate(span, ["1.8", "2.1.3"])
    pg.click('#depsSvg g.dnode[data-id="3.1"] circle')
    pg.click('#depsSvg g.dnode[data-id="1.8"] circle')
    pg.wait_for_timeout(300)
    b1 = pg.evaluate(span, ["1.8", "2.1.3"])
    shift18 = pg.evaluate("""(a) => { const d=(x,y)=>Math.round((Date.parse(y)-Date.parse(x))/86400000);
        return [d(a[0][0], a[1][0]), d(a[1][0], a[1][1])]; }""", [b0[0], b1[0]])
    check(shift18[0] > 0, f"⑨' 違反になる結びは確認のうえ後ろへずらす（1.8 の開始 +{shift18[0]}日）")
    check(b1[0][2] == b0[0][2] + 1 and b1[1][2] == b0[1][2] + 1,
          "⑨' ずらした葉と後続の両方に _planLog が1件ずつ増える")
    d18 = pg.evaluate("""(a)=>{const d=(x,y)=>Math.round((Date.parse(y)-Date.parse(x))/86400000);
        return d(a[0][0], a[1][0]); }""", [b0[1], b1[1]])
    check(d18 == shift18[0], f"⑨' 後続 2.1.3 も同じ日数だけ動く（{d18}日）")
    b.close()

finish(errors)
