"""ドキュメント一覧 (docs/index.md) を自動生成する.

docs/ 配下の全 .md を再帰走査し、ディレクトリをカテゴリとして index.md を生成する。
手書きで一覧を維持しない（腐らせない）ための生成スクリプト。標準ライブラリのみ。

使い方:
    uv run python scripts/refresh_docs_index.py
    # または
    python3 scripts/refresh_docs_index.py
"""

from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
INDEX_PATH = DOCS_DIR / "index.md"

# ディレクトリ → 表示名
DIR_LABELS = {
    "": "プロジェクト全体",
    "design": "設計書",
    "adr": "設計決定記録 (ADR)",
}

# 表示順序
DIR_ORDER = ["", "design", "adr"]


def get_title_and_desc(filepath: Path) -> tuple[str, str]:
    """ファイル先頭から「# タイトル」と最初の本文行（概要）を取得する."""
    try:
        lines = filepath.read_text(encoding="utf-8").splitlines()
    except OSError:
        return filepath.stem, ""
    title = ""
    desc = ""
    for line in lines:
        line = line.strip()
        if not title and line.startswith("# "):
            title = line[2:].strip()
        elif title and line and not line.startswith(("#", "*", "-", ">", "|")):
            desc = line
            break
    return title or filepath.stem, desc


def main() -> None:
    """index.md を再生成する."""
    all_files: dict[str, list[Path]] = {}
    for f in sorted(DOCS_DIR.rglob("*.md")):
        if f.name == "index.md":
            continue
        rel = f.relative_to(DOCS_DIR)
        dir_key = str(rel.parent) if str(rel.parent) != "." else ""
        all_files.setdefault(dir_key, []).append(f)

    total_files = sum(len(v) for v in all_files.values())

    lines = [
        "# ドキュメント一覧",
        "",
        "single-file-wbs (WBS Viewer) の設計ドキュメント。",
        "仕様の単一ソースは [`CLAUDE.md`](../CLAUDE.md)、使い方は [`README.md`](../README.md)。",
        "",
        f"*自動生成（`scripts/refresh_docs_index.py`）: {total_files}ファイル*",
        "",
    ]

    ordered = DIR_ORDER + [k for k in all_files if k not in DIR_ORDER]
    for dir_key in ordered:
        if dir_key not in all_files:
            continue
        label = DIR_LABELS.get(dir_key, dir_key or "その他")
        lines += [f"## {label}", "", "| ドキュメント | 概要 |", "|---|---|"]
        for f in all_files[dir_key]:
            rel = f.relative_to(DOCS_DIR)
            title, desc = get_title_and_desc(f)
            if len(desc) > 80:
                desc = desc[:77] + "..."
            lines.append(f"| [{title}]({rel}) | {desc} |")
        lines.append("")

    INDEX_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"docs/index.md を更新しました ({total_files}ファイル)")


if __name__ == "__main__":
    main()
