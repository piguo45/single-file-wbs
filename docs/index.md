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
| [ADR-0001: 依存ゼロの単一HTML・`file://` で動かす](adr/0001-dependency-free-single-file.md) | 承認済み（基盤決定・v1.0 から） |
| [ADR-0002: ブラウザ内編集に File System Access API を使う](adr/0002-file-system-access-editing.md) | 承認済み（#17〜#19, #29, #60 で制約と回避を確定） |
| [ADR-0003: 派生値をデータに持たせない（描画時に算出）](adr/0003-no-derived-values-in-data.md) | 承認済み（基盤決定・v1.0 から） |
| [ADR-0004: AIを第一級ユーザーにする（JSON＝AIのAPI仕様）](adr/0004-ai-first-json-as-api.md) | 承認済み（#67 でコンセプトを明文化） |
| [ADR-0005: 配色はCUD配慮（色だけに意味を担わせない）](adr/0005-cud-color-design.md) | 承認済み（#35 / #34 / #65） |
| [ADR-0006: 回帰テストは headless Chromium（self-contained・uv）](adr/0006-e2e-headless-chromium.md) | 承認済み（#53 で公開・可搬化、後に uv で self-contained 化） |
| [ADR-0007: ライセンスは MIT を継続（AGPL移行は却下）](adr/0007-license-mit.md) | 承認済み（#73 を MIT継続で決着） |
