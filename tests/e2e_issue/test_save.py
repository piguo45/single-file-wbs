"""保存パス（聖域）: デバウンス・保存の直列化・InvalidStateError の1回リトライ・派生値の除外。
   姉妹品 single-file-wbs から移植した writeNow/queueSave/flushSaves を壊す変更はここで捕まる。"""
import json
from playwright.sync_api import sync_playwright
from common import S, VIEWER, book, check, finish, granted_handle_init, issue, action, new_page, DECIDED

DATA = book([issue(1, "元のタイトル", due="2026-09-20", decisions=DECIDED,
                   actions=[action("2026-09-01", "着手", "ぴぐお", True)])],
            name="保存テスト", _meta={"owner": "tester"})

# 初回 createWritable だけ InvalidStateError を投げ、2回目は成功するフェイクハンドル
RETRY_INIT = """
window.__file = %s; window.__writes = 0; window.__cwCalls = 0;
const fh = {kind:'file',
  getFile: async()=> new File([window.__file],'issue.json',{type:'application/json',lastModified:window.__mt||1000}),
  queryPermission: async()=>'granted', requestPermission: async()=>'granted',
  createWritable: async()=>{
    window.__cwCalls++;
    if(window.__cwCalls===1){ throw new DOMException("state had changed since it was read from disk","InvalidStateError"); }
    let b=null;
    return {write:async s=>{b=s;}, abort:async()=>{},
      close:async()=>{window.__file=b; window.__mt=(window.__mt||1000)+1; window.__writes++;}};
  }};
window.showOpenFilePicker = async()=>[fh];
""" % json.dumps(json.dumps(DATA, ensure_ascii=False))

errors, dialogs = [], []
with sync_playwright() as p:
    b = p.chromium.launch()

    # --- デバウンス・直列化・派生値の除外 ---
    pg = new_page(b, viewport={"width": 1500, "height": 800})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    pg.add_init_script(granted_handle_init(DATA))
    pg.goto(VIEWER)
    pg.click(S("#openBtn")); pg.wait_for_timeout(200)
    pg.click(S("#editBtn")); pg.wait_for_timeout(250)
    base_writes = pg.evaluate("()=>window.__writes")

    # 400ms のデバウンス内に3回編集 → 書込は1回だけ
    for v in ("あ", "あい", "あいう"):
        pg.fill('input[data-i="0"][data-a="0"][data-field="assignee"]', v)
        pg.dispatch_event('input[data-i="0"][data-a="0"][data-field="assignee"]', "change")
        pg.wait_for_timeout(60)
    pg.wait_for_timeout(700)
    w = pg.evaluate("()=>window.__writes") - base_writes
    check(w == 1, f"デバウンス：連続3編集で書込は1回 得 {w}")
    saved = json.loads(pg.evaluate("()=>window.__file"))
    check(saved["projects"][0]["issues"][0]["actions"][0]["assignee"] == "あいう", "最後の値が保存される")
    check("_calc" not in pg.evaluate("()=>window.__file"), "派生値 _calc はファイルに書かれない")
    check(saved.get("_meta", {}).get("owner") == "tester", "トップの _meta は保持される")
    # 派生値（状態・期限超過・★の判定）そのものが JSON に現れない
    # ※ トップレベルの `star` は「報告期間の設定」であって派生値ではない（書かれてよい・test_star.py 参照）
    txt = pg.evaluate("()=>window.__file")
    check(all(k not in txt for k in ('"state"', '"overdue"', '"hasStar"', '"starActs"')),
          "状態/期限超過/★の判定は JSON に書かれない（すべて導出）")
    check('"assignee"' in txt and saved["projects"][0]["issues"][0].get("assignee") is None,
          "担当も導出：課題レベルの assignee は生えない（行動側にだけ存在する）")

    # 直列化：書込が重ならず、保存回数＝フラッシュ回数
    n0 = pg.evaluate("()=>window.__writes")
    for i, v in enumerate(("A", "B")):
        pg.fill('input[data-i="0"][data-a="0"][data-field="assignee"]', v)
        pg.dispatch_event('input[data-i="0"][data-a="0"][data-field="assignee"]', "change")
        pg.wait_for_timeout(600)
    n1 = pg.evaluate("()=>window.__writes")
    check(n1 - n0 == 2, f"直列化：デバウンスを跨いだ2編集で書込2回 得 {n1 - n0}")
    check(json.loads(pg.evaluate("()=>window.__file"))["projects"][0]["issues"][0]["actions"][0]["assignee"] == "B",
          "最後の書込が勝つ（後勝ちの取りこぼし無し）")
    pg.close()

    # --- InvalidStateError の1回リトライ ---
    pg2 = new_page(b, viewport={"width": 1500, "height": 800})
    pg2.on("pageerror", lambda e: errors.append(str(e)))
    pg2.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    pg2.add_init_script(RETRY_INIT)
    pg2.goto(VIEWER)
    pg2.click(S("#openBtn")); pg2.wait_for_timeout(200)
    pg2.click(S("#editBtn")); pg2.wait_for_timeout(250)
    pg2.fill('input[data-i="0"][data-a="0"][data-field="assignee"]', "新担当")
    pg2.dispatch_event('input[data-i="0"][data-a="0"][data-field="assignee"]', "change")
    pg2.wait_for_timeout(1300)   # debounce(400)+retry delay(250)+余裕

    cw = pg2.evaluate("()=>window.__cwCalls")
    writes = pg2.evaluate("()=>window.__writes")
    check(cw == 2, f"createWritable が2回呼ばれた（初回失敗→1回だけ再試行）得 {cw}")
    check(writes == 1, f"再試行で書込が1回成功した 得 {writes}")
    check(json.loads(pg2.evaluate("()=>window.__file"))["projects"][0]["issues"][0]["actions"][0]["assignee"] == "新担当",
          "再試行後のファイルに編集が反映")
    check(not any("失敗" in d for d in dialogs), f"保存失敗アラートが出ていない 得 {dialogs}")
    b.close()
finish(errors)
