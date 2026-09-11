"""統合ビューア（計画｜課題）：スイッチ・逆引き札・両方向の行き来・後方互換・両側の編集・性能。
   本日=CLOCK_PIN(2026-09-15)／更新期間=2026-09-01〜09-07。"""
import json
from playwright.sync_api import sync_playwright
from common import (VIEWER, check, finish, granted_handle_init,
                    load_test_json, new_page, reload)

D = load_test_json("正常_統合.json")
BIG = load_test_json("正常_大量統合1000課題.json")
MAX_FIRST_MS, MAX_SWITCH_MS = 1500, 500

errors, dialogs = [], []
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1500, "height": 900})
    pg = new_page(ctx, issue_view=False)   # 既定表示そのものを試すので寄せない
    pg.on("pageerror", lambda e: errors.append(str(e).split("\n")[0]))
    pg.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
    pg.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    pg.goto(VIEWER)

    sw = lambda: pg.eval_on_selector_all("#pmSwitch .pm-b", "e=>e.map(x=>[x.getAttribute('data-pmv'), x.innerText, x.classList.contains('on')])")
    view = lambda: ("issue" if not pg.eval_on_selector("#isMain", "e=>e.hidden") else "plan")
    badges = lambda: pg.eval_on_selector_all("#leftRows .lrow", """e=>e.map(r=>{
        const num=r.querySelector('.c.num'); const bs=[...r.querySelectorAll('.pmb')];
        return [num?num.innerText.trim():'', bs.map(x=>x.innerText)];})""")

    # ===== スイッチの表示条件 =====
    # ファイルを開く前から「計画｜課題」を出す（統合版だと分かるように）
    check(not pg.eval_on_selector("#pmSwitch", "e=>e.hidden"), "ファイルを開く前でもスイッチを出す")
    check([x[0] for x in sw()] == ["plan", "issue"], f"開く前も2択 -> {sw()}")
    # 版表記：製品は 1 つ（v2.0.0）。ファイルの中身で加算表記を出し分けることはしない
    ver = lambda: pg.eval_on_selector(".ver", "e=>e.innerText.replace(/\\s+/g,' ').trim()")
    check(ver() == "v2.0.0", f"開く前の版表記 -> {ver()!r}")

    pg.evaluate("d=>window.renderData(d)", D); pg.wait_for_timeout(350)
    # 大きさ：同じ列の操作ボタン（#editBtn）と高さ・上端・文字サイズを揃える
    geo = pg.evaluate("""()=>{const r=e=>e.getBoundingClientRect();
        const s=r(document.getElementById('pmSwitch')), e=r(document.getElementById('editBtn'));
        const b=document.querySelector('#pmSwitch .pm-b');
        return [s.height, e.height, s.top, e.top, getComputedStyle(b).fontSize,
                getComputedStyle(document.getElementById('editBtn')).fontSize,
                getComputedStyle(document.getElementById('pmSwitch')).borderTopLeftRadius,
                getComputedStyle(b.classList.contains('on')?b:document.querySelector('#pmSwitch .pm-b.on')).backgroundColor];}""")
    check(abs(geo[0] - geo[1]) <= 1, f"スイッチの高さが #editBtn と同じ（±1px） -> {geo[0]} vs {geo[1]}")
    check(abs(geo[2] - geo[3]) <= 1, f"スイッチの上端が #editBtn と揃う（±1px） -> {geo[2]} vs {geo[3]}")
    check(geo[4] == geo[5], f"文字サイズが操作ボタンと同じ -> {geo[4]} vs {geo[5]}")
    check(geo[6] == "6px", f"角丸は操作ボタンと同じ 6px -> {geo[6]}")
    check(geo[7] == "rgb(37, 99, 235)", f"選択中は #openBtn.primary と同じ塗り -> {geo[7]}")
    check(ver() == "v2.0.0", f"両方あるファイルでも版表記は変わらない -> {ver()!r}")
    pg.click("#langBtn"); pg.wait_for_timeout(300)
    check(ver() == "v2.0.0", f"EN でも版表記は変わらない（言語に依らない） -> {ver()!r}")
    pg.click("#langBtn"); pg.wait_for_timeout(300)
    check(not errors, f"読み込みで JS エラーが出ない -> {errors[:2]}")
    check(not pg.eval_on_selector("#pmSwitch", "e=>e.hidden"), "tasks と issues が両方あればスイッチが出る")
    check([x[0] for x in sw()] == ["plan", "issue"] and [x[1] for x in sw()] == ["計画", "課題"],
          f"2択スイッチ（計画｜課題） -> {sw()}")
    check(view() == "plan", f"既定は計画（localStorage 未設定） -> {view()}")
    check([x[2] for x in sw()] == [True, False], "計画側が塗られている")

    only_tasks = {"name": "計画だけ", "projects": [{"name": "P", "tasks": D["projects"][0]["tasks"]}]}
    pg.evaluate("d=>window.renderData(d)", only_tasks); pg.wait_for_timeout(250)
    check(pg.eval_on_selector("#pmSwitch", "e=>e.hidden") and view() == "plan",
          "tasks しか無ければスイッチを出さない（計画だけ）")
    check(ver() == "v2.0.0", f"計画だけのファイルでも版表記は同じ -> {ver()!r}")
    only_issues = {"name": "課題だけ", "projects": [{"name": "P", "issues": D["projects"][0]["issues"]}]}
    pg.evaluate("d=>window.renderData(d)", only_issues); pg.wait_for_timeout(250)
    check(not pg.eval_on_selector("#pmSwitch", "e=>e.hidden") and view() == "issue",
          "issues しか無ければ課題表示。スイッチは出して計画側を無効にする")
    check(ver() == "v2.0.0", f"課題だけのファイルでも版表記は同じ -> {ver()!r}")
    dis = pg.eval_on_selector_all("#pmSwitch .pm-b", "e=>e.map(x=>[x.getAttribute('data-pmv'), x.disabled, x.title])")
    check(dis[0][1] is True and dis[0][2] == "この JSON には計画がありません" and dis[1][1] is False,
          f"無い側は disabled＋ツールチップ -> {dis}")
    pg.click("#pmSwitch .pm-b[data-pmv='plan']", force=True); pg.wait_for_timeout(250)
    check(view() == "issue", "無効な側を押しても切り替わらない")

    # ===== 切替と localStorage =====
    pg.evaluate("d=>window.renderData(d)", D); pg.wait_for_timeout(250)
    pg.click("#pmSwitch .pm-b[data-pmv='issue']"); pg.wait_for_timeout(300)
    check(view() == "issue" and pg.eval_on_selector("#main", "e=>getComputedStyle(e).display") == "none",
          "課題へ切替（計画は隠れる）")
    # 右上：課題ビューでは wbs の集計（期間・工数・進捗・遅延）を隠し、課題の件数と更新期間だけにする
    st = pg.eval_on_selector("#stat", "e=>{const c=getComputedStyle(e);return [c.display, Math.round(e.getBoundingClientRect().width), Math.round(e.getBoundingClientRect().height)];}")
    check(st[0] == "none" and st[1] == 0 and st[2] == 0,
          f"課題ビューでは wbs の右上集計を隠す（場所ごと畳む＝操作バーが伸びない） -> {st}")
    check(pg.eval_on_selector("#isStat", "e=>getComputedStyle(e).display") != "none"
          and "更新期間" in pg.inner_text("#isStat"), "課題側の件数・更新期間は出る")
    pg.click("#pmSwitch .pm-b[data-pmv='plan']"); pg.wait_for_timeout(300)
    check(pg.eval_on_selector("#stat", "e=>getComputedStyle(e).visibility") == "visible"
          and pg.eval_on_selector("#stat", "e=>e.getBoundingClientRect().width") > 0,
          "計画ビューでは wbs の右上集計が出る")
    check(not pg.is_visible("#isStat"), "計画ビューでは課題の件数行は出ない")
    check(not pg.evaluate("()=>document.body.classList.contains('pm-issue')"),
          "計画ビューでは body に pm-issue が付かない（wbs の見た目は不変）")
    langR_plan = pg.evaluate("()=>Math.round(document.getElementById('langBtn').getBoundingClientRect().right)")
    pg.click("#pmSwitch .pm-b[data-pmv='issue']"); pg.wait_for_timeout(300)
    langR_iss = pg.evaluate("()=>Math.round(document.getElementById('langBtn').getBoundingClientRect().right)")
    check(abs(langR_plan - langR_iss) <= 2,
          f"課題ビューでも言語ボタンの右端が計画ビューと同じ（±2px） -> 計画{langR_plan} / 課題{langR_iss}")
    # #0 回帰：課題ビューで操作バーが縦に伸びない（visibility:hidden で場所だけ残すと 3 段ぶんの高さが残った）
    tb = lambda: pg.evaluate("()=>Math.round(document.getElementById('topbar').getBoundingClientRect().height)")
    h_iss = tb()
    pg.click("#pmSwitch .pm-b[data-pmv='plan']"); pg.wait_for_timeout(300)
    h_plan = tb()
    check(h_iss <= h_plan, f"課題ビューの操作バーが計画ビューより高くならない -> 課題{h_iss} / 計画{h_plan}")
    check(h_iss <= 56, f"課題ビューの操作バーは 1 段に収まる -> {h_iss}px")
    pg.click("#pmSwitch .pm-b[data-pmv='issue']"); pg.wait_for_timeout(300)
    pg.click("#pmSwitch .pm-b[data-pmv='plan']"); pg.wait_for_timeout(250)
    pg.click("#pmSwitch .pm-b[data-pmv='issue']"); pg.wait_for_timeout(300)
    check(pg.eval_on_selector_all("#isTbody tr", "e=>e.length") == 3, "開いている案件の課題3件")
    check(pg.evaluate("()=>localStorage.getItem('pmView')") == "issue", "表示は localStorage に記憶")
    reload(pg); pg.wait_for_timeout(200)
    pg.evaluate("d=>window.renderData(d)", D); pg.wait_for_timeout(300)
    check(view() == "issue", "リロード後も前回の表示に戻る")
    pg.click("#pmSwitch .pm-b[data-pmv='plan']"); pg.wait_for_timeout(300)
    check(view() == "plan" and pg.eval_on_selector_all("#leftRows .lrow", "e=>e.length") > 0, "計画へ戻せる")

    # ===== 逆引き札（0件・1件・複数・別案件） =====
    bs = dict((n, v) for n, v in badges() if n)
    check(bs.get("2.3") == ["#1", "#3"], f"同じ案件から2件リンクされたタスクに札2つ -> {bs.get('2.3')}")
    check(bs.get("2.4") == ["勤怠システム更改 #2"], f"別案件からのリンクは案件名付き -> {bs.get('2.4')}")
    check(bs.get("2") == [], "リンクの無い親タスクには札が出ない")
    check(pg.eval_on_selector("#leftRows .pmb", "e=>[getComputedStyle(e).fontSize, e.closest('.pmb-w').getAttribute('title')]")
          == ["10px", "このタスクに紐づく課題（クリックで課題表示へ）"], "札は小さく・ツールチップ付き")
    # links が1つも無いファイルでは DOM を作らない（ゴールデンの前提）
    pg.evaluate("d=>window.renderData(d)", only_tasks); pg.wait_for_timeout(250)
    check(pg.eval_on_selector_all("#leftRows .pmb,#leftRows .pmb-w", "e=>e.length") == 0,
          "links が無いファイルでは札の DOM を1つも作らない")
    pg.evaluate("d=>window.renderData(d)", D); pg.wait_for_timeout(300)

    # ===== 札 → 課題へ飛ぶ（#issue= と強調） =====
    pg.click("#leftRows .pmb"); pg.wait_for_timeout(400)
    check(view() == "issue", "札のクリックで課題表示へ切り替わる")
    check(pg.eval_on_selector_all("#isTbody tr.jump", "e=>e.map(x=>x.getAttribute('data-key'))") == ["販売管理システム移行|1"],
          "飛び先の課題が強調される")
    check(pg.evaluate("()=>location.hash").startswith("#issue="), f"URL に #issue= -> {pg.evaluate('()=>location.hash')}")

    # ===== 課題の WBS リンク → 同じページで計画へ（新しいタブではない） =====
    npages = len(ctx.pages)
    pg.click("#isMain .lk [data-jw]"); pg.wait_for_timeout(500)
    check(len(ctx.pages) == npages, "新しいタブを開かない（同じページで切り替える）")
    check(view() == "plan", "計画表示へ切り替わる")
    jr = pg.eval_on_selector_all("#leftRows .lrow.pmjump", "e=>e.map(x=>x.querySelector('.c.num').innerText.trim())")
    check(jr == ["2.3"], f"該当タスク行が2秒強調される -> {jr}")
    check(pg.evaluate("()=>location.hash").startswith("#wbs="), f"URL に #wbs= -> {pg.evaluate('()=>location.hash')}")
    pg.wait_for_timeout(2100)
    check(pg.eval_on_selector_all("#leftRows .lrow.pmjump", "e=>e.length") == 0, "強調は2秒で消える")

    # 折りたたんだ親の中の葉でも開いて飛ぶ
    pg.evaluate("()=>{localStorage.setItem('wbsCollapsed','[]');}")
    pg.click("#pmSwitch .pm-b[data-pmv='plan']"); pg.wait_for_timeout(200)
    pg.click("#leftRows [data-collapse]"); pg.wait_for_timeout(200)
    n_after_collapse = pg.eval_on_selector_all("#leftRows .lrow", "e=>e.length")
    pg.click("#pmSwitch .pm-b[data-pmv='issue']"); pg.wait_for_timeout(250)
    pg.click("#isMain .lk [data-jw]"); pg.wait_for_timeout(500)
    check(pg.eval_on_selector_all("#leftRows .lrow", "e=>e.length") > n_after_collapse,
          "たたんだ親の中の葉でも、祖先を開いてから飛ぶ")

    # ===== 「戻る」（計画→課題→計画 と積んでから戻す） =====
    pg.click("#pmSwitch .pm-b[data-pmv='plan']"); pg.wait_for_timeout(250)
    pg.click("#leftRows .pmb"); pg.wait_for_timeout(400)          # → #issue=
    h_issue = pg.evaluate("()=>location.hash")
    check(h_issue.startswith("#issue="), f"札で #issue= が積まれる -> {h_issue}")
    pg.click("#isMain .lk [data-jw]"); pg.wait_for_timeout(450)   # → #wbs=
    check(pg.evaluate("()=>location.hash").startswith("#wbs="), "WBSリンクで #wbs= が積まれる")
    pg.go_back(); pg.wait_for_timeout(450)
    check(pg.evaluate("()=>location.hash") == h_issue,
          f"戻るで前の目印（#issue=）へ戻る -> {pg.evaluate('()=>location.hash')}")
    check(view() == "issue", "戻ると課題表示に戻る")
    check(not errors, f"ここまで JS エラー無し -> {errors[:2]}")

    # ===== 後方互換（4形） =====
    for label, d, exp_sw, exp_view in [
        ("wbs 既存（projects/tasks のみ）", only_tasks, True, "plan"),
        ("wbs 旧形式（project/tasks）", {"project": "旧PJ", "milestones": [],
                                        "tasks": D["projects"][0]["tasks"]}, True, "plan"),
        # 課題側は projects 一本（旧形式の読み替えは廃止）＝課題として読まないので計画表示のまま落ちない
        ("旧 issue 形式（sheets）", {"name": "v0.1", "sheets": [{"name": "S", "issues": D["projects"][0]["issues"]}]}, True, "plan"),
        ("旧 issue 形式（単一 issues）", {"name": "v0.1s", "issues": D["projects"][0]["issues"]}, True, "plan"),
    ]:
        n0 = len(errors)
        pg.evaluate("d=>window.renderData(d)", d); pg.wait_for_timeout(300)
        ok = len(errors) == n0 and pg.eval_on_selector("#pmSwitch", "e=>e.hidden") == exp_sw and view() == exp_view
        check(ok, f"後方互換: {label} -> switch隠れ={pg.eval_on_selector('#pmSwitch','e=>e.hidden')} 表示={view()} err={errors[n0:]}")
    b.close()

    # ===== 課題側に旧形式の読み替えは無い：wbs 側の旧フォーマット確認だけが出る =====
    # 課題の形は v0.2（projects[].issues）が最初の公開形。sheets / トップ issues は読まない。
    V01 = {"name": "旧 issue 形式のまま", "star": {"from": "2026-09-01", "to": "2026-09-07"},
           "sheets": [{"name": "S1", "_memo": "残るはず", "issues": D["projects"][0]["issues"]}]}
    b3 = p.chromium.launch()
    pg4 = new_page(b3, issue_view=False, viewport={"width": 1500, "height": 900})
    pg4.on("pageerror", lambda e: errors.append(str(e).split("\n")[0]))
    dlg4 = []
    pg4.on("dialog", lambda d: (dlg4.append(d.message), d.accept()))
    pg4.add_init_script(granted_handle_init(V01))
    pg4.goto(VIEWER)
    before = pg4.evaluate("()=>window.__file")
    pg4.click("#openBtn"); pg4.wait_for_timeout(400)
    check(pg4.eval_on_selector_all("#isTbody tr", "e=>e.length") == 0,
          "旧 issue 形式（sheets）は課題として読まない")
    check(pg4.eval_on_selector("#pmSwitch", "e=>e.hidden"), "課題が無いのでスイッチは出さない")
    check(pg4.evaluate("()=>window.__file") == before, "閲覧だけならファイルは1バイトも書き換わらない")
    check(pg4.evaluate("()=>window.__writes") == 0, "閲覧だけでは保存が走らない")
    n4 = len(dlg4)
    pg4.click("#editBtn"); pg4.wait_for_timeout(450)
    check(not any("v0.1" in d for d in dlg4[n4:]),
          f"課題側の変換確認は出さない（読み替えを廃止したため） -> {dlg4[n4:]}")
    check(not errors, f"旧形式を読ませても JS エラーは出ない -> {errors[:2]}")
    b3.close()

    # ===== 両側の編集（相手のデータを壊さない） =====
    b2 = p.chromium.launch()
    pg2 = new_page(b2, issue_view=False, viewport={"width": 1500, "height": 900})
    pg2.on("pageerror", lambda e: errors.append(str(e).split("\n")[0]))
    pg2.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    pg2.add_init_script(granted_handle_init(D))
    pg2.goto(VIEWER)
    saved = lambda: json.loads(pg2.evaluate("()=>window.__file"))
    pg2.click("#openBtn"); pg2.wait_for_timeout(300)
    pg2.click("#editBtn"); pg2.wait_for_timeout(350)
    # 計画側の編集 → issues が保持される
    pg2.fill('#leftRows input[data-field="name"]', "変換ツール（改）")
    pg2.dispatch_event('#leftRows input[data-field="name"]', "change")
    pg2.wait_for_timeout(700)
    s1 = saved()
    check(s1["projects"][0]["tasks"][0]["name"] == "変換ツール（改）", "計画側の編集が保存される")
    check(len(s1["projects"][0]["issues"]) == 3 and s1["projects"][0]["issues"][1]["links"][0] == {"wbs": "2.3"},
          "計画側を編集しても issues と links がそのまま残る")
    # 課題側の編集 → tasks が保持される
    pg2.click("#pmSwitch .pm-b[data-pmv='issue']"); pg2.wait_for_timeout(350)
    pg2.fill('#isTbody input[data-field="title"]', "タイトルを直した")
    pg2.dispatch_event('#isTbody input[data-field="title"]', "change")
    pg2.wait_for_timeout(700)
    s2 = saved()
    check(s2["projects"][0]["issues"][0]["title"] == "タイトルを直した", "課題側の編集が保存される")
    check(len(s2["projects"][0]["tasks"][0]["children"]) == 2
          and s2["projects"][0]["tasks"][0]["children"][0]["id"] == "2.3", "課題側を編集しても tasks がそのまま残る")
    check(s2["projects"][0].get("milestones", [{}])[0].get("label") == "本番切替", "milestones も残る")
    check("_calc" not in pg2.evaluate("()=>window.__file"), "派生値は保存されない")
    pg2.close()

    # ===== 課題ビューでは編集の ON/OFF によらず計画側の絞り込みバーを出さない =====
    # wbs の render()（updateSummaryAndScroll）が #filterBar に style.display="flex" を直に書くため、
    # 編集トグルの render で計画側のバーが復活し、課題側のバーが 32px 押し下げられていた（v2.0.0 の不具合）。
    pg5 = new_page(b2, issue_view=False, viewport={"width": 1500, "height": 900})
    pg5.on("pageerror", lambda e: errors.append(str(e).split("\n")[0]))
    pg5.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    pg5.add_init_script(granted_handle_init(D))
    pg5.goto(VIEWER)
    # 高さ・表示・課題側バーの上端をまとめて採る（押し下げは高さでなく上端に出る）
    bars = lambda: pg5.evaluate("""()=>{const g=id=>{const e=document.getElementById(id);
        return [e.offsetHeight, getComputedStyle(e).display];};
        return {plan:g('filterBar'), issue:g('isFilterBar'), topbar:g('topbar')[0],
                tabbar:g('isTabBar')[0], isMain:g('isMain')[0],
                isMainTop:Math.round(document.getElementById('isMain').getBoundingClientRect().top)};}""")
    pg5.click("#openBtn"); pg5.wait_for_timeout(400)
    pg5.click("#pmSwitch .pm-b[data-pmv='issue']"); pg5.wait_for_timeout(350)
    off = bars()
    check(off["plan"][0] == 0 and off["plan"][1] == "none",
          f"課題ビュー（編集OFF）：計画側の絞り込みバーは 0px -> {off['plan']}")
    check(off["issue"][0] > 0, f"課題ビュー（編集OFF）：課題側の絞り込みバーは出る -> {off['issue']}")
    pg5.click("#editBtn"); pg5.wait_for_timeout(500)
    on = bars()
    check(on["plan"][0] == 0 and on["plan"][1] == "none",
          f"課題ビュー（編集ON）：計画側の絞り込みバーを出さない -> {on['plan']}")
    check(on["issue"][0] > 0, f"課題ビュー（編集ON）：課題側の絞り込みバーは出たまま -> {on['issue']}")
    check((on["topbar"], on["tabbar"]) == (off["topbar"], off["tabbar"]),
          f"編集ONで操作バー・タブの高さが変わらない -> {(on['topbar'], on['tabbar'])} vs {(off['topbar'], off['tabbar'])}")
    # 押し下げの証拠は課題側の板の位置と高さ（不具合時は 79→111 / 852→820 になっていた）。
    # 件数表（#isStat）は編集中だけ 4px 伸びる＝これは本来の挙動なので、断言は #isMain で取る。
    check(on["isMain"] == off["isMain"] and on["isMainTop"] == off["isMainTop"],
          f"編集ONで課題側が押し下げられない -> 高さ {on['isMain']} vs {off['isMain']} / 上端 {on['isMainTop']} vs {off['isMainTop']}")
    pg5.click("#editBtn"); pg5.wait_for_timeout(500)
    back = bars()
    check(back["plan"][0] == 0 and back["issue"][0] > 0 and back["isMain"] == off["isMain"]
          and back["isMainTop"] == off["isMainTop"],
          f"編集を OFF に戻しても課題側のバーだけ（残留しない） -> {back}")
    pg5.click("#pmSwitch .pm-b[data-pmv='plan']"); pg5.wait_for_timeout(350)
    pl = bars()
    check(pl["plan"][0] > 0 and pl["plan"][1] == "flex",
          f"計画ビューに戻すと計画側の絞り込みバーが出る -> {pl['plan']}")
    check(pl["issue"][0] == 0, f"計画ビューでは課題側のバーは出ない -> {pl['issue']}")
    pg5.click("#editBtn"); pg5.wait_for_timeout(500)
    pe = bars()
    check(pe["plan"][0] > 0 and pe["plan"][1] == "flex",
          f"計画ビューは従来どおり編集ONでも絞り込みバーが出る -> {pe['plan']}")
    check(pe["issue"][0] == 0, f"計画ビュー（編集ON）でも課題側のバーは出ない -> {pe['issue']}")
    pg5.close()

    # ===== 性能（1000課題＋225タスク行・実ポインタ） =====
    pg3 = new_page(b2, issue_view=False, viewport={"width": 1500, "height": 900})
    perr = []
    pg3.on("pageerror", lambda e: perr.append(str(e).split("\n")[0]))
    pg3.goto(VIEWER)
    first = pg3.evaluate("d=>{const a=performance.now();window.renderData(d);return performance.now()-a;}", BIG)
    check(first < MAX_FIRST_MS, f"初回描画 {first:.0f}ms < {MAX_FIRST_MS}ms（1000課題＋225タスク行）")
    # 計測はページ内で開始（capture フェーズ）＝クリック送出の往復を計測に含めない
    pg3.evaluate("()=>{document.getElementById('pmSwitch').addEventListener('click',"
                 "()=>{window.__t0=performance.now();},true);}")
    sws = []
    for v in ("issue", "plan", "issue", "plan"):
        pg3.click(f"#pmSwitch .pm-b[data-pmv='{v}']", timeout=3000)
        sws.append(pg3.evaluate("()=>performance.now()-window.__t0"))
    check(max(sws) < MAX_SWITCH_MS, f"表示切替 最大 {max(sws):.0f}ms < {MAX_SWITCH_MS}ms（各 {[round(x) for x in sws]}）")
    check(not perr, f"大量データで JS エラー無し -> {perr}")
    print(f"     [実測] 初回描画 {first:.0f}ms / 切替 {[round(x) for x in sws]}ms")
    b2.close()
finish(errors)
