"""フィルタバー：状態(#91)＋遅延(#92)。表示専用＝行を間引くだけ・データ/横軸は不変。
状態=3排他ON/OFF・遅延=遅れてるタスクのみ・軸間AND・親残し判定・左右の高さ同期・横軸固定・サマリ不変・永続化・全OFF graceful。
本日=CLOCK_PIN(2026-06-15)固定。done=実績終了あり / wip=着手のみ / todo=実績なし。1.2は予定終了6/12<本日=overdue(遅延)。"""
from playwright.sync_api import sync_playwright
from common import VIEWER, check, finish, leaf, granted_handle_init, new_page

# P: 工程1(=done/wip/todo混在→完了OFFでも親は残る) ＋ 工程2(=全子done→完了OFFで親ごと消える)
# 1.2は予定終了6/12<本日6/15かつ未完=overdue（遅延フィルタで唯一残る）
DATA = {"projects": [{"name": "P", "milestones": [], "tasks": [
    {"id": "1", "name": "工程1", "children": [
        leaf("1.1", "完了タスク",   asg="佐藤", ps="2026-06-01", pe="2026-06-05", as_="2026-06-01", ae="2026-06-10"),
        leaf("1.2", "進行中タスク", asg="田中", ps="2026-06-08", pe="2026-06-12", as_="2026-06-12"),
        leaf("1.3", "未着手タスク", asg="佐藤", ps="2026-06-18", pe="2026-06-25")]},
    {"id": "2", "name": "工程2", "children": [
        leaf("2.1", "完了のみ", asg="鈴木", ps="2026-06-01", pe="2026-06-05", as_="2026-06-01", ae="2026-06-09")]}]}]}

errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_page(b, viewport={"width": 1500, "height": 600})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.add_init_script(granted_handle_init(DATA))
    pg.goto(VIEWER)
    pg.click("#openBtn"); pg.wait_for_timeout(200)

    nL = lambda: pg.eval_on_selector_all("#leftRows .lrow", "e=>e.length")
    nG = lambda: pg.eval_on_selector_all("#rightBody .grow", "e=>e.length")
    nDays = lambda: pg.eval_on_selector_all("#dates .d", "e=>e.length")
    leafNames = lambda: pg.eval_on_selector_all("#leftRows .lrow .nm", "e=>e.map(x=>x.textContent)")

    # 移設(#91/4.4.4)：トグルは左の情報表の真上の「フィルタバー」にある（topbarでない）
    nState = pg.eval_on_selector_all('#filterBar .sf-btn[data-state]', "e=>e.length")
    nDelay = pg.eval_on_selector_all('#filterBar .sf-btn[data-delay]', "e=>e.length")
    inTop = pg.eval_on_selector_all("#topbar .sf-btn", "e=>e.length")
    check(nState == 3 and nDelay == 1 and inTop == 0, f"状態3+遅延1がフィルタバー内・topbarに無い ({nState}+{nDelay}/{inTop})")
    check(pg.is_visible("#filterBar"), "データ読込でフィルタバーが表示される")

    # 既定=全ON：proj(1)+工程1+1.1/1.2/1.3+工程2+2.1 = 7行・左右一致
    check(nL() == 7, f"既定全ONで全7行 -> {nL()}")
    check(nL() == nG(), f"左右の行数が一致(高さ同期) {nL()}/{nG()}")
    summaryAll = pg.inner_text("#stat")
    daysAll = nDays()

    # 完了をOFF：1.1と2.1が消え、工程2(全子done)も親ごと消える。工程1は1.2/1.3が残るので残る
    pg.click('.sf-btn[data-state="done"]'); pg.wait_for_timeout(200)
    names = leafNames()
    check(nL() == 4, f"完了OFFで4行(proj+工程1+1.2+1.3) -> {nL()} {names}")
    check(nL() == nG(), f"完了OFF後も左右一致(高さ同期) {nL()}/{nG()}")
    check(not any("完了" in n for n in names), f"完了タスクが消えた -> {names}")
    check(any("工程1" in n for n in names) and not any(n.strip() == "工程2" for n in names),
          f"親残し判定:工程1は残り工程2は消える -> {names}")

    # 横軸は固定（行を隠しても時間軸の日数は不変＝バーが動いて見えない・#91核心）
    check(nDays() == daysAll, f"横軸の日数が不変(固定) {nDays()}/{daysAll}")
    # サマリ(工数/進捗/遅延)は完了込みのまま不変＝誠実なview
    check(pg.inner_text("#stat") == summaryAll, "全体サマリは隠しても不変(完了込み)")
    # 押下式の見た目：完了ピルはOFF表示（onクラスが外れる）
    doneOn = pg.eval_on_selector('.sf-btn[data-state="done"]', "e=>e.classList.contains('on')")
    check(doneOn is False, "完了ピルはOFF状態(onクラスなし)")
    # localStorageに永続化（残ON=未着手/進行中）
    saved = pg.evaluate("()=>localStorage.getItem('wbsStateFilter')")
    check(saved and "done" not in saved and "todo" in saved and "wip" in saved,
          f"フィルタ状態がlocalStorageに保存 -> {saved}")

    # 全OFF：空表示でもクラッシュしない（graceful）
    pg.click('.sf-btn[data-state="todo"]'); pg.wait_for_timeout(80)
    pg.click('.sf-btn[data-state="wip"]'); pg.wait_for_timeout(150)
    check(nL() == 0 and nG() == 0, f"全OFFで空表示・左右0行 {nL()}/{nG()}")
    check(nDays() == daysAll, f"全OFFでも横軸は不変 {nDays()}/{daysAll}")

    # 再ON：完了を戻すと完了タスクが復活（表示専用＝データは消えていない）
    pg.click('.sf-btn[data-state="done"]'); pg.wait_for_timeout(150)
    check(any("完了" in n for n in leafNames()), "完了を再ONで復活(目隠しであって削除でない)")

    # ===== 遅延フィルタ(#92) =====
    pg.click('.sf-btn[data-state="todo"]'); pg.click('.sf-btn[data-state="wip"]'); pg.wait_for_timeout(150)  # 状態を全ONに戻す
    check(nL() == 7, f"遅延テスト前提:状態全ONで7行 -> {nL()}")
    # 遅延のみON：1.2(overdue)だけ残る。1.1/2.1(done)・1.3(未来todo)は遅延でない
    pg.click('.sf-btn[data-delay="1"]'); pg.wait_for_timeout(200)
    dn = leafNames()
    check(nL() == 3, f"遅延ON=遅れてる1.2のみ→proj+工程1+1.2=3行 -> {nL()} {dn}")
    check(nL() == nG(), f"遅延ON後も左右一致(高さ同期) {nL()}/{nG()}")
    check(any("進行中" in n for n in dn) and not any(("未着手" in n or "完了" in n) for n in dn),
          f"遅れてるタスクだけ(進行中overdue)・未着手/完了は出ない -> {dn}")
    check(nDays() == daysAll, f"遅延ONでも横軸は不変 {nDays()}/{daysAll}")
    check(pg.inner_text("#stat") == summaryAll, "遅延ONでもサマリ不変(誠実なview)")
    dOn = pg.eval_on_selector('.sf-btn[data-delay="1"]', "e=>e.classList.contains('on')")
    check(dOn is True and pg.evaluate("()=>localStorage.getItem('wbsDelayOnly')") == "1",
          f"遅延ピルON・localStorage保存 (on={dOn})")
    # 軸間AND：遅延ON かつ 状態=未着手のみ → 未着手で遅れてるもの=無し(1.3は未来)＝0行
    pg.click('.sf-btn[data-state="wip"]'); pg.click('.sf-btn[data-state="done"]'); pg.wait_for_timeout(150)
    check(nL() == 0, f"軸間AND:未着手∩遅延=空(1.3は未来)→0行 -> {nL()}")
    # 遅延OFF＋状態全ON→全復活（表示専用＝消えていない）
    pg.click('.sf-btn[data-delay="1"]'); pg.click('.sf-btn[data-state="wip"]'); pg.click('.sf-btn[data-state="done"]'); pg.wait_for_timeout(150)
    check(nL() == 7, f"遅延OFF+状態全ONで全復活7行 -> {nL()}")
    check(pg.evaluate("()=>localStorage.getItem('wbsDelayOnly')") == "0", "遅延OFFがlocalStorageに保存")

    # ===== 担当フィルタ(#93) ===== (開始状態:状態全ON・遅延OFF・担当全員=7行)
    pg.click(".asg-dd > summary"); pg.wait_for_timeout(150)   # ドロップダウンを開く
    asgs = pg.eval_on_selector_all(".asg-list .asg-cb", "e=>e.map(x=>x.getAttribute('data-asg'))")
    check(sorted(asgs) == ["佐藤", "田中", "鈴木"], f"担当を動的収集(重複なし) -> {asgs}")
    # 佐藤を外す→1.1/1.3(佐藤)が消える。工程2(2.1鈴木)は残る
    pg.click('.asg-cb[data-asg="佐藤"]'); pg.wait_for_timeout(200)
    check(nL() == 5, f"佐藤OFF→proj+工程1+1.2+工程2+2.1=5行 -> {nL()}")
    check(nL() == nG(), f"担当フィルタ後も左右一致(高さ同期) {nL()}/{nG()}")
    check(nDays() == daysAll, f"担当フィルタでも横軸不変 {nDays()}/{daysAll}")
    check(pg.inner_text("#stat") == summaryAll, "担当フィルタでもサマリ不変(誠実なview)")
    saved = pg.evaluate("()=>localStorage.getItem('wbsAsgOff')")
    check(saved and "佐藤" in saved, f"担当OFFがlocalStorageに保存 -> {saved}")
    check(pg.is_visible(".asg-list"), "チェック後もドロップダウンは開いたまま(開閉保持)")
    # 全解除→0行、田中だけチェック→3行(軸内OR/複数選択の基礎)
    pg.click(".asg-none"); pg.wait_for_timeout(150)
    check(nL() == 0, f"担当全解除で0行(graceful) -> {nL()}")
    pg.click('.asg-cb[data-asg="田中"]'); pg.wait_for_timeout(200)
    check(nL() == 3, f"田中のみ→proj+工程1+1.2=3行 -> {nL()}")
    # 軸間AND：担当=佐藤のみ × 状態=完了のみ → 1.1(佐藤+done)だけ＝proj+工程1+1.1=3行
    pg.click(".asg-none"); pg.click('.asg-cb[data-asg="佐藤"]'); pg.wait_for_timeout(120)
    pg.click('.sf-btn[data-state="wip"]'); pg.click('.sf-btn[data-state="todo"]'); pg.wait_for_timeout(150)
    adn = leafNames()
    check(nL() == 3 and any("完了タスク" in n for n in adn), f"軸間AND:佐藤∩完了=1.1→3行 -> {nL()} {adn}")
    # 全員に戻す＋状態全ON→全復活(表示専用＝担当データは消えていない)
    pg.click(".asg-all"); pg.click('.sf-btn[data-state="wip"]'); pg.click('.sf-btn[data-state="todo"]'); pg.wait_for_timeout(150)
    check(nL() == 7, f"担当全員+状態全ONで全復活7行 -> {nL()}")
    check(pg.evaluate("()=>localStorage.getItem('wbsAsgOff')") == "[]", "全員=空off集合がlocalStorageに保存")

    # ===== 期間フィルタ(#94) ===== 本日=月曜(2026-06-15)・週=6/15〜6/21
    check(pg.eval_on_selector_all(".seg-btn.on", "e=>e.length") == 1, "期間は単一選択(onは1つ)")
    # 今日(6/15)：実績が本日に重なる1.2だけ(1.1/2.1は過去完了・1.3は未来予定)
    pg.click('.seg-btn[data-period="today"]'); pg.wait_for_timeout(200)
    tn = leafNames()
    check(nL() == 3 and any("進行中" in n for n in tn), f"今日→本日に重なる1.2のみ=3行 -> {nL()} {tn}")
    check(nL() == nG(), f"期間フィルタ後も左右一致(高さ同期) {nL()}/{nG()}")
    check(nDays() == daysAll, f"期間フィルタでも横軸は不変(行だけ絞る) {nDays()}/{daysAll}")
    check(pg.inner_text("#stat") == summaryAll, "期間フィルタでもサマリ不変(誠実なview)")
    check(pg.evaluate("()=>localStorage.getItem('wbsPeriod')") == "today", "期間がlocalStorageに保存")
    # 今週(6/15-6/21)：1.2(実績)＋1.3(予定6/18-6/25が重なる)＝4行
    pg.click('.seg-btn[data-period="week"]'); pg.wait_for_timeout(200)
    wn = leafNames()
    check(nL() == 4 and any("未着手" in n for n in wn), f"今週→1.2+1.3(予定が週に重なる)=4行 -> {nL()} {wn}")
    # 全期間に戻す→全復活
    pg.click('.seg-btn[data-period="all"]'); pg.wait_for_timeout(150)
    check(nL() == 7, f"全期間で全復活7行 -> {nL()}")
    check(pg.evaluate("()=>localStorage.getItem('wbsPeriod')") == "all", "全期間がlocalStorageに保存")
    b.close()
finish(errors)
