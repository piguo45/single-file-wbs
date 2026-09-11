"""方針（decisions[]）：決まった/未決の見え方・未決 N の印・決める/＋方針/✕・保存JSONの形。
   本日=CLOCK_PIN(2026-09-15)。単体版・統合版の両方で回る。"""
import json
from playwright.sync_api import sync_playwright
from common import (S, J, VIEWER, action, book, check, decision, finish,
                    granted_handle_init, issue, new_page)

D = book([
    issue(1, "決まったのと未決が混じる", due="2026-09-20",
          decisions=[decision("どの方式で直すか", "2026-09-02", "2026-09-14", "変換処理を直す"),
                     decision("誰が検収するか", "2026-09-03"),
                     decision("いつ入れるか", "2026-09-05")],
          actions=[action("2026-09-14", "調査", "ぴぐお", True)]),
    issue(2, "方針がまだ無い", decisions=[]),
    issue(3, "完了した課題", decisions=[decision("やるか", "2026-09-01")],
          closed={"at": "2026-09-14", "how": "resolved", "note": "直った"},
          actions=[action("2026-09-14", "直した", "", True)]),
], star={"from": "2026-09-10", "to": "2026-09-15"})

with sync_playwright() as pw:
    b = pw.chromium.launch()
    errors, dlg = [], []
    pg = new_page(b, viewport={"width": 1500, "height": 1000})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("dialog", lambda d: (dlg.append(d.message), d.accept()))
    pg.add_init_script(granted_handle_init(D))
    pg.goto(VIEWER)
    saved = lambda: json.loads(pg.evaluate("()=>window.__file"))["projects"][0]["issues"]
    dtl = lambda n: pg.inner_text(S(f"#tbody tr:nth-child({n}) td.detail"))
    pg.click(S("#openBtn")); pg.wait_for_timeout(350)

    # ===== 概要の「方針：」＝決まった項目ごとに1行（配列順） =====
    dl = lambda n: pg.eval_on_selector_all(
        S(f"#tbody tr:nth-child({n}) .ln"),
        "e=>e.filter(x=>x.querySelector('.lb')&&x.querySelector('.lb').innerText==='方針：').map(x=>x.innerText)")
    check(len(dl(1)) == 1 and "変換処理を直す" in dl(1)[0] and "9/14" in dl(1)[0],
          f"決まった方針だけ 方針：答え（M/D） で出る（未決は出さない） -> {dl(1)}")
    check("方針：未定" in dtl(2), f"決まったものが無ければ 方針：未定 -> {dtl(2)!r}")

    # ===== 「方針（未決）」の帯 =====
    check("方針（未決）" in dtl(1), "未決があれば帯を出す")
    check("方針（未決）" not in dtl(2), "未決が無ければ帯ごと出さない")
    od = pg.eval_on_selector_all(S("#tbody tr:nth-child(1) .odec"), "e=>e.map(x=>x.innerText)")
    check(len(od) == 2, f"未決の項目だけ並ぶ（決まったものは出さない） -> {od}")
    check(od[0].startswith("・") and "誰が検収するか" in od[0],
          f"行頭「・」＋本文 -> {od[0]!r}")
    check("12日経過（9/3〜）" in od[0] and "10日経過（9/5〜）" in od[1],
          f"経過は「N日経過（M/D〜）」の1組 -> {od}")
    check(pg.eval_on_selector(S("#tbody tr:nth-child(1) .odec .dcmeta"), "e=>e.title")
          == "9/3 に載せてから 12 日", "経過にはツールチップで「いつ載せて何日」を出す")
    check("問" not in dtl(1) and "決" not in dtl(1).replace("未決", "").replace("決まっ", ""),
          "記号「問」「決」は使わない")

    # ===== 未決 N の印（状態列・タイトル横・タブ・件数）／完了には付けない =====
    check(pg.eval_on_selector(S("#tbody tr:nth-child(1) .mk-open"), "e=>e.innerText") == "未決 2",
          "状態列の下に 未決 N")
    check(pg.eval_on_selector(S("#tbody tr:nth-child(1) .opn"), "e=>e.textContent.trim()") == "未決 2",
          "タイトル横にも 未決 N")
    check(pg.eval_on_selector(S("#tbody tr:nth-child(1) .opn"), "e=>getComputedStyle(e).color")
          == "rgb(138, 109, 31)", "タイトル横の未決は橙・小")
    check(pg.eval_on_selector_all(S("#tbody tr:nth-child(3) .mk-open,#tbody tr:nth-child(3) .opn"),
                                  "e=>e.length") == 0, "完了した課題には未決の印を付けない")
    # 右上・タブ・サマリは「課題数」（待ち／凍結と揃える）。項目数はタイトル横と状態列の下だけ
    check("未決 1" in pg.inner_text(S("#counts")).replace("\n", " "),
          f"右上の件数は未決の課題数（項目数ではない） -> {pg.inner_text(S('#counts'))!r}")
    check(pg.eval_on_selector(S("#tbody tr:nth-child(1) .mk-open"), "e=>e.title").endswith("（項目数）")
          and "課題数" in pg.eval_on_selector_all(S("#counts .cnt"),
              "e=>e.filter(x=>x.innerText.includes('未決')).map(x=>x.title)")[0],
          "ツールチップで「項目数」「課題数」を言い分ける")

    # ===== ★＝decided が期間内なら付く（since は数えない） =====
    check(pg.eval_on_selector_all(S("#tbody tr:nth-child(1) .tt .star"), "e=>e.length") == 1,
          "9/14 に決めた＝期間内なので ★ が付く")
    check(pg.eval_on_selector_all(S("#tbody tr:nth-child(2) .tt .star"), "e=>e.length") == 0,
          "起票（since）だけでは ★ にしない")

    # ===== 編集：決める／＋方針／✕ =====
    pg.click(S("#editBtn")); pg.wait_for_timeout(400)
    check(pg.eval_on_selector_all(S('#tbody [data-act="decide"]'), "e=>e.length") == 0,
          "「方針を決める」ボタンは無い（1課題1方針をやめたため）")
    n0 = len(saved()[0]["decisions"])
    pg.click(S("#tbody tr:nth-child(1) [data-decide]")); pg.wait_for_timeout(300)
    pg.fill("#isForm input[data-fm='a']", "情シスに検収してもらう")
    pg.click("#isForm .fm-ok"); pg.wait_for_timeout(700)
    d1 = saved()[0]["decisions"][1]
    check(d1 == {"q": "誰が検収するか", "since": "2026-09-03",
                 "decided": "2026-09-15", "a": "情シスに検収してもらう"},
          f"決める＝decided に本日・a に答え（q と since は動かさない） -> {d1}")
    check(len(saved()[0]["decisions"]) == n0, "決めても件数は増えない（同じ項目が決まるだけ）")
    check(len(dl(1)) == 2 and "情シスに検収してもらう" in dl(1)[1],
          f"決めた項目は概要の「方針：」へ移る -> {dl(1)}")
    check(pg.eval_on_selector_all(S("#tbody tr:nth-child(1) .odec"), "e=>e.length") == 1,
          "帯からは消える")

    # 編集モードの行が崩れない（行動の編集行と同じ1行 flex）
    lay = pg.eval_on_selector(S("#tbody tr:nth-child(1) .odec.edit"), J("""e=>{
        const r=x=>x.getBoundingClientRect(), cy=x=>r(x).top+r(x).height/2;
        const ok=e.querySelector('.dcok'), q=e.querySelector('.dcq'),
              ut=e.querySelector('.dcuntil'), mt=e.querySelector('.dcmeta'),
              dl=e.querySelector('.decdel');
        return [Math.round(Math.abs(cy(ok)-cy(q))), Math.round(r(q).width),
                r(ok).left<r(q).left, r(ut).left>r(q).left,
                Math.round(r(dl).right-r(mt).right)>=0, Math.round(r(e).height)];}"""))
    check(lay[0] <= 2, f"「確定」と本文欄が同じ行（y中心 ±2px） -> {lay[0]}px")
    check(lay[1] > 100, f"本文欄が潰れていない -> {lay[1]}px")
    check(lay[2], "「確定」は行頭（行動の 済/未 チェックと同じ位置）")
    check(lay[3] and lay[4], "期限欄は本文の右・✕ は最も右")
    check(lay[5] <= 30, f"1500px なら1行に収まる -> 行高 {lay[5]}px")
    check(pg.eval_on_selector(S("#tbody .odec.edit .dcok"), "e=>e.textContent") == "確定"
          and pg.eval_on_selector(S("#tbody .odec.edit .dcok"), "e=>e.title") == "答えを書いて確定する",
          "行頭のボタンは「確定」（ツールチップ付き）")
    check(pg.eval_on_selector_all(S("#tbody .odec.edit .dcgo"), "e=>e.length") == 0,
          "「決める」ボタンは廃止")

    pg.click(S('#tbody tr:nth-child(2) [data-act="adddec"]')); pg.wait_for_timeout(700)
    check(saved()[1]["decisions"] == [{"q": "", "since": "2026-09-15", "decided": None, "a": ""}],
          f"＋方針＝末尾に未決を1つ（since=本日） -> {saved()[1]['decisions']}")
    pg.fill(S("#tbody tr:nth-child(2) .odec .dcq"), "先に誰に聞くか決める")
    pg.dispatch_event(S("#tbody tr:nth-child(2) .odec .dcq"), "change"); pg.wait_for_timeout(700)
    check(saved()[1]["decisions"][0]["q"] == "先に誰に聞くか決める", "帯の欄に書いた文が q に入る")

    m = len(dlg)
    pg.click(S("#tbody tr:nth-child(2) .odec .decdel")); pg.wait_for_timeout(700)
    check(len(dlg) > m and "削除" in dlg[-1], f"✕ は確認を出す -> {dlg[-1:]}")
    check(saved()[1]["decisions"] == [], "✕ で decisions から消える")
    pg.click(S("#tbody tr:nth-child(1) .ln .decdel")); pg.wait_for_timeout(700)
    check(len(saved()[0]["decisions"]) == n0 - 1, "概要の「方針：」行にも ✕ がある")

    # ===== 保存 JSON の形 =====
    raw = pg.evaluate("()=>window.__file")
    check("_calc" not in raw, "派生値 _calc は書かない")
    check('"decision"' not in raw and "decisionLog" not in raw,
          "旧キー（decision / decisionLog）は書かない")
    check(all(sorted(d) == ["a", "decided", "q", "since"] for d in saved()[0]["decisions"]),
          f"1件の鍵は q / since / decided / a の4つ -> {saved()[0]['decisions']}")
    check(not errors, f"JS エラーが出ない -> {errors[:2]}")

    # ===== 異常系：中身を持てない項目は表示モードでは出さない（件数は事実のまま） =====
    # a（方針）が空＝方針の行にしない／q（決めるべきこと）が空＝帯に出さない
    BAD = book([
        issue(1, "a が空の決まった項目", due="2026-09-20",
              decisions=[{"q": "どの方式で直すか", "since": "2026-09-02",
                          "decided": "2026-09-14", "a": ""}]),
        issue(2, "q が空の未決", due="2026-09-20",
              decisions=[{"q": "", "since": "2026-09-02", "decided": None, "a": ""},
                         {"q": "こちらは出る", "since": "2026-09-02", "decided": None, "a": ""}]),
        issue(3, "未決は q が空の1件だけ", due="2026-09-20",
              decisions=[{"q": "", "since": "2026-09-02", "decided": None, "a": ""}]),
    ], star={"from": "2026-09-10", "to": "2026-09-15"})
    n0 = len(errors)
    pg.evaluate("d=>window.renderData(d)", BAD); pg.wait_for_timeout(250)
    check(len(errors) == n0, f"壊れた decisions で JS エラーを出さない -> {errors[n0:]}")
    check(dl(1) == ["方針：未定"],
          f"a（方針）が空なら方針の行を出さない（方針：未定 に落ちる） -> {dl(1)}")
    odec = lambda n: pg.eval_on_selector_all(
        S(f"#tbody tr:nth-child({n}) .ln.odec"), "e=>e.map(x=>x.innerText)")
    check(len(odec(2)) == 1 and "こちらは出る" in odec(2)[0],
          f"q（決めるべきこと）が空の項目は帯に出さない -> {odec(2)}")
    check(odec(3) == [], f"未決が q 空の1件だけなら帯ごと出さない -> {odec(3)}")
    cnt = pg.inner_text(S("#counts")).replace("\n", " ")
    check("未決 2" in cnt,
          f"件数は事実のまま数える（q が空でも未決＝#2 と #3 の2件） -> {cnt!r}")
    b.close()
finish(errors)
