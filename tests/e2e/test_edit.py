"""編集モード回帰: 保存・_キー保持・id採番・自動展開・同期render・旧形式変換・誤上書き防止・外部変更検知
   ＋外部変更をキャンセルした後の「更新」で未保存の編集を黙って捨てないこと"""
import json
from playwright.sync_api import sync_playwright
from common import VIEWER, check, finish, leaf, new_page

NEW_FMT = {"_meta": {"owner": "tester"},
           "projects": [{"name": "P1", "milestones": [],
                         "tasks": [{"id": "1", "name": "工程1", "_memo": "user key", "children": [
                                       leaf("1.1", "作業A", "佐藤", "2026-06-01", "2026-06-05"),
                                       leaf("1.2", "作業B", "佐藤", "2026-06-03", "2026-06-08"),
                                       leaf("1.3", "作業C", "佐藤", "2026-06-05", "2026-06-10")]},
                                   leaf("3", "単独3", "佐藤", "2026-06-08", "2026-06-12")]}]}
OLD_FMT = {"project": "旧PJ", "milestones": [],
           "tasks": [leaf("1", "旧作業", "佐藤", "2026-06-01", "2026-06-05")]}
BROKEN = "{ broken json !!!"

INIT = """
window.__files = {}; window.__mtimes = {}; window.__pick = 'A';
function mkHandle(key){
  return {kind:'file',
    getFile: async () => new File([window.__files[key]], key+'.json',
                {type:'application/json', lastModified: window.__mtimes[key]||1000}),
    queryPermission: async () => 'granted', requestPermission: async () => 'granted',
    createWritable: async () => ({ write: async (s)=>{ window.__buf = s; },
                               close: async ()=>{ window.__files[key] = window.__buf;
                                                window.__mtimes[key]=(window.__mtimes[key]||1000)+1; } })};
}
window.showOpenFilePicker = async () => [mkHandle(window.__pick)];
"""

