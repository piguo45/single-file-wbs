"""GitHub Pages 用のデモ版 `demo.html` を生成する.

製品本体 `wbs_viewer.html` は 1 バイトも変えない。その複製の末尾（製品の
`<script>` より後ろ）に、デモ専用データ `wbs_demo.json` を埋め込んだ
`<script>` を 1 本足すだけ。開いた瞬間に `window.renderData()` が走り、
計画と課題が表示される。

埋め込んだデータは、描く直前に「開いた日」へ平行移動する（`_demoToday` を
基準日として、今日までの差を 7 日単位に丸めてずらす）。いつ開いても本日線が
真ん中に来る＝デモが古びない。ずらすのは**埋め込み側のスクリプト**だけで、
製品本体にも `wbs_demo.json` にも手を入れない。

外部送信は足さない（fetch も CDN も使わない＝依存ゼロのまま）。データは
HTML の中に文字列として入るので、Pages でもファイルを取りに行かない。

出力は冪等（同じ入力なら毎回同じバイト列）。生成物 `demo.html` はリポジトリに
コミットする（Pages がそのまま配るため）。デモ専用データやビューアを変えたら
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
DATA_JSON = ROOT / "wbs_demo.json"
DEFAULT_OUT = ROOT / "demo.html"

# 追記ブロックの目印。e2e（tests/e2e/test_demo.py）はこの間を取り除いた本文が
# `wbs_viewer.html` と一致することを確かめる＝「本体を変えていない」の機械検証。
BEGIN = "<!-- BEGIN build_demo.py -->"
END = "<!-- END build_demo.py -->"

HEADER = ("<!-- このファイルは scripts/build_demo.py の生成物。直接編集しない。"
          "再生成: uv run python scripts/build_demo.py -->")

# 埋め込むデータは JSON なので `<` は文字列の中にしか現れない。`</` と `<!--` を
# 潰しておけば、HTML パーサが script を早く閉じたり escaped-text 状態に入ったりしない。
# （`\/` も `\!` も JS の文字列リテラルではその文字そのものを表す）
ESCAPES = (("</", r"<\/"), ("<!--", r"<\!--"))

BLOCK = """%(begin)s
<script>
// GitHub Pages のデモ：開いた瞬間にデモ専用データ（wbs_demo.json）を描く。
// 製品のスクリプトより後ろに置くので、ここでは renderData が定義済み。
(function(){
  var DATA = %(data)s;
  if(typeof window.renderData!=="function")return;   // 本体が変わっていたら何もしない（壊さない）
  shiftToToday(DATA);
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

  // データの基準日（_demoToday）から今日までの差だけ、日付をまとめて後ろ／前へずらす。
  function shiftToToday(root){
    var DAY = 86400000;
    var DATE = /^\\d{4}-\\d{2}-\\d{2}$/;
    var STAMP = /^\\d{4}-\\d{2}-\\d{2}T[0-9:.]+(Z|[+-][0-9:]+)?$/;
    // Why not new Date().toISOString(): 製品の todayStr() と同じ「地方時の暦日」にそろえる
    // （UTC にすると時差のぶんだけ本日が 1 日ずれ、デモ側と本体側で食い違う）。
    var n = new Date();
    var today = iso(Date.UTC(n.getFullYear(), n.getMonth(), n.getDate()));
    var base = root && root._demoToday;
    if(!DATE.test(base||""))return;
    // Why not 1 日単位: 7 日単位に丸めると曜日が変わらない＝土日の位置とバーの形が保たれる。
    var shift = Math.round((ms(today) - ms(base)) / DAY / 7) * 7;
    if(shift)walk(root, null);

    function iso(t){ return new Date(t).toISOString().slice(0, 10); }
    function ms(s){ return Date.UTC(+s.slice(0,4), +s.slice(5,7)-1, +s.slice(8,10)); }
    function add(s){ return iso(ms(s) + shift * DAY); }
    function walk(node, key){
      // Why not 祝日もずらす: 祝日は暦の事実。動かすと日付と名前（海の日など）が食い違う。
      if(key === "holidays")return node;
      if(Object.prototype.toString.call(node) === "[object Array]"){
        for(var i = 0; i < node.length; i++)node[i] = walk(node[i], null);
        return node;
      }
      if(node && typeof node === "object"){
        for(var k in node)if(Object.prototype.hasOwnProperty.call(node, k))node[k] = walk(node[k], k);
        return node;
      }
      // 値そのものが日付（YYYY-MM-DD）か ISO 日時のときだけ動かす。
      // 備考の本文に出てくる数字は形が合わないので触らない。
      if(typeof node === "string"){
        if(DATE.test(node))return add(node);
        if(STAMP.test(node))return add(node.slice(0, 10)) + node.slice(10);
      }
      return node;
    }
  }
})();
</script>
%(end)s
"""


def read_text(path: pathlib.Path) -> str:
    """改行を変換せずに読む（生成物のバイト一致を壊さないため）."""
    return path.read_bytes().decode("utf-8")


def embed(viewer: str, data_json: str) -> str:
    """ビューアの `</body>` の直前に、デモ専用データを描くブロックを差し込む."""
    if BEGIN in viewer:
        raise SystemExit("生成物を入力にしている（BEGIN の目印がある）。"
                         "入力は wbs_viewer.html にする。")
    data = data_json.strip()
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

    html = embed(read_text(VIEWER), read_text(DATA_JSON))
    out = pathlib.Path(args.out)
    out.write_bytes(html.encode("utf-8"))
    print(f"{out}: {len(html.encode('utf-8')):,} バイト "
          f"（{VIEWER.name} + {DATA_JSON.name}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
