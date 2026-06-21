# ドキュメント一覧

single-file-wbs (WBS Viewer) の設計ドキュメント。
仕様の単一ソースは [`CLAUDE.md`](../CLAUDE.md)、使い方は [`README.md`](../README.md)。

*自動生成（`scripts/refresh_docs_index.py`）: 8ファイル*

## 設計書

| ドキュメント | 概要 |
|---|---|
| [WBS Viewer 全体概要](design/system-overview.md) | `wbs_viewer.html` と周辺ファイルの構成から逆生成した全体像（構成・依存・データの流れ）。 |

## 設計決定記録 (ADR)

| ドキュメント | 概要 |
|---|---|
| [ADR-0001: 依存ゼロの単一HTML・`file://` で動かす](adr/0001-dependency-free-single-file.md) | サーバー・ビルド・外部依存を持たず、単一HTMLを `file://` で開く形態を製品の前提にする。 |
| [ADR-0002: ブラウザ内編集に File System Access API を使う](adr/0002-file-system-access-editing.md) | サーバーレスのまま `wbs.json` へ書き戻すため、ブラウザ内編集の保存に File System Access API を使う。 |
| [ADR-0003: 派生値をデータに持たせない（描画時に算出）](adr/0003-no-derived-values-in-data.md) | データは事実（日付・数量）だけを持ち、工数・進捗・座標は描画時に決定論的に算出する。 |
| [ADR-0004: AIを第一級ユーザーにする（JSON＝AIのAPI仕様）](adr/0004-ai-first-json-as-api.md) | 人間=GUI／AI=素のJSON＋`CLAUDE.md` の2経路を第一級にし、スキーマをほぼ固定する。 |
| [ADR-0005: 配色はCUD配慮（色だけに意味を担わせない）](adr/0005-cud-color-design.md) | 色だけに意味を持たせず、形・位置・ラベルで冗長化する（色覚多様性への配慮）。 |
| [ADR-0006: 回帰テストは headless Chromium（self-contained・uv）](adr/0006-e2e-headless-chromium.md) | 実ブラウザの描画が仕様なので、回帰テストは headless Chromium で実描画を検証する（uvで自己完結）。 |
| [ADR-0007: ライセンスは MIT を継続（AGPL移行は却下）](adr/0007-license-mit.md) | クライアント完結でAGPLの前提と噛み合わないため、ライセンスは MIT を継続する。 |
