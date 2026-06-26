"""ゴールデンマスター（characterization）: 全fixtureの『値レベルの描画結果』を凍結。
   生のHTMLでなく、画面が表現する値（セルテキスト・バー幾何/色・座標・遅延ラベル・編集UI）を撮る＝
   属性順など無害な差では赤くせず、見た目に出る挙動変化だけを検出する。

   本日は CLOCK_PIN で 2026-06-15 に固定（イナズマ線・進行中バーを決定論化）＝
   golden.json をコミットしても日付で毎日赤くならない。

   使い方:
     生成:  python golden.py --generate   → tests/e2e/golden.json を書き出し
     検証:  python golden.py             → golden.json と現在の描画を比較（差分ゼロでPASS）
   run_all からは test_golden.py 経由で検証が走る。表示仕様を意図的に変えたら --generate で撮り直す。"""
import json
import pathlib
import sys
from playwright.sync_api import sync_playwright
from common import ROOT, VIEWER, CLOCK_PIN, granted_handle_init

GOLDEN = pathlib.Path(__file__).resolve().parent / "golden.json"
FIXTURES = sorted((ROOT / "tests").glob("正常_*.json")) + sorted((ROOT / "tests").glob("異常_*.json"))
# 編集モードを凍結する fixture（新フォーマット・編集可能なもの）。編集UIの崩れを #63 着手前に保護
EDIT_FIXTURES = ["正常_4階層ネスト.json", "正常_カスタムキー.json", "正常_全機能.json"]

# view モード：画面が表現する値（innerHTML全体ではなく意味のある中間表現）
CAPTURE = r"""()=>{
  const cs = el => getComputedStyle(el);
  const rows = [...document.querySelectorAll('#leftRows .lrow')].map(r=>({
    cls: [...r.classList].filter(c=>c!=='lrow').join(' '),
    cells: [...r.querySelectorAll('.c')].map(c=>c.innerText),
    links: [...r.querySelectorAll('.c.note a')].map(a=>a.getAttribute('href')),
  }));
  const bars = [...document.querySelectorAll('#grows .bar')].map(b=>({
    kind: b.className.replace('bar','').trim(),
    left: b.style.left, width: b.style.width, top: b.style.top, height: b.style.height,
    bg: cs(b).backgroundColor, border: cs(b).borderTopColor,   // #65 の予実/遅延/完了/親の色・太さ・縦位置を凍結
  }));
  const delays = [...document.querySelectorAll('#grows .delay')].map(d=>({
    txt: d.innerText, left: d.style.left, color: cs(d).color,   // 「+N」遅延ラベル
  }));
  const ov = document.querySelector('#overlay');
  const poly = ov ? (ov.querySelector('polyline')||{}).getAttribute?.('points') : null;
  const ms = ov ? [...ov.querySelectorAll('rect:not(.we)')].map(r=>r.getAttribute('fill')) : [];   // ラベル背景rect=マイルストーン色（列シェード.weは除外）
  const shade = ov ? [...ov.querySelectorAll('rect.we')].map(r=>+r.getAttribute('x')) : [];          // 土日/祝日の列シェードx（祝日設定で増減）
  const header = [...document.querySelectorAll('#leftHead .h, #leftHead .hgt, #leftHead .hsub')].map(h=>h.innerText);
  // stat(読込時刻)は実行ごとに変わる時計なので撮らない。本日依存(poly/進行中バー)は CLOCK_PIN で固定済み
  return {rows, bars, delays, poly, ms, shade, header};
}"""

# edit モード：入力欄(field→value)と行操作ボタンを凍結（4分割入力など足す前の編集UIを保護）
EDIT_CAPTURE = r"""()=>{
  const inputs = [...document.querySelectorAll('#leftRows input')].map(i=>({
    f: i.getAttribute('data-field'), v: i.value, type: i.type,
  }));
  const btns = [...document.querySelectorAll('#leftRows button')].map(b=>b.textContent.trim());
  return {inputs, btns};
}"""

