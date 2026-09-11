# 統合ビューアの差し込み口（段階 C で wbs 本家へ移すための指示書）

統合ビューアを本家へ移すための差し込み口の一覧（橋 `PM` の窓口・課題描画器の作り方・取り込み手順）。

> 移植元 single-file-issue（非公開リポ） から。v2.0.0 の統合に至る**設計の履歴**として本家に置く（本文は当時の記録のまま。`issue.json` ／ `issue_viewer.html` は現在の `wbs.json` ／ `wbs_viewer.html`）。

> 作成：2026-09-07（段階 B・実装ワーカー）。対象：`wbs_viewer.html`（**本家 main `ce833e1` を土台**）。
> 土台の履歴：`763421f`（v1.4.0）→ **`ce833e1`**（2026-09-10 取り込み・#105 期間フィルタ「今月」／#106 進捗タブの専用色＋細バー）。
> 版表記（`.ver`）は本家がまだ `v1.4.0` のままなので、以下の `v1.4.0` の記述はそのまま有効。
> **（2026-09-11 追記）統合は完了し、本家の版表記は `v2.0.0` になった。以下に出てくる `v1.4.0` は、いずれも移植作業時点の土台を指す当時の記述である。**
> **原則**：wbs の既存行は書き換えない。**加算のみ**（分岐の追加・末尾への連結・フック呼び出し 1 行）。
> `issues` も `links` も無い JSON では、追記コードは DOM・CSS・localStorage・保存内容の**いずれにも痕跡を残さない**。
> 証拠：`tests/wbs_e2e/test_golden.py`（49 スナップショット全一致）／`test_pixel.py`（8 枚とも 0/1,350,000 画素）。

## 1. 差し込み口の一覧（8 か所）＋ 聖域の変更 1 か所

| # | 場所（現在の行） | 追記内容 | 無害な理由 | 段階 C での移し方 |
|---|---|---|---|---|
| 1 | `<style>` 末尾（254 行〜） | 統合用 CSS。`#pmSwitch` / `.pmb` / `.pmjump` と、課題描画器の CSS（266 行〜・すべて `#isMain` スコープ・変数は `--is-*`） | **新規セレクタのみ**。wbs の既存規則・`:root` 変数に一切触れない。課題側は `#isMain` の中だけに当たる | ブロックごとコピー。`:root{--is-*}` は wbs の `:root` と別ブロックのまま保つ |
| 2 | `#topbar`（473 行） | `<span id="pmSwitch" hidden></span>` を `#editBtn` の直後に 1 行 | `hidden` 属性＝`display:none`＝**0 ピクセル**。`tasks` と `issues` の両方があるファイルでだけ中身が入る | 同じ位置に 1 行 |
| 3 | `<body>`（486 行） | `<div id="isMain" hidden></div>` を `#main` の直後に 1 行 | 同上（0 ピクセル）。課題描画器はこの中だけを触る | 同じ位置に 1 行 |
| 4 | `applyData()`（1201 行） | 末尾に `PM.emit("data",data,isNew);` 1 行 | 購読が無ければ何もしない。wbs の `render(data)` は先に完了済み | 1 行追加 |
| 5 | `$("editBtn")` ハンドラ（1410 行） | 末尾に `PM.emit("edit",editMode);` 1 行 | 同上 | 1 行追加 |
| 6 | `applyLang()`（1684 行） | 末尾に `PM.emit("lang",lang);` 1 行 | 同上 | 1 行追加 |
| 7 | `buildRowBodies()` の作業項目セル（1020 行） | `const pmb=PM.badge(r.key,n.id);` と、表示モードの 2 分岐の末尾に `${pmb}` | `links` が無ければ `PM.badge` は `""` を返し、**DOM を 1 つも作らない**。`golden.json` が撮る `cells[].innerText` は不変 | 同じ 3 行 |
| 8 | `#topbar` の `#langBtn` の**直前**（DOM は `glue.js` が生成） | **凡例ボタン**（`#pmLegend`＝`?`）と吹き出し（`#pmLegendPop`）。HTML には 1 行も書かず、`glue.js` が**加算 DOM** で作って `#langBtn.before(...)` で差し込む。中身＝状態 3 つと印 6 つの意味 | 既定は `#pmLegend{display:none}` で、`body.pm-issue` が付いている時だけ表示する規則を 1 本足す。**計画ビューでは常に `display:none`＝0 ピクセル**（`issues` の無い素の `wbs.json` では最初から出ない）。文言の言語追随は wbs の `applyLang()` を書き換えず、`tail.js` の**統合版 `applyLang`** が `PM.on("lang")` で受けて差し替える | `glue.js` の生成ブロック・`body.pm-issue #pmLegend{...}` の CSS・`tail.js` の凡例文言（ja/en）の **3 か所をそのまま移す**。wbs 本家の `applyLang()` には触れない（通知は差し込み口 6 の `PM.emit("lang")` のまま） |

