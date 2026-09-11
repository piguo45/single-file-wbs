"""描画: 列構成・詳細ブロックの構造（概要/実績/予定の帯・備考は印だけ＝詳細は test_note.py）・(調整中)・M/D表示とISOツールチップ。
   ★の意味（報告期間に動いたもの）は test_star.py が受け持つ。"""
from playwright.sync_api import sync_playwright
from common import S, TITLE_SUFFIX, UNIFIED, VIEWER, check, finish, load_test_json, new_page

errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_page(b, viewport={"width": 1500, "height": 900})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(VIEWER)
    pg.evaluate("d=>window.renderData(d)", load_test_json("正常_全機能.json"))
    pg.wait_for_timeout(200)

    heads = pg.eval_on_selector_all(S("#tbl thead th"), "e=>e.map(x=>x.innerText.trim())")
    check(heads == ["No.", "優先度", "▼タイトル", "詳細", "状態", "期限"],
          f"列は No/優先度/タイトル/詳細/状態/期限 の6列（この順） -> {heads}")
    check("担当" not in "".join(heads), "見出しに「担当」は無い（担当は行動の行にだけ出る）")
    check(pg.eval_on_selector_all(S("#tbl thead th"), "e=>e.map(x=>x.className)")
          == ["num", "prio", "title", "detail", "state", "due"], "列の並び（class）も No→優先度→タイトル→詳細→状態→期限")
    check(pg.eval_on_selector(S("#allCaret"), "e=>e.closest('th').className") == "title",
          "全展開/全たたみの ▼/▶ はタイトル列の見出しにある")
    check(pg.eval_on_selector_all(S("#tbody tr"), "e=>e.length") == 8, "8件が描画される")

    r1 = S("#tbody tr:nth-child(1) ") + " "
    secs = pg.eval_on_selector_all(r1 + ".sec", "e=>e.map(x=>x.innerText)")
    check(secs == ["概要", "方針（未決）", "実績", "予定"],
          f"概要/方針（未決）/実績/予定の見出し（■は付けない） -> {secs}")
    # 区切り見出し＝薄い灰の小さな帯（線は引かない・文字幅に合わせて行頭に単独で並ぶ）
    sty = pg.eval_on_selector(r1 + ".sec", """e=>{const c=getComputedStyle(e);
        return {d:c.display, bg:c.backgroundColor, r:c.borderTopLeftRadius, fs:c.fontSize, bw:c.borderTopWidth};}""")
    check(sty == {"d": "inline-block", "bg": "rgb(221, 226, 234)", "r": "9px", "fs": "11px", "bw": "0px"},
          f"帯の見た目（薄い灰の塗り・角丸9px・11px・線なし） -> {sty}")
    check(pg.eval_on_selector(r1 + ".sec", "e=>getComputedStyle(e).color") == "rgb(43, 49, 64)", "帯の文字は濃い灰")
    box = pg.eval_on_selector(r1 + ".sec",
        "e=>{const r=e.getBoundingClientRect(),p=e.parentElement.getBoundingClientRect();return [r.width<p.width*0.5, r.width>25];}")
    check(box == [True, True], f"帯は文字幅ぶんだけ（セル幅いっぱいに伸びない） -> {box}")
    check(pg.eval_on_selector(r1 + ".body>.sec:first-child", "e=>getComputedStyle(e).marginTop") == "0px",
          "最初の帯（概要）は詳細セルの上端に揃える")
    tcell = pg.inner_text(r1 + "td.title")
    check("▼" in tcell and "移行テストで文字コード" in tcell, f"タイトル列＝caret＋タイトル -> {tcell!r}")
    check(pg.eval_on_selector(r1 + "td.title b", "e=>getComputedStyle(e).fontWeight") in ("700", "bold"),
          "タイトルは太字")
    check(pg.eval_on_selector_all(r1 + "td.detail .tcell,#tbody .ttl", "e=>e.length") == 0,
          "詳細列にタイトル行は無い（タイトルは専用列へ移動）")
    check(pg.eval_on_selector(r1 + "td.detail", "e=>e.innerText.trim().startsWith('概要')"),
          "詳細列は「概要」の帯から始まる")
    lbs = pg.eval_on_selector_all(r1 + ".ln .lb", "e=>e.map(x=>x.innerText)")
    check(lbs == ["支障：", "完了条件：", "方針："],
          f"空の「価値：」は行ごと省略・備考は本文を出さない -> {lbs}")
    # 見出しは短い語に。問いと従来語の橋はツールチップに残す
    tips = pg.eval_on_selector_all(r1 + ".ln .lb", "e=>e.map(x=>x.getAttribute('title'))")
    check(tips[0] is not None and "放置すると、いつ・何が起きるか" in tips[0]
          and "例：" in tips[0] and "影響" in tips[0],
          f"「支障」のツールチップに 問い＋例＋従来語（影響） -> {tips[0]!r}")
    check(tips[1] is None and tips[2] is None, f"Tip の無い見出しには title を付けない -> {tips}")

    # 行動は6件（実績2＋予定4）。★の意味は「報告期間(9/1〜9/7)に動いた」＝実績2件とも該当
    stars = pg.eval_on_selector_all(r1 + ".act", "e=>e.map(x=>[x.querySelector('.star').innerText, x.querySelector('.at').innerText])")
    check(len(stars) == 6, f"行動6件（実績2＋予定4） -> {len(stars)}")
    check([t for s, t in stars if s == "★"] == ["事象発生", "調査方針検討、影響調査"],
          f"★は報告期間内に済んだ行動 -> {[t for s, t in stars if s == '★']}")

    tbd = pg.eval_on_selector_all(r1 + ".act .ad.tbd", "e=>e.map(x=>x.innerText)")
    check(tbd == ["(調整中)", "(調整中)"], f"date:null は (調整中) -> {tbd}")
    check(pg.eval_on_selector_all(r1 + ".act .aw", "e=>e.length") == 0,
          "actions[].wbs は v0.2 で廃止＝行動行に WBS の小タグは出ない")

    # 日付は M/D 表示・ツールチップは ISO
    d0 = pg.eval_on_selector(r1 + ".act .ad", "e=>[e.innerText, e.getAttribute('title')]")
    check(d0 == ["9/5", "2026-09-05"], f"行動日は M/D 表示・title は ISO -> {d0}")
    due = pg.eval_on_selector(r1 + "td.due span", "e=>[e.innerText, e.getAttribute('title')]")
    check(due == ["9/10", "2026-09-10"], f"期限も M/D 表示・title は ISO -> {due}")
    check(pg.inner_text(S("#tbody tr:nth-child(3) td.due")).strip() == "—", "期限 null は —")

    # 備考は添え書き＝本文を常時出さず、小さな印だけ（中身は test_note.py）
    check(pg.eval_on_selector_all(r1 + ".lk [data-note]", "e=>e.length") == 1,
          "備考はタイトル下のリンク行に並ぶ（詳細の末尾には出さない）")
    check("関連リンクは note に素のURLで" not in pg.inner_text(S("#tbody")), "備考の本文は詳細に出さない")
    check(pg.eval_on_selector_all(S("#tbody a"), "e=>e.length") == 0, "備考を出さないので表の中にリンクは無い")

    # 担当は行動の行の右端に「担当：○○」。担当が空の行はラベルごと出さない
    aa = pg.eval_on_selector_all(r1 + ".act .aa", "e=>e.map(x=>x.innerText)")
    check(aa == ["担当：ぴぐお", "担当：ぴぐお/Aさん", "担当：ぴぐお", "担当：ぴぐお"],
          f"担当ラベル付き・空の行は出さない（6行動中4行） -> {aa}")
    lb = pg.eval_on_selector(r1 + ".act .aa .lb", "e=>[e.innerText, getComputedStyle(e).color]")
    check(lb[0] == "担当：" and lb[1] == "rgb(107, 114, 128)", f"「担当：」は薄い灰色 -> {lb}")
    check(pg.eval_on_selector(r1 + ".act .aa", "e=>getComputedStyle(e).color") == "rgb(31, 36, 48)",
          "名前は通常色")

    # 詳細の中は「役割ごとに表現を1種類」：★＝黒の記号／済・未＝文字の濃淡（塗り・枠は使わない）
    stars = pg.eval_on_selector_all(S("#tbody .star"),
        "e=>[...new Set(e.filter(x=>x.innerText==='★').map(x=>getComputedStyle(x).color))]")
    check(stars == ["rgb(31, 36, 48)"], f"★はどこでも黒（1か所の --star で持つ） -> {stars}")
    dns = pg.eval_on_selector_all(r1 + ".act .dn",
        "e=>e.map(x=>[x.innerText, getComputedStyle(x).color, getComputedStyle(x).fontWeight, getComputedStyle(x).borderTopWidth, getComputedStyle(x).backgroundColor, getComputedStyle(x).textDecorationLine])")
    check([d[:3] for d in dns if d[0] == "済"] == [["済", "rgb(75, 85, 99)", "600"]] * 2,
          f"済＝濃い＋太字 -> {[d[:3] for d in dns if d[0] == '済']}")
    check([d[:3] for d in dns if d[0] == "未"] == [["未", "rgb(138, 143, 152)", "400"]] * 4,
          f"未＝薄い（通常の太さ） -> {[d[:3] for d in dns if d[0] == '未']}")
    check(all(d[3] == "0px" and d[4] == "rgba(0, 0, 0, 0)" and d[5] == "none" for d in dns),
          f"済/未 は塗り・枠・取り消し線を使わない -> {dns[:1]}")

    # 完了行（背景灰）でも「未」が溶けない＝一段濃くする
    pg.evaluate("""()=>window.renderData({name:"完了行の未",projects:[{name:"P",issues:[
      {id:1,title:"完了だが未が残る",ifIgnored:"x",closeWhen:"y",
       decisions:[{q:"やるか",since:"2026-08-01",decided:"2026-08-01",a:"やる"}],
       closed:{at:"2026-08-20",how:"resolved",note:"確認"},
       actions:[{date:"2026-08-02",text:"済",assignee:"",done:true},
                {date:"2026-09-30",text:"未",assignee:"",done:false}]}]}]})""")
    pg.wait_for_timeout(200)
    cl = pg.eval_on_selector(S("#tbody tr.st-closed .act .dn.dn-t"),
        "e=>[getComputedStyle(e).color, getComputedStyle(e.closest('tr')).backgroundColor]")
    check(cl == ["rgb(124, 133, 145)", "rgb(236, 239, 242)"],
          f"完了行の「未」は一段濃く（灰背景に溶けない） -> {cl}")
    pg.evaluate("d=>window.renderData(d)", load_test_json("正常_全機能.json")); pg.wait_for_timeout(200)

    # 完了行＝グレー＋タイトル取り消し線
    closed = pg.eval_on_selector_all(S("#tbody tr.st-closed"), "e=>e.length")
    check(closed == 3, f"完了行に st-closed が付く -> {closed}")
    deco = pg.eval_on_selector(S("#tbody tr.st-closed td.title b"), "e=>getComputedStyle(e).textDecorationLine")
    check("line-through" in deco, f"完了行のタイトルは取り消し線 -> {deco}")
    bg = pg.eval_on_selector(S("#tbody tr.st-closed td.num"), "e=>getComputedStyle(e.parentElement).backgroundColor")
    check(bg not in ("rgba(0, 0, 0, 0)", "rgb(255, 255, 255)"), f"完了行はグレー背景 -> {bg}")

    # 優先度は色＋ラベル（CUD：色だけに頼らない）
    prios = pg.eval_on_selector_all(S("#tbody td.prio .bdg"), "e=>e.map(x=>[x.className, x.innerText])")
    check(prios[0] == ["bdg p-high", "高"] and prios[1] == ["bdg p-mid", "中"] and prios[2] == ["bdg p-low", "低"],
          f"優先度はラベル併記 -> {prios[:3]}")
    # 簡素表示トグル（タイトルクリックでロゴ/版/"Viewer"を隠す・localStorage記憶）
    # ブラウザのタブ名＝「ブック名 – (WBS|Issue) Viewer」／簡素モードはブック名だけ
    check(pg.title() == "○○移行プロジェクト" + TITLE_SUFFIX, f"document.title -> {pg.title()!r}")
    if UNIFIED:   # 簡素表示は wbs 側の機能（tests/e2e/test_plain.py が受け持つ）
        b.close()
        finish(errors)
    pg.click(S("#brandTitle")); pg.wait_for_timeout(120)
    check(pg.evaluate("()=>document.body.classList.contains('plain')")
          and pg.title() == "○○移行プロジェクト", f"簡素表示ON（タイトルはブック名だけ） -> {pg.title()!r}")
    check(not pg.is_visible(S("#brandTitle .logo")), "簡素表示でロゴが隠れる")
    pg.click(S("#brandTitle")); pg.wait_for_timeout(120)
    check(pg.title() == "○○移行プロジェクト" + TITLE_SUFFIX and pg.is_visible(S("#brandTitle .logo")),
          "もう一度クリックで戻る")

    b.close()
finish(errors)