# 進捗タブ：進捗バー（青実績/赤不足分）の幾何＋PV目盛り線を凍結
PROG_CAPTURE = r"""()=>{
  const rows = [...document.querySelectorAll('#progbody .prw')].map(r=>({
    cls: [...r.classList].filter(c=>c!=='prw').join(' '),
    bars: [...r.querySelectorAll('.pbar')].map(b=>({kind:b.className.replace('pbar','').trim(), left:b.style.left, width:b.style.width})),
  }));
  return {rows};
}"""


def capture_all():
    out = {}
    errs = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        # view モード：1ページで全fixtureを順に renderData
        pg = b.new_page(viewport={"width": 1500, "height": 900})
        pg.add_init_script(CLOCK_PIN)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(VIEWER)
        for fx in FIXTURES:
            data = json.loads(fx.read_text(encoding="utf-8"))
            pg.evaluate("d => window.renderData(d)", data)
            pg.wait_for_timeout(120)
            out[fx.name] = pg.evaluate(CAPTURE)
        # 進捗タブに切替えて、各fixtureの進捗バーを凍結
        pg.click('.rtab[data-view="progress"]'); pg.wait_for_timeout(120)
        for fx in FIXTURES:
            data = json.loads(fx.read_text(encoding="utf-8"))
            pg.evaluate("d => window.renderData(d)", data)
            pg.wait_for_timeout(120)
            out[fx.name + "::prog"] = pg.evaluate(PROG_CAPTURE)
        pg.close()
        # edit モード：fixtureごとに新ページ（granted handle の中身が init で決まるため）
        for name in EDIT_FIXTURES:
            data = json.loads((ROOT / "tests" / name).read_text(encoding="utf-8"))
            ep = b.new_page(viewport={"width": 1500, "height": 900})
            ep.add_init_script(CLOCK_PIN)
            ep.add_init_script(granted_handle_init(data))
            ep.on("pageerror", lambda e: errs.append(str(e)))
            ep.on("dialog", lambda d: d.accept())
            ep.goto(VIEWER)
            ep.click("#openBtn"); ep.wait_for_timeout(120)
            ep.click("#editBtn"); ep.wait_for_timeout(180)
            out[name + "::edit"] = ep.evaluate(EDIT_CAPTURE)
            ep.close()
        b.close()
    if errs:
        print("=== JSエラー（撮影中）===", errs)
        sys.exit(2)
    return out


def diff_against_golden(cur):
    """golden.json と比較し、差分のあるfixture名リストを返す（詳細も標準出力）。"""
    if not GOLDEN.exists():
        print("golden.json が無い。先に --generate で生成してください。")
        sys.exit(1)
    gold = json.loads(GOLDEN.read_text(encoding="utf-8"))
    diffs = []
    for name in sorted(set(cur) | set(gold)):
        if cur.get(name) != gold.get(name):
            diffs.append(name)
            g, c = gold.get(name, {}), cur.get(name, {})
            print(f"  ✗ {name}")
            for key in sorted(set(g) | set(c)):
                if g.get(key) != c.get(key):
                    print(f"      [{key}] 期待={json.dumps(g.get(key), ensure_ascii=False)[:140]}")
                    print(f"            現在={json.dumps(c.get(key), ensure_ascii=False)[:140]}")
    return diffs


def main():
    cur = capture_all()
    if "--generate" in sys.argv:
        GOLDEN.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"ゴールデン生成: {GOLDEN}  ({len(cur)} スナップショット)")
        return
    diffs = diff_against_golden(cur)
    if diffs:
        print("=== ゴールデン不一致（挙動が変わった）===")
        sys.exit(1)
    print(f"=== ゴールデン一致: {len(cur)} スナップショット 全て挙動不変 ===")


if __name__ == "__main__":
    main()