### 聖域（保存パス）の変更 — 1 か所だけ（作者承認 2026-09-09）

| 場所 | 変更 | 理由 | 段階 C での扱い |
|---|---|---|---|
| `deferRender()` の `tick`：`issue_viewer.html` 1226 行／`wbs_viewer.html` 2697 行（課題側の第 2 IIFE） | `if(focusedInTable())` → **`if(focusedInTable()&#124;&#124;formEl)`** | 入力欄に文字を入れた直後に「待ち」「凍結」「確定」「＋リンク」を押すと、**開いたフォームが約 0.4 秒後に消える**（`render()` の先頭が `closeForm()` を呼ぶため、保留中の遅延再描画がフォームを巻き込む）。フォームを開いている間は再描画を待たせるだけで、保存キュー・mtime 検知・`_calc` 除外には触れていない | 同じ 1 行を移す。移植元は `scratchpad/glue.js`（統合版）と `issue_viewer.html`（単体版）の**両方**にあるので、片方だけ直すと統合版に残る |

**wbs 本家（v1.4.0）にも同じ危険がある**（今回は直さない・段階 C の起票候補）。
本家の `render()` は先頭で `closeRsUI()` を呼び、リスケの吹き出し `#rsPop` とフォーム `#rsForm` を閉じる（1113〜1120 行の `deferRender` にはフォームの見張りが無い）。
再現手順：編集モードで左表の入力欄に文字を入れ、確定せずにそのまま **↷（リスケ）** を押す。
フォームが開いた直後、遅延していた再描画が走って `closeRsUI()` がフォームを消す。

補助として **橋の本体**（491〜540 行あたり）を IIFE の**先頭**に置く。
`const PM={...}` を末尾に置くと、初期化中に走る `applyLang()` から TDZ で `ReferenceError` になるため**先頭が必須**。

## 2. 橋（PM）の窓口

`window.__PM` として公開。課題描画器（第 2 IIFE）はこれだけを使う。

| 窓口 | 引数 | 役割 |
|---|---|---|
| `PM.on(kind, fn)` | `kind` = `"data"` / `"lang"` / `"edit"` / `"view"` | 通知の購読 |
| `PM.emit(kind, ...a)` | — | wbs 側からの通知。購読側の例外は `setTimeout` で投げ直し、**握り潰さない**（pageerror として表に出す） |
| `PM.setBadge(fn)` | `fn(rowKey, taskId) -> HTML` | 逆引き札の生成関数を登録。未登録なら `""` |
| `PM.badge(rowKey, taskId)` | — | 上を安全に呼ぶ（例外時も `""`） |
| `PM.queueSave()` | — | wbs の保存キュー（**聖域は wbs の 1 本だけ**） |
| `PM.notice(m)` | — | ページ内の案内バー |
| `PM.today()` / `PM.lang()` / `PM.isEdit()` / `PM.data()` | — | 本日・言語・編集状態・現在のデータ |
| `PM.render()` | — | wbs 側を描き直す |
| `PM.gotoWbs(pname, tid)` | 案件名・WBS id | 課題→計画：`expandTo` で祖先を開き → 計画表示へ → 行へスクロール → 2 秒強調 |

補助関数（同じく wbs 側 IIFE に追加）：
- `expandTo(pname, tid)` … 折りたたみキー `"P|案件"` / `"T|案件|id"` の**祖先チェーン**を `collapsed` から外す。畳んだ親の中の葉は DOM に無いため、目的の行だけでなく祖先すべてを開く必要がある。
- `scrollToTask(pname, tid)` … 該当行へスクロールし、左表とガント行に `.pmjump` を 2 秒付ける。

