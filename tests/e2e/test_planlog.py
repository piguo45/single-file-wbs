"""リスケ履歴(#96)：表示（直近トレイル1本・↷Nバッジ・クリック吹き出し）と記録（↷フォーム→plan自動更新＋_planLog追記）。
訂正（日付セル直接編集）は履歴を残さない＝リスケとの分離。XSS(esc)・壊れ入力graceful・変更なしは記録しない。
本日=CLOCK_PIN(2026-06-15)固定。"""
from playwright.sync_api import sync_playwright
from common import VIEWER, check, finish, leaf, granted_handle_init, new_page
import json

def mklog(fs, fe, ts, te, reason=None, at="2026-06-10T09:00:00Z"):
    e = {"at": at, "from": {"start": fs, "end": fe}, "to": {"start": ts, "end": te}, "by": "manual"}
    if reason: e["reason"] = reason
    return e

L1 = leaf("1.1", "両方リスケ", ps="2026-06-17", pe="2026-06-21")
L1["_planLog"] = [mklog("2026-06-01", "2026-06-05", "2026-06-06", "2026-06-10", "要件追加"),
                  mklog("2026-06-11", "2026-06-15", "2026-06-17", "2026-06-21", "<img src=x onerror=alert(1)>注入テスト")]
L2 = leaf("1.2", "終了のみリスケ", ps="2026-06-16", pe="2026-06-25")
L2["_planLog"] = [mklog("2026-06-16", "2026-06-22", "2026-06-16", "2026-06-25")]
L3 = leaf("1.3", "リスケなし", ps="2026-06-22", pe="2026-06-25")
L4 = leaf("1.4", "壊れ混在", ps="2026-06-16", pe="2026-06-20")
L4["_planLog"] = ["str", 123, None, {}, mklog("2026-06-10", "2026-06-14", "2026-06-16", "2026-06-20")]
DATA = {"projects": [{"name": "P", "milestones": [], "tasks": [
    {"id": "1", "name": "工程", "children": [L1, L2, L3, L4]}]}]}

errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_page(b, viewport={"width": 1500, "height": 700})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.add_init_script(granted_handle_init(DATA))
    pg.goto(VIEWER)
    pg.click("#openBtn"); pg.wait_for_timeout(200)

    # ===== 表示 =====
    bdgs = pg.eval_on_selector_all("#leftRows .rsbdg", "e=>e.map(x=>x.textContent)")
    check(bdgs == ["↷2", "↷1", "↷1"], f"↷N=有効エントリ数（壊れ要素は数えない・なし行は無印） -> {bdgs}")
    # トレイル：L1=直近が両方変更→上下2本 / L2=終了のみ→上1本 / L3=なし / L4=直近fromが有効日付→出る
    trails = pg.evaluate("""()=>[...document.querySelectorAll('#grows .grow')].map(r=>({
        bot:r.querySelectorAll('.rs-seg:not(.top)').length, top:r.querySelectorAll('.rs-seg.top').length}))""")
    tr = [t for t in trails if t["bot"] or t["top"]]
    check(trails[2] == {"bot": 1, "top": 1}, f"両方リスケ=上下1本ずつ -> {trails[2]}")
    check(trails[3] == {"bot": 0, "top": 1}, f"終了のみ=上だけ1本 -> {trails[3]}")
    check(trails[4] == {"bot": 0, "top": 0}, f"リスケなし=トレイルなし -> {trails[4]}")
    check(len(tr) == 3, f"トレイルは直近1修正ぶんだけ（行数3） -> {len(tr)}")
    # 吹き出し：バッジクリックで開く・履歴と当初比・XSSがエスケープされている
    pg.click('#leftRows .rsbdg >> nth=0'); pg.wait_for_timeout(100)
    check(pg.is_visible("#rsPop"), "バッジクリックで吹き出しが開く")
    pop = pg.inner_text("#rsPop")
    check("変更履歴（2回）" in pop and "要件追加" in pop, f"全履歴と理由が出る -> {pop[:60]}")
    check("当初" in pop and "6/1〜6/5" in pop, "当初（先頭エントリのfrom）が出る")
    check(pg.eval_on_selector_all("#rsPop img", "e=>e.length") == 0 and "onerror" in pop,
          "理由内のHTMLはエスケープされ実行されない（XSS防御）")
    pg.click('#leftRows .rsbdg >> nth=0'); pg.wait_for_timeout(100)
    check(not pg.is_visible("#rsPop"), "同じバッジ再クリックで閉じる（トグル）")
    # バーclickでも開く／外側クリックで閉じる
    pg.click('.bar.plan[data-rslog] >> nth=0'); pg.wait_for_timeout(100)
    check(pg.is_visible("#rsPop"), "リスケ済みバーのクリックでも開く")
    pg.click("#leftHead", position={"x": 5, "y": 5}); pg.wait_for_timeout(100)
    check(not pg.is_visible("#rsPop"), "外側クリックで閉じる")

    # ===== 記録（編集モード） =====
    pg.click("#editBtn"); pg.wait_for_timeout(300)
    # リスケなし行(L3)の↷でフォーム→新日付＋理由→確定
    pg.click('button[data-act="resched"] >> nth=2'); pg.wait_for_timeout(100)
    check(pg.is_visible("#rsForm"), "↷でリスケフォームが開く")
    pg.fill('#rsForm [data-rs="s"]', "2026-06-24")
    pg.fill('#rsForm [data-rs="e"]', "2026-06-27")
    pg.fill('#rsForm [data-rs="r"]', "上流の遅延")
    pg.click("#rsForm .rs-ok"); pg.wait_for_timeout(800)   # 確定→自動保存(0.4sデバウンス)を待つ
    saved = json.loads(pg.evaluate("()=>window.__file"))
    n3 = saved["projects"][0]["tasks"][0]["children"][2]
    check(n3["plan"] == {"start": "2026-06-24", "end": "2026-06-27"}, f"確定でplanが自動更新 -> {n3['plan']}")
    log = n3.get("_planLog", [])
    check(len(log) == 1 and log[0]["from"] == {"start": "2026-06-22", "end": "2026-06-25"}
          and log[0]["to"] == {"start": "2026-06-24", "end": "2026-06-27"}
          and log[0]["by"] == "manual" and log[0]["reason"] == "上流の遅延" and "T" in log[0].get("at", ""),
          f"_planLogに1件追記(from/to/by/reason/at) -> {log}")
    check(pg.eval_on_selector_all("#leftRows .rsbdg", "e=>e.map(x=>x.textContent)")[2] == "↷1",
          "確定後にバッジ↷1が現れる")
    # 変更なし＝記録しない
    pg.click('button[data-act="resched"] >> nth=2'); pg.wait_for_timeout(100)
    pg.click("#rsForm .rs-ok"); pg.wait_for_timeout(700)
    saved = json.loads(pg.evaluate("()=>window.__file"))
    check(len(saved["projects"][0]["tasks"][0]["children"][2]["_planLog"]) == 1,
          "変更なしで確定しても記録されない")
    # 訂正（日付セル直接編集）＝履歴に残さない
    pg.fill('input[data-field="ps"] >> nth=2', "2026-06-25")
    pg.dispatch_event('input[data-field="ps"] >> nth=2', "change"); pg.wait_for_timeout(800)
    saved = json.loads(pg.evaluate("()=>window.__file"))
    n3 = saved["projects"][0]["tasks"][0]["children"][2]
    check(n3["plan"]["start"] == "2026-06-25" and len(n3["_planLog"]) == 1,
          f"直接編集=訂正（planは変わるが履歴は増えない） -> plan={n3['plan']} log={len(n3['_planLog'])}件")
    # キャンセル
    pg.click('button[data-act="resched"] >> nth=0'); pg.wait_for_timeout(100)
    pg.click("#rsForm .rs-cancel"); pg.wait_for_timeout(100)
    check(not pg.is_visible("#rsForm"), "取消でフォームが閉じる（記録なし）")
    b.close()
finish(errors)
