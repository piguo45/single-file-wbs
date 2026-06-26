"""#70 入れ子(子タスク)編集の回帰テスト【テスト先行＝実装前は RED】

確定した契約・挙動（案Y 対称モデル）:
- ＋子ボタン = button[data-act="addchild"][data-path="<path>"]
    - リーフに初回 → 値を子1へ移して集計化（総工数・進捗は不変）
    - 集計に → 末尾に空の子（既定値）。総工数は増える
    - 3L(深さ2)の行には ＋子 を出さない（4L禁止のガード）
- 削除(既存 data-act="del") で「最後の子」を消すと、その子の値が親へ戻り
  リーフに降格する（案Y）。総工数は不変。
- 不変条件: 工数の実値は常に葉にあり、昇格/降格の前後で保存される。

実装(#70)が入るまで addchild ボタンが存在しないため、本スイートは RED。
グリーンになるように wbs_viewer.html を実装する。
"""
import json
from playwright.sync_api import sync_playwright
from common import VIEWER, granted_handle_init, check, finish


def effort(node):
    """ノードの工数(人日) = 配下リーフの qty*hours/8 合計。children 無し/空＝リーフ。"""
    ch = node.get("children")
    if ch:
        return sum(effort(c) for c in ch)
    return (node.get("qty") or 0) * (node.get("hours") or 0) / 8


def node_at(d, *path):
    """projects[0].tasks をルートに index で辿る。(0,)=task0 / (0,0)=task0.child0"""
    node = d["projects"][0]["tasks"][path[0]]
    for i in path[1:]:
        node = node["children"][i]
    return node


# fixture: 設計(2Lリーフ 1x40=5人日 / _progress40 / _memo)・実装(2Lリーフ 2x16=4人日)・単独(1Lリーフ 1x8)
DATA = {"projects": [{"name": "P", "milestones": [], "tasks": [
    {"id": "1", "name": "フェーズ", "children": [
        {"id": "1.1", "name": "設計", "qty": 1, "hours": 40, "assignee": "佐藤",
         "plan": {"start": "2026-06-01", "end": "2026-06-10"},
         "actual": {"start": "2026-06-02", "end": None}, "note": "n",
         "_progress": 40, "_memo": "keep-me"},
        {"id": "1.2", "name": "実装", "qty": 2, "hours": 16, "assignee": "田中",
         "plan": {"start": None, "end": None}, "actual": {"start": None, "end": None}, "note": ""},
    ]},
    {"id": "2", "name": "単独", "qty": 1, "hours": 8, "assignee": "ぴぐお",
     "plan": {"start": None, "end": None}, "actual": {"start": None, "end": None}, "note": ""},
]}]}

errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1500, "height": 700})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.on("dialog", lambda d: d.accept())            # 削除確認は OK
    pg.add_init_script(granted_handle_init(DATA))     # 書込可ハンドル＋window.__file

    def setup():
        pg.goto(VIEWER)                               # 再ナビゲートで __file を初期化
        pg.click("#openBtn"); pg.wait_for_timeout(150)
        pg.click("#editBtn"); pg.wait_for_timeout(200)

    def saved():
        pg.wait_for_timeout(550)                      # 保存デバウンス(400ms)+余裕
        return json.loads(pg.evaluate("()=>window.__file"))

    def addchild(path):
        return pg.query_selector(f'button[data-act="addchild"][data-path="{path}"]')

    # ===== T1: 契約 ＋ 昇格(A1) ＋ フィールド引き継ぎ(A3) ＋ id採番(D1) ＋ 3Lガード(A4) =====
    setup()
    check("on" in (pg.get_attribute("#editBtn", "class") or ""), "T1 編集ON")
    check(addchild("0/0/0") is not None, "T1 ＋子が2Lリーフ(設計)にある [A]")
    check(addchild("0/1") is not None, "T1 ＋子が1Lリーフ(単独)にある [A]")
    btn = addchild("0/0/0")
    if btn:
        btn.click(); pg.wait_for_timeout(250)
        d = saved()
        sg = node_at(d, 0, 0)                         # 設計
        ch = sg.get("children") or []
        check(len(ch) == 1, "T1 設計が集計化(子1件) [A1]")
        check(round(effort(sg), 3) == 5.0, "T1 昇格後も総工数=5人日で不変 [A1]")
        if ch:
            c = ch[0]
            check(c.get("qty") == 1 and c.get("hours") == 40, "T1 数量/時間を子へ引き継ぐ [A1]")
            check(c.get("assignee") == "佐藤", "T1 担当を子へ引き継ぐ [A3]")
            check(c.get("_progress") == 40, "T1 _progress を子へ保持 [A3]")
            check(c.get("_memo") == "keep-me", "T1 カスタム_キーを子へ保持 [A3]")
            check(c.get("id") == "1.1.1", "T1 子idが親id+連番 [D1]")
        check(addchild("0/0/0/0") is None, "T1 3L(子)には＋子を出さない [A4]")
    else:
        check(False, "T1 ＋子ボタンが無い＝未実装(RED) [A1]")

    # ===== T2: 集計に＋子で空の子を追加(B1) ＋ id採番(D1) =====
    setup()
    btn = addchild("0/0")                             # フェーズ集計
    if btn:
        btn.click(); pg.wait_for_timeout(250)
        d = saved()
        ph = node_at(d, 0)                            # フェーズ（tasks[0]）
        kids = ph.get("children") or []
        check(len(kids) == 3, "T2 集計に空の子が1件追加(計3件) [B1]")
        if len(kids) == 3:
            nc = kids[2]
            check(nc.get("id") == "1.3", "T2 追加子のidが1.3 [D1]")
            # 元のフェーズ工数(設計5+実装4=9) ＋ 新子の工数 と一致
            check(round(effort(ph), 3) == round(9 + effort(nc), 3), "T2 合計=元9+新子(移行なし) [B1]")
    else:
        check(False, "T2 集計への＋子ボタンが無い＝未実装(RED) [B1]")

    # ===== T3: 降格(案Y/C2) ＝ 昇格→最後の子削除で値が親へ戻る ＋ 総工数不変(G3) =====
    setup()
    btn = addchild("0/0/0")                           # 設計を集計化(子=1.1.1)
    if btn:
        btn.click(); pg.wait_for_timeout(250)
        delb = pg.query_selector('button[data-act="del"][data-path="0/0/0/0"]')
        check(delb is not None, "T3 子(3L)の削除✕がある")
        if delb:
            delb.click(); pg.wait_for_timeout(300)    # confirm は自動OK
            d = saved()
            sg = node_at(d, 0, 0)                      # 設計
            check(not sg.get("children"), "T3 最後の子削除で設計がリーフに降格 [C2]")
            check(sg.get("qty") == 1 and sg.get("hours") == 40, "T3 子の値が親へ戻る [C2/案Y]")
            check(sg.get("_memo") == "keep-me", "T3 _キーも親へ戻る [C2]")
            check(round(effort(sg), 3) == 5.0, "T3 降格後も総工数=5で不変 [C2/G3]")
    else:
        check(False, "T3 ＋子ボタンが無い＝未実装(RED) [C2]")

    # ===== T4: 複数子のうち1件削除は降格しない（arr.length===0 分岐の誤発火防止） =====
    setup()
    delb = pg.query_selector('button[data-act="del"][data-path="0/0/1"]')   # 実装（2子のうち1件）
    check(delb is not None, "T4 実装(2L子)の削除✕がある")
    if delb:
        delb.click(); pg.wait_for_timeout(300)
        d = saved()
        ph = node_at(d, 0)                            # フェーズ
        check(bool(ph.get("children")), "T4 子が残る間はフェーズが集計のまま（降格しない）")
        kids = ph.get("children") or []
        check(len(kids) == 1 and kids[0].get("name") == "設計", "T4 残った子は設計のみ")
        check(round(effort(ph), 3) == 5.0, "T4 実装(4人日)削除で工数=5 [G3]")

    # ===== T5: 元から複数子の集計を最後まで削って降格＝値が親へ戻る・工数/日付不変（案Y対称） =====
    setup()
    d1 = pg.query_selector('button[data-act="del"][data-path="0/0/1"]')     # 実装を削除（残=設計1件）
    if d1:
        d1.click(); pg.wait_for_timeout(300)
        d2 = pg.query_selector('button[data-act="del"][data-path="0/0/0"]') # 最後の子=設計を削除→降格
        check(d2 is not None, "T5 最後の子(設計)の削除✕がある")
        if d2:
            d2.click(); pg.wait_for_timeout(300)
            d = saved()
            ph = node_at(d, 0)                        # フェーズ
            check(not ph.get("children"), "T5 最後の子削除でフェーズがリーフに降格 [C2]")
            check(ph.get("qty") == 1 and ph.get("hours") == 40, "T5 設計の数量/時間が親へ戻る [C2]")
            check(ph.get("actual", {}).get("start") == "2026-06-02", "T5 実績日付も親へ戻る（日付値の往復）")
            check(ph.get("_progress") == 40 and ph.get("_memo") == "keep-me", "T5 _progress/_キーも親へ戻る")
            check(round(effort(ph), 3) == 5.0, "T5 降格後も総工数=5で不変 [G3]")

    b.close()

finish(errors)
