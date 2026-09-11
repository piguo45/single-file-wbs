"""待ちの相手に課題を指定する（pending.who が {issue} / {project,issue}）：表示・リンク・
   相手が完了していたら催促・フォームの出し分け・別案件の呼び名。本日=CLOCK_PIN(2026-09-15)。"""
import json
from playwright.sync_api import sync_playwright
from common import (S, VIEWER, action, book, check, finish, granted_handle_init,
                    issue, issue_ref, new_page, waiting)

D = {"name": "待ちの相手", "projects": [
    {"name": "案件A", "issues": [
        issue(1, "同じ案件の課題を待つ",
              pending={"kind": "waiting", "since": "2026-09-06", "who": issue_ref(2),
                       "what": "完了", "until": None}),
        issue(2, "待たれている（未完了）"),
        issue(3, "別案件の課題を待つ",
              pending={"kind": "waiting", "since": "2026-09-06",
                       "who": issue_ref(5, "勤怠システム更改"), "what": "完了", "until": None}),
        issue(4, "相手が壊れている",
              pending={"kind": "waiting", "since": "2026-09-06", "who": {"project": "無い案件", "issue": 9},
                       "what": "回答", "until": None}),
        issue(5, "人名を待つ", pending=waiting("開発部", "仕様の回答", "2026-09-06"))]},
    {"name": "勤怠システム更改", "issues": [
        issue(5, "向こうの課題（完了済み）",
              closed={"at": "2026-09-10", "how": "resolved", "note": "済"},
              actions=[action("2026-09-10", "やった", "", True)])]}]}

