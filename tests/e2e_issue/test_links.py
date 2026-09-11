"""リンク台帳（links[]）＝課題側だけに持つ4形。タイトルの下に1行（序列：タイトル＞リンク）。
   課題リンクは同じビューア内で飛ぶ（案件タブ合わせ→開く→スクロール→2秒強調・#issue= と戻る）。
   WBS は wbs_viewer.html#wbs=案件名/id を新しいタブ。URL は http(s) のみ。壊れリンクは取り消し線。
   本日=CLOCK_PIN(2026-09-15)。"""
from playwright.sync_api import sync_playwright
from common import J, S, UNIFIED, VIEWER, check, finish, load_test_json, new_page, reload

D = load_test_json("正常_案件3件.json")
BAD = load_test_json("異常_リンク不正.json")

errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1500, "height": 800})
    pg = new_page(ctx)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
    pg.goto(VIEWER)
    pg.evaluate("()=>{window.__xss=false;const o=window.alert;window.alert=()=>{window.__xss=true;};}")
    pg.evaluate("d=>window.renderData(d)", D); pg.wait_for_timeout(250)

    items = lambda: pg.eval_on_selector_all(S("#tbody .lk .lk-i"),
        "e=>e.map(x=>[x.tagName, x.innerText, x.getAttribute('href'), x.getAttribute('data-jp'), x.getAttribute('data-ji'), x.className])")
    onTab = lambda: pg.eval_on_selector_all(S("#tabBar .stab.on"), "e=>e.map(x=>x.getAttribute('data-tab'))")

    # --- 4形の表示（同じ案件の WBS／同じ案件の課題／別案件の課題／外部URL） ---
    check(pg.eval_on_selector_all(S("#tbody .lk"), "e=>e.length") == 1, "links を持つ課題にだけリンク行が出る")
    check([x.strip() for x in pg.inner_text(S("#tbody .lk")).splitlines() if x.strip()]
          == ["WBS 2.3", "課題 #2", "勤怠-1", "仕様書"],
          f"4形が1行1リンクで縦に並ぶ -> {pg.inner_text(S('#tbody .lk'))!r}")
    check(pg.eval_on_selector(S("#tbody .lk .lk-i"), "e=>getComputedStyle(e).display") == "block",
          "リンクは1行1件（block）")
    it = items()
    if UNIFIED:   # 統合ビューアは同じページで計画表示へ切り替える（新しいタブにしない）
        check(it[0][0] == "SPAN" and it[0][1] == "WBS 2.3",
              f"統合版の WBS リンクは同一ページ遷移（span＋data-jw） -> {it[0][:3]}")
    else:
        check(it[0][:3] == ["A", "WBS 2.3", "wbs_viewer.html#wbs=%E8%B2%A9%E5%A3%B2%E7%AE%A1%E7%90%86%E7%A7%BB%E8%A1%8C/2.3"],
              f"WBS は wbs_viewer.html#wbs=案件名/id（案件名はエンコード） -> {it[0][:3]}")
    check(pg.eval_on_selector(S("#tbody .lk a"), "e=>[e.target, e.rel]") == ["_blank", "noopener noreferrer"],
          "外部URL は新しいタブ（rel=noopener）")
    check(it[1][1] == "課題 #2" and it[1][3:5] == ["販売管理移行", "2"], f"同じ案件の課題＝課題 #N -> {it[1]}")
    check(it[2][1] == "勤怠-1" and it[2][3:5] == ["勤怠システム", "1"],
          f"別案件の課題は案件名の先頭2文字＋番号（勤怠-1） -> {it[2]}")
    check(pg.eval_on_selector(S('#tbody .lk [data-jp="勤怠システム"]'), "e=>e.title") == "勤怠システム #1",
          "略称のツールチップに正式名を持たせる")
    check(it[3][:3] == ["A", "仕様書", "https://example.com/spec"], f"外部URLは title を出す -> {it[3][:3]}")

    # --- 序列：タイトル ＞ リンク（薄く・小さく・枠なし） ---
    ttl = pg.eval_on_selector(S("#tbody td.title b"), "e=>[getComputedStyle(e).fontSize, getComputedStyle(e).fontWeight, getComputedStyle(e).color]")
    lk = pg.eval_on_selector(S("#tbody .lk"), "e=>[getComputedStyle(e).fontSize, getComputedStyle(e).fontWeight, getComputedStyle(e).color, getComputedStyle(e).borderTopWidth]")
    check(ttl == ["12.5px", "700", "rgb(31, 36, 48)"], f"タイトル -> {ttl}")
    check(lk == ["11px", "400", "rgb(139, 148, 163)", "0px"], f"リンクは小さく薄く・枠なし -> {lk}")
    check(float(lk[0][:-2]) < float(ttl[0][:-2]), "リンクはタイトルより小さい")

    # --- たたんだ時も出す ---
    pg.click(S("#tbody tr:nth-child(1) td.title b")); pg.wait_for_timeout(200)
    check(pg.eval_on_selector_all(S("#tbody tr:nth-child(1) .lk"), "e=>e.length") == 1, "たたんでもリンク行は出る")
    check(pg.eval_on_selector_all(S("#tbody tr:nth-child(1) td.detail .body"), "e=>e.length") == 0, "（本当にたたまれている）")
    pg.click(S("#tbody tr:nth-child(1) td.title .caret")); pg.wait_for_timeout(200)
    check(pg.eval_on_selector_all(S("#tbody tr:nth-child(1) td.detail .body"), "e=>e.length") == 1, "caret で開き直せる")

    # --- 同じ案件の課題へ飛ぶ（リンクのクリックで折りたたみは起きない） ---
    pg.click(S("#tbody .lk [data-ji='2'][data-jp='販売管理移行']")); pg.wait_for_timeout(400)
    jump = pg.eval_on_selector_all(S("#tbody tr.jump"), "e=>e.map(x=>x.getAttribute('data-key'))")
    check(jump == ["販売管理移行|2"], f"同じ案件の課題へ飛ぶ＋強調 -> {jump}")
    check(pg.evaluate("()=>location.hash") == "#issue=%E8%B2%A9%E5%A3%B2%E7%AE%A1%E7%90%86%E7%A7%BB%E8%A1%8C/2",
          f"URL に #issue=案件名/id が付く -> {pg.evaluate('()=>location.hash')}")
    check(pg.eval_on_selector_all(S("#tbody tr:nth-child(1) td.detail .body"), "e=>e.length") == 1,
          "リンクのクリックで折りたたみは起きない")
    pg.wait_for_timeout(2000)
    check(pg.eval_on_selector_all(S("#tbody tr.jump"), "e=>e.length") == 0, "強調は2秒で消える")

    # --- 別案件の課題へ飛ぶ（タブが切り替わる）／たたんでいても開く ---
    pg.evaluate("()=>{const k='勤怠システム|1';const s=JSON.parse(localStorage.getItem('issCollapsed')||'[]');s.push(k);localStorage.setItem('issCollapsed',JSON.stringify(s));}")
    reload(pg); pg.wait_for_timeout(200)
    pg.evaluate("d=>window.renderData(d)", D); pg.wait_for_timeout(250)
    pg.click(S("#tbody .lk [data-jp='勤怠システム']")); pg.wait_for_timeout(400)
    check(onTab() == ["勤怠システム"], f"別案件のタブに切り替わる -> {onTab()}")
    check(pg.eval_on_selector_all(S("#tbody tr.jump"), "e=>e.map(x=>x.getAttribute('data-key'))") == ["勤怠システム|1"],
          "飛び先が強調される")
    check(pg.eval_on_selector_all(S("#tbody tr:nth-child(1) td.detail .body"), "e=>e.length") == 1,
          "たたんでいた飛び先は開かれる")

    # --- #issue= と「戻る」 ---
    check(pg.evaluate("()=>location.hash").startswith("#issue="), "hash が付いている")
    pg.go_back(); pg.wait_for_timeout(400)
    check(pg.evaluate("()=>location.hash") == "#issue=%E8%B2%A9%E5%A3%B2%E7%AE%A1%E7%90%86%E7%A7%BB%E8%A1%8C/2",
          f"「戻る」で直前の飛び先へ戻る -> {pg.evaluate('()=>location.hash')!r}")
    check(onTab() == ["販売管理移行"], f"戻ると案件タブも元へ -> {onTab()}")
    check(not errors, f"戻るで JS エラーが出ない -> {errors}")
    # 未読込で #issue= を開くと案内バー
    pg.evaluate(J("()=>{location.hash='#issue=%E5%8B%A4%E6%80%A0%E3%82%B7%E3%82%B9%E3%83%86%E3%83%A0/1';}"))
    pg.wait_for_timeout(300)
    check(pg.eval_on_selector_all(S("#tbody tr.jump"), "e=>e.length") == 1, "hashchange で同じ処理が走る")
    pg.goto("about:blank")   # 同じURLへの goto はドキュメントを読み直さないので、いったん離れてから開く
    pg.goto(VIEWER + "#issue=%E5%8B%A4%E6%80%A0%E3%82%B7%E3%82%B9%E3%83%86%E3%83%A0/1"); pg.wait_for_timeout(300)
    check("JSON を開いて" in pg.inner_text(S("#notice")), f"未読込なら案内バー -> {pg.inner_text(S('#notice'))!r}")
    pg.evaluate("d=>window.renderData(d)", D); pg.wait_for_timeout(400)
    check(pg.eval_on_selector_all(S("#tbody tr.jump"), "e=>e.map(x=>x.getAttribute('data-key'))") == ["勤怠システム|1"],
          "読み込むと #issue= の行へ飛ぶ（URL を貼って渡せる）")

    # --- 壊れたリンク（薄い取り消し線＋ツールチップ）・XSS ---
    pg.goto(VIEWER); pg.wait_for_timeout(150)
    pg.evaluate("()=>{window.__xss=false;const o=window.alert;window.alert=()=>{window.__xss=true;};}")
    pg.evaluate("d=>window.renderData(d)", BAD); pg.wait_for_timeout(250)
    x = pg.eval_on_selector_all(S("#tbody .lk-x"), "e=>e.map(x=>[x.innerText, x.getAttribute('title'), getComputedStyle(x).textDecorationLine, x.tagName])")
    check([e[0] for e in x] == ["WBS 9.9", "課題 #99", "無い-1", "危険", '">-1'],
          f"壊れたリンク5件（WBS/課題/案件/非http(s)URL/別案件名） -> {[e[0] for e in x]}")
    check(all(e[1] == "リンク先が見つかりません" and "line-through" in e[2] and e[3] == "SPAN" for e in x),
          f"取り消し線＋ツールチップ・<a>にはしない -> {x[:1]}")
    ok = pg.eval_on_selector_all(S("#tbody .lk .lk-i:not(.lk-x)"), "e=>e.map(x=>[x.tagName, x.innerText, x.getAttribute('href')])")
    check(ok == [["A", '"><img src=x onerror=alert(1)>', "https://example.com/a?x=1&y=2"]],
          f"http(s) の1件だけ生きる（title は esc 済み） -> {ok}")
    check(pg.eval_on_selector_all(S("#tbody img,#tbody script"), "e=>e.length") == 0, "属性/タグの注入が生DOMにならない")
    check(pg.evaluate(J("()=>[...document.querySelectorAll('#tbody .lk *')].some(e=>e.getAttributeNames().some(n=>n.startsWith('on')))")) is False,
          "on* イベント属性が注入されていない")
    check(not pg.evaluate("()=>window.__xss"), "alert が実行されない")
    # links が非配列／要素が壊れている課題は、行そのものを出さない
    rows = pg.eval_on_selector_all(S("#tbody tr"), "e=>e.map(x=>[x.querySelector('td.num').innerText, !!x.querySelector('.lk')])")
    check([r[0] for r in rows if not r[1]] == ["5", "6"],
          f"links 非配列（#5）と壊れ要素だけ（#6）はリンク行を出さない -> {rows}")
    b.close()
finish(errors)