## 3. 課題描画器（第 2 IIFE）の作り方

`issue_viewer.html` から機械変換して差し込む（生成器：`scratchpad/port.py` ＋ `glue.js` ＋ `tail.js`）。

- **CSS**：`:root` の変数を `--is-*` に改名。共有シェル（`#topbar` / `#openBtn` / `#refreshBtn` / `#editBtn` / `#langBtn` / `#notice` / `body` / `html` / `*`）の規則は捨てる。残りの全セレクタに `#isMain ` を前置。
- **id**：wbs と衝突する 16 個を `is*` に改名（`filterBar`→`isFilterBar`、`stat`→`isStat`、`tbl`→`isTbl`、`main`→`isMain` など）。`#isForm` / `#notePop` は `body` 直下に出すため素のまま。
- **クラス名**：`#isMain` スコープだけでは足りない。wbs の e2e が `.seg-btn.on` のように**グローバルに数える**断言を持つため、
  名前がぶつかるクラスのうち **JS の識別子になり得ないもの**（ハイフン付き等）を `is-` 接頭辞に改名する：
  `sf-btn` `sf-lbl` `sf-sep` `sf-solo` `sfilter` `asg-dd` `asg-cnt` `asg-list` `asg-acts` `asg-cb` `asg-all` `asg-none`
  `seg-btn` `seg` `fbar-ttl` `date-wrap` `cal-proxy` `cal-btn` `nm-in` `mstat` `donechk` `ic`。
  `act` / `num` / `sub` / `on` / `title` / `caret` / `clk` / `over(due)` は**裸語で JS の変数名とぶつかる**ため触らない
  （wbs の 356 断言に影響しないことを回帰網で確認済み）。テスト側は `tests/e2e/common.py` の `S()` / `J()` が 1 か所で読み替える。
- **捨てるもの**（wbs の 1 本を使う）：保存パス一式（`ensureWritable` / `writeNow` / `flushSaves` / `setSaveMsg`）・開く／更新／D&D・言語ボタン・簡素表示トグル・`window.renderData` の再定義。
- **残すもの**：導出（状態・★更新・期限超過）・6 列・帯・濃淡・フィルタ・並び・折りたたみ・案件タブ・サマリ・編集（状態遷移／行動／リンク行／備考の吹き出し）・`#issue=` の処理。

## 4. 本家の既知の脆さ（段階 C で wbs 側に起票する。**今回は直さない**）

PM のランダム変異テスト（サンプル JSON の値を欠落・型違い・巨大値に置き換えて 200 回読ませる）で見つかったもの。
ゴールデン維持のため今回は wbs のコードに触れていない。

| 症状 | 場所（v1.4.0） | 入力 |
|---|---|---|
| `forEach is not a function` | 608 行 | `projects[].milestones` が非配列 |
| `n.children.map is not a function` | 539 行 | `tasks[].children` が非配列 |
| `Cannot create property '_calc'` | 565 行 | `tasks[]` の要素が数値・文字列 |
| `[object Object]` が画面に出る | 名前セル | `tasks[].name` がオブジェクト |
| 開いたリスケフォームが 0.4 秒後に消える | `deferRender`（1113〜1120 行）にフォームの見張りが無い／`render()` が `closeRsUI()` を呼ぶ | 入力欄に入力 → 確定せずに ↷ を押す |

課題側（統合ビューアの課題描画器）で同種のものは**直済み**：
`links[].wbs` の検査が `tasks` を再帰する `walk` で、`children` が非配列だと落ちていた（`Array.isArray` で「子なし」扱いに）。
案件名がオブジェクトの場合も `str()` で空扱いにし、`[object Object]` を出さない。
回帰は `tests/e2e/test_corpus.py` の inline ケース（`children が数値` ほか 7 件）と、`[object Object]` を出さない断言で固定。

## 5. 単体版と統合版で意図的に違うところ

