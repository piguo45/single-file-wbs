"""★＝更新期間に動いたもの（導出・JSONには書かない）。画面では「更新」という言葉を添える。
   期間はトップレベルの任意 star:{from,to}（to 省略＝本日）。無い/不正/from>to は既定＝本日を含む直近7日。
   本日=CLOCK_PIN(2026-09-15)固定なので、既定期間は 9/9〜9/15。"""
import json
from playwright.sync_api import sync_playwright
from common import (S, VIEWER, action, book, check, decision, finish, frozen,
                    granted_handle_init, issue, new_page, waiting)

SR = {"from": "2026-09-01", "to": "2026-09-07"}
OLD_DEC = [decision("対応方針", "2026-08-01", "2026-08-01", "やる")]

ISSUES = [
    # #1 済みの行動：期間内だけ★（期間外・date:null・未 には付けない）
    issue(1, "行動の★", actions=[action("2026-09-03", "期間内の済み", "ぴぐお", True),
                                 action("2026-08-20", "期間外の済み", "ぴぐお", True),
                                 action(None, "日付なしの済み", "ぴぐお", True),
                                 action("2026-09-04", "期間内だが未", "ぴぐお", False)]),
    # #2 decisions[].decided が期間内（since は数えない）
    issue(2, "決定の★", decisions=[decision("やるか", "2026-08-01", "2026-09-05", "やる")],
          actions=[action("2026-08-01", "昔の済み", "", True)]),
    # #3 pending.since が期間内
    issue(3, "待ちの★", decisions=OLD_DEC,
          pending=waiting("開発部", "回答", "2026-09-02")),
    # #4 closed.at が期間内（★だけは印の例外＝完了にも付く。「今週閉じた」を報告に載せるため）
    issue(4, "完了の★", decisions=OLD_DEC,
          closed={"at": "2026-09-06", "how": "resolved", "note": "確認"}),
    # #5 すべて期間外 → ★なし
    issue(5, "★なし", decisions=OLD_DEC, actions=[action("2026-08-02", "昔", "", True)]),
    # #6 既定期間（9/9〜9/15）の境界確認用：9/15=本日 と 9/9=起点 は入る／9/8 は入らない
    issue(6, "既定期間の境界", actions=[action("2026-09-15", "本日の済み", "", True),
                                        action("2026-09-09", "起点の済み", "", True),
                                        action("2026-09-08", "起点の前日の済み", "", True)]),
]
DATA = book(ISSUES, name="★テスト", star=dict(SR))
NO_STAR = book(ISSUES, name="★テスト")

