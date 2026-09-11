"""コーパス回帰: tests/issue/ の全fixtureを読み込み、JSエラー/NaN/undefined 文字列が無い（graceful degradation）。
   正常_=正しく描画・異常_=崩れてもクラッシュしない。非オブジェクトトップは inline でも併検。"""
import json
from playwright.sync_api import sync_playwright
from common import ROOT, UNIFIED, VIEWER, check, finish, new_page

CORPUS = ROOT / "tests" / "issue"    # 課題側のコーパス（wbs 本家の tests/*.json とは別ディレクトリ）
FIXTURES = sorted(CORPUS.glob("正常_*.json")) + sorted(CORPUS.glob("異常_*.json"))
INLINE = [("null", None), ("空配列", []), ("数値", 7), ("文字列", "x"), ("空オブジェクト", {}),
          ("issues非配列", {"issues": "abc"}), ("issues要素が非オブジェクト", {"issues": [None, 3, "x", [1]]}),
          ("projects非配列(文字列)", {"projects": "abc"}), ("projects非配列(オブジェクト)", {"projects": {}}),
          ("projects空", {"projects": []}),
          ("projectsとissuesが両方", {"projects": [{"name": "P", "issues": []}], "issues": [{"id": 1, "title": "無視される"}]}),
          ("v0.1 sheets非配列", {"sheets": "abc"}), ("v0.1 sheets空", {"sheets": []}),
          ("links非配列", {"projects": [{"name": "P", "issues": [{"id": 1, "title": "x", "links": "abc"}]}]}),
          ("links要素が壊れ", {"projects": [{"name": "P", "issues": [{"id": 1, "title": "x", "links": [None, 3, {}, [1]]}]}]}),
          # ランダム変異テストで見つかった落とし穴（links[].wbs の検査が tasks を再帰する経路）
          ("children が数値", {"projects": [{"name": "P", "tasks": [{"id": "1", "children": 5}],
                                            "issues": [{"id": 1, "title": "x", "links": [{"wbs": "9"}]}]}]}),
          ("children が文字列", {"projects": [{"name": "P", "tasks": [{"id": "1", "children": "abc"}],
                                              "issues": [{"id": 1, "title": "x", "links": [{"wbs": "9"}]}]}]}),
          ("children がオブジェクト", {"projects": [{"name": "P", "tasks": [{"id": "1", "children": {"a": 1}}],
                                                  "issues": [{"id": 1, "title": "x", "links": [{"wbs": "9"}]}]}]}),
          ("tasks の要素が非オブジェクト", {"projects": [{"name": "P", "tasks": [3, "x", None, [1]],
                                                      "issues": [{"id": 1, "title": "x", "links": [{"wbs": "9"}]}]}]}),
          ("tasks が非配列", {"projects": [{"name": "P", "tasks": 7,
                                          "issues": [{"id": 1, "title": "x", "links": [{"wbs": "9"}]}]}]}),
          ("案件名がオブジェクト", {"projects": [{"name": {"a": 1},
                                              "issues": [{"id": 1, "title": "x", "links": [{"issue": 1}]}]}]}),
          ("milestones が非配列", {"projects": [{"name": "P", "milestones": 3, "issues": [{"id": 1, "title": "x"}]}]})]

errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_page(b, viewport={"width": 1500, "height": 820})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
    pg.goto(VIEWER)

    def render_no_crash(label, data):
        before = len(errors)
        pg.evaluate("d => window.renderData(d)", data)
        pg.wait_for_timeout(80)
        txt = pg.evaluate("()=>document.body.innerText")
        ok = (len(errors) == before and "NaN" not in txt and "undefined" not in txt
              and "[object Object]" not in txt)
        check(ok, f"no-crash/no-NaN/no-undefined/no-[object Object]: {label}")

    for fx in FIXTURES:
        render_no_crash(fx.name, json.loads(fx.read_text(encoding="utf-8")))
    # 壊れた tasks/children/milestones で落ちる、wbs 側（計画の描画）の既知の脆さ
    # （docs/design/unified-touchpoints.md §4）。統合版では wbs 側が先に描くので、
    # 課題側のコーパス回帰では対象外にする（計画側の課題として別途起票）。
    WBS_FRAGILE = ("children が数値", "children が文字列", "children がオブジェクト",
                   "tasks の要素が非オブジェクト", "tasks が非配列", "milestones が非配列")
    for label, val in INLINE:
        if UNIFIED and label in WBS_FRAGILE:
            print(f"SKIP {label}（wbs 本家の既知の脆さ・段階Cで起票）")
            continue
        render_no_crash(f"inline:{label}", val)

    check(len(FIXTURES) >= 15, f"fixture が15件以上ある -> {len(FIXTURES)}")
    b.close()
finish(errors)
