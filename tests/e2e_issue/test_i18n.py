"""言語切替: 既定ja・ENトグルで全UI英語化・localStorage記憶・ja復帰（データは翻訳しない）"""
from playwright.sync_api import sync_playwright
from common import S, VIEWER, check, finish, load_test_json, new_page, reload

DATA = load_test_json("正常_全機能.json")

errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1500, "height": 900})
    pg = new_page(ctx)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(VIEWER)
    check(pg.inner_text(S("#openBtn")).startswith("ファイルを開く") and "ドラッグ" in pg.inner_text(S("#openBtn")), "既定は日本語")
    pg.evaluate("d=>window.renderData(d)", DATA); pg.wait_for_timeout(200)

    pg.click(S("#langBtn")); pg.wait_for_timeout(250)
    check(pg.inner_text(S("#openBtn")).startswith("Open file") and "drag" in pg.inner_text(S("#openBtn")), "EN: ボタン英語化")
    heads = pg.eval_on_selector_all(S("#tbl thead th"), "e=>e.map(x=>x.innerText.trim())")
    check(heads == ["No.", "Priority", "▼Title", "Detail", "State", "Due"], f"EN: 列見出し（6列） -> {heads}")
    st = pg.eval_on_selector_all(S("#tbody td.state"), "e=>e.map(x=>x.innerText.replace('\\n','/'))")
    check([x.split("/")[0] for x in st[:3]] == ["In progress"] * 3
          and "Undecided 1" in st[0] and "Waiting 企画部" in st[2] and "Waiting 14d" in st[2],
          f"EN: 状態バッジと印（待ち／未決／経過日数）も英語化される -> {st[:3]}")
    check(pg.eval_on_selector_all(S("#tbody td.prio"), "e=>e.map(x=>x.innerText)")[0] == "High", "EN: 優先度")
    # 区切りの帯だけを数える（備考の印は同じ .sec の形を使い回しているので除く）
    secs = pg.eval_on_selector_all(S("#tbody tr:nth-child(1) .sec"), "e=>e.map(x=>x.innerText)")
    check(secs == ["Summary", "Policy (open)", "Done", "Planned"],
          f"EN: 概要/方針（未決）/実績/予定の帯（[ ]は付けない） -> {secs}")
    od = pg.eval_on_selector_all(S("#tbody .odec .dcmeta"), "e=>e.map(x=>x.textContent)")
    check(od and all(" days open (since " in x for x in od),
          f"EN: 経過は「N days open (since M/D)」 -> {od[:2]}")
    lbs = pg.eval_on_selector_all(S("#tbody tr:nth-child(1) .ln .lb"),
        "e=>e.map(x=>[x.innerText, x.getAttribute('title')])")
    check(lbs[0][0] == "Harm: " and "Impact" in (lbs[0][1] or ""),
          f"EN: 支障→Harm:（ツールチップに従来語 Impact） -> {lbs[0]}")
    check(pg.eval_on_selector(S("#tbody tr:nth-child(1) .lk [data-note]"),
                              "e=>[e.textContent.trim(), e.getAttribute('title')]")
          == ["Notes", "Notes (click to open)"], "EN: 備考の印と案内も英語化される")
    aa = pg.eval_on_selector_all(S("#tbody tr:nth-child(1) .act .aa"), "e=>e.map(x=>x.innerText)")
    check(aa[:2] == ["Owner: ぴぐお", "Owner: ぴぐお/Aさん"], f"EN: 担当：→ Owner:（名前は翻訳しない） -> {aa[:2]}")
    check("(TBD)" in pg.inner_text(S("#tbody tr:nth-child(1)")), "EN: (調整中) → (TBD)")
    # 済/未マーカーは en だと done/todo と長い。固定幅で折り返さないこと（同じ行の日付 .ad と同じ高さ＝1行）
    dn = pg.eval_on_selector_all(S("#tbody tr:nth-child(1) .act"),
        "e=>e.map(x=>[x.querySelector('.dn').innerText, x.querySelector('.dn').offsetHeight, x.querySelector('.ad').offsetHeight])")
    check(all(t in ("☑", "☐") for t, _, _ in dn), f"EN: 済/未 → ☑/☐ -> {[t for t,_,_ in dn]}")
    check(all(h == a for _, h, a in dn), f"EN: .dn が折り返さない（日付 .ad と同じ1行の高さ） -> {dn}")
    # 濃淡の規則は ja/en 共通（☑ 濃い・☐ 薄い）。行の高さは ja と同じ 19.2px のまま
    tone = pg.eval_on_selector_all(S("#tbody tr:nth-child(1) .act .dn"),
        "e=>e.map(x=>[x.innerText, getComputedStyle(x).color, getComputedStyle(x).fontSize])")
    check([x[1] for x in tone if x[0] == "☑"][0] == "rgb(75, 85, 99)"
          and [x[1] for x in tone if x[0] == "☐"][0] == "rgb(138, 143, 152)",
          f"EN: ☑ は濃く・☐ は薄く -> {tone[:3]}")
    check(all(x[2] == "13px" for x in tone), f"EN: ☑☐ は 13px -> {tone[:1]}")
    h = pg.eval_on_selector_all(S("#tbody tr:nth-child(1) .act"), "e=>[...new Set(e.map(x=>Math.round(x.getBoundingClientRect().height*10)/10))]")
    check(h == [19.2], f"EN: 行の高さは ja と同じ -> {h}")
    cn = pg.inner_text(S("#counts"))
    check("Undecided" in cn and "Overdue" in cn, f"EN: 件数サマリ -> {cn!r}")
    # 印の名前は ピル・状態列・件数 で同じ語を使う（Waiting/Frozen/Undecided/Overdue/Nudge/★ Updated）
    pills = pg.eval_on_selector_all(S("#filterBar .sf-btn[data-mark]"), "e=>e.map(x=>x.innerText)")
    check(pills == ["Waiting", "Frozen", "Undecided", "Overdue", "Nudge", "★ Updated"],
          f"EN: 印のピル（「only」は付けない） -> {pills}")
    for w in ("Waiting", "Undecided"):
        check(w in pg.inner_text(S("#tbody")), f"EN: 状態列の印も同じ語（{w}）")
    check(pg.inner_text(S("#starRange")) == "Update period: 9/1–9/7",
          f"EN: 更新期間は M/D と – 区切り -> {pg.inner_text(S('#starRange'))!r}")
    check("★ Updated" in pg.inner_text(S("#counts")), f"EN: 件数は ★ Updated -> {pg.inner_text(S('#counts'))!r}")
    pg.evaluate("d=>{const x={...d};delete x.star;window.renderData(x);}", DATA); pg.wait_for_timeout(150)
    check(pg.inner_text(S("#starRange")) == "Update period: last 7 days",
          f"EN: 既定は Update period: last 7 days -> {pg.inner_text(S('#starRange'))!r}")
    pg.evaluate("d=>window.renderData(d)", DATA); pg.wait_for_timeout(150)
    pg.click(S("#allCaret")); pg.wait_for_timeout(200)   # たたんだ時の次の一手1行も英語化される
    nx = pg.eval_on_selector_all(S("#tbody td.detail"), "e=>e.map(x=>x.innerText.replace(/\\n/g,' '))")
    check(nx[0] == "☐ 9/11 資料作成、内部Rv Owner: ぴぐお/Aさん",
          f"EN: たたんだ詳細＝次の一手1行（todo/Owner:） -> {nx[0]!r}")
    pg.click(S("#allCaret")); pg.wait_for_timeout(200)
    check("Filter" in pg.inner_text(S("#filterBar")) and "Sort" in pg.inner_text(S("#filterBar")), "EN: フィルタバー")
    check(pg.get_attribute("html", "lang") == "en", "html lang=en")
    # データ（課題本文）は翻訳しない
    check("移行テストで文字コード" in pg.inner_text(S("#tbody tr:nth-child(1)")), "データは翻訳しない")

    # リロード後は「言語が戻ったこと」を条件で待つ（固定待ちだと負荷時に取りこぼす）
    reload(pg)
    try:
        pg.wait_for_function("()=>document.documentElement.lang==='en'", timeout=5000)
    except Exception:
        pass
    check(pg.inner_text(S("#openBtn")).startswith("Open file"),
          f"リロード後もENを記憶 -> {pg.inner_text(S('#openBtn'))!r} lang={pg.get_attribute('html','lang')}")
    pg.click(S("#langBtn"))
    try:
        pg.wait_for_function("()=>document.documentElement.lang==='ja'", timeout=5000)
    except Exception:
        pass
    check(pg.inner_text(S("#openBtn")).startswith("ファイルを開く"),
          f"日本語へ復帰 -> {pg.inner_text(S('#openBtn'))!r} lang={pg.get_attribute('html','lang')}")
    b.close()
finish(errors)
