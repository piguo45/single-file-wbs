"""編集モード: インライン編集の保存往復・`_`キー保持・派生値の除外・done トグル・
   行動の追加/削除/並べ替え（同じ群の隣と入替）・状態遷移（待ち/凍結/解除/閉じる/再オープン）・
   ＋課題の id 採番・外部変更検知。本日=CLOCK_PIN(2026-09-15)。"""
import json
from playwright.sync_api import sync_playwright
from common import S, VIEWER, book, check, finish, granted_handle_init, issue, action, new_page, PINNED_TODAY

DATA = book([
            dict(issue(1, "元のタイトル", priority="mid", due="2026-09-20",
                       actions=[action("2026-09-01", "実績1", "ぴぐお", True),
                                action("2026-09-02", "実績2", "ぴぐお", True),
                                action("2026-09-10", "予定1"),
                                action(None, "予定2")]),
                 _ai={"tokens": 12, "memo": "AIのメタ置き場"}),
            issue(5, "2件目（id は飛び番）", priority="low", due=None)],
           name="編集テスト", _meta={"owner": "tester"})

errors, dialogs = [], []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_page(b, viewport={"width": 1600, "height": 900})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("dialog", lambda d: (dialogs.append(d.message), d.accept("原因調査と修正で対応する")))
    pg.add_init_script(granted_handle_init(DATA))
    pg.goto(VIEWER)

    def saved():
        return json.loads(pg.evaluate("()=>window.__file"))["projects"][0]

    def flush():
        pg.wait_for_timeout(650)   # 保存デバウンス(400ms)+余裕

    def acts():
        return [a["text"] for a in saved()["issues"][0]["actions"]]

    pg.click(S("#openBtn")); pg.wait_for_timeout(200)
    check("on" not in (pg.get_attribute(S("#editBtn"), "class") or ""), "読込直後は編集OFF")
    pg.click(S("#editBtn")); pg.wait_for_timeout(250)
    check("on" in (pg.get_attribute(S("#editBtn"), "class") or ""), "編集ON")

    # 担当は導出値：課題レベルの入力欄は存在せず、担当セルは読み取り専用
    check(pg.eval_on_selector_all('input[data-field="assignee"]:not([data-a])', "e=>e.length") == 0,
          "課題レベルの担当入力欄は無い（担当は行動側から導出）")
    check(pg.eval_on_selector_all(S("#tbody td.asg"), "e=>e.length") == 0, "担当列そのものが無い（担当は行動の行だけ）")
    check(pg.eval_on_selector_all(S("#tbody tr:nth-child(1) .sec"), "e=>e.map(x=>x.innerText)") == ["概要", "方針（未決）", "実績", "予定"]
          and pg.eval_on_selector(S("#tbody .sec"), "e=>getComputedStyle(e).backgroundColor") == "rgb(221, 226, 234)",
          "編集モードの詳細でも同じ帯を使う")
    check(pg.eval_on_selector_all(S('#tbody td.title input[data-field="title"]'), "e=>e.length") == 2,
          "タイトルの input はタイトル列にある")
    check(pg.eval_on_selector_all(S('#tbody td.title button[data-act="delissue"]'), "e=>e.length") == 2,
          "課題削除の ✕ もタイトル列にある")
    check(pg.eval_on_selector_all(S('#tbody td.detail input[data-field="title"]'), "e=>e.length") == 0,
          "詳細列にタイトルの input は無い")

    # --- インライン編集（title / priority / 行動の担当 / due 短縮入力 / textarea 改行保持 / wbs） ---
    pg.fill('input[data-i="0"][data-field="title"]', "新しいタイトル")
    pg.dispatch_event('input[data-i="0"][data-field="title"]', "change")
    pg.select_option('select[data-i="0"][data-field="priority"]', "high")
    pg.fill('input[data-i="0"][data-a="2"][data-field="assignee"]', "佐藤")
    pg.dispatch_event('input[data-i="0"][data-a="2"][data-field="assignee"]', "change")
    pg.fill('input[data-i="0"][data-field="due"]', "1001")            # 短縮入力（年は既存値から補完）
    pg.dispatch_event('input[data-i="0"][data-field="due"]', "change")
    pg.fill('textarea[data-i="0"][data-field="closeWhen"]', "1行目\n2行目")
    pg.dispatch_event('textarea[data-i="0"][data-field="closeWhen"]', "change")
    flush()
    s = saved()["issues"][0]
    check(s["title"] == "新しいタイトル", f"title 保存 -> {s['title']!r}")
    check(s["priority"] == "high", f"priority 保存 -> {s['priority']!r}")
    check(s["actions"][2]["assignee"] == "佐藤", f"行動の担当を保存 -> {s['actions'][2]['assignee']!r}")
    check("assignee" not in s, f"課題レベルの assignee は生えない -> {sorted(s)}")
    # 入力にフォーカス中は再描画を遅らせる（deferRender）ので、blur してから導出表示を見る
    pg.evaluate("()=>document.activeElement && document.activeElement.blur()")
    pg.wait_for_timeout(500)
    pg.click(S('#tbody tr:nth-child(1) td.title [data-tog]')); pg.wait_for_timeout(150)   # 編集モードでも caret でたためる
    got = pg.eval_on_selector(S('#tbody tr:nth-child(1) td.detail'), "e=>e.innerText.replace(/\\n/g,' ').trim()")
    check(got == "未 9/10 予定1 担当：佐藤",
          f"たたむと詳細が次の一手1行になる（担当も付く／編集が導出に反映される） -> {got!r}")
    pg.click(S('#tbody tr:nth-child(1) td.title [data-tog]')); pg.wait_for_timeout(150)   # 戻す（本文の編集UIを再び触るため）
    check(s["due"] == "2026-10-01", f"due の短縮入力 1001 → ISO -> {s['due']!r}")
    check(s["closeWhen"] == "1行目\n2行目", f"textarea の改行が保持される -> {s['closeWhen']!r}")
    check(pg.eval_on_selector_all(S('#tbody input[data-field="wbs"]'), "e=>e.length") == 0,
          "actions[].wbs は v0.2 で廃止＝編集欄も出さない")
    # `_` キー（ユーザー/AIのメタ）は round-trip する。派生値 _calc は書かれない
    check(json.loads(pg.evaluate("()=>window.__file")).get("_meta", {}).get("owner") == "tester", "トップの _meta が残る")
    check(s.get("_ai", {}).get("memo") == "AIのメタ置き場", "課題の _ai が残る")
    check("_calc" not in pg.evaluate("()=>window.__file"), "派生値 _calc は書かれない")

    # 不正な日付は無視（ゴミを保存しない）
    pg.fill('input[data-i="0"][data-field="due"]', "ないひ")
    pg.dispatch_event('input[data-i="0"][data-field="due"]', "change")
    flush()
    check(saved()["issues"][0]["due"] == "2026-10-01", "解釈不能な日付は無視して元の値のまま")

    # --- 行動：並べ替え（同じ群の隣と入替）／done トグル／追加／削除 ---
    check(acts() == ["実績1", "実績2", "予定1", "予定2"], f"初期の行動順 -> {acts()}")
    pg.click('button[data-act="aup"][data-i="0"][data-a="1"]'); flush()
    check(acts() == ["実績2", "実績1", "予定1", "予定2"], f"▲で済の群の中で入替 -> {acts()}")
    pg.click('button[data-act="adown"][data-i="0"][data-a="2"]'); flush()
    check(acts() == ["実績2", "実績1", "予定2", "予定1"], f"▼で未の群の中で入替 -> {acts()}")

    pg.click('button[data-act="done"][data-i="0"][data-a="2"]'); flush()
    check(saved()["issues"][0]["actions"][2]["done"] is True, "done チェックで済になる")
    # 済3件＋未1件。未の先頭を▲しても「済の群」へは移動しない（表示の並びと一致させる仕様）
    before = acts()
    pg.click('button[data-act="aup"][data-i="0"][data-a="3"]'); flush()
    check(acts() == before, f"群をまたぐ移動はしない -> {acts()}")
    pg.click('button[data-act="done"][data-i="0"][data-a="2"]'); flush()
    check(saved()["issues"][0]["actions"][2]["done"] is False, "もう一度押すと未に戻る")

    pg.click('button[data-act="aadd"][data-i="0"]'); flush()
    check(len(acts()) == 5 and acts()[4] == "", f"＋で末尾に空の行動を追加 -> {acts()}")
    pg.click('button[data-act="adel"][data-i="0"][data-a="4"]'); flush()
    check(len(acts()) == 4, f"✕で削除 -> {acts()}")

    # --- 状態遷移：待ち → 解除 → 凍結 → 閉じる → 再オープン ---
    check(pg.inner_text(S('#tbody tr:nth-child(1) td.state')).strip().startswith("対応中"),
          "済んだ行動があるので対応中")
    check(pg.eval_on_selector_all('button[data-act="decide"]', "e=>e.length") == 0,
          "「方針を決める」ボタンは無い（方針は decisions[] の帯で足す）")

    pg.click('button[data-act="wait"][data-i="0"]'); pg.wait_for_timeout(200)
    check(pg.eval_on_selector_all(S("#isForm"), "e=>e.length") == 1, "待ちフォームが開く")
    pg.fill(S('#isForm input[data-fm="who"]'), "開発部")
    pg.fill(S('#isForm input[data-fm="what"]'), "仕様の回答")
    pg.fill(S('#isForm input[data-field="__until"]'), "09-25")
    pg.click(S("#isForm .fm-ok")); flush()
    pd = saved()["issues"][0]["pending"]
    check(pd == {"kind": "waiting", "since": PINNED_TODAY, "who": "開発部",
                 "what": "仕様の回答", "until": "2026-09-25"}, f"待ちを記録 -> {pd}")
    st = pg.inner_text(S('#tbody tr:nth-child(1) td.state'))
    check("対応中" in st and "待ち 開発部（9/25）" in st, f"状態は対応中のまま・下に待ちの印 -> {st!r}")
    check(pg.eval_on_selector_all(S("#isForm"), "e=>e.length") == 0, "OKでフォームが閉じる")

    pg.click('button[data-act="unpend"][data-i="0"]'); flush()
    check(saved()["issues"][0]["pending"] is None, "解除で pending=null")

    # 止めたまま「閉じる」→ 閉じたら止めた記録は残さない（片手落ち防止・AIへの依頼例と GUI 経路を揃える）
    pg.click('button[data-act="frozen"][data-i="0"]'); pg.wait_for_timeout(200)
    pg.fill(S('#isForm input[data-fm="resumeWhen"]'), "移行が終わったら")
    pg.click(S("#isForm .fm-ok")); flush()
    check(saved()["issues"][0]["pending"] == {"kind": "frozen", "since": PINNED_TODAY,
                                              "resumeWhen": "移行が終わったら", "detail": ""},
          f"凍結を記録 -> {saved()['issues'][0]['pending']}")

    pg.click('button[data-act="close"][data-i="0"]'); pg.wait_for_timeout(200)
    pg.select_option(S('#isForm select[data-fm="how"]'), "not_occurred")
    pg.fill(S('#isForm textarea[data-fm="note"]'), "期限を過ぎたが何も起きなかった")
    pg.click(S("#isForm .fm-ok")); flush()
    cl = saved()["issues"][0]["closed"]
    check(cl == {"at": PINNED_TODAY, "how": "not_occurred", "note": "期限を過ぎたが何も起きなかった"},
          f"閉じるを記録 -> {cl}")
    st = pg.inner_text(S('#tbody tr:nth-child(1) td.state'))
    check("完了" in st and "発生せず" in st, f"完了＋閉じ方バッジ -> {st!r}")
    check(pg.eval_on_selector_all(S("#tbody tr:nth-child(1)"), "e=>e[0].className") == "st-closed", "完了行になる")
    check(saved()["issues"][0]["pending"] is None, "閉じると pending は null に戻る（止めたまま完了にしない）")

    pg.click('button[data-act="reopen"][data-i="0"]'); flush()
    check(saved()["issues"][0]["closed"] is None, "再オープンで closed=null")
    check(saved()["issues"][0]["pending"] is None, "再オープンは closed のみ戻す（待ち／凍結は復活させない）")

    # --- ＋課題（id=最大+1・起票日=本日・優先度=中）／✕削除 ---
    pg.click(S('#filterBar .addissue')); flush()
    iss = saved()["issues"]
    check(len(iss) == 3, f"課題が1件増える -> {len(iss)}")
    check(iss[2]["id"] == 6, f"id は既存最大(5)+1 -> {iss[2]['id']}")
    check(iss[2]["opened"] == PINNED_TODAY and iss[2]["priority"] == "mid" and iss[2]["actions"] == [],
          f"起票日=本日・優先度=中・actions=[] -> {iss[2]}")
    check("assignee" not in iss[2], f"＋課題の初期値に assignee は入らない -> {sorted(iss[2])}")
    pg.click(S('#tbody tr:nth-child(3) td.title [data-tog]')); pg.wait_for_timeout(150)
    check(pg.inner_text(S('#tbody tr:nth-child(3) td.detail')).strip() == "",
          "行動0件の新課題は、たたむと詳細が空")
    pg.click(S('#tbody tr:nth-child(3) td.title [data-tog]')); pg.wait_for_timeout(150)
    n = len(dialogs)
    pg.click('button[data-act="delissue"][data-i="2"]'); flush()
    check(len(dialogs) > n and "削除します" in dialogs[-1], "✕削除は確認ダイアログを出す")
    check(len(saved()["issues"]) == 2, "確認OKで削除される")

    # --- 外部変更検知（AI等がツール外で書き換えた場合） ---
    flush()
    pg.evaluate("()=>{window.__mt += 500;}")
    n = len(dialogs)
    pg.fill('input[data-i="0"][data-a="0"][data-field="assignee"]', "競合テスト")
    pg.dispatch_event('input[data-i="0"][data-a="0"][data-field="assignee"]', "change")
    flush(); pg.wait_for_timeout(300)
    check(any("ツール外" in d for d in dialogs[n:]), f"外部変更の上書き確認が出る -> {dialogs[n:]}")

    # --- 並び替え中でも編集の対象を取り違えない（data-i はデータ順の添字・表示順とは別） ---
    pg.select_option('select[data-i="0"][data-field="priority"]', "low")
    pg.select_option('select[data-i="1"][data-field="priority"]', "high")
    pg.click(S('.seg-btn[data-sort="prio"]')); pg.wait_for_timeout(200)
    order = pg.eval_on_selector_all(S("#tbody td.num"), "e=>e.map(x=>x.innerText)")
    check(order == ["5", "1"], f"優先度順で表示が入れ替わる -> {order}")
    di = pg.eval_on_selector(S('#tbody tr:nth-child(1) button[data-act="delissue"]'), "e=>e.getAttribute('data-i')")
    check(di == "1", f"表示1行目(#5)のボタンはデータ順の添字1を指す -> {di}")
    pg.fill(S('#tbody tr:nth-child(1) input[data-field="title"]'), "並び替え中の編集")
    pg.dispatch_event(S('#tbody tr:nth-child(1) input[data-field="title"]'), "change")
    flush()
    titles = {i["id"]: i["title"] for i in saved()["issues"]}
    check(titles.get(5) == "並び替え中の編集" and titles.get(1) == "新しいタイトル",
          f"並び替え中でも編集は表示中の課題に当たる -> {titles}")
    pg.click(S('#tbody tr:nth-child(1) button[data-act="delissue"]')); flush()
    left = [i["id"] for i in saved()["issues"]]
    check(left == [1], f"並び替え中の✕は表示中の課題(#5)を消す -> {left}")

    b.close()
finish(errors)
