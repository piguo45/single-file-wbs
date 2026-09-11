"""file:// 権限フロー: 保存ピッカーfallback・ジェスチャー失効→再クリック・選択時切り詰めへの即時書込・案内バー遷移。
   姉妹品 single-file-wbs の ensureWritable をそのまま移植しているため、同じシナリオで守る。"""
import json
from playwright.sync_api import sync_playwright
from common import J, S, VIEWER, action, book, check, finish, issue, new_page

DATA = book([issue(1, "作業", due="2026-09-20", actions=[action("2026-09-12", "次の一手", "ぴぐお")])],
            name="権限テスト")

# file://模擬: 読取ハンドルは権限API不可。保存ピッカーは1回目=ジェスチャー失効、2回目=切り詰めの上で書込可ハンドル
INIT = """
window.__file = %s; window.__cnt = {req:0, cw:0, picker:0};
const blocked = m => {throw new DOMException(m);};
const readHandle = {kind:'file', __id:'issue',
  getFile: async()=> new File([window.__file],'issue.json',{type:'application/json',lastModified:1000}),
  queryPermission: async()=>'prompt',
  requestPermission: async()=>{window.__cnt.req++; blocked("Not allowed to request permissions in this context.");},
  createWritable: async()=>{window.__cnt.cw++; blocked("Not allowed to request permissions in this context.");},
  isSameEntry: async(o)=>o.__id==='issue'};
const writeHandle = {kind:'file', __id:'issue',
  getFile: async()=> new File([window.__file??''],'issue.json',{type:'application/json',lastModified:2000}),
  queryPermission: async()=>'granted',
  createWritable: async()=>{let b=null;return {write:async s=>{b=s;},abort:async()=>{},
    close:async()=>{if(b!=null)window.__file=b;}}},
  isSameEntry: async(o)=>o.__id==='issue'};
window.showOpenFilePicker = async()=>[readHandle];
window.showSaveFilePicker = async()=>{
  window.__noticeAtPicker = document.getElementById('notice').textContent;
  window.__cnt.picker++;
  if(window.__cnt.picker===1){const e=new DOMException("Must be handling a user gesture to show a file picker.");
    Object.defineProperty(e,'name',{value:'NotAllowedError'}); throw e;}
  window.__file = '';   // Chromeの「選択時切り詰め」を再現
  return writeHandle;};
""" % json.dumps(json.dumps(DATA, ensure_ascii=False))

errors, dialogs = [], []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_page(b, viewport={"width": 1500, "height": 800})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    pg.add_init_script(INIT)
    pg.goto(VIEWER)
    pg.click(S("#openBtn")); pg.wait_for_timeout(200)

    # 1回目: ピッカーがジェスチャー失効 → 案内バーで再クリック誘導（編集ONにならない）
    pg.click(S("#editBtn")); pg.wait_for_timeout(350)
    check("on" not in (pg.get_attribute(S("#editBtn"), "class") or ""), "ジェスチャー失効時は編集ONにならない")
    check("保存ダイアログが開きます" in (pg.evaluate("()=>window.__noticeAtPicker") or ""),
          "ピッカー表示時点で案内バーが出ている（alertでジェスチャーを消費しない）")
    check("もう一度" in pg.inner_text(S("#notice")), "失効後は再クリック案内に切替")
    check(not [d for d in dialogs if "取得できませんでした" in d], "失敗アラートは出さない（バー案内のみ）")

    # 2回目: 前処理スキップで直接ピッカー → 選択時切り詰め → 即書込で空のまま残らない
    pg.click(S("#editBtn")); pg.wait_for_timeout(450)
    cnt = pg.evaluate("()=>window.__cnt")
    check("on" in (pg.get_attribute(S("#editBtn"), "class") or ""), "2回目で編集ON")
    check(cnt["req"] == 1, f"2回目は requestPermission をスキップ（ジェスチャー温存） -> {cnt}")
    content = pg.evaluate("()=>window.__file")
    check(content and len(content) > 10, "選択時切り詰め後に即書込（ファイルが空のまま残らない）")
    check(json.loads(content)["projects"][0]["issues"][0]["title"] == "作業", "即書込の内容が読込データと一致")
    check(not pg.evaluate(J("()=>document.getElementById('notice').classList.contains('show')")),
          "成功後は案内バーが消える")

    # 以後の編集が新ハンドル経由で自動保存される
    pg.fill('input[data-i="0"][data-a="0"][data-field="assignee"]', "佐藤")
    pg.dispatch_event('input[data-i="0"][data-a="0"][data-field="assignee"]', "change")
    pg.wait_for_timeout(700)
    check(json.loads(pg.evaluate("()=>window.__file"))["projects"][0]["issues"][0]["actions"][0]["assignee"] == "佐藤",
          "以後の編集が自動保存される")
    b.close()
finish(errors)
