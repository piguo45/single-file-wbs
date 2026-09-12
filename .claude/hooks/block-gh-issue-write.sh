#!/usr/bin/env bash
# PreToolUse(Bash) フック：GitHub Issue は「読むだけ」。読み取り以外の gh issue を Claude に禁止する。
# 理由：このリポの課題の正本は wbs_roadmap.json の issues[]（CLAUDE.md「このリポの正本」）。
#       GitHub Issue は外部からの報告窓口＝読んで JSON に転記するだけで、Claude は書かない。
# 人間が本当に書きたい時は、プロンプトで `! gh issue ...` と打てば Claude を経由せず実行できる。
#
# 許可（読み取り）：gh issue list / view / status、gh api の GET
# 禁止：上記以外の gh issue <サブコマンド> すべて（create/comment/edit/close/reopen/delete/lock/pin/transfer/develop …）
#       gh api で issues に書くもの（-X/--method が GET 以外、または -f/-F/--field/--raw-field/--input 付き）
set -u
cmd=$(jq -r '.tool_input.command // empty' 2>/dev/null)
[ -z "$cmd" ] && exit 0

deny() {
  jq -cn --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
  exit 0
}
MSG="GitHub Issue は読み取り専用（gh issue list/view/status のみ可）。課題の正本は wbs_roadmap.json の issues[]。人間が書くなら '! gh issue ...' で実行する。"

# セグメント（; | & で区切った各コマンド）ごとに判定
while IFS= read -r seg; do
  # 1) gh issue <sub>：sub が list/view/status 以外なら禁止（-h/--help や sub なしは通す）
  sub=$(grep -Eo '(^|\s)gh\s+issue\s+[A-Za-z][A-Za-z-]*' <<<"$seg" | head -1 | awk '{print $3}')
  if [ -n "$sub" ] && ! grep -Eq '^(list|view|status)$' <<<"$sub"; then deny "$MSG"; fi
  # 2) gh api で issues に書く
  if grep -Eq '(^|\s)gh\s+api\b' <<<"$seg" && grep -q 'issues' <<<"$seg"; then
    if grep -Eq -- '(^|\s)(-X|--method)\s*=?\s*(POST|PATCH|PUT|DELETE)\b' <<<"$seg" \
       || grep -Eq -- '(^|\s)(-f|-F|--field|--raw-field|--input)(\s|=)' <<<"$seg"; then deny "$MSG"; fi
  fi
done < <(tr ';|&' '\n\n\n' <<<"$cmd")
exit 0
