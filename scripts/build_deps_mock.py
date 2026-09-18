"""依存タブ（構造の軸）の「動くモック」 `deps_mock.html` を生成する（依存ゼロ・標準ライブラリのみ）.

製品本体 `wbs_viewer.html` は 1 バイトも変えない。`scripts/build_demo.py` と同じやり方で、
複製の `</body>` 直前に `<script>` を 2 本足すだけ。

  1本目: デモ専用データ `wbs_demo.json` に `_deps`（依存の事実）を足したものを埋め込んで描く。
         日付を「開いた日」へ平行移動する仕掛けは build_demo.py の BLOCK をそのまま使う
         （7 日単位に丸める・祝日は動かさない）。
  2本目: 依存タブの差し込み層 `scripts/deps_mock/deps_tab.js`（第3版＝案G′）。右ペインに3つ目の
         タブ「依存」を足し、方眼紙に○（作業）と直線の矢印（依存）を描く。日数・最長経路・
         違反はその場で計算する（brief-deps v0.2 §5）。

モックなので **JSON には保存しない**（メモリ上のデータを書き換えて再描画するだけ）。
`deps_mock.html` は単体で開けば動く（データ埋め込み・ファイル選択不要）。

使い方:
    uv run python scripts/build_deps_mock.py
    # uv が無い環境では
    python3 scripts/build_deps_mock.py
"""

import argparse
import json
import pathlib
import sys

import build_demo   # 日付の平行移動（BLOCK）と `</` のエスケープ規則を二重に持たない

ROOT = pathlib.Path(__file__).resolve().parent.parent
VIEWER = ROOT / "wbs_viewer.html"
DATA_JSON = ROOT / "wbs_demo.json"
LAYER_JS = ROOT / "scripts" / "deps_mock" / "deps_tab.js"
DEFAULT_OUT = ROOT / "deps_mock.html"

BEGIN = "<!-- BEGIN build_deps_mock.py -->"
END = "<!-- END build_deps_mock.py -->"
HEADER = ("<!-- このファイルは scripts/build_deps_mock.py の生成物（依存タブの動くモック）。"
          "直接編集しない。再生成: uv run python scripts/build_deps_mock.py -->")

# ===== どの葉を図に載せ、どこへ矢印を引くか（モック用に機械的に付与する） =====
# 後続側の葉に `_deps: ["前工程の id", …]`（FS のみ）。`[]` は「図に載るが前工程なし」。
# 意図（brief-deps v0.2 の要求）：
#   ・4 段の鎖        1.2 → 1.6 → 2.1.2 → 2.2.3（2.2.3 は前工程2つ＝段は max+1 の確認）
#   ・最長経路        上の鎖が 8+8+9+15＝40 日で最長（赤＋太線・右下に「最長経路 40 日」）
#   ・フェーズまたぎ  1.6 → 2.1.2 ／ 1.8 → 2.1.3 ／ 2.3.1 → 3.2 ／ 2.4.1 → 3.6
#   ・わざとの違反    3.5（予定開始 9/22 が前工程 3.6 の予定終了 9/29 以前＝8 日重なる）
#   ・実遅れで割れる  2.3.1 の実績終了が予定より 3 日遅い → 後続 3.2 / 2.3.3 が追い越される
#   ・前工程なし      1.2 ／ 2.3.1 ／ 2.4.1 ／ 3.1（`[]`＝図に載るが前工程なし）
DEPS = {
    "1.2": [],                      # 要件定義（起点）
    "1.6": ["1.2"],                 # 画面設計
    "1.8": ["1.2"],                 # 設計レビュー
    "2.1.2": ["1.6"],               # マスタ管理（フェーズまたぎ 1→2）
    "2.1.3": ["1.8"],               # ログ基盤（フェーズまたぎ 1→2）
    "2.2.2": ["1.6"],               # 入出庫登録
    "2.2.3": ["2.1.2", "2.1.3"],    # 在庫引当ロジック（前工程2つ＝4段目）
    "2.4.2": ["2.2.2"],             # 在庫アラート
    "2.3.1": [],                    # 入荷予定取込（実績が予定より遅れている）
    "3.2": ["2.3.1"],               # 結合テスト（在庫）（フェーズまたぎ 2→3・実遅れの影響）
    "2.3.3": ["2.3.1"],             # バーコード読取（実遅れの影響）
    "2.4.1": [],                    # 在庫帳票（余裕0）
    "3.6": ["2.4.1"],               # 受入テスト準備（余裕0・フェーズまたぎ 2→3）
    "3.5": ["3.6"],                 # 移行リハーサル（わざとの違反）
    "3.1": [],                      # 単体テスト（余裕が長い＝線を「…」で打ち切る）
}

