#!/usr/bin/env bash
set -euo pipefail

# Build a seed prompt file that includes the usual startup checklist
# and (optionally) the last Codex session transcript, then print its path.
#
# Usage:
#   bash scripts/codex_build_resume_seed.sh \
#     [--limit N] [--no-resume] [--out PATH] [--project-root DIR] [--split] \
#     [--id SESSION_ID | --index N | --pick | --list [N]]
#
# - By default, it tries to include the last session transcript from
#   ~/.codex/history.jsonl and ~/.codex/sessions/**.jsonl
# - Use --limit N to tail the last N transcript lines
# - Use --no-resume to skip transcript inclusion
# - Use --out PATH to write to a specific path (default: ~/.codex/tmp/seed_prompt_<ts>.md)
# - Use --project-root DIR to write into DIR/sessions/seed_prompt_<ts>.md and update DIR/sessions/latest.md
# - Use --split to write the transcript to a separate file and link to it from the seed prompt.
# - Use --id to select an explicit session_id from your Codex history.
# - Use --index N to select the Nth most recent unique session (1 = most recent).
# - Use --pick to select interactively (uses fzf if available).
# - Use --list [N] to print the last N sessions (default 20) and exit.

resume=1
limit=""
out=""
project_root=""
split=0
transcript_content=""
session_id_override=""
index_override=""
list_only=0
list_count=20
pick=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --limit)
      shift
      if [[ -n "${1:-}" && "$1" =~ ^[0-9]+$ ]]; then
        limit="$1"
      else
        echo "Error: --limit requires a numeric argument" >&2
        exit 1
      fi
      ;;
    --no-resume)
      resume=0
      ;;
    --out)
      shift
      out="${1:-}"
      ;;
    --project-root)
      shift
      project_root="${1:-}"
      ;;
    --split)
      split=1
      ;;
    --id)
      shift
      session_id_override="${1:-}"
      ;;
    --index)
      shift
      if [[ -n "${1:-}" && "$1" =~ ^[0-9]+$ ]]; then
        index_override="$1"
      else
        echo "Error: --index requires a positive integer" >&2
        exit 1
      fi
      ;;
    --list)
      list_only=1
      # optional count
      if [[ -n "${2:-}" && "$2" =~ ^[0-9]+$ ]]; then
        list_count="$2"; shift
      fi
      ;;
    --pick)
      pick=1
      ;;
    *)
      # ignore unknown args
      ;;
  esac
  shift || true
done

default_message=$'1. Run '\''source .venv/bin/activate && set -a && [ -f .env ] && source .env'\''
2. Activate the current dir as project using serena.
3. Peruse the README.md and the pyproject.toml.'

content_to_load="$default_message"

