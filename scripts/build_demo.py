"""GitHub Pages 用のデモ版 `demo.html` を生成する.

製品本体 `wbs_viewer.html` は 1 バイトも変えない。その複製の末尾（製品の
`<script>` より後ろ）に、サンプル `wbs_sample_issues.json` を埋め込んだ
`<script>` を 1 本足すだけ。開いた瞬間に `window.renderData()` が走り、
計画と課題が表示される。

外部送信は足さない（fetch も CDN も使わない＝依存ゼロのまま）。サンプルは
HTML の中に文字列として入るので、Pages でもファイルを取りに行かない。

出力は冪等（同じ入力なら毎回同じバイト列）。生成物 `demo.html` はリポジトリに
コミットする（Pages がそのまま配るため）。サンプルやビューアを変えたら
**再生成してコミットし直す**。

使い方:
    uv run python scripts/build_demo.py
    # uv が無い環境では
    python3 scripts/build_demo.py
"""

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
VIEWER = ROOT / "wbs_viewer.html"
SAMPLE = ROOT / "wbs_sample_issues.json"
DEFAULT_OUT = ROOT / "demo.html"

# 追記ブロックの目印。e2e（tests/e2e/test_demo.py）はこの間を取り除いた本文が
# `wbs_viewer.html` と一致することを確かめる＝「本体を変えていない」の機械検証。
BEGIN = "<!-- BEGIN build_demo.py -->"
END = "<!-- END build_demo.py -->"

HEADER = ("<!-- このファイルは scripts/build_demo.py の生成物。直接編集しない。"
          "再生成: uv run python scripts/build_demo.py -->")

# 埋め込むサンプルは JSON なので `<` は文字列の中にしか現れない。`</` と `<!--` を
# 潰しておけば、HTML パーサが script を早く閉じたり escaped-text 状態に入ったりしない。
# （`\/` も `\!` も JS の文字列リテラルではその文字そのものを表す）
ESCAPES = (("</", r"<\/"), ("<!--", r"<\!--"))

BLOCK = """%(begin)s
<script>
// GitHub Pages のデモ：開いた瞬間にサンプル（wbs_sample_issues.json）を描く。
// 製品のスクリプトより後ろに置くので、ここでは renderData が定義済み。
(function(){
  var DATA = %(data)s;
  if(typeof window.renderData!=="function")return;   // 本体が変わっていたら何もしない（壊さない）
  window.renderData(DATA);
  // 版表記の後ろに小さく「demo」（簡素表示では版ごと隠れる＝#79 の逃げ道を壊さない）。
  // Why not <title>: タブ名は描画のたびにデータの name から書き直されるので、ここでは持たない。
  var ver = document.querySelector("#brandTitle .ver");
  if(!ver)return;
  var tag = document.createElement("span");
  tag.textContent = "demo";
  tag.title = "サンプルデータを表示しています / Showing sample data";
  tag.style.cssText = "margin-left:4px;padding:0 3px;border-radius:2px;"
    + "background:#eceef1;color:#6b7280";
  ver.appendChild(tag);
})();
</script>
%(end)s
"""


def read_text(path: pathlib.Path) -> str:
    """改行を変換せずに読む（生成物のバイト一致を壊さないため）."""
    return path.read_bytes().decode("utf-8")


def embed(viewer: str, sample: str) -> str:
    """ビューアの `</body>` の直前に、サンプルを描くブロックを差し込む."""
    if BEGIN in viewer:
        raise SystemExit("生成物を入力にしている（BEGIN の目印がある）。"
                         "入力は wbs_viewer.html にする。")
    data = sample.strip()
    for src, dst in ESCAPES:
        data = data.replace(src, dst)
    block = BLOCK % {"begin": BEGIN, "end": END, "data": data}

    at = viewer.rfind("</body>")
    if at < 0:
        raise SystemExit("wbs_viewer.html に </body> が見つからない。")
    out = viewer[:at] + block + viewer[at:]

    # 冒頭（doctype の次の行）に「生成物」の断り書きを置く。
    # Why not doctype より前: 古いブラウザが quirks モードに落ちる書き方を避ける。
    nl = out.find("\n")
    return out[:nl + 1] + HEADER + "\n" + out[nl + 1:]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="GitHub Pages 用のデモ版 demo.html を生成する（依存ゼロ）。")
    parser.add_argument("-o", "--out", default=str(DEFAULT_OUT), metavar="HTML",
                        help="出力先（既定: リポジトリ直下の demo.html）")
    args = parser.parse_args(argv)

    html = embed(read_text(VIEWER), read_text(SAMPLE))
    out = pathlib.Path(args.out)
    out.write_bytes(html.encode("utf-8"))
    print(f"{out}: {len(html.encode('utf-8')):,} バイト "
          f"（{VIEWER.name} + {SAMPLE.name}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
