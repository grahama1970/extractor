#!/usr/bin/env bash
# Blind adversarial test suite for EmbryStyle dark theme compliance
# The coding agent sees ONLY pass/fail output — never assertions or expected values.
set -euo pipefail

TARGET="${1:-../src}"
RESULTS_JSON="${2:-results.json}"
cd "$(dirname "$0")"

PASS=0
FAIL=0
FAILURES=()

check() {
  local name="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    PASS=$((PASS + 1))
  else
    FAIL=$((FAIL + 1))
    FAILURES+=("$name")
  fi
}

# ─── T1: Dark mode class on HTML root ───────────────────────────────
check "[dark-mode] HTML root has dark class" \
  grep -q 'class="[^"]*dark[^"]*"' "$TARGET/../index.html"

# ─── T2: data-distance attribute on HTML root ───────────────────────
check "[distance] HTML root has data-distance attribute" \
  grep -q 'data-distance=' "$TARGET/../index.html"

# ─── T3: EmbryStyle background token (0 0% 4%) ─────────────────────
check "[tokens] .dark background is EmbryStyle #0a0a0a" \
  grep -qP '^\s+--background:\s*0\s+0%\s+4%' "$TARGET/index.css"

# ─── T4: EmbryStyle surface token (0 0% 9%) ────────────────────────
check "[tokens] .dark card is EmbryStyle #171717" \
  grep -qP '^\s+--card:\s*0\s+0%\s+9%' "$TARGET/index.css"

# ─── T5: EmbryStyle border token (0 0% 25%) ────────────────────────
check "[tokens] .dark border is EmbryStyle #404040" \
  grep -qP '^\s+--border:\s*0\s+0%\s+25%' "$TARGET/index.css"

# ─── T6: EmbryStyle muted-foreground token ──────────────────────────
check "[tokens] .dark muted-foreground is EmbryStyle #a3a3a3" \
  grep -qP '^\s+--muted-foreground:\s*0\s+0%\s+64%' "$TARGET/index.css"

# ─── T7: NVIS HUD annotation overrides exist ───────────────────────
check "[nvis] HUD annotation overrides defined" \
  grep -q 'data-distance="hud"' "$TARGET/index.css"

# ─── T8: NVIS uses hostile red (0 100% 50%) ────────────────────────
check "[nvis] HUD section annotation is hostile red" \
  bash -c 'sed -n "/data-distance=\"hud\"/,/}/p" "$1/index.css" | grep -qP "annotation-section.*0\s+100%\s+50%"' _ "$TARGET"

# ─── T9: NVIS uses primary green ───────────────────────────────────
check "[nvis] HUD text annotation uses NVIS green" \
  bash -c 'sed -n "/data-distance=\"hud\"/,/}/p" "$1/index.css" | grep -qP "annotation-text.*120\s+100%\s+50%"' _ "$TARGET"

# ─── T10: font-mono CSS utility defined ─────────────────────────────
check "[typography] font-mono utility class defined in CSS" \
  grep -qP '\.font-mono\s*\{' "$TARGET/index.css"

# ─── T11: JetBrains Mono in font stack ─────────────────────────────
check "[typography] JetBrains Mono in font-mono stack" \
  grep -q "JetBrains Mono" "$TARGET/index.css"

# ─── T12: No text-destructive on panel headings ────────────────────
check "[semantic] ClassicLayout panel headings do NOT use text-destructive" \
  bash -c '! grep -B2 -A2 "Explorer\|Inspector\|Annotation" "$1/pages/ClassicLayout.tsx" | grep -q "text-destructive"' _ "$TARGET"

# ─── T13: Panel headings use muted-foreground ──────────────────────
check "[semantic] ClassicLayout panel headings use muted-foreground" \
  bash -c 'grep -A1 "Explorer" "$1/pages/ClassicLayout.tsx" | grep -q "muted-foreground"' _ "$TARGET"

# ─── T14: font-mono on stem identifiers (ReviewLayout) ─────────────
check "[mono] ReviewLayout stem uses font-mono" \
  grep -q 'font-mono.*run\.stem\|run\.stem.*font-mono' "$TARGET/pages/ReviewLayout.tsx"

# ─── T15: font-mono on page count (ReviewLayout) ───────────────────
check "[mono] ReviewLayout page_count uses font-mono" \
  bash -c 'grep "page_count" "$1/pages/ReviewLayout.tsx" | grep -q "font-mono"' _ "$TARGET"

# ─── T16: font-mono on stem identifiers (QuarantineView) ───────────
check "[mono] QuarantineView stem uses font-mono" \
  bash -c 'grep "font-mono" "$1/pages/QuarantineView.tsx" | grep -q "stem\|truncate"' _ "$TARGET"