| 項目 | 単体（`issue_viewer.html`） | 統合（`wbs_viewer.html`） | 理由 |
|---|---|---|---|
| WBS リンク | `wbs_viewer.html#wbs=…` を新しいタブ | **同じページ**で計画表示へ切替＋2 秒強調 | 段階 B の目的（1 枚・1 クリック） |
| `document.title` | `name – Issue Viewer` | `name – WBS Viewer` | 製品名は当面 WBS Viewer のまま |
| 簡素表示トグル | 課題側が持つ | wbs 側が持つ（`tests/wbs_e2e/test_plain.py`） | 土台は 1 本 |

## 6. 実機確認で入れた仕上げ（第1弾）と、pixel の制約

| 項目 | 実装 | pixel への影響 |
|---|---|---|
| 課題ビューで EN が左に寄る | `body.pm-issue #stat{display:none}` ＋ `body.pm-issue #topbar .tdiv:last-of-type{margin-left:auto}`（右寄せの支えを最後の操作ボタン群へ移す）。`visibility:hidden` だけだと**3 段ぶんの高さが残り操作バーが伸びる**ため不可。実測：EN の右端は計画/課題とも 1488px（差 0px）・操作バーの高さは計画 79px／課題 48px | 課題ビューでしか効かない＝wbs の fixture では 0 画素 |
| スイッチの大きさ | `#pmSwitch{height:40px;border-radius:6px}` ＋ `.pm-b{font:inherit;padding:0 10px}`。選択中は `var(--accent)` 地に白字。実測で高さ・上端・文字サイズとも `#editBtn` と一致 | 同上 |
| スイッチの常時表示 | **開く前は出す／課題があるファイルでは出す／計画だけのファイル（＝素の wbs.json）では出さない**。無い側は `disabled`＋ツールチップ | この落とし方でのみ 0 画素。常時表示にすると計画ビューの操作バーが変わる |
| 版表記 `v1.4.0 +課題`（en `+issues`） | wbs の `.ver` の文言は書き換えず、**中に加算の `<span id="pmVer" hidden>`** を置き、スイッチと**同じ規則**で出す | 同上（計画だけのファイルでは出さないので 0 画素） |

### pixel の制約と、段階 C での扱い

`test_pixel.py` は `pg.screenshot(full_page=True)`＝**操作バーを含む全画面**を baseline PNG と比較する。
そのため「データを読み込んだ状態で操作バーに何かを常時足す」変更は、必ず画素差になる。

**実測（作者裁定の判断材料）**：`.ver` の隣に `+課題` を**常時表示**にすると **158/1,350,000 画素 = 0.012%** の差分。
`test_pixel` の許容は 0.10% なのでテスト自体は緑のままだが、この許容値はフォントのサブピクセル揺れを吸収するためのもので
意図的な UI 追加を隠すためのものではない。よって段階 B では**常時表示にせず**、上記の条件付き表示を採用した（作者承認 2026-09-09）。

**段階 C（本家へ移す時）**：本家では baseline を撮り直せるので、
「スイッチと版表記を常時表示にする」は **baseline 撮り直しの候補**として起票する。
撮り直す場合は、撮り直しの理由（操作バーに統合版の目印を常時出す）を必ずコミットメッセージに残すこと。

`golden.py` は `#leftRows` / `#grows` / `#overlay` / `#leftHead` / `#progbody` だけを撮るので、操作バーの変更には反応しない。

## 7. 動作確認の入口

`window.renderData(book)` が**統合の唯一の入口**で、計画（`projects[].tasks`）と課題（`projects[].issues`）の**両方**を描く。
PM のランダム変異テスト（`scratchpad/pm_fuzz.py`）はこの 1 つを叩けばよい。

---

## 8. 本家の取り込み手順（次回やる人へ）

統合版を作った生成器（`scratchpad/port.py` ／ `glue.js` ／ `tail.js`）は**失われている**。
なので**統合版を作り直す方式は取れない**。今後の取り込みは次の 2 本立てで行う。

### (1) ビューア＝本家の差分を統合版に当てる

```
# 前回の土台 commit（この文書の冒頭に書いてある）から本家 HEAD までの差分を作る
git -C <本家> diff <前回土台>..<本家HEAD> -- wbs_viewer.html > .upstream_viewer.diff
patch -p1 --dry-run < .upstream_viewer.diff        # 全 hunk が当たるか先に見る
patch -p1           < .upstream_viewer.diff
rm -f .upstream_viewer.diff wbs_viewer.html.orig
```

