"""折りたたみ: タイトル行クリックで1行⇄全文・ヘッダ▼/▶で全展開/全たたみ・localStorage記憶（キー＝id）"""
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
    pg.evaluate("d=>window.renderData(d)", DATA); pg.wait_for_timeout(200)

    # たたむ＝詳細列が本文(.body)から「次の一手1行」に変わる（タイトル列の caret は ▶ に）
    ncol = lambda: pg.eval_on_selector_all(S("#tbody td.title .caret"), "e=>e.filter(x=>x.innerText==='▶').length")
    body1 = lambda: pg.eval_on_selector_all(S("#tbody tr:nth-child(1) td.detail .body"), "e=>e.length") == 1
    dtl = lambda n: pg.eval_on_selector(S(f"#tbody tr:nth-child({n}) td.detail"), "e=>e.innerText.replace(/\\n/g,' ')").strip()

    check(ncol() == 0 and body1(), "既定は全文表示")
    check(pg.inner_text(S("#allCaret")) == "▼", "全部開いている時はヘッダ▼")

    pg.click(S("#tbody tr:nth-child(1) td.title .caret")); pg.wait_for_timeout(120)
    check(ncol() == 1 and not body1(), "タイトルセルのクリックで畳む")
    check(pg.inner_text(S("#tbody tr:nth-child(1) td.title")).strip().startswith("▶"), "畳んだら caret は ▶")
    # 1行表示でも No/優先度/状態/期限は見える。担当は末尾の「次：○○」に集約
    row = pg.inner_text(S("#tbody tr:nth-child(1)"))
    check("高" in row and "対応中" in row and "9/10" in row, f"畳んでも他列は見える -> {row!r}")
    check(dtl(1) == "未 9/11 資料作成、内部Rv 担当：ぴぐお/Aさん",
          f"たたんだ詳細＝次の一手（未の最初）を1行 -> {dtl(1)!r}")
    check(pg.eval_on_selector_all(S("#tbody tr:nth-child(1) td.title b"), "e=>e.length") == 1,
          "畳んでもタイトルはタイトル列に残る")

    pg.click(S("#tbody tr:nth-child(1) td.title .caret")); pg.wait_for_timeout(120)
    check(ncol() == 0 and body1(), "もう一度クリックで全文に戻る")
    check(dtl(1).startswith("概要"), f"開いたら詳細は本文（概要の帯から） -> {dtl(1)[:20]!r}")

    pg.click(S("#allCaret")); pg.wait_for_timeout(150)
    check(ncol() == 8, f"▼で全たたみ -> {ncol()}")
    check(pg.inner_text(S("#allCaret")) == "▶", "全たたみ後はヘッダ▶")
    # 全たたみ状態の詳細＝次の一手1行。未の行動が無い/完了した課題は空
    tags = pg.eval_on_selector_all(S("#tbody tr"),
        "e=>e.map(x=>[x.querySelector('td.num').innerText, x.querySelector('td.detail').innerText.replace(/\\n/g,' ').trim()])")
    check([t for _, t in tags] == ["未 9/11 資料作成、内部Rv 担当：ぴぐお/Aさん",
                                   "未 (調整中) チューニング方針を決める 担当：Aさん",
                                   "",
                                   "未 (調整中) 受領後に検証を再開 担当：ぴぐお",
                                   "", "", "", ""],
          f"次の一手1行（date null は (調整中)・未の行動が無い #3/#5 は空） -> {tags}")
    closed_tags = [t for i, t in tags if i in ("6", "7", "8")]
    check(closed_tags == ["", "", ""],
          f"完了（#6解決/#7不対応/#8発生せず）の詳細は空 -> {closed_tags}")
    check(pg.eval_on_selector_all(S("#tbody tr.st-closed td.detail *"), "e=>e.length") == 0,
          "完了行の詳細セルには要素が1つも無い")

    pg.click(S("#allCaret")); pg.wait_for_timeout(150)
    check(ncol() == 0, "▶で全展開")
    check(pg.eval_on_selector_all(S("#tbody td.detail .body"), "e=>e.length") == 8, "全展開すると全部が本文表示に戻る")

    # localStorage 記憶（キー＝id）：#2 だけ畳んでリロード
    pg.click(S("#tbody tr:nth-child(2) td.title .caret")); pg.wait_for_timeout(120)
    saved = pg.evaluate("()=>localStorage.getItem('issCollapsed')")
    check(saved and '"○○移行プロジェクト|2"' in saved,
          f"折りたたみ状態は 案件名|id で localStorage に記憶（案件ごとに独立） -> {saved}")
    reload(pg); pg.wait_for_timeout(150)
    pg.evaluate("d=>window.renderData(d)", DATA); pg.wait_for_timeout(200)
    cols = pg.eval_on_selector_all(S("#tbody tr"),
        "e=>e.filter(x=>!x.querySelector('td.detail .body')).map(x=>x.getAttribute('data-key'))")
    check(cols == ["○○移行プロジェクト|2"], f"リロード後も #2 だけ畳まれている -> {cols}")
    b.close()
finish(errors)
