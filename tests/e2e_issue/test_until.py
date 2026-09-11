"""未決の「いつまでに」（decisions[].until）：表示・催促の印・件数への合流・編集。
   本日=CLOCK_PIN(2026-09-15)。単体版・統合版の両方で回る。"""
import json
from playwright.sync_api import sync_playwright
from common import (J, S, VIEWER, action, book, check, decision, finish,
                    granted_handle_init, issue, new_page, waiting)

D = book([
    issue(1, "期限切れの未決", decisions=[decision("どの方式にするか", "2026-09-02", until="2026-09-05"),
                                          decision("誰に確認するか", "2026-09-03", until="2026-09-30")]),
    issue(2, "期限なしの未決", decisions=[decision("あとで決める", "2026-09-03")]),
    issue(3, "決まった方針は催促しない",
          decisions=[decision("決めた", "2026-09-01", "2026-09-02", "やる", until="2026-09-01")],
          actions=[action("2026-09-02", "着手", "", True)]),
    issue(4, "待ちの期限切れ", pending=waiting("開発部", "回答", "2026-09-01", "2026-09-02")),
])

with sync_playwright() as pw:
    b = pw.chromium.launch()
    errors = []
    pg = new_page(b, viewport={"width": 1500, "height": 1000})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script(granted_handle_init(D))
    pg.goto(VIEWER)
    saved = lambda: json.loads(pg.evaluate("()=>window.__file"))["projects"][0]["issues"]
    odec = lambda n: pg.eval_on_selector_all(S(f"#tbody tr:nth-child({n}) .odec"), "e=>e.map(x=>x.innerText)")
    mks = lambda n: pg.eval_on_selector_all(S(f"#tbody tr:nth-child({n}) td.state .mk"),
                                            "e=>e.map(x=>x.className.replace('mk ',''))")
    pg.click(S("#openBtn")); pg.wait_for_timeout(350)

    # ===== 表示：（〜M/D）と ⚠ 催促 =====
    o1 = odec(1)
    check("（〜9/5）" in o1[0] and "⚠ 催促" in o1[0], f"期限切れの未決は（〜M/D）＋⚠ 催促 -> {o1[0]!r}")
    check("（〜9/30）" in o1[1] and "催促" not in o1[1], f"期限内は（〜M/D）だけ -> {o1[1]!r}")
    check("（〜" not in odec(2)[0] and "催促" not in odec(2)[0],
          f"until が無ければ何も足さない -> {odec(2)[0]!r}")
    check(pg.eval_on_selector(S("#tbody tr:nth-child(1) .odec .mk-nudge"), "e=>e.title")
          == "決める期限を過ぎています。決めてください", "未決の催促は理由の分かるツールチップ")

    # ===== 状態列：「未決 N」の下に ⚠ 催促 =====
    check([m.split()[0] for m in mks(1)] == ["mk-open", "mk-nudge", "mk-days"],
          f"状態列は 未決N → ⚠催促 → 経過日数 の順 -> {mks(1)}")
    check("mk-nudge" not in mks(2), f"期限なしの未決では催促しない -> {mks(2)}")
    check("mk-nudge" not in mks(3), f"決まった方針は until を過ぎていても催促しない -> {mks(3)}")

    # ===== 件数・タブ・絞り込みは待ちと未決の両方を数える（課題数） =====
    cnt = pg.inner_text(S("#counts")).replace("\n", " ")
    check("⚠ 催促 2" in cnt, f"催促は待ち(#4)と未決(#1)の合計＝課題数 -> {cnt!r}")
    # サマリの「催促」列も同じ数え方（待ち＋未決・課題数）
    pg.click(S("#tabBar .stab[data-summary]")); pg.wait_for_timeout(250)
    head = pg.eval_on_selector_all(S("#tbl thead th"), "e=>e.map(x=>x.innerText.trim())")
    row = pg.eval_on_selector_all(S("#tbody tr.sumtot td"), "e=>e.map(x=>x.innerText.trim())")
    check(row[head.index("催促")] == "2", f"サマリの催促も待ち＋未決 -> {dict(zip(head, row))}")
    pg.click(S("#tabBar .stab[data-si='0']")); pg.wait_for_timeout(250)
    pg.click(S('.sf-btn[data-mark="nudge"]')); pg.wait_for_timeout(200)
    ids = pg.eval_on_selector_all(S("#tbody td.num"), "e=>e.map(x=>x.innerText)")
    check(ids == ["1", "4"], f"「催促のみ」は待ちと未決の両方を拾う -> {ids}")
    pg.click(S('.sf-btn[data-mark="nudge"]')); pg.wait_for_timeout(200)

    # ===== 編集：本文欄の右に期限の日付欄（placeholder で示す・短縮入力・📅） =====
    pg.click(S("#editBtn")); pg.wait_for_timeout(400)
    check(pg.eval_on_selector_all(S("#tbody tr:nth-child(2) .odec .dcuntil"), "e=>e.length") == 1,
          "未決の行に「いつまでに」の欄がある")
    check(pg.eval_on_selector_all(S("#tbody tr:nth-child(2) .odec .dcuntil .lb"), "e=>e.length") == 0,
          "「いつまでに」のラベルは出さない（placeholder で示す）")
    check(pg.eval_on_selector(S('#tbody tr:nth-child(2) .odec input[data-field="until"]'),
                              "e=>e.placeholder") == "期限 MM-DD", "placeholder は「期限 MM-DD」")
    check(pg.eval_on_selector_all(S("#tbody tr:nth-child(2) .odec .dcuntil .cal-btn"), "e=>e.length") == 1,
          "📅 も付く（他の日付欄と同じ作法）")
    # 並びは 確定 → 本文 → 期限欄 → 経過 → ✕
    order = pg.eval_on_selector(S("#tbody tr:nth-child(1) .odec.edit"),
        "e=>[...e.children].map(x=>x.className.split(' ')[0])")
    check(order[:3] == ["dcok", "dcq", "dcuntil"] and order[-1] == "decdel",
          f"1行の並び -> {order}")
    check(pg.eval_on_selector(S("#tbody tr:nth-child(1) .odec.edit .dcmeta"), "e=>e.textContent")
          == "13日経過（9/2〜）", "経過は「N日経過（M/D〜）」の1組")
    check(pg.eval_on_selector(S("#tbody tr:nth-child(1) .odec.edit .dcmeta"),
                              "e=>getComputedStyle(e).color") == "rgb(107, 114, 128)", "その1組は薄い字")
    w = pg.eval_on_selector(S('#tbody tr:nth-child(1) .odec input[data-field="until"]'),
                            "e=>Math.round(e.getBoundingClientRect().width)")
    # placeholder が切れないこと＝欄幅 ≧ 文字の実測幅（ja の「期限 MM-DD」が最長）
    need = pg.eval_on_selector(S('#tbody tr:nth-child(1) .odec .dcuntil input[data-field="until"]'), """i=>{
        const cs=getComputedStyle(i), p=document.createElement('span');
        p.style.cssText='position:absolute;visibility:hidden;white-space:pre;font:'+cs.font;
        p.textContent=i.placeholder; document.body.appendChild(p);
        const w=Math.ceil(p.getBoundingClientRect().width)
          +parseFloat(cs.paddingLeft)+parseFloat(cs.paddingRight)
          +parseFloat(cs.borderLeftWidth)+parseFloat(cs.borderRightWidth);
        p.remove(); return Math.ceil(w);}""")
    check(w >= need, f"期限欄は placeholder が切れない幅 -> 欄 {w}px / 必要 {need}px")
    check(78 <= w <= 90, f"期限欄は 82px 程度（ja/en 共通） -> {w}px")
    same = pg.eval_on_selector(S("#tbody tr:nth-child(1) .odec.edit"), J("""e=>{
        const r=x=>x.getBoundingClientRect(), cy=x=>r(x).top+r(x).height/2;
        return Math.round(Math.abs(cy(e.querySelector('.dcok'))-cy(e.querySelector('.dcq'))));}"""))
    check(same <= 2, f"「確定」と本文欄が同じ行（y中心 ±2px） -> {same}px")
    fld = S('#tbody tr:nth-child(2) .odec input[data-dec="0"][data-field="until"]')
    pg.fill(fld, "09-20"); pg.dispatch_event(fld, "change"); pg.wait_for_timeout(700)
    check(saved()[1]["decisions"][0].get("until") == "2026-09-20",
          f"短縮入力(MM-DD)が ISO で保存される -> {saved()[1]['decisions'][0]}")
    pg.fill(fld, ""); pg.dispatch_event(fld, "change"); pg.wait_for_timeout(700)
    check(saved()[1]["decisions"][0]["until"] is None, "空にすると期限なし（null）")
    pg.fill(fld, "13-99"); pg.dispatch_event(fld, "change"); pg.wait_for_timeout(700)
    check(saved()[1]["decisions"][0]["until"] is None, "解釈できない日付は無視（ゴミを保存しない）")

    # ===== 決まったら表示から消える（データは残す） =====
    pg.click(S("#tbody tr:nth-child(1) [data-decide]")); pg.wait_for_timeout(300)
    pg.fill("#isForm input[data-fm='a']", "A方式にする")
    pg.click("#isForm .fm-ok"); pg.wait_for_timeout(700)
    check(saved()[0]["decisions"][0].get("until") == "2026-09-05",
          f"決めても until はデータに残る -> {saved()[0]['decisions'][0]}")
    check(len(odec(1)) == 1 and "どの方式にするか" not in odec(1)[0],
          f"決めた項目は未決の帯から消える -> {odec(1)}")
    check("mk-nudge" not in mks(1), "催促の元が無くなれば印も消える")
    check(not errors, f"JS エラーが出ない -> {errors[:2]}")
    b.close()
finish(errors)
