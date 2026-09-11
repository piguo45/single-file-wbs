"""セキュリティ回帰: XSSエスケープ（esc）と属性インジェクション。
   1箇所でも esc() を忘れたらここが赤くなる。備考の自動リンクは http(s) のみ。"""
from playwright.sync_api import sync_playwright
from common import J, S, VIEWER, check, finish, granted_handle_init, load_test_json, new_page

D = load_test_json("正常_特殊文字エスケープ.json")

errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_page(b, viewport={"width": 1500, "height": 900})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.add_init_script(granted_handle_init(D))
    pg.goto(VIEWER)
    pg.evaluate("()=>{window.__xss=false;const o=window.alert;window.alert=()=>{window.__xss=true;};}")

    no_on_attr = J("""()=>[...document.querySelectorAll('#tbody *,#filterBar *,#stat *')]
        .some(e=>e.getAttributeNames().some(n=>n.startsWith('on')))""")

    def audit(label):
        check(not pg.evaluate("()=>window.__xss"), f"{label}: alert が実行されない")
        check(pg.eval_on_selector_all(S("#tbody script"), "e=>e.length") == 0, f"{label}: <script> が生DOMになっていない")
        check(pg.eval_on_selector_all(S("#tbody img"), "e=>e.length") == 0, f"{label}: <img onerror> が生DOMにならない")
        check(pg.evaluate(no_on_attr) is False, f"{label}: on* イベント属性が注入されていない")
        check(pg.eval_on_selector_all(S("#tbody tr:nth-child(1) td"), "e=>e.length") == 6,
              f"{label}: </td> 注入で列が増えない（6列のまま）")

    # --- 表示モード ---
    pg.click(S("#openBtn")); pg.wait_for_timeout(250)
    audit("表示")
    body = pg.inner_text(S("#tbody"))
    check("<script>alert(1)</script>" in body, "表示: タグはテキストとして可視（esc済み）")
    check('"引用"' in body and "&" in body, "表示: 引用符と & がそのまま見える")
    # 備考は印だけ（本文は吹き出し）。開いてから自動リンクとエスケープを見る
    pg.click(S("#tbody .lk [data-note]")); pg.wait_for_timeout(200)
    hrefs = pg.eval_on_selector_all(S("#notePop a"), "e=>e.map(x=>x.getAttribute('href'))")
    check(hrefs == ["https://example.com/a?x=1&y=2"], f"備考の吹き出し: http(s) だけリンク化・javascript: は素通し -> {hrefs}")
    check(pg.eval_on_selector_all(S("#notePop script,#notePop img"), "e=>e.length") == 0,
          "備考の吹き出し: <script>/<img onerror> が生DOMにならない")
    check(pg.evaluate(J("()=>[...document.querySelectorAll('#notePop *')].some(e=>e.getAttributeNames().some(n=>n.startsWith('on')))")) is False,
          "備考の吹き出し: on* イベント属性が注入されていない")
    check(not pg.evaluate("()=>window.__xss"), "備考の吹き出し: alert が実行されない")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    # 担当フィルタのチェックボックス（data-asg）にも生値を流さない
    asg = pg.eval_on_selector_all(S("#filterBar .asg-cb"), "e=>e.map(x=>x.getAttribute('data-asg'))")
    check(asg == ['"><img src=x onerror=alert(1)>', '</td><td>注入'],
          f"表示: 行動の担当（フィルタ候補）の生値は属性値として無害化 -> {asg}")

    # --- 編集モード（input の value / title 属性も同じ経路でエスケープされる） ---
    pg.click(S("#editBtn")); pg.wait_for_timeout(300)
    check("on" in (pg.get_attribute(S("#editBtn"), "class") or ""), "編集ON")
    audit("編集")
    val = pg.eval_on_selector('input[data-i="0"][data-field="title"]', "e=>e.value")
    check(val == '<script>alert(1)</script> & "引用" <b>太字</b>', f"編集: value に生の文字列が復元される -> {val!r}")
    av = pg.eval_on_selector('input[data-i="0"][data-a="0"][data-field="assignee"]', "e=>e.value")
    check(av == '"><img src=x onerror=alert(1)>', f"編集: 行動の担当の value も壊れない -> {av!r}")
    b.close()
finish(errors)
