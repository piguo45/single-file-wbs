"""案件（projects[]）＝画面タブ。v0.2 は `projects[].issues` が正。
   タブの表示/切替・バッジ ★N ⚠N・サマリ表と合計・行クリック遷移・案件ごとの状態・
   ＋案件/✕/名前変更・projects が無い器でも ＋案件 から書き始められること・
   案件の知らないキー（tasks/milestones）の保持・保存 JSON に派生値が無い・document.title・性能。
   本日=CLOCK_PIN(2026-09-15)／報告期間=2026-09-01〜09-07。"""
import json
from statistics import median
from playwright.sync_api import sync_playwright
from common import J, S, TITLE_SUFFIX, UNIFIED, VIEWER, check, finish, granted_handle_init, load_test_json, new_page, reload

D = load_test_json("正常_案件3件.json")
BIG = load_test_json("正常_大量案件1000件.json")
BAD = load_test_json("異常_projects不正.json")

MAX_FIRST_MS, MAX_SWITCH_MS = 1500, 500
PERF_N = 5   # 性能は5回計って中央値で判定（負荷のスパイク1回で赤くしない）

errors, dialogs = [], []
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1500, "height": 900})
    pg = new_page(ctx)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append("console:" + m.text) if m.type == "error" else None)
    pg.on("dialog", lambda d: (dialogs.append(d.message), d.accept("新案件")))
    pg.add_init_script(granted_handle_init(D))
    pg.goto(VIEWER)

    tabs = lambda: pg.eval_on_selector_all(S("#tabBar .stab"), "e=>e.map(x=>x.innerText.replace(/\\n/g,''))")
    nrow = lambda: pg.eval_on_selector_all(S("#tbody tr"), "e=>e.length")
    titles = lambda: pg.eval_on_selector_all(S("#tbody td.title b"), "e=>e.map(x=>x.innerText)")
    grid = lambda: pg.eval_on_selector_all(S("#tbody tr"),
        "e=>e.map(x=>[...x.querySelectorAll('td')].map(t=>t.innerText.trim()))")

    # --- タブの表示・バッジ ---
    pg.evaluate("d=>window.renderData(d)", D); pg.wait_for_timeout(250)
    check(pg.is_visible(S("#tabBar")), "projects 形式ではタブバーが出る")
    check(tabs() == ["サマリ", "販売管理移行★2⚠2", "勤怠システム★1", "サーバ更改⚠1"],
          f"先頭がサマリ・各案件に ★N/⚠N（0は非表示・記号のまま） -> {tabs()}")
    check(pg.eval_on_selector(S("#tabBar .stab[data-si='0'] .tb.st"), "e=>e.getAttribute('title')")
          == "更新 2 件（期間内に動いた課題）", "タブの★は title に件数入りの言葉を持つ")
    check(pg.eval_on_selector(S("#tabBar .stab[data-si='0']"), "e=>e.classList.contains('on')"),
          "既定は最初の案件が開いている（サマリではない）")
    check(nrow() == 4, f"開いている案件の4件だけ描く -> {nrow()}")
    check(pg.inner_text(S("#counts")).replace("\n", " ").startswith("未着手 0対応中 3完了 1"),
          f"右上の件数は開いている案件のもの -> {pg.inner_text(S('#counts'))!r}")
    check(pg.title() == "自分の課題管理表" + TITLE_SUFFIX, f"document.title -> {pg.title()!r}")
    check("自分の課題管理表" in pg.inner_text(S("#stat")), "メタ行にブック名")
    check(pg.inner_text(S("#starRange")) == "更新期間 9/1〜9/7", "更新期間はブック共通")

    # --- レイアウト回帰：タブが操作バーに食い込まない（実ポインタで押せること） ---
    # body は縦の flex。画面が低いと帯が潰れ、align-items:flex-end のタブが上へはみ出して
    # #topbar に覆われ、実クリックが "topbar intercepts pointer events" で通らない事故があった
    def tab_geo():
        return pg.evaluate(J("""()=>{
          const r=e=>e.getBoundingClientRect();
          const tb=r(document.getElementById('tabBar')), tp=r(document.getElementById('topbar'));
          return [...document.querySelectorAll('#tabBar .stab')].map(el=>{
            const q=r(el), hit=document.elementFromPoint(q.left+q.width/2, q.top+q.height/2);
            return {n:el.innerText.trim().slice(0,4),
                    inBar:q.top>=tb.top-0.5 && q.bottom<=tb.bottom+0.5,
                    onTopbar:q.top < tp.bottom-0.5,
                    hit:!!(hit && (hit===el || el.contains(hit)))};});}"""))
    for vh in (500, 360, 900):
        pg.set_viewport_size({"width": 1500, "height": vh}); pg.wait_for_timeout(150)
        g = tab_geo()
        check(g and all(x["inBar"] for x in g), f"高さ{vh}px: .stab が #tabBar の内側に収まる -> {g}")
        check(not any(x["onTopbar"] for x in g), f"高さ{vh}px: .stab が #topbar と重ならない -> {g}")
        check(all(x["hit"] for x in g), f"高さ{vh}px: 各タブの中心の elementFromPoint がそのタブ -> {g}")
    pg.set_viewport_size({"width": 1500, "height": 500}); pg.wait_for_timeout(150)
    pg.click(S("#tabBar .stab[data-si='1']"), timeout=3000)   # 実ポインタ（合成イベントではない）
    pg.wait_for_timeout(200)
    check(pg.eval_on_selector(S("#tabBar .stab[data-si='1']"), "e=>e.classList.contains('on')"),
          "低い画面でも実ポインタでタブを切り替えられる")
    pg.set_viewport_size({"width": 1500, "height": 900}); pg.wait_for_timeout(150)
    pg.click(S("#tabBar .stab[data-si='0']")); pg.wait_for_timeout(200)

    # --- 切替：他案件の DOM は作らない ---
    pg.click(S("#tabBar .stab[data-si='1']")); pg.wait_for_timeout(200)
    check(nrow() == 3 and titles()[0] == "打刻の丸め仕様が未確定", f"タブ切替で中身が変わる -> {titles()}")
    check(pg.eval_on_selector_all(S("#tbody tr"), "e=>e.filter(x=>x.innerText.includes('移行テスト')).length") == 0,
          "他案件の行は DOM に存在しない")
    # 案件ごとの担当候補（開いている案件から収集）
    asg1 = pg.eval_on_selector_all(S("#filterBar .asg-cb"), "e=>e.map(x=>x.getAttribute('data-asg'))")
    check(sorted(asg1) == sorted(["", "ぴぐお"]), f"担当候補は開いている案件から -> {asg1}")
    pg.click(S("#tabBar .stab[data-si='0']")); pg.wait_for_timeout(200)
    asg0 = pg.eval_on_selector_all(S("#filterBar .asg-cb"), "e=>e.map(x=>x.getAttribute('data-asg'))")
    check(sorted(asg0) == sorted(["Aさん", "ぴぐお", "佐藤"]), f"案件を変えると担当候補も変わる -> {asg0}")

    # --- 案件ごとの折りたたみ ---
    pg.click(S("#tbody tr:nth-child(1) td.title .caret")); pg.wait_for_timeout(150)
    check(pg.eval_on_selector_all(S("#tbody td.detail .body"), "e=>e.length") == 3, "1件だけ畳んだ")
    pg.click(S("#tabBar .stab[data-si='1']")); pg.wait_for_timeout(200)
    check(pg.eval_on_selector_all(S("#tbody td.detail .body"), "e=>e.length") == 3,
          "別案件は畳まれていない（折りたたみキーに案件名が入る）")
    pg.click(S("#tabBar .stab[data-si='0']")); pg.wait_for_timeout(200)
    nb = pg.eval_on_selector_all(S("#tbody td.detail .body"), "e=>e.length")
    check(nb == 3, f"戻ると畳んだ状態が残っている -> body={nb} / 行={nrow()} / titles={titles()}")
    pg.click(S("#tbody tr:nth-child(1) td.title .caret")); pg.wait_for_timeout(150)

    # --- 絞り込み・並び順はブック共通 ---
    pg.click(S('.sf-btn[data-state="closed"]')); pg.wait_for_timeout(200)
    check(nrow() == 3, f"完了OFF（販売管理移行は完了1件） -> {nrow()}")
    pg.click(S("#tabBar .stab[data-si='1']")); pg.wait_for_timeout(200)
    check(nrow() == 2, f"別案件でも同じ絞り込みが効く（ブック共通） -> {nrow()}")
    pg.click(S('.sf-btn[data-state="closed"]')); pg.wait_for_timeout(200)
    pg.click(S("#tabBar .stab[data-si='0']")); pg.wait_for_timeout(200)

    # --- サマリタブ ---
    pg.click(S("#tabBar .stab[data-summary]")); pg.wait_for_timeout(250)
    heads = pg.eval_on_selector_all(S("#tbl thead th"), "e=>e.map(x=>x.innerText.trim())")
    check(heads == ["案件", "未着手", "対応中", "完了", "待ち", "凍結", "未決",
                    "★ 更新", "期限超過", "催促", "次の期限"],
          f"サマリの列＝状態3つ＋印6つ＋次の期限 -> {heads}")
    check(grid() == [["販売管理移行", "0", "3", "1", "1", "0", "0", "2", "2", "0", "9/5"],
                     ["勤怠システム", "1", "1", "1", "0", "0", "0", "1", "0", "0", "10/1"],
                     ["サーバ更改", "2", "1", "0", "0", "1", "0", "0", "1", "0", "9/12"],
                     ["合計", "3", "5", "2", "1", "1", "0", "3", "3", "0", "9/5"]],
          f"サマリの値と合計（次の期限＝未完了の最小 due） -> {grid()}")
    check(not pg.is_visible(S("#filterBar")), "サマリではフィルタバーを出さない（読み取り専用）")
    check(pg.inner_text(S("#starRange")) == "更新期間 9/1〜9/7", "サマリでも更新期間は右上に出る")
    check("★ 更新 3" in pg.inner_text(S("#counts")), f"サマリの件数はブック合計 -> {pg.inner_text(S('#counts'))!r}")
    # 行クリックでその案件へ
    pg.click(S("#tbody tr[data-proj='サーバ更改']")); pg.wait_for_timeout(250)
    check(pg.eval_on_selector(S("#tabBar .stab[data-si='2']"), "e=>e.classList.contains('on')")
          and nrow() == 3, f"サマリの行クリックでその案件へ -> {tabs()}")

    # --- タブの記憶（リロード） ---
    reload(pg); pg.wait_for_timeout(200)
    pg.evaluate("d=>window.renderData(d)", D); pg.wait_for_timeout(250)
    check(pg.eval_on_selector(S("#tabBar .stab[data-si='2']"), "e=>e.classList.contains('on')"),
          "開いていたタブを案件名で記憶")
    pg.evaluate("()=>localStorage.setItem('issProj','存在しない案件')")
    reload(pg); pg.wait_for_timeout(200)   # 記憶は読み込み時に効くのでリロードしてから確かめる
    pg.evaluate("d=>window.renderData(d)", D); pg.wait_for_timeout(200)
    check(pg.eval_on_selector(S("#tabBar .stab[data-si='0']"), "e=>e.classList.contains('on')"),
          "記憶した案件が無ければ最初の案件")

    # --- 課題側は projects 一本（旧 sheets／トップ issues の読み替えは持たない） ---
    old = {"name": "旧形式", "sheets": [{"name": "S", "issues": [{"id": 8, "title": "sheets側"}]}],
           "issues": [{"id": 1, "title": "issues側"}]}
    pg.evaluate("d=>window.renderData(d)", old); pg.wait_for_timeout(250)
    # 統合版は課題が0件なら計画表示に寄るので、課題側の空表示そのものは単体版で見る
    check(titles() == [] and (UNIFIED or pg.is_visible(S("#empty"))),
          f"sheets / トップ issues は読まない（空表示・落ちない） -> {titles()}")
    pg.evaluate("d=>window.renderData(d)", D); pg.wait_for_timeout(200)

    # --- 異常な projects（要素が非オブジェクト／issues 非配列／名前欠損）→ 落ちない ---
    n0 = len(errors)
    pg.evaluate("d=>window.renderData(d)", BAD); pg.wait_for_timeout(250)
    check(len(errors) == n0, "壊れた projects でも JS エラーを出さない")
    check(tabs() == ["サマリ", "(名前なし)", "名前あり・issues 欠損", "正常な案件"],
          f"非オブジェクト要素は捨て、名前欠損は (名前なし) 表示 -> {tabs()}")
    b.close()

    # ===== 編集モード：＋案件／✕／名前変更／従来形式の変換 =====
    b2 = p.chromium.launch()
    pg2 = new_page(b2, viewport={"width": 1500, "height": 900})
    pg2.on("pageerror", lambda e: errors.append(str(e)))
    pg2.on("dialog", lambda d: (dialogs.append(d.message), d.accept("新案件")))
    pg2.add_init_script(granted_handle_init(D))
    pg2.goto(VIEWER)
    saved = lambda: json.loads(pg2.evaluate("()=>window.__file"))
    flush = lambda: pg2.wait_for_timeout(650)
    pg2.click(S("#openBtn")); pg2.wait_for_timeout(250)
    pg2.click(S("#editBtn")); pg2.wait_for_timeout(300)
    check(pg2.eval_on_selector_all(S('#tabBar [data-act="addproj"]'), "e=>e.length") == 1, "編集モードで ＋案件 が出る")
    check(pg2.eval_on_selector_all(S("#tabBar .stab.on [data-delproj]"), "e=>e.length") == 1,
          "開いているタブにだけ ✕ が出る")

    pg2.click(S('#tabBar [data-act="addproj"]')); flush()
    names = [s["name"] for s in saved()["projects"]]
    check(names == ["販売管理移行", "勤怠システム", "サーバ更改", "新案件"], f"＋案件で末尾に追加 -> {names}")
    check(pg2.eval_on_selector(S("#tabBar .stab[data-si='3']"), "e=>e.classList.contains('on')"), "追加後にその案件へ切替")
    check(saved()["projects"][3]["issues"] == [], "新しい案件の issues は空")
    # 番号(id)は案件ごと＝新案件の ＋課題 は 1 から
    pg2.click(S('#filterBar .addissue')); flush()
    check(saved()["projects"][3]["issues"][0]["id"] == 1, f"新案件の＋課題は id=1 -> {saved()['projects'][3]['issues'][0]['id']}")
    pg2.click(S("#tabBar .stab[data-si='0']")); pg2.wait_for_timeout(200)
    pg2.click(S('#filterBar .addissue')); flush()
    check(saved()["projects"][0]["issues"][-1]["id"] == 5,
          f"既存案件の＋課題はその案件の最大id+1 -> {saved()['projects'][0]['issues'][-1]['id']}")

    # 名前変更（ダブルクリック）＝実マウス。開いているタブを作り直さなくしたので dblclick が届く
    pg2.dblclick(S("#tabBar .stab[data-si='0']")); flush()
    check(saved()["projects"][0]["name"] == "新案件", f"ダブルクリックで名前変更 -> {saved()['projects'][0]['name']}")
    check(saved()["projects"][0].get("_memo") == "案件のカスタムキー（保存で保持）", "案件の `_` キーは保持される")
    check("sheets" not in saved(), "保存 JSON に sheets キーは出ない")
    # 案件の知らないキー（tasks / milestones）は触らず保存で残す
    p0 = saved()["projects"][0]
    check(isinstance(p0.get("tasks"), list) and len(p0["tasks"]) == 2, f"tasks が保持される -> {type(p0.get('tasks'))}")
    check(p0["tasks"][1]["children"][0]["id"] == "2.3", "tasks の中身も無傷")
    check(isinstance(p0.get("milestones"), list) and p0["milestones"][0]["label"] == "本番切替", "milestones も保持される")

    # ✕で案件削除（課題ごと）
    n = len(dialogs)
    pg2.click(S("#tabBar .stab.on [data-delproj]")); flush()
    check(len(dialogs) > n and "課題ごと削除" in dialogs[-1], "案件削除は確認ダイアログを出す")
    check([s["name"] for s in saved()["projects"]] == ["勤怠システム", "サーバ更改", "新案件"], "確認OKで削除される")
    check("_calc" not in pg2.evaluate("()=>window.__file"), "保存 JSON に派生値は入らない")
    pg2.close()

    # ===== projects が無い「空の器」でも ＋案件 から書き始められる =====
    # 統合版は「課題も計画も無いファイル」では計画表示に寄る規則なので、単体版だけで見る
    if not UNIFIED:
        pg3 = new_page(b2, viewport={"width": 1500, "height": 900})
        pg3.on("pageerror", lambda e: errors.append(str(e)))
        pg3.on("dialog", lambda d: (dialogs.append(d.message), d.accept("2件目")))
        pg3.add_init_script(granted_handle_init({"name": "空の器"}))
        pg3.goto(VIEWER)
        pg3.click(S("#openBtn")); pg3.wait_for_timeout(250)
        n = len(dialogs)
        pg3.click(S("#editBtn")); pg3.wait_for_timeout(350)
        check(not any("v0.1" in d for d in dialogs[n:]),
              f"編集ONで旧形式の変換確認は出ない（読み替えは廃止した） -> {dialogs[n:] or None}")
        pg3.click(S('#tabBar [data-act="addproj"]')); pg3.wait_for_timeout(650)
        sv = json.loads(pg3.evaluate("()=>window.__file"))
        check(sv.get("projects") == [{"name": "2件目", "issues": []}],
              f"projects が無いファイルでも ＋案件 で書き始められる -> {sv.get('projects')}")
        check("sheets" not in sv and "issues" not in sv, f"旧キーは作らない -> {sorted(sv)}")
        pg3.close()

    # ===== 性能：5案件×200件（開いている案件だけ描く証拠） =====
    pg4 = new_page(b2, viewport={"width": 1500, "height": 500})   # 低い画面＝帯が潰れやすい条件でも押せること
    perr = []
    pg4.on("pageerror", lambda e: perr.append(str(e)))
    pg4.on("console", lambda m: perr.append("console:" + m.text) if m.type == "error" else None)
    pg4.goto(VIEWER)
    fs = [pg4.evaluate("d=>{const a=performance.now();window.renderData(d);return performance.now()-a;}", BIG)
          for _ in range(PERF_N)]
    check(pg4.eval_on_selector_all(S("#tabBar .stab"), "e=>e.length") == 6, "サマリ＋5案件のタブ")
    check(pg4.eval_on_selector_all(S("#tbody tr"), "e=>e.length") == 200,
          f"DOM の行数＝開いている案件の件数（他案件は描いていない） -> {pg4.eval_on_selector_all(S('#tbody tr'), 'e=>e.length')}")
    # 合否は中央値。最大値は負荷のスパイクを拾うので [実測] 行に出すだけにする
    check(median(fs) < MAX_FIRST_MS,
          f"描画 中央値 {median(fs):.0f}ms < {MAX_FIRST_MS}ms（1000件・5案件・{PERF_N}回／最大 {max(fs):.0f}ms）")
    # 実ポインタで押す。計測はページ内で開始（capture フェーズ）＝クリック送出の往復を計測に含めない
    pg4.evaluate(J("()=>{document.getElementById('tabBar').addEventListener('click',"
                   "()=>{window.__t0=performance.now();},true);}"))
    sw = []
    for si in (1, 2, 3, 4, 0):
        pg4.click(S(f"#tabBar .stab[data-si='{si}']"), timeout=3000)
        sw.append(pg4.evaluate("()=>performance.now()-window.__t0"))
        check(pg4.eval_on_selector_all(S("#tbody tr"), "e=>e.length") == 200, f"切替後も行数は200（案件{si}）")
    check(median(sw) < MAX_SWITCH_MS,
          f"タブ切替 中央値 {median(sw):.0f}ms < {MAX_SWITCH_MS}ms（{PERF_N}回／最大 {max(sw):.0f}ms）")
    ts = []
    for n, si in enumerate((1, 2, 3, 4, 0)):     # 200行の案件 → サマリ を PERF_N 回（最後はサマリで終わる）
        pg4.click(S("#tabBar .stab[data-summary]"), timeout=3000)
        ts.append(pg4.evaluate("()=>performance.now()-window.__t0"))
        if n < PERF_N - 1:
            pg4.click(S(f"#tabBar .stab[data-si='{si}']"), timeout=3000)
    check(median(ts) < MAX_SWITCH_MS and pg4.eval_on_selector_all(S("#tbody tr"), "e=>e.length") == 6,
          f"サマリ表示 中央値 {median(ts):.0f}ms・6行（5案件＋合計／最大 {max(ts):.0f}ms）")
    check(not perr, f"大量データで JS エラー無し -> {perr}")
    print(f"     [実測] 描画 {[round(x) for x in fs]}ms / タブ切替 {[round(x) for x in sw]}ms"
          f" / サマリ {[round(x) for x in ts]}ms（合否は中央値）")
    b2.close()
finish(errors)
