"""#211 デモ版 demo.html：URL を開いた瞬間にサンプルの計画と課題が出る（ファイル選択なし）。

生成物なので、描画だけでなく「本体 wbs_viewer.html を変えていない」ことも機械で見る。
追記ブロック（scripts/build_demo.py の目印の間）を取り除いた本文がバイト一致することと、
再生成しても同じバイト列になること（＝サンプル更新の取り込み漏れが無いこと）を確かめる。
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
          "demo.html は再生成しても同じバイト列（冪等・サンプル/本体の最新を反映）")

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
    pg.wait_for_timeout(200)

    check(len(pg.query_selector_all("#leftRows .lrow")) > 0, "開いた瞬間に計画の行が出る")
    body = pg.inner_text("body")
    check("販売管理システム移行" in body, "埋め込んだサンプルの案件名が出ている")
    check("NaN" not in body, "本文に NaN が無い")
    check(not pg.eval_on_selector("#pmSwitch", "e=>e.hidden"), "「計画｜課題」スイッチが出ている")
    check(pg.eval_on_selector("#brandTitle .ver", "e=>e.innerText").strip().endswith("demo"),
          "版表記の後ろに demo の印が付く")

    pg.click('#pmSwitch [data-pmv="issue"]')
    pg.wait_for_timeout(200)
    check(not pg.eval_on_selector("#isMain", "e=>e.hidden"), "課題側に切り替わる")
    check(len(pg.query_selector_all("#isTbody tr")) > 0, "課題の行が出る")
    check("移行テストで文字コード起因のエラーが大量発生" in pg.inner_text("#isMain"),
          "サンプルの課題タイトルが出ている")

    b.close()
finish(errors)