統合版は本家の行を**ほぼ書き換えていない**（加算のみ・書き換えは 3 行だけ＝`#brandTitle` と逆引き札の 2 行）ので、
本家の差分は**行番号のオフセットだけずれて素直に当たる**。当たらない hunk が出たら、
その場所が §1 の差し込み口と重なっている＝**手で合成して §1 の表を直す**。

**当てた結果の検証は目視でなく集合比較で行う**（差し込みは 1500 行あって読めない）：

```
git -C <本家> show <前回土台>:wbs_viewer.html > /tmp/before_base.html
git -C <本家> show <本家HEAD>:wbs_viewer.html > /tmp/after_base.html
diff -u /tmp/before_base.html <当てる前の統合版> > /tmp/before.diff   # ← 当てる前に取っておく
diff -u /tmp/after_base.html  wbs_viewer.html  > /tmp/after.diff
grep '^[+-]' /tmp/before.diff | grep -v '^\(---\|+++\) ' | sort > /tmp/a
grep '^[+-]' /tmp/after.diff  | grep -v '^\(---\|+++\) ' | sort > /tmp/b
diff /tmp/a /tmp/b     # 空なら「本家HEAD ＋ 前と同じ差し込み」であることの証明
```

hunk 数が §1 の**7 つ**（＝差し込み口 8 か所のうち #8 は JS 生成なので HTML に出ない）のままであることも見る。

`<当てる前の統合版>` は**取り込み前の commit の `wbs_viewer.html`**（`git show HEAD:wbs_viewer.html`）でよい。
つまり **今回の `after.diff` が、次回の `before.diff` そのもの**。作業前に取り忘れても、git から必ず作り直せる。

### (2) 回帰網＝本家 `tests/e2e/` から `tests/wbs_e2e/` へ同期

`tests/wbs_e2e/` は本家 `tests/e2e/` の写しで、**このリポ向けの改変は 3 ファイル・4 行だけ**
（コーパスの置き場が `tests/` ではなく `tests/wbs/` になっている）：

| ファイル | 改変 |
|---|---|
| `common.py` | `load_test_json()` の `ROOT/"tests"/name` → `ROOT/"tests"/"wbs"/name`（1 行） |
| `golden.py` | `FIXTURES` の glob（1 行）と `EDIT_FIXTURES` ループの読み込み（1 行） |
| `test_corpus.py` | `FIXTURES` の glob（1 行） |

同期のやり方：**本家のファイルをそのまま上書きコピーし、上の 4 行を `sed` で当て直す**（手で合成しない）。
`baseline/*.png` と `golden.json` は**本家のものをそのまま使う**（撮り直さない・生成し直さない）。
コーパス `tests/wbs/*.json` は本家 `tests/*.json` と同名・同内容なので、本家で変わった時だけコピーする。

### (3) 緑の確認（3 系統）

```
uv run python tests/wbs_e2e/run_all.py                       # 本家の回帰網（golden 49・pixel 8 枚）
uv run python tests/e2e/run_all.py                           # 課題側 24 スイート（単体版）
ISSUE_VIEWER=wbs_viewer.html uv run python tests/e2e/run_all.py   # 課題側 24 スイート（統合版）
uv run python scripts/check.py wbs_sample_issues.json wbs_roadmap.json
```

pixel が 0 画素でないときは**撮り直さない**。原因は ①差し込みの影響 ②当て漏れ ③実行環境のフォント差 のどれかなので、
まず (1) の集合比較をやり直し、次に本家 HEAD の素の `wbs_viewer.html` に対して `test_pixel.py` を回して切り分ける。

### (4) 最後に必ず

- **この文書の冒頭の「土台」commit を新しい本家 HEAD に書き換える**（忘れると次回の差分の起点がずれる）。
- §1 の表の**行番号は目安**（取り込みのたびに数行ずれる）。位置は行番号ではなく**前後のコードで特定する**。
- `CLAUDE.md` ／ `CLAUDE.en.md` は本家仕様を再掲しない方針なので、**本家の機能追加では原則触らない**
  （`grep` して当たった時だけ ja/en を同じコミットで直す）。
