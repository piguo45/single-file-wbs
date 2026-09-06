# E2E テスト（headless Chromium / Playwright）

`wbs_viewer.html` の描画・編集・保存・権限フローを headless Chromium で検証します。
File System Access API はフェイクハンドルで模擬しているため、**実ファイルには一切書き込みません**。

> 注: ここで使う Playwright は**テスト専用の開発ツール**です。製品本体 `wbs_viewer.html` は依存ゼロ（ライブラリ/CDN/ビルド不要）のままです。

## 実行方法（uv・推奨）

リポジトリ直下の `pyproject.toml` で依存（playwright）を管理しています。

```bash
uv sync                               # 初回のみ：.venv を作成（playwright 等を導入）
uv run playwright install chromium    # 初回のみ：headless Chromium を取得
uv run python tests/e2e/run_all.py    # 全スイート
uv run python tests/e2e/test_render.py  # 個別スイート
```

<details><summary>uv を使わない場合（pip）</summary>

```bash
pip install playwright && playwright install chromium
python tests/e2e/run_all.py
```
</details>

決定論化：本日依存（イナズマ線・進行中バー等）は `common.CLOCK_PIN`（2026-06-15 固定）で固定しています。

## スイート一覧

| ファイル | 検証内容 |
|---|---|
| run_all.py | 全 `test_*.py` を順に実行（1つでも赤なら FAILED） |
| test_render.py | 2段見出し・イナズマ線の座標（仕様式で日付非依存）・NaN無し |
| test_corpus.py | `tests/` の全 JSON を読み込み、JSエラー・NaN が無いこと（正常系/異常系） |
| test_golden.py | 構造ゴールデン（全 fixture の値スナップショット：セル/バー幾何・色・座標・遅延ラベル・編集UI） |
| test_pixel.py | ピクセル回帰（代表 fixture の canvas 面内 diff・PIL非依存） |
| test_color_audit.py | 配色監査（CUD：色覚3型でのΔE・隣接コントラスト・調和） |
| test_gantt_bars.py | ガントの予実バー幾何（予定=枠／実績=塗り／終了遅延=赤+N／完了=グレー／親=細サマリー） |
| test_progress.py | 進捗ビュー（ステッパー・状況列・EVM=実績/予定/遅れ・予定終了の赤・タブ切替） |
| test_colcollapse.py | 列の折りたたみ（アウトライン式 +/−・畳むと列が消え左が縮む・+で復元） |
| test_col_resize.py | 列幅の変更（ヘッダ境界ドラッグ・最小幅・localStorage 記憶・ダブルクリックで既定復帰・ドラッグ中は再描画しない） |
| test_collapse.py | 行の全体caret（▼▶/状態依存tooltip/全展開・全たたみ/Ctrl+Z復旧） |
| test_highlight.py | 行/列ハイライト（十字の縦横） |
| test_done.py | 完了トグル（✓・実績終了=本日・行グレー＋取り消し線） |
| test_links.py | 備考内 URL の自動リンク（http(s) のみ・新規タブ） |
| test_dates.py | 日付欄（ISO固定表示・📅連携・スラッシュ正規化・範囲外拒否） |
| test_date_shorthand.py | 日付の短縮入力（`611`・`6/11` → ISO 正規化） |
| test_display.py | 列の表示・整列（メタデータ駆動の描画） |
| test_i18n.py | 言語切替（EN/日本語・localStorage 記憶・UI文言） |
| test_edit.py | 編集パイプライン（保存・`_`キー保持・id採番・同期render・旧形式変換・誤上書き防止・外部変更検知） |
| test_save.py | 保存（デバウンス・単一キュー直列化・派生値除外・`_`キー保持） |
| test_save_retry.py | 保存リトライ（同期/AV 競合の InvalidStateError → 1回だけ自動再保存） |
| test_permissions.py | file:// 権限フロー（保存ピッカー/ジェスチャー再試行/選択時切り詰めへの即書込/案内バー） |
| test_load.py | D&D・読込の堅牢性（空ファイルのエラー表示・ハンドル空読みフォールバック） |
| test_ui.py | 保存状態表示の遷移・クリックターゲット寸法 |
| test_security.py | XSS/属性インジェクション（`esc()`・色は `isColor()` で `#hex` のみ許可） |

注意: 実ブラウザの保存ダイアログ・権限UIは headless では検証できません。
Chrome メジャー更新後は実機での30秒スモーク（開く→編集ON→1編集→保存済表示）を推奨します。