# 2本目の <script>：差し込み層をそのまま埋める（版表記の「demo」だけ「deps mock」に直す）
LAYER_BLOCK = """<script>
// 版表記を「deps mock」に（1本目の build_demo.BLOCK が付けた "demo" の札を書き換える）
(function(){var v=document.querySelector("#brandTitle .ver span");if(v)v.textContent="deps mock";})();
%(js)s
</script>
"""


def read_text(path):
    """改行を変換せずに読む（生成物のバイト一致を壊さないため）."""
    return path.read_bytes().decode("utf-8")


def leaves(tasks):
    """葉（children を持たない節）を順に返す."""
    for n in tasks or []:
        if isinstance(n, dict) and n.get("children"):
            for x in leaves(n["children"]):
                yield x
        elif isinstance(n, dict):
            yield n


def with_deps(data_json, deps=DEPS):
    """デモ専用データに `_deps` を足した JSON 文字列を返す（葉の id で引き当て）."""
    data = json.loads(data_json)
    found = set()
    for proj in data.get("projects", []):
        for leaf in leaves(proj.get("tasks", [])):
            key = str(leaf.get("id"))
            if key in deps:
                leaf["_deps"] = list(deps[key])
                found.add(key)
    missing = sorted(set(deps) - found)
    if missing:
        raise SystemExit(f"_deps を付ける葉が見つからない: {missing}")
    return json.dumps(data, ensure_ascii=False, indent=2)


def embed(viewer, data_json, layer_js):
    """ビューアの `</body>` 直前に、データと差し込み層の 2 本の <script> を入れる."""
    if BEGIN in viewer or build_demo.BEGIN in viewer:
        raise SystemExit("生成物を入力にしている（目印がある）。入力は wbs_viewer.html にする。")
    data = data_json.strip()
    for src, dst in build_demo.ESCAPES:          # 埋め込み JSON が script を早く閉じないように
        data = data.replace(src, dst)
    block = (BEGIN + "\n"
             + build_demo.BLOCK % {"begin": "", "end": "", "data": data}
             + LAYER_BLOCK % {"js": layer_js.rstrip("\n")}
             + END + "\n")

    at = viewer.rfind("</body>")
    if at < 0:
        raise SystemExit("wbs_viewer.html に </body> が見つからない。")
    out = viewer[:at] + block + viewer[at:]
    nl = out.find("\n")
    return out[:nl + 1] + HEADER + "\n" + out[nl + 1:]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="依存タブの動くモック deps_mock.html を生成する（依存ゼロ）。")
    parser.add_argument("-o", "--out", default=str(DEFAULT_OUT), metavar="HTML",
                        help="出力先（既定: リポジトリ直下の deps_mock.html）")
    args = parser.parse_args(argv)

    html = embed(read_text(VIEWER), with_deps(read_text(DATA_JSON)), read_text(LAYER_JS))
    out = pathlib.Path(args.out)
    out.write_bytes(html.encode("utf-8"))
    print(f"{out}: {len(html.encode('utf-8')):,} バイト "
          f"（{VIEWER.name} + {DATA_JSON.name} + _deps {len(DEPS)}葉 + {LAYER_JS.name}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
