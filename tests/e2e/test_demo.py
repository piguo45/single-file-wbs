"""#211 デモ版 demo.html：URL を開いた瞬間にデモ専用データの計画と課題が出る（ファイル選択なし）。

生成物なので、描画だけでなく「本体 wbs_viewer.html を変えていない」ことも機械で見る。
追記ブロック（scripts/build_demo.py の目印の間）を取り除いた本文がバイト一致することと、
再生成しても同じバイト列になること（＝データ更新の取り込み漏れが無いこと）を確かめる。

デモの日付は開いた日へ平行移動する（`_demoToday` からの差を 7 日単位に丸めてずらす）。
本日は CLOCK_PIN（2026-06-15）固定なのでずらし幅も決まる＝断言が実行日でぶれない。
ずらし幅は 7 の倍数に丸まるため、データ上の「本日」は実際の本日と最大 3 日ずれる。
断言する遅延・期限超過・催促には、基準日から 7 日以上の余裕を持たせてある。
"""
import pathlib
import subprocess
import sys
import tempfile
from playwright.sync_api import sync_playwright
from common import ROOT, check, finish, new_page

sys.path.append(str(ROOT / "scripts"))   # 末尾に足す＝隣の common.py を scripts/ が覆わない
import build_demo  # noqa: E402  （目印と断り書きの文字列を二重に持たない）

DEMO = ROOT / "demo.html"
demo_src = DEMO.read_bytes().decode("utf-8")
viewer_src = (ROOT / "wbs_viewer.html").read_bytes().decode("utf-8")

# --- 生成物としての検査（ブラウザを開く前に済ませる） ---
with tempfile.TemporaryDirectory() as tmp:              # worktree の外に出す（PII grep と git status を汚さない）
    again = pathlib.Path(tmp) / "demo.html"
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_demo.py"),
                        "-o", str(again)], capture_output=True)
    check(r.returncode == 0, f"build_demo.py が正常終了 -> {r.stderr.decode('utf-8', 'replace')[:200]}")
    check(r.returncode == 0 and again.read_bytes() == DEMO.read_bytes(),
          "demo.html は再生成しても同じバイト列（冪等・データ/本体の最新を反映）")

stripped = demo_src.replace(build_demo.HEADER + "\n", "", 1)
i = stripped.find(build_demo.BEGIN)
j = stripped.find(build_demo.END)
check(i > 0 and j > i, "追記ブロックの目印がある")
block = stripped[i:j + len(build_demo.END)]
stripped = stripped[:i] + stripped[j + len(build_demo.END) + 1:]   # 目印の後ろの改行まで落とす
check(stripped == viewer_src, "追記ブロックを除くと wbs_viewer.html とバイト一致（本体は無改変）")
check(block.count("</script") == 1,
      "追記ブロックの中の </script は終端の1つだけ（埋め込み JSON の早期終端なし）")

errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_page(b, viewport={"width": 1500, "height": 820})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
    pg.goto(DEMO.as_uri())                               # ファイルを開く操作はしない
    pg.wait_for_timeout(300)

    rows = pg.query_selector_all("#leftRows .lrow")
    check(len(rows) >= 30, f"開いた瞬間に計画の行が出る（葉 33 ＋ 集約・案件・MS）-> {len(rows)}")
    body = pg.inner_text("body")
    check("社内在庫管理システム刷新" in body, "埋め込んだデモの案件名が出ている")
    check("NaN" not in body, "本文に NaN が無い")
    check(not pg.eval_on_selector("#pmSwitch", "e=>e.hidden"), "「計画｜課題」スイッチが出ている")
    check(pg.eval_on_selector("#brandTitle .ver", "e=>e.innerText").strip().endswith("demo"),
          "版表記の後ろに demo の印が付く")

    # --- ずらした後も「進行中」と「遅延」が残る（デモの見せ場が実行日で消えない） ---
    bars = pg.eval_on_selector_all("#grows .bar", "e=>e.map(x=>x.className)")
    check(any("cut" in c for c in bars), f"進行中（本日で切れた実績バー）がある -> {sorted(set(bars))}")
    check(any("over" in c for c in bars), "終了遅延（予定枠を超えた赤バー）がある")
    delays = pg.eval_on_selector_all("#grows .delay", "e=>e.map(x=>x.innerText)")
    check(len(delays) >= 4, f"「+N」の遅延ラベルが4件以上 -> {delays}")
    badges = pg.eval_on_selector_all(".dbadge", "e=>e.map(x=>x.innerText)")
    check(len(badges) == 2 and "期限" in badges[0] and "進捗" in badges[1],
          f"全体サマリの遅延バッジに 期限・進捗 の両方が出る -> {badges}")
    poly = pg.eval_on_selector("#overlay polyline", "e=>e.getAttribute('points')")
    xs = {pt.split(",")[0] for pt in (poly or "").split()}
    check(len(xs) >= 3, f"イナズマ線が本日線から左へ折れている（x が3種類以上）-> {sorted(xs)}")
    ms = pg.eval_on_selector_all("#overlay rect:not(.we)", "e=>e.map(x=>x.getAttribute('fill'))")
    check(len(ms) == 4, f"マイルストーン線が4本出る（1本は色なし＝既定色）-> {ms}")
    check("#cc79a7" in ms, f"色を書かないマイルストーンは既定色 #cc79a7 -> {ms}")

    # 祝日はずらさない（暦の事実）＝ずらした時間軸の上に 2026 年の祝日がそのまま出る
    hol = pg.eval_on_selector_all("#dates .d.hol", "e=>e.map(x=>x.getAttribute('title'))")
    check("海の日" in hol, f"ずらしていない祝日（2026-07-20 海の日）が赤字で出る -> {hol}")
    check(pg.eval_on_selector_all("#overlay rect.we", "e=>e.length") > 0,
          "土日・祝日の列が薄ピンクで塗られる")

    # --- 課題側：3状態と6つの印がすべて出る ---
    pg.click('#pmSwitch [data-pmv="issue"]')
    pg.wait_for_timeout(300)
    check(not pg.eval_on_selector("#isMain", "e=>e.hidden"), "課題側に切り替わる")
    check(len(pg.query_selector_all("#isTbody tr")) >= 9, "課題の行が9件以上出る")
    states = pg.eval_on_selector_all("#isTbody td.state .bdg", "e=>e.map(x=>x.innerText)")
    check(all(s in states for s in ("未着手", "対応中", "完了")),
          f"状態3つ（未着手／対応中／完了）がすべて出る -> {sorted(set(states))}")
    cnts = pg.eval_on_selector_all("#isCounts .cnt",
                                   "e=>e.map(x=>x.innerText.replace(/\\s+/g,' ').trim())")
    for mark in ("待ち", "凍結", "未決", "⚠ 期限超過", "⚠ 催促", "★ 更新"):
        hit = [c for c in cnts if c.startswith(mark + " ")]
        check(bool(hit) and hit[0] != mark + " 0",
              f"印「{mark}」が1件以上ある -> {cnts}")
    check(pg.eval_on_selector_all("#isTbody td.due.overdue", "e=>e.length") >= 1,
          "期限超過の赤字が出る（未完了の行だけ）")
    check(len(pg.query_selector_all("#isTbody .lk")) >= 7,
          "計画の葉などへのリンク行が7件以上出る（逆引き札の見せ場）")

    b.close()
finish(errors)