with sync_playwright() as pw:
    b = pw.chromium.launch()
    errors = []
    pg = new_page(b, viewport={"width": 1500, "height": 1000})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script(granted_handle_init(D))
    pg.goto(VIEWER)
    saved = lambda: json.loads(pg.evaluate("()=>window.__file"))["projects"][0]["issues"]
    dtl = lambda n: pg.inner_text(S(f"#tbody tr:nth-child({n}) td.detail")).replace("\n", " ")
    mks = lambda n: pg.eval_on_selector_all(S(f"#tbody tr:nth-child({n}) td.state .mk"),
                                            "e=>e.map(x=>x.innerText)")
    pg.click(S("#openBtn")); pg.wait_for_timeout(350)

    # ===== 表示：待ち：課題 #2 の完了 =====
    check("待ち：課題 #2の完了" in dtl(1), f"同じ案件は「課題 #2」 -> {dtl(1)!r}")
    check("待ち：勤怠-5の完了" in dtl(3), f"別案件は略称「勤怠-5」 -> {dtl(3)!r}")
    ref = pg.eval_on_selector(S("#tbody tr:nth-child(3) .iref"), "e=>[e.textContent, e.title]")
    check(ref == ["勤怠-5", "勤怠システム更改 #5"], f"ツールチップは正式名 -> {ref}")
    check("待ち：開発部に仕様の回答" in dtl(5), f"人名のときは従来どおり -> {dtl(5)!r}")
    brk = pg.eval_on_selector(S("#tbody tr:nth-child(4) .iref"),
                              "e=>[e.className, getComputedStyle(e).textDecorationLine]")
    check("lk-x" in brk[0] and brk[1] == "line-through",
          f"相手が居なければ取り消し線（迷子の参照が見て分かる） -> {brk}")

    # ===== 状態列：待ちの相手を添える =====
    check(mks(1)[0] == "待ち 課題 #2", f"状態列にも相手 -> {mks(1)}")
    check(mks(3)[0] == "待ち 勤怠-5", f"状態列も略称 -> {mks(3)}")
    # 相手が居ない待ちは、印の側も links と同じ取り消し線＋「リンク先が見つかりません」
    mbrk = pg.eval_on_selector(S("#tbody tr:nth-child(4) .mk-wait .mksub"),
                               "e=>[e.className, e.title, getComputedStyle(e).textDecorationLine]")
    check("lk-x" in mbrk[0] and mbrk[1] == "リンク先が見つかりません" and mbrk[2] == "line-through",
          f"印の相手も壊れたリンク表示（待ち続ける理由が消えたのが見て分かる） -> {mbrk}")
    mok = pg.eval_on_selector(S("#tbody tr:nth-child(1) .mk-wait .mksub"),
                              "e=>[e.className, getComputedStyle(e).textDecorationLine]")
    check("lk-x" not in mok[0] and mok[1] == "none",
          f"相手が居る待ちには取り消し線を付けない -> {mok}")

    # ===== 相手が完了していたら催促 =====
    check(any("催促" in m for m in mks(3)), f"相手の課題が完了→催促 -> {mks(3)}")
    check(not any("催促" in m for m in mks(1)), f"相手が未完了なら催促しない -> {mks(1)}")
    tip = pg.eval_on_selector(S("#tbody tr:nth-child(3) td.state .mk-nudge"), "e=>e.title")
    check(tip == "相手の課題は完了しています。再開してください", f"理由の分かるツールチップ -> {tip!r}")
    cnt = pg.inner_text(S("#counts")).replace("\n", " ")
    check("⚠ 催促 1" in cnt, f"件数にも合流 -> {cnt!r}")

    # ===== 押すと飛ぶ =====
    pg.click(S("#tbody tr:nth-child(1) .iref")); pg.wait_for_timeout(400)
    check(pg.eval_on_selector_all(S("#tbody tr.jump td.num"), "e=>e.map(x=>x.innerText)") == ["2"],
          "待ちの相手を押すとその課題へ飛ぶ")

    # ===== 編集：相手の種類（人名／課題）を選べる =====
    pg.click(S("#editBtn")); pg.wait_for_timeout(400)
    pg.click(S('#tbody tr:nth-child(2) [data-act="wait"]')); pg.wait_for_timeout(300)
    kinds = pg.eval_on_selector_all('#isForm select[data-fm="whoKind"] option', "e=>e.map(x=>x.textContent)")
    check(kinds == ["人名", "課題"], f"相手は「人名」か「課題」 -> {kinds}")
    check(not pg.eval_on_selector('#isForm .fm-f[data-f="person"]', "e=>e.hidden")
          and pg.eval_on_selector('#isForm .fm-f[data-f="issue"]', "e=>e.hidden"),
          "既定は人名（課題の欄は隠す）")
    pg.select_option('#isForm select[data-fm="whoKind"]', "issue"); pg.wait_for_timeout(200)
    check(pg.eval_on_selector('#isForm .fm-f[data-f="person"]', "e=>e.hidden")
          and not pg.eval_on_selector('#isForm .fm-f[data-f="issue"]', "e=>e.hidden"),
          "「課題」を選ぶと案件＋番号の欄に切り替わる")
    pg.fill('#isForm input[data-fm="wissue"]', "1")
    pg.fill('#isForm input[data-fm="what"]', "方針が決まること")
    pg.click("#isForm .fm-ok"); pg.wait_for_timeout(700)
    check(saved()[1]["pending"] == {"kind": "waiting", "since": "2026-09-15",
                                    "who": {"issue": 1}, "what": "方針が決まること", "until": None},
          f"同じ案件は {{issue}} だけで書く -> {saved()[1]['pending']}")
    # 待ちが付いた行のボタンは「解除」になる（同時に2つは持てない）
    check(pg.eval_on_selector_all(S('#tbody tr:nth-child(2) [data-act="wait"]'), "e=>e.length") == 0
          and pg.eval_on_selector_all(S('#tbody tr:nth-child(2) [data-act="unpend"]'), "e=>e.length") == 1,
          "待ちを付けるとそのボタンは「解除」になる")
    # 壊れた相手を持つ行（#4）を、別案件の課題を待つように直す
    pg.click(S('#tbody tr:nth-child(4) [data-act="unpend"]')); pg.wait_for_timeout(600)
    pg.click(S('#tbody tr:nth-child(4) [data-act="wait"]')); pg.wait_for_timeout(300)
    pg.select_option('#isForm select[data-fm="whoKind"]', "issue"); pg.wait_for_timeout(200)
    pg.select_option('#isForm select[data-fm="wproj"]', "勤怠システム更改")
    pg.fill('#isForm input[data-fm="wissue"]', "5")
    pg.click("#isForm .fm-ok"); pg.wait_for_timeout(700)
    check(saved()[3]["pending"]["who"] == {"project": "勤怠システム更改", "issue": 5},
          f"別案件は project 付き -> {saved()[3]['pending']['who']}")
    check(any("催促" in m for m in mks(4)), f"相手が完了済みなので催促が付く -> {mks(4)}")
    # 存在しない番号は受け付けない（人名の待ちを課題に付け替えようとして失敗させる）
    pg.click(S('#tbody tr:nth-child(5) [data-act="unpend"]')); pg.wait_for_timeout(600)
    pg.click(S('#tbody tr:nth-child(5) [data-act="wait"]')); pg.wait_for_timeout(300)
    pg.select_option('#isForm select[data-fm="whoKind"]', "issue"); pg.wait_for_timeout(200)
    pg.fill('#isForm input[data-fm="wissue"]', "99")
    pg.click("#isForm .fm-ok"); pg.wait_for_timeout(400)
    check(saved()[4]["pending"] is None, "存在しない番号では書かない（解除したままにする）")
    check(pg.eval_on_selector_all("#isForm", "e=>e.length") == 1, "拒否のときフォームは閉じない")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    raw = pg.evaluate("()=>window.__file")
    check("_calc" not in raw, "派生値 _calc は書かない")
    check(not errors, f"JS エラーが出ない -> {errors[:2]}")
    b.close()
finish(errors)