if (( resume )); then
  history_file="$HOME/.codex/history.jsonl"
  sessions_root="$HOME/.codex/sessions"

  if ! command -v jq >/dev/null 2>&1; then
    echo "Warning: 'jq' not found; skipping transcript." >&2
  elif [[ ! -s "$history_file" ]]; then
    echo "History not found at $history_file; skipping transcript." >&2
  else
    # Build recent unique session IDs, most-recent first
    # Note: requires 'tac'; if not present, we fallback to plain order
    if command -v tac >/dev/null 2>&1; then
      mapfile -t recent_ids < <( tac "$history_file" \
        | jq -r '.session_id // empty' \
        | awk 'NF' \
        | awk '!seen[$0]++' ) || true
    else
      mapfile -t recent_ids < <( jq -r '.session_id // empty' "$history_file" \
        | awk 'NF' \
        | awk '!seen[$0]++' \
        | tac ) || true
    fi

    # Handle --list
    if (( list_only )); then
      count=0
      for sid in "${recent_ids[@]}"; do
        session_file=$( { find "$sessions_root" -type f -name '*.jsonl' -print0 2>/dev/null \
                        | xargs -0 grep -l -- "$sid" 2>/dev/null \
                        | sort; } | tail -n 1 )
        [[ -z "$session_file" ]] && continue
        base=$(basename "$session_file")
        ts_name=$(printf "%s" "$base" | sed -E 's/.*rollout-([0-9]{4}-[0-9]{2}-[0-9]{2})T([0-9]{2})-([0-9]{2})-([0-9]{2}).*/\1T\2:\3:\4/')
        count=$((count+1))
        printf "%2d. %s  %s  %s\n" "$count" "${ts_name:-"?"}" "$sid" "$base"
        [[ $count -ge $list_count ]] && break
      done
      exit 0
    fi

    # Choose session id based on overrides or default to most recent
    chosen_id=""
    if [[ -n "$session_id_override" ]]; then
      chosen_id="$session_id_override"
    elif [[ -n "$index_override" ]]; then
      idx=$((index_override))
      if (( idx < 1 || idx > ${#recent_ids[@]} )); then
        echo "Error: --index out of range (1..${#recent_ids[@]})" >&2; exit 1
      fi
      chosen_id="${recent_ids[$((idx-1))]}"
    elif (( pick )); then
      # Build a menu for fzf selection
      menu_file="$(mktemp)"
      trap 'rm -f "$menu_file"' EXIT
      count=0
      for sid in "${recent_ids[@]}"; do
        session_file=$( { find "$sessions_root" -type f -name '*.jsonl' -print0 2>/dev/null \
                        | xargs -0 grep -l -- "$sid" 2>/dev/null \
                        | sort; } | tail -n 1 )
        [[ -z "$session_file" ]] && continue
        base=$(basename "$session_file")
        ts_name=$(printf "%s" "$base" | sed -E 's/.*rollout-([0-9]{4}-[0-9]{2}-[0-9]{2})T([0-9]{2})-([0-9]{2})-([0-9]{2}).*/\1T\2:\3:\4/')
        count=$((count+1))
        printf "%2d\t%s\t%s\t%s\n" "$count" "${ts_name:-"?"}" "$sid" "$base" >> "$menu_file"
        [[ $count -ge $list_count ]] && break
      done
      if command -v fzf >/dev/null 2>&1 && [[ -t 1 ]]; then
        selected_line=$(fzf --with-nth=1,2,4 --delimiter='\t' --ansi < "$menu_file" || true)
        chosen_id=$(printf "%s" "$selected_line" | awk -F'\t' '{print $3}')
      else
        echo "Interactive pick requested, but 'fzf' not available or non-interactive TTY." >&2
        echo "Use --list to see options, then re-run with --index N or --id SESSION_ID." >&2
        exit 1
      fi
      if [[ -z "$chosen_id" ]]; then
        echo "No selection made; skipping transcript." >&2
      fi
    else
      chosen_id="${recent_ids[0]:-}"
    fi

    if [[ -z "$chosen_id" ]]; then
      echo "No session selected; skipping transcript." >&2
    else
      session_file=$( { find "$sessions_root" -type f -name '*.jsonl' -print0 2>/dev/null \
                      | xargs -0 grep -l -- "$chosen_id" 2>/dev/null \
                      | sort; } | tail -n 1 )
      if [[ -z "$session_file" ]]; then
        echo "No session file found under $sessions_root for session_id=$chosen_id." >&2
      else
        # Extract user/assistant messages, flattening content[].text or .text
        transcript=$( jq -r '
          select(.type=="message" and (.role=="user" or .role=="assistant")) as $m
          | [ $m.role
            , ( ($m.content[]? | select(.text? and (.text|type=="string")) | .text)
                // ($m.text // "") )
            ]
          | @tsv
        ' "$session_file" \
        | awk -F'\t' 'BEGIN{OFS=""} {
            role=$1; text=$2;
            gsub("\r", "", text);
            if (role=="user")      print "User: ", text;
            else if (role=="assistant") print "Assistant: ", text;
          }' )

        if [[ -n "$limit" && -n "$transcript" ]]; then
          transcript=$(printf "%s\n" "$transcript" | tail -n "$limit")
        fi

        if [[ -n "$transcript" ]]; then
          transcript_content="$transcript"
        fi
      fi
    fi
  fi
fi

# Determine output path (project-root overrides default tmp if provided)
ts=$(date +%s)
if [[ -n "$project_root" && -z "$out" ]]; then
  proj_sessions_dir="$project_root/sessions"
  mkdir -p "$proj_sessions_dir"
  out="$proj_sessions_dir/seed_prompt_${ts}.md"
fi

if [[ -z "$out" ]]; then
  tmp_dir="$HOME/.codex/tmp"
  mkdir -p "$tmp_dir"
  out="$tmp_dir/seed_prompt_${ts}.md"
else
  mkdir -p "$(dirname "$out")"
fi

printf "%b\n" "$content_to_load" > "$out"

# If splitting transcripts, write transcript to a separate file and link it
if (( split )) && [[ -n "$transcript_content" ]]; then
  out_dir="$(dirname "$out")"
  # Derive transcripts dir
  if [[ -n "$project_root" ]]; then
    transcripts_dir="$project_root/sessions/transcripts"
    link_path_rel="./transcripts/transcript_${ts}.md"
  else
    transcripts_dir="$out_dir/transcripts"
    link_path_rel="$transcripts_dir/transcript_${ts}.md"
  fi
  mkdir -p "$transcripts_dir"
  transcript_path="$transcripts_dir/transcript_${ts}.md"
  printf "%b\n" $'=== Last Session Transcript ===\n'"$transcript_content" > "$transcript_path"

  # Replace seed prompt content to include a link instead of inlined transcript
  seed_with_link="$default_message\n\nTranscript: $link_path_rel"
  printf "%b\n" "$seed_with_link" > "$out"

  # Update latest pointers when in a project
  if [[ -n "$project_root" ]]; then
    printf "%b\n" "$seed_with_link" > "$project_root/sessions/latest.md"
    printf "%b\n" $'=== Last Session Transcript ===\n'"$transcript_content" > "$project_root/sessions/latest_transcript.md"
  fi
else
  # Non-split mode: keep existing latest.md behavior
  if [[ -n "$project_root" ]]; then
    latest_path="$project_root/sessions/latest.md"
    printf "%b\n" "$content_to_load" > "$latest_path"
  fi
fi

echo "$out"
