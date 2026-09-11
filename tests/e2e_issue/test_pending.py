"""止まっている理由＝待ち／凍結の2つ。催促（until 切れ）の導出・2ボタン・フォーム・保存JSON。
   本日=CLOCK_PIN(2026-09-15)。単体版・統合版の両方で回る。"""
import json
from playwright.sync_api import sync_playwright
from common import (S, VIEWER, action, book, check, finish, frozen,
                    granted_handle_init, issue, new_page, waiting)

D = book([
    issue(1, "回答待ちの課題", due="2026-09-30",
          pending=waiting("開発部", "変換仕様の回答", "2026-09-06", "2026-09-12"),
          actions=[action("2026-09-14", "問い合わせ", "ぴぐお", True)]),
    issue(2, "期限内の待ち", pending=waiting("企画部", "画面案の確認", "2026-09-06", "2026-09-20")),
    issue(3, "凍結の課題", pending=frozen("v0.1 をリリースしたら", "2026-09-06")),
    issue(4, "完了した課題", pending=waiting("X", "回答", "2026-09-01", "2026-09-02"),
          closed={"at": "2026-09-14", "how": "resolved", "note": "直った"},
          actions=[action("2026-09-14", "直した", "", True)]),
    # 異常系：kind が既知値（waiting/frozen）以外 → pending は「無いもの」として描く（印を出さない）
    issue(5, "kind が壊れている", pending={"kind": "???", "since": "2026-09-06"}),
])

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
                                            "e=>e.map(x=>[x.className.replace('mk ',''), x.innerText])")
    pg.click(S("#openBtn")); pg.wait_for_timeout(350)

    # ===== 状態列の印 =====
    # 印は 待ち → 待ちN日 → 凍結 → 未決 → ⚠催促 → 未着手N日 の順に縦に並ぶ
    kinds = lambda n: [m[0].split()[0] for m in mks(n)]
    check(mks(1)[0] == ["mk-wait", "待ち 開発部（9/12）"] and "mk-nudge" in kinds(1),
          f"待ちは 相手（期限）・期限切れは ⚠ 催促 -> {mks(1)}")
    check(mks(2)[0] == ["mk-wait", "待ち 企画部（9/20）"] and "mk-nudge" not in kinds(2),
          f"期限内なら催促は付かない -> {mks(2)}")
    check(mks(3)[0] == ["mk-frozen", "凍結 v0.1 をリリースしたら"], f"凍結は再開条件を添える -> {mks(3)}")
    check(mks(4) == [], f"完了した課題には印を付けない（待ち・催促・経過日数とも） -> {mks(4)}")
    check([m for m in mks(5) if m[0].split()[0] in ("mk-wait", "mk-frozen", "mk-nudge")] == [],
          f"kind が既知値以外なら印を出さない（pending は無いものとして描く） -> {mks(5)}")
    # 経過日数（待ち＝since から・未着手＝opened から）
    check(["待ち 9日"] == [m[1] for m in mks(1) if m[0] == "mk-days" and m[1].startswith("待ち")],
          f"待ちは「待ち N 日」（since から） -> {mks(1)}")
    check([m[1] for m in mks(2) if m[1].startswith("未着手")] == ["未着手 14日"],
          f"未着手は「未着手 N 日」（opened から） -> {mks(2)}")
    check("mk-old" in [m[0] for m in mks(2)][-1], "7日以上の未着手は橙で目立たせる")
    check(pg.eval_on_selector(S("#tbody tr:nth-child(1) .mk-nudge"), "e=>getComputedStyle(e).color")
          == "rgb(192, 57, 43)", "催促は期限超過と同じ赤系")
    check("催促" in pg.eval_on_selector(S("#tbody tr:nth-child(1) .mk-nudge"), "e=>e.title")
          and "返事" in pg.eval_on_selector(S("#tbody tr:nth-child(1) .mk-nudge"), "e=>e.title"),
          "催促のツールチップで「何をすればいいか」が分かる")

    # ===== 概要の1行 =====
    check("待ち：開発部に変換仕様の回答（9/6〜・9/12 まで）" in dtl(1), f"待ちの1行 -> {dtl(1)!r}")
    check("凍結：v0.1 をリリースしたら再開（9/6〜）" in dtl(3), f"凍結の1行 -> {dtl(3)!r}")
    check("保留" not in dtl(1) and "保留" not in dtl(3), "「保留」という言葉は使わない")

    # ===== 右上の件数・サマリ =====
    cnt = pg.inner_text(S("#counts")).replace("\n", " ")
    check("待ち 2" in cnt and "凍結 1" in cnt and "催促 1" in cnt,
          f"件数＝待ち2（完了と kind 不正は除く）・凍結1・催促1 -> {cnt!r}")

    # ===== 編集：待ち／凍結の2ボタン =====
    pg.click(S("#editBtn")); pg.wait_for_timeout(400)
    btns = lambda n: pg.eval_on_selector_all(S(f"#tbody tr:nth-child({n}) .stbtns button"),
                                             "e=>e.map(x=>x.textContent)")
    check(btns(1) == ["解除", "凍結", "クローズ"], f"待ちが付いていれば「解除」＋凍結 -> {btns(1)}")
    check(btns(3) == ["待ち", "解除", "クローズ"], f"凍結が付いていれば待ち＋「解除」 -> {btns(3)}")
    check(btns(2)[0] == "解除" and btns(2)[1] == "凍結", "どちらか1つだけが「解除」になる")

    # 待ちフォーム
    pg.click(S('#tbody tr:nth-child(3) [data-act="wait"]')); pg.wait_for_timeout(300)
    pg.fill("#isForm input[data-fm='who']", "情シス")
    pg.fill("#isForm input[data-fm='what']", "接続情報の払い出し")
    pg.fill("#isForm input[data-field='__until']", "09-25")
    pg.click("#isForm .fm-ok"); pg.wait_for_timeout(700)
    check(saved()[2]["pending"] == {"kind": "waiting", "since": "2026-09-15", "who": "情シス",
                                    "what": "接続情報の払い出し", "until": "2026-09-25"},
          f"待ちフォーム＝誰を/何を/いつまで -> {saved()[2]['pending']}")
    check(mks(3)[0] == ["mk-wait", "待ち 情シス（9/25）"], "凍結は上書きされて待ちになる（同時には持てない）")
    # 凍結フォーム
    pg.click(S('#tbody tr:nth-child(3) [data-act="frozen"]')); pg.wait_for_timeout(300)
    pg.fill("#isForm input[data-fm='resumeWhen']", "移行が終わったら")
    pg.click("#isForm .fm-ok"); pg.wait_for_timeout(700)
    check(saved()[2]["pending"] == {"kind": "frozen", "since": "2026-09-15",
                                    "resumeWhen": "移行が終わったら", "detail": ""},
          f"凍結フォーム＝再開条件 -> {saved()[2]['pending']}")
    # 解除
    pg.click(S('#tbody tr:nth-child(3) [data-act="unpend"]')); pg.wait_for_timeout(700)
    check(saved()[2]["pending"] is None, "解除で pending は null")
    check([m for m in mks(3) if m[0] != "mk-days" or not m[1].startswith("待ち")] == mks(3)
          and not [m for m in mks(3) if m[0].startswith("mk-wait")], "解除すると待ちの印は消える")
    # 期限を空にしたら until は null（ゴミを書かない）
    pg.click(S('#tbody tr:nth-child(3) [data-act="wait"]')); pg.wait_for_timeout(300)
    pg.fill("#isForm input[data-fm='who']", "誰か")
    pg.click("#isForm .fm-ok"); pg.wait_for_timeout(700)
    check(saved()[2]["pending"]["until"] is None, "いつまでが空なら until は null")

    raw = pg.evaluate("()=>window.__file")
    check('"reason"' not in raw, "旧キー reason は書かない")
    check("_calc" not in raw, "派生値 _calc は書かない")
    check(not errors, f"JS エラーが出ない -> {errors[:2]}")
    b.close()
finish(errors)