errors, dialogs = [], []
ACCEPT = [True]      # ダイアログを受けるか取り消すか（外部変更／読み直しの確認を切り替える）
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_page(b, viewport={"width": 1500, "height": 600})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("dialog", lambda d: (dialogs.append(d.message), d.accept() if ACCEPT[0] else d.dismiss()))
    pg.add_init_script(INIT)
    pg.goto(VIEWER)

    def setfile(key, text, mtime=1000):
        pg.evaluate("a => {window.__files[a.k]=a.t; window.__mtimes[a.k]=a.m;}",
                    {"k": key, "t": text, "m": mtime})
    def getfile(key):
        return pg.evaluate("k => window.__files[k]", key)
    def openfile(key):
        pg.evaluate("k => {window.__pick=k;}", key)
        pg.click("#openBtn"); pg.wait_for_timeout(150)
    def flush():
        pg.wait_for_timeout(600)  # 保存デバウンス(400ms)+余裕

    setfile("A", json.dumps(NEW_FMT, ensure_ascii=False))
    openfile("A")
    pg.click("#editBtn"); pg.wait_for_timeout(150)
    check("on" in (pg.get_attribute("#editBtn", "class") or ""), "編集ON")
    pg.fill('input[data-path="0/0/0"][data-field="assignee"]', "鈴木")
    pg.dispatch_event('input[data-path="0/0/0"][data-field="assignee"]', "change")
    flush()
    saved = json.loads(getfile("A"))
    check(saved["projects"][0]["tasks"][0]["children"][0]["assignee"] == "鈴木", "フィールド編集が保存される")
    check(saved.get("_meta", {}).get("owner") == "tester", "トップの _meta が残る")
    check(saved["projects"][0]["tasks"][0].get("_memo") == "user key", "ノードの _memo が残る")
    check("_calc" not in getfile("A") and "_leaf" not in getfile("A"), "_calc/_leaf は除外")

    pg.click('button[data-act="del"][data-path="0/0/1"]'); pg.wait_for_timeout(100)
    pg.click('button[data-act="addtask"][data-proj="0"]'); pg.wait_for_timeout(100)
    flush()
    ids = [str(t["id"]) for t in json.loads(getfile("A"))["projects"][0]["tasks"]]
    check(len(ids) == len(set(ids)), f"＋タスクのid重複なし -> {ids}")

    pg.click('#allCaret'); pg.wait_for_timeout(100)   # 全たたみ
    before = len(pg.query_selector_all("#leftRows .lrow"))
    pg.click('button[data-act="addtask"][data-proj="0"]'); pg.wait_for_timeout(150)
    check(len(pg.query_selector_all("#leftRows .lrow")) > before, "折りたたみ中の＋タスクで自動展開")
    flush()

    pg.click('button[data-act="add"][data-path="0/0/1"]'); pg.wait_for_timeout(100)
    moved = pg.evaluate("""()=>{
      const sel = p => document.querySelector(`input[data-path="${p}"][data-field="name"]`).value;
      const before = sel('0/0/2');
      document.querySelector('button[data-act="up"][data-path="0/0/2"]').click();
      return {before, at1: sel('0/0/1')};
    }""")
    check(moved["at1"] == moved["before"], "構造操作はクリック直後に同期render（stale path無し）")
    flush()

    setfile("B", json.dumps(OLD_FMT, ensure_ascii=False))
    openfile("B")
    check("on" not in (pg.get_attribute("#editBtn", "class") or ""), "新規読込で編集OFF")
    n = len(dialogs)
    pg.click("#editBtn"); pg.wait_for_timeout(200)
    check(len(dialogs) > n and "旧フォーマット" in dialogs[-1], "旧フォーマット変換確認が出る")
    pg.fill('input[data-pname="0"]', "新PJ名")
    pg.dispatch_event('input[data-pname="0"]', "change")
    flush()
    check(json.loads(getfile("B")).get("projects", [{}])[0].get("name") == "新PJ名", "旧→新変換後にrename保存")

    setfile("C", BROKEN)
    before_c = getfile("C")
    openfile("C"); pg.wait_for_timeout(200)
    pg.fill('input[data-pname="0"]', "さらに変更")
    pg.dispatch_event('input[data-pname="0"]', "change")
    flush()
    check(getfile("C") == before_c, "壊れたファイルを開いても上書きしない")
    check(json.loads(getfile("B"))["projects"][0]["name"] == "さらに変更", "編集は元ファイルに保存され続ける")

    pg.evaluate("() => {window.__mtimes['B'] += 100;}")
    n = len(dialogs)
    pg.fill('input[data-pname="0"]', "競合テスト")
    pg.dispatch_event('input[data-pname="0"]', "change")
    flush(); pg.wait_for_timeout(300)
    check(any("ツール外" in d for d in dialogs[n:]), "外部変更の上書き確認が出る")

    # ===== 外部変更をキャンセル → 「更新」で未保存の編集を黙って捨てない =====
    ACCEPT[0] = False                                   # 以降の確認はすべてキャンセル
    pg.evaluate("() => {window.__mtimes['B'] += 100;}")
    pg.fill('input[data-pname="0"]', "捨てられては困る編集")
    pg.dispatch_event('input[data-pname="0"]', "change")
    flush(); pg.wait_for_timeout(300)                   # 外部変更の確認をキャンセル＝書けずに残る
    n = len(dialogs)
    pg.click("#refreshBtn"); pg.wait_for_timeout(400)
    check(any("未保存" in d for d in dialogs[n:]),
          f"未保存のまま「更新」を押すと確認が出る -> {dialogs[n:]}")
    check(pg.input_value('input[data-pname="0"]') == "捨てられては困る編集",
          "確認をキャンセルすれば読み直さない（編集は画面に残る）")
    ACCEPT[0] = True
    pg.click("#refreshBtn"); pg.wait_for_timeout(500)
    check(pg.input_value('input[data-pname="0"]') == "競合テスト",
          f"確認をOKすれば読み直す -> {pg.input_value('input[data-pname=\'0\']')!r}")
    b.close()
finish(errors)
