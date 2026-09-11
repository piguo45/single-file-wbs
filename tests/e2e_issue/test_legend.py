"""凡例ボタン（操作バーの EN の左）：課題ビューだけに出る・吹き出し10行・ja/en・開閉。
   統合版では計画ビューで出さない（wbs の見た目＝pixel を変えないため）。"""
from playwright.sync_api import sync_playwright
from common import S, UNIFIED, VIEWER, book, check, decision, finish, granted_handle_init, issue, new_page

D = book([issue(1, "凡例テスト", decisions=[decision("決めること", "2026-09-02")])])

with sync_playwright() as pw:
    b = pw.chromium.launch()
    errors = []
    pg = new_page(b, viewport={"width": 1500, "height": 900})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script(granted_handle_init(D))
    pg.goto(VIEWER)
    pg.click(S("#openBtn")); pg.wait_for_timeout(350)
    lines = lambda: pg.eval_on_selector_all("#legendPop .lg-h,#legendPop .lg-b", "e=>e.map(x=>x.innerText)")

    # ===== 置き場所：EN の左・操作バーの中 =====
    geo = pg.evaluate("""()=>{const r=e=>e.getBoundingClientRect();
        const lg=document.getElementById('legendBtn'), en=document.getElementById('langBtn'),
              tp=document.getElementById('topbar');
        if(!lg)return null;
        return [Math.round(r(lg).right)<=Math.round(r(en).left)+1,
                r(lg).top>=r(tp).top-0.5 && r(lg).bottom<=r(tp).bottom+0.5,
                getComputedStyle(lg).display!=='none'];}""")
    check(geo is not None, "凡例ボタンが操作バーにある")
    check(geo[0], "凡例は EN の左に置く")
    check(geo[1], "凡例は操作バーの中に収まる（はみ出さない）")
    check(geo[2], "課題ビューでは見える")

    # ===== 吹き出し＝10行・見出しと本文 =====
    pg.click(S("#legendBtn")); pg.wait_for_timeout(250)
    ls = lines()
    check(len(ls) == 10, f"凡例は10行 -> {len(ls)}行")
    check(pg.eval_on_selector("#legendPop .np-ttl", "e=>e.textContent") == "この画面の見かた", "題が付く")
    body = "\n".join(ls)
    for word in ("未着手", "対応中", "完了", "★", "期限超過", "催促", "待ち", "凍結", "未決",
                 "概要", "方針（未決）", "実績", "予定", "済", "未"):
        check(word in body, f"凡例に「{word}」の説明がある")
    check("JSON" in body, "「状態と印は毎回計算する（JSONに書かない）」を書く")

    # ===== 開閉 =====
    pg.click(S("#legendBtn")); pg.wait_for_timeout(200)
    check(pg.eval_on_selector_all("#legendPop", "e=>e.length") == 0, "もう一度押すと閉じる")
    pg.click(S("#legendBtn")); pg.wait_for_timeout(200)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    check(pg.eval_on_selector_all("#legendPop", "e=>e.length") == 0, "Esc で閉じる")
    pg.click(S("#legendBtn")); pg.wait_for_timeout(200)
    pg.click(S("#tbody tr:nth-child(1) td.title .caret")); pg.wait_for_timeout(200)
    check(pg.eval_on_selector_all("#legendPop", "e=>e.length") == 0, "外側をクリックすると閉じる")

    # ===== 英語 =====
    pg.click(S("#langBtn")); pg.wait_for_timeout(300)
    check(pg.inner_text(S("#legendBtn")).strip() == "Legend", "EN でボタンも英語になる")
    pg.click(S("#legendBtn")); pg.wait_for_timeout(250)
    en = "\n".join(lines())
    check(len(lines()) == 10 and "Not started" in en and "Undecided" in en and "Policy (open)" in en,
          f"EN でも10行・語も英語 -> {lines()[:2]}")
    check("未着手" not in en and "方針" not in en, "EN に日本語が混ざらない")
    pg.click(S("#langBtn")); pg.wait_for_timeout(300)

    # ===== 統合版：計画ビューでは出さない（wbs の見た目を変えない） =====
    if UNIFIED:
        # 計画にも切り替えられるよう、計画（tasks）と課題の両方を持つファイルを読ませる
        both = {"name": "両方", "projects": [{"name": "P",
                "tasks": [{"id": "1", "name": "工程", "start": "2026-09-01", "end": "2026-09-10"}],
                "issues": D["projects"][0]["issues"]}]}
        pg.evaluate("d=>window.renderData(d)", both); pg.wait_for_timeout(350)
        pg.click("#pmSwitch .pm-b[data-pmv='plan']"); pg.wait_for_timeout(300)
        check(pg.eval_on_selector("#legendBtn", "e=>getComputedStyle(e).display") == "none",
              "計画ビューでは凡例ボタンを出さない（pixel 不変）")
        pg.click("#pmSwitch .pm-b[data-pmv='issue']"); pg.wait_for_timeout(300)
        check(pg.eval_on_selector("#legendBtn", "e=>getComputedStyle(e).display") != "none",
              "課題ビューに戻すと出る")
    check(not errors, f"JS エラーが出ない -> {errors[:2]}")
    b.close()
finish(errors)
