"""#205: 編集モードで左表の入力欄を変更した直後にリスケフォーム(#rsForm)を開くと、
deferRender()の遅延再描画が0.4〜0.8秒後に発火してフォームが消えてしまう回帰の固定。
原因：deferRenderのtickは「#leftRows内のINPUTにフォーカスがある間」だけ延期していたが、
document.body直下に置かれる#rsForm/#rsPopは見ておらず、render()冒頭のcloseRsUI()で消えていた。
本日=CLOCK_PIN(2026-06-15)固定。"""
from playwright.sync_api import sync_playwright
from common import VIEWER, check, finish, leaf, granted_handle_init, new_page

L1 = leaf("1", "タスクA", ps="2026-06-01", pe="2026-06-05")
DATA = {"projects": [{"name": "P", "milestones": [], "tasks": [L1]}]}

errors = []
with sync_playwright() as p:
    b = p.chromium.launch()

    # ===== ① 変更なしで↷→残る（従来どおりのベースライン） =====
    pg = new_page(b, viewport={"width": 1500, "height": 700})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script(granted_handle_init(DATA))
    pg.goto(VIEWER)
    pg.click("#openBtn"); pg.wait_for_timeout(200)
    pg.click("#editBtn"); pg.wait_for_timeout(200)
    pg.click('button[data-act="resched"] >> nth=0')
    check(pg.is_visible("#rsForm"), "①変更なし：↷でフォームが開く")
    pg.wait_for_timeout(800)
    check(pg.is_visible("#rsForm"), "①変更なし：0.8秒後もフォームが残る")
    pg.close()

    # ===== ② 名前欄の変更直後に↷→0.8秒後も残る（#205の再現→修正確認） =====
    pg = new_page(b, viewport={"width": 1500, "height": 700})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.add_init_script(granted_handle_init(DATA))
    pg.goto(VIEWER)
    pg.click("#openBtn"); pg.wait_for_timeout(200)
    pg.click("#editBtn"); pg.wait_for_timeout(200)
    pg.locator('input[data-field="name"]').first.fill("変更後タスク")   # deferRenderを予約させる
    pg.click('button[data-act="resched"] >> nth=0')
    check(pg.is_visible("#rsForm"), "②変更直後：↷でフォームが開く")
    # 消える前のDOMノードに印を付け、render()（フルinnerHTML置換）が走ったかどうかの証拠にする
    pg.evaluate("document.querySelector('input[data-field=\"name\"]').setAttribute('data-probe','205')")
    pg.wait_for_timeout(800)
    check(pg.is_visible("#rsForm"), "②変更直後：0.8秒後もフォームが残る（#205本体の修正確認）")
    check(pg.evaluate("!!document.querySelector('[data-probe=\"205\"]')"),
          "②変更直後：フォームが開いている間はDOMが置き換わっていない（render()が発火していない証拠）")

    # ===== ③ フォームを閉じた後は再描画が走る =====
    pg.click("#rsForm .rs-cancel")
    check(not pg.is_visible("#rsForm"), "③取消でフォームが閉じる")
    pg.wait_for_timeout(1000)   # RENDER_DEFER_MS(350)+FOCUS_POLL_MS(400)ぶんの余裕を見て待つ
    check(not pg.evaluate("!!document.querySelector('[data-probe=\"205\"]')"),
          "③フォームを閉じた後、遅延していたrender()が発火してDOMが置き換わる")
    check(pg.locator('input[data-field="name"]').first.input_value() == "変更後タスク",
          "③再描画後も編集した値（curProjectsへ反映済み）は保持される")
    pg.close()

    b.close()
finish(errors)
