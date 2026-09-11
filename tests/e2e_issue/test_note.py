"""備考（note）＝課題の中身ではなく添え書き。詳細には本文を出さず、小さな印だけ置く。
   印のクリックで吹き出し（全文＋http(s) の自動リンク）。たたんだ時は出さない。編集モードは textarea。
   本日=CLOCK_PIN(2026-09-15)。"""
import json
from playwright.sync_api import sync_playwright
from common import J, S, VIEWER, action, book, check, finish, granted_handle_init, issue, new_page

NOTE1 = "1行目 https://example.com/a?x=1&y=2 を参照\n2行目は javascript:alert(1) と <script>alert(2)</script>"
NOTE2 = '2件目の備考 "引用" & <img src=x onerror=alert(3)>'
DATA = book([
    issue(1, "備考あり", actions=[action("2026-09-03", "着手", "ぴぐお", True)], note=NOTE1),
    issue(2, "備考あり2", note=NOTE2),
    issue(3, "備考なし", note=""),
    issue(4, "備考が文字列でない", actions=[]),
], name="備考テスト")
DATA["projects"][0]["issues"][3]["note"] = 42   # 文字列以外は「空」扱い

errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_page(b, viewport={"width": 1500, "height": 800})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
    pg.on("dialog", lambda d: d.accept())
    pg.add_init_script(granted_handle_init(DATA))
    pg.goto(VIEWER)
    pg.evaluate("()=>{window.__xss=false;const o=window.alert;window.alert=()=>{window.__xss=true;};}")
    pg.evaluate("d=>window.renderData(d)", DATA); pg.wait_for_timeout(250)

    marks = lambda: pg.eval_on_selector_all(S("#tbody tr"),
        "e=>e.map(x=>[x.querySelector('td.num').innerText, !!x.querySelector('.lk [data-note]')])")
    pop = lambda: pg.eval_on_selector_all(S("#notePop"), "e=>e.length")

    # --- 印：空／非文字列なら出さない ---
    check(marks() == [["1", True], ["2", True], ["3", False], ["4", False]],
          f"備考が空・文字列でない課題には印を出さない -> {marks()}")
    m = pg.eval_on_selector(S("#tbody tr:nth-child(1) .lk [data-note]"), """e=>{const c=getComputedStyle(e);
        return [e.textContent.trim(), c.color, c.fontSize, c.borderTopWidth, c.display];}""")
    check(m == ["備考", "rgb(139, 148, 163)", "11px", "0px", "block"],
          f"印はリンク行と同じ薄く小さい文字・枠なし・1行 -> {m}")
    ttl = pg.eval_on_selector(S("#tbody tr:nth-child(1) .lk [data-note]"), "e=>e.getAttribute('title')")
    check(ttl == "備考（クリックで開く）", f"title は案内（全文は吹き出しで見せる） -> {ttl!r}")
    check("1行目" not in pg.inner_text(S("#tbody")) and "2件目の備考" not in pg.inner_text(S("#tbody")),
          "備考の本文は詳細に出さない")
    check(pg.eval_on_selector_all(S("#tbody a"), "e=>e.length") == 0, "表の中にリンクは無い（本文を出さないので）")

    # --- クリックで吹き出し（全文・改行保持・自動リンク） ---
    check(pop() == 0, "はじめは吹き出しなし")
    pg.click(S("#tbody tr:nth-child(1) .lk [data-note]")); pg.wait_for_timeout(200)
    check(pop() == 1, "印のクリックで吹き出しが開く")
    check(pg.inner_text(S("#notePop .np-ttl")) == "備考", "吹き出しの見出しは「備考」")
    check(pg.inner_text(S("#notePop .np-body")) == NOTE1, f"全文が出る（改行も保持） -> {pg.inner_text(S('#notePop .np-body'))!r}")
    check(pg.eval_on_selector(S("#notePop .np-body"), "e=>getComputedStyle(e).whiteSpace") == "pre-wrap",
          "本文は pre-wrap（改行が見える）")
    a = pg.eval_on_selector_all(S("#notePop a"), "e=>e.map(x=>[x.getAttribute('href'), x.target, x.rel])")
    check(a == [["https://example.com/a?x=1&y=2", "_blank", "noopener noreferrer"]],
          f"http(s) だけ自動リンク・javascript: は素通し -> {a}")
    # 吹き出しはアンカー直下・画面内
    geo = pg.eval_on_selector(S("#notePop"), """e=>{const r=e.getBoundingClientRect();
        return [r.left>=0, r.top>=0, r.right<=innerWidth+1, r.bottom<=innerHeight+1];}""")
    check(geo == [True, True, True, True], f"吹き出しは画面内にクランプされる -> {geo}")

    # --- XSS：吹き出しの中でも生DOMにならない ---
    check(pg.eval_on_selector_all(S("#notePop script,#notePop img"), "e=>e.length") == 0,
          "吹き出し: <script>/<img> が生DOMにならない")
    check(pg.evaluate(J("()=>[...document.querySelectorAll('#notePop *')].some(e=>e.getAttributeNames().some(n=>n.startsWith('on')))")) is False,
          "吹き出し: on* イベント属性が注入されていない")
    check("<script>alert(2)</script>" in pg.inner_text(S("#notePop")), "タグはテキストとして見える（esc済み）")
    check(not pg.evaluate("()=>window.__xss"), "alert が実行されない")

    # --- 同時に1つ／外側クリック／Esc／同じ印で閉じる ---
    pg.click(S("#tbody tr:nth-child(2) .lk [data-note]")); pg.wait_for_timeout(200)
    check(pop() == 1 and NOTE2 in pg.inner_text(S("#notePop")),
          f"2つ目を開くと1つ目は閉じる（同時に1つ） -> {pg.inner_text(S('#notePop'))!r}")
    check(pg.eval_on_selector_all(S("#notePop img"), "e=>e.length") == 0, "2件目の <img onerror> も生DOMにならない")
    pg.click(S("#tbody tr:nth-child(2) .lk [data-note]")); pg.wait_for_timeout(200)
    check(pop() == 0, "同じ印をもう一度押すと閉じる")
    pg.click(S("#tbody tr:nth-child(1) .lk [data-note]")); pg.wait_for_timeout(200)
    pg.click(S("#tbl thead th.detail")); pg.wait_for_timeout(200)
    check(pop() == 0, "外側クリックで閉じる")
    pg.click(S("#tbody tr:nth-child(1) .lk [data-note]")); pg.wait_for_timeout(200)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    check(pop() == 0, "Esc で閉じる")

    # --- たたんだ時は印を出さない ---
    pg.click(S("#tbody tr:nth-child(1) td.title .caret")); pg.wait_for_timeout(200)
    check(pg.eval_on_selector_all(S("#tbody tr:nth-child(1) .lk [data-note]"), "e=>e.length") == 1,
          "たたんでも印は出る（リンク行はタイトルの下に残る）")
    pg.click(S("#allCaret")); pg.wait_for_timeout(200)
    check(pg.eval_on_selector_all(S("#tbody .lk [data-note]"), "e=>e.length") == 2, "全たたみでも印は出る")
    pg.click(S("#allCaret")); pg.wait_for_timeout(200)
    check(pg.eval_on_selector_all(S("#tbody .lk [data-note]"), "e=>e.length") == 2, "全展開で印が戻る")

    # --- 編集モードは textarea で直接編集（印も吹き出しも出さない） ---
    pg.click(S("#openBtn")); pg.wait_for_timeout(250)
    pg.click(S("#editBtn")); pg.wait_for_timeout(300)
    check("on" in (pg.get_attribute(S("#editBtn"), "class") or ""), "編集ON")
    check(pg.eval_on_selector_all(S("#tbody .lk [data-note]"), "e=>e.length") == 2,
          "編集モードでも印は出る（本文の編集は textarea・印は吹き出し用）")
    ta = pg.eval_on_selector(S('#tbody textarea[data-i="0"][data-field="note"]'), "e=>e.value")
    check(ta == NOTE1, f"編集モードは textarea で全文を直接編集 -> {ta[:12]!r}…")
    pg.fill(S('#tbody textarea[data-i="0"][data-field="note"]'), "書き換えた備考")
    pg.dispatch_event(S('#tbody textarea[data-i="0"][data-field="note"]'), "change")
    pg.wait_for_timeout(700)
    check(json.loads(pg.evaluate("()=>window.__file"))["projects"][0]["issues"][0]["note"] == "書き換えた備考",
          "編集した備考が保存される")
    pg.click(S("#editBtn")); pg.wait_for_timeout(300)
    pg.click(S("#tbody tr:nth-child(1) .lk [data-note]")); pg.wait_for_timeout(200)
    check(pg.inner_text(S("#notePop .np-body")) == "書き換えた備考", "編集後の内容が吹き出しに出る")
    b.close()
finish(errors)