# ─── T17: font-mono on page count (QuarantineView) ─────────────────
check "[mono] QuarantineView page_count uses font-mono" \
  bash -c 'grep "page_count" "$1/pages/QuarantineView.tsx" | grep -q "font-mono"' _ "$TARGET"

# ─── T18: font-mono on confidence/score data ────────────────────────
check "[mono] ReviewLayout confidence uses font-mono" \
  bash -c 'grep -i "confidence\|score" "$1/pages/ReviewLayout.tsx" | grep -q "font-mono"' _ "$TARGET"

# ─── T19: No hardcoded light bg in NotFound ─────────────────────────
check "[tokens] NotFound page uses semantic tokens (no bg-gray/bg-white)" \
  bash -c '! grep -qP "bg-gray|bg-white|#f[0-9a-f]{5}" "$1/pages/NotFound.tsx"' _ "$TARGET"

# ─── T20: NotFound uses bg-background ──────────────────────────────
check "[tokens] NotFound page uses bg-background" \
  grep -q "bg-background" "$TARGET/pages/NotFound.tsx"

# ─── T21: QuarantineView empty state has surface card ───────────────
check "[empty-state] QuarantineView empty state uses bg-card" \
  bash -c 'grep -A5 "filtered.length === 0\|Queue clear" "$1/pages/QuarantineView.tsx" | grep -q "bg-card"' _ "$TARGET"

# ─── T22: ReviewLayout selected item has left border ────────────────
check "[selection] ReviewLayout selected item has left-border indicator" \
  bash -c 'grep "selectedStem" "$1/pages/ReviewLayout.tsx" | grep -q "border-l"' _ "$TARGET"

# ─── T23: ClassicLayout PDF canvas has ring/shadow ──────────────────
check "[canvas] ClassicLayout PDF canvas has ring or shadow" \
  bash -c 'grep -B20 "PdfCanvas" "$1/pages/ClassicLayout.tsx" | grep -qP "ring|shadow"' _ "$TARGET"

# ─── T24: QuarantineView heading has tracking-wider ─────────────────
check "[typography] QuarantineView heading has tracking-wider" \
  bash -c 'grep -i "quarantine" "$1/pages/QuarantineView.tsx" | grep -q "tracking-wider"' _ "$TARGET"

# ─── T25: Vite build succeeds ──────────────────────────────────────
check "[build] Vite build completes without errors" \
  bash -c 'cd "$1/.." && npx vite build 2>&1 | tail -1 | grep -q "built in"' _ "$TARGET"

# ─── T26: No bg-gray-100 in page components ────────────────────────
check "[tokens] No bg-gray-100 in page components" \
  bash -c '! grep -r "bg-gray-100" "$1/pages/"' _ "$TARGET"

# ─── T27: Sidebar tokens mapped to EmbryStyle ──────────────────────
check "[tokens] Sidebar background uses EmbryStyle surface" \
  grep -qP '^\s+--sidebar-background:\s*0\s+0%\s+9%' "$TARGET/index.css"

# ─── T28: Dark theme status colors present ──────────────────────────
check "[tokens] Status-complete color defined in dark theme" \
  bash -c 'sed -n "/\.dark/,/^  }/p" "$1/index.css" | grep -q "status-complete"' _ "$TARGET"

# ─── T29: Persona accent CSS utility ───────────────────────────────
check "[tokens] Persona accent utility classes defined" \
  grep -q "text-persona\|\.text-persona" "$TARGET/index.css"

# ─── T30: Full viewport setup ──────────────────────────────────────
check "[layout] html/body/#root have 100% height" \
  grep -q '#root.*height.*100%\|height.*100%.*#root' "$TARGET/index.css"

# ─── Report ─────────────────────────────────────────────────────────
TOTAL=$((PASS + FAIL))
echo ""
echo "═══════════════════════════════════════════════"
echo "  BLIND TEST RESULTS: EmbryStyle Compliance"
echo "═══════════════════════════════════════════════"
echo "  PASS: $PASS / $TOTAL"
echo "  FAIL: $FAIL / $TOTAL"
echo "═══════════════════════════════════════════════"

if [ ${#FAILURES[@]} -gt 0 ]; then
  echo ""
  echo "FAILURES:"
  for f in "${FAILURES[@]}"; do
    echo "  - $f"
  done
fi

# Write JSON results
cat > "$RESULTS_JSON" <<ENDJSON
{
  "target": "$TARGET",
  "timestamp": "$(date -Iseconds)",
  "total": $TOTAL,
  "pass": $PASS,
  "fail": $FAIL,
  "status": "$([ $FAIL -eq 0 ] && echo PASS || echo FAIL)",
  "failures": [$(printf '"%s",' "${FAILURES[@]}" 2>/dev/null | sed 's/,$//' )]
}
ENDJSON

echo ""
echo "Results written to $RESULTS_JSON"
exit $FAIL