errors, dialogs = [], []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_page(b, viewport={"width": 1500, "height": 900})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    pg.add_init_script(granted_handle_init(NO_STAR))
    pg.goto(VIEWER)

    titles = lambda: pg.eval_on_selector_all(S("#tbody tr"),
        "e=>e.map(x=>[x.querySelector('td.num').innerText, !!x.querySelector('td.title .star')])")
    nstar = lambda: pg.inner_text(S("#starCount"))
    rng = lambda: pg.inner_text(S("#starRange"))

    # --- (a) 済みの行動：期間内だけ★ ---
    pg.evaluate("d=>window.renderData(d)", DATA); pg.wait_for_timeout(250)
    acts = pg.eval_on_selector_all(S("#tbody tr:nth-child(1) .act"),
        "e=>e.map(x=>[x.querySelector('.star').innerText, x.querySelector('.at').innerText])")
    check(acts == [["★", "期間内の済み"], ["", "期間外の済み"], ["", "日付なしの済み"], ["", "期間内だが未"]],
          f"(a) 済み×期間内だけ★（期間外/date:null/未 には付けない） -> {acts}")
    tip = pg.eval_on_selector(S("#tbody tr:nth-child(1) .act .star"), "e=>e.getAttribute('title')")
    check(tip == "更新（期間内）", f"(a) ★にツールチップ -> {tip!r}")
    col = pg.eval_on_selector_all(S("#tbody .star"),
        "e=>[...new Set(e.filter(x=>x.innerText==='★').map(x=>getComputedStyle(x).color))]")
    check(col == ["rgb(31, 36, 48)"], f"(a) ★は黒（判定は色に依らない） -> {col}")

    # --- (b) 状態の変化（決定／保留／完了）が期間内なら、その行に★ ---
    lnstar = lambda n: pg.eval_on_selector_all(S(f"#tbody tr:nth-child({n}) .ln"),
        "e=>e.map(x=>[!!x.querySelector('.star'), x.querySelector('.lb').innerText])")
    check([x for x in lnstar(2) if x[0]] == [[True, "方針："]], f"(b) decided が期間内 → 方針の行に★ -> {lnstar(2)}")
    check([x for x in lnstar(3) if x[0]] == [[True, "待ち："]], f"(b) pending.since が期間内 → 待ちの行に★ -> {lnstar(3)}")
    check([x for x in lnstar(4) if x[0]] == [[True, "完了："]], f"(b) closed.at が期間内 → 完了の行に★ -> {lnstar(4)}")
    check(pg.eval_on_selector_all(S("#tbody tr:nth-child(5) .star"), "e=>e.filter(x=>x.innerText==='★').length") == 0,
          "(b) すべて期間外の課題には★が1つも無い")

    # --- (c) タイトル列の★と「★ N」 ---
    check(titles() == [["1", True], ["2", True], ["3", True], ["4", True], ["5", False], ["6", False]],
          f"(c) ★は印の例外＝完了(#4)にも付く（今週閉じたことを報告するため） -> {titles()}")
    check(nstar() == "4", f"(c) サマリの ★ N ＝ ★のある課題数（完了込み） -> {nstar()}")
    ttip = pg.eval_on_selector(S("#tbody tr:nth-child(1) td.title .star"), "e=>e.getAttribute('title')")
    check(ttip == "更新あり（期間内に動いた課題）", f"(c) タイトル★のツールチップ -> {ttip!r}")
    check(rng() == "更新期間 9/1〜9/7", f"(c) メタ行は「更新期間」と言葉で示す -> {rng()!r}")
    check(pg.inner_text(S("#counts")).endswith("★ 更新 4"), f"(c) 件数は「★ 更新 N」 -> {pg.inner_text(S('#counts'))!r}")
    # たたんでもタイトルの★は残る
    pg.click(S("#allCaret")); pg.wait_for_timeout(200)
    check([t for _, t in titles()] == [True, True, True, True, False, False], "(c) たたんでもタイトルの★は出る")
    pg.click(S("#allCaret")); pg.wait_for_timeout(200)

    # --- (d) star が無ければ既定＝本日を含む直近7日（9/9〜9/15） ---
    pg.evaluate("d=>window.renderData(d)", NO_STAR); pg.wait_for_timeout(250)
    check(rng() == "更新期間 直近7日", f"(d) 既定は「更新期間 直近7日」表示 -> {rng()!r}")
    check(titles() == [["1", False], ["2", False], ["3", False], ["4", False], ["5", False], ["6", True]],
          f"(d) 既定期間では #6 だけ★ -> {titles()}")
    check(nstar() == "1", f"(d) ★N -> {nstar()}")
    d6 = pg.eval_on_selector_all(S("#tbody tr:nth-child(6) .act"),
        "e=>e.map(x=>[x.querySelector('.star').innerText, x.querySelector('.at').innerText])")
    check(d6 == [["★", "本日の済み"], ["★", "起点の済み"], ["", "起点の前日の済み"]],
          f"(d) 既定期間は本日(9/15)と起点(9/9)を含み、その前日(9/8)は含まない -> {d6}")

    # --- (e) 不正な star は既定へ落とす（落ちない） ---
    for label, bad in [("月日が範囲外", {"from": "2026-13-99"}), ("from>to", {"from": "2026-09-10", "to": "2026-09-01"}),
                       ("非オブジェクト", "abc"), ("from が無い", {"to": "2026-09-07"}),
                       ("to が不正", {"from": "2026-09-01", "to": "x"})]:
        pg.evaluate("d=>window.renderData(d)", dict(NO_STAR, star=bad)); pg.wait_for_timeout(150)
        check(rng() == "更新期間 直近7日", f"(e) 不正な star（{label}）は既定 -> {rng()!r}")
    # to 省略＝本日
    pg.evaluate("d=>window.renderData(d)", dict(NO_STAR, star={"from": "2026-09-09"})); pg.wait_for_timeout(150)
    check(rng() == "更新期間 9/9〜9/15", f"(e) to 省略＝本日 -> {rng()!r}")

    # --- (f) 編集モードで更新期間を直す ---
    pg.click(S("#openBtn")); pg.wait_for_timeout(250)
    pg.click(S("#editBtn")); pg.wait_for_timeout(300)
    saved = lambda: json.loads(pg.evaluate("()=>window.__file"))
    check("star" not in saved(), "(f) 既定のまま＝JSON に star を書き戻さない")
    check(pg.eval_on_selector_all(S('#stat input[data-star]'), "e=>e.length") == 2,
          "(f) 編集モードでは from/to の入力が出る")
    check(pg.inner_text(S("#stat .srng")).startswith("更新期間"),
          f"(f) 入力欄のラベルも「更新期間」 -> {pg.inner_text(S('#stat .srng'))!r}")

    for f, v in (("from", "0901"), ("to", "0907")):          # 短縮入力（年は本日から補完）
        pg.fill(S(f'#stat input[data-star="{f}"]'), v)
        pg.dispatch_event(S(f'#stat input[data-star="{f}"]'), "change")
    pg.wait_for_timeout(700)
    check(saved().get("star") == {"from": "2026-09-01", "to": "2026-09-07"},
          f"(f) 編集した期間が star として保存される -> {saved().get('star')}")
    txt = pg.evaluate("()=>window.__file")
    check(all(k not in txt for k in ('"hasStar"', '"starActs"', '"starDecs"', '"_calc"')),
          "(f) ★の判定結果（派生値）は JSON に書かれない")

    pg.evaluate("()=>document.activeElement && document.activeElement.blur()")
    pg.wait_for_timeout(500)                                  # deferRender を待って導出表示を見る
    check(nstar() == "4", f"(f) 期間を変えると★の件数も変わる -> {nstar()}")

    pg.fill(S('#stat input[data-star="from"]'), "")              # from を空に＝既定へ戻す
    pg.dispatch_event(S('#stat input[data-star="from"]'), "change")
    pg.wait_for_timeout(700)
    check("star" not in saved(), f"(f) from を空にすると star キーごと消える -> {sorted(saved())}")
    pg.evaluate("()=>document.activeElement && document.activeElement.blur()")
    pg.wait_for_timeout(500)
    check(pg.inner_text(S("#starCount")) == "1", "(f) 既定に戻ると★の件数も既定期間のものになる")
    b.close()
finish(errors)
