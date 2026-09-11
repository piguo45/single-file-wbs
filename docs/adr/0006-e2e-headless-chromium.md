# ADR-0006: 回帰テストは headless Chromium（self-contained・uv）

実ブラウザの描画が仕様なので、回帰テストは headless Chromium で実描画を検証する（uvで自己完結）。

## ステータス
承認済み（#53 で公開・可搬化、後に uv で self-contained 化）

## コンテキスト
製品は単一HTML（[ADR-0001](0001-dependency-free-single-file.md)）で、価値は「実ブラウザでの描画・座標・配色・編集挙動」にある。ユニットテストでは描画結果（SVGイナズマ線の座標・バー幾何・色）を検証できない。当初テストは別リポのPlaywright環境に依存し、パスが固定で可搬性が無かった。

## 決定
e2eを **headless Chromium（Playwright）** で実装し、`file://` で開いて `window.renderData(JSON)` を注入して検査する。実行環境は **uv で self-contained**（`pyproject.toml` / `uv.lock`）にし、他リポ非依存にする。

```
uv sync && uv run playwright install chromium && uv run python tests/e2e/run_all.py
```

## 理由
- **実描画が仕様**：セル/バーの幾何・色・イナズマ座標・遅延ラベル・編集UIを実DOMで検証できる。
- **決定論化**：本日依存（イナズマ/進行中バー）は `common.CLOCK_PIN`（2026-06-15固定）で固定。
- 構造ゴールデン（`golden.py`）＋ピクセル（`test_pixel.py`・PIL不使用）＋配色監査（[ADR-0005](0005-cud-color-design.md)）で多層化。

## 結果
- 表示を意図的に変えたらゴールデン/ピクセルを撮り直し→目視（撮り直しの乱用は回帰検知を殺す）。
- **保存パス（File System Access）の権限/実ダイアログは headless で再現できない**ため、そこだけは実機スモークで人間が確認（[ADR-0002](0002-file-system-access-editing.md)）。
- `run_all.py` が `test_*.py` を glob 自動収集（現在 23 スイート）。

## 根拠
#53。実行手順の詳細は [`tests/e2e/README.md`](../../tests/e2e/README.md)。

## v2.0.0 での扱い（2026-09-11 追記）

**回帰網は2系統になった。** 計画側 **`tests/e2e/`**（[README](../../tests/e2e/README.md)）と課題側 **`tests/e2e_issue/`**（[README](../../tests/e2e_issue/README.md)）で、**完了の自動検証では両方を通す**。本文の「現在 23 スイート」は v1.4 時点の数で、いまは計画側・課題側それぞれが `run_all.py` の glob で自動収集する（数は増える）。
- **本日固定（`CLOCK_PIN`）は系統ごとに別**：計画側 `tests/e2e/common.py` ＝ **2026-06-15**、課題側 `tests/e2e_issue/common.py` ＝ **2026-09-15**。期待値はそれぞれの固定日で書く。
- 検査データも2か所：計画＝`tests/`（[INDEX](../../tests/INDEX.md)）、課題＝`tests/issue/`（[INDEX](../../tests/issue/INDEX.md)）。
- ブラウザを使わない検査として **`scripts/check.py`**（番号の重複・日付・enum・`links` の指す先の存在・旧キーの残存）も完了条件に入る。
