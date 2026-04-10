#!/usr/bin/env bash
# 04-verify.sh — Run the automated checklist on every HTML file in a batch.
#
# Why this exists:
#   Catches structural issues (missing tables, charts, FAQs, sources, CTA, disclaimer)
#   BEFORE publishing. If anything fails, fix it locally and re-run before
#   wasting Sanity API calls and CDN cache.
#
# Usage:
#   bash 04-verify.sh <batch-directory>

set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: bash 04-verify.sh <batch-directory>"
  exit 1
fi

BATCH_DIR="$1"

if [ ! -d "$BATCH_DIR" ]; then
  echo "ERROR: not a directory: $BATCH_DIR"
  exit 1
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=== VERIFY: $BATCH_DIR ==="
echo ""

PASS_COUNT=0
FAIL_COUNT=0

for f in "$BATCH_DIR"/*.html; do
  [ -f "$f" ] || continue
  name=$(basename "$f")

  # Counts
  # grep -c prints "0" on zero matches and exits 1 — use `|| true` so set -e
  # tolerates the exit code without adding a second "0" to stdout.
  wrappers=$(grep -c "<!DOCTYPE\|<html\|<head\|<style\|<script" "$f" 2>/dev/null || true)
  tables=$(grep -c "<table" "$f" 2>/dev/null || true)
  imgs=$(grep -c "<img" "$f" 2>/dev/null || true)
  svgs=$(grep -c "<svg" "$f" 2>/dev/null || true)
  figures=$(grep -c "<figure" "$f" 2>/dev/null || true)
  faqs=$(grep -c "<h3>" "$f" 2>/dev/null || true)
  sources=$(grep -c "<li><a" "$f" 2>/dev/null || true)
  cta=$(grep -c 'Ask Silvia</a>\|cfosilvia.com</a>' "$f" 2>/dev/null || true)
  disclaimer=$(grep -c "informational purposes" "$f" 2>/dev/null || true)
  banned_phrase=$(grep -ic "consult a qualified" "$f" 2>/dev/null || true)
  words=$(wc -w < "$f" 2>/dev/null || echo 0)

  fails=""
  [ "${wrappers:-0}" -gt 0 ] && fails="$fails WRAPPERS"
  [ "${tables:-0}" -lt 1 ] && fails="$fails NO_TABLE"
  [ "${imgs:-0}" -gt 0 ] && fails="$fails UNEXPECTED_IMG(${imgs:-0})"
  [ "${svgs:-0}" -gt 0 ] && fails="$fails RAW_SVG"
  [ "${figures:-0}" -gt 0 ] && fails="$fails RAW_FIGURE"
  [ "${faqs:-0}" -lt 3 ] && fails="$fails LOW_FAQ(${faqs:-0})"
  [ "${sources:-0}" -lt 3 ] && fails="$fails LOW_SRC(${sources:-0})"
  [ "${cta:-0}" -lt 1 ] && fails="$fails NO_CTA"
  [ "${disclaimer:-0}" -lt 1 ] && fails="$fails NO_DISC"
  [ "${banned_phrase:-0}" -gt 0 ] && fails="$fails BANNED_CONSULT_PHRASE"
  [ "${words:-0}" -lt 800 ] && fails="$fails SHORT(${words:-0})"

  if [ -z "$fails" ]; then
    printf "${GREEN}PASS${NC} %-50s | %4dw | tbl:%s faq:%s src:%s\n" \
      "$name" "${words:-0}" "${tables:-0}" "${faqs:-0}" "${sources:-0}"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    printf "${RED}FAIL${NC} %-50s |%s\n" "$name" "$fails"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
done

echo ""
echo "=== SUMMARY ==="
printf "${GREEN}PASS: %d${NC}\n" "$PASS_COUNT"
printf "${RED}FAIL: %d${NC}\n" "$FAIL_COUNT"
echo ""

if [ "$FAIL_COUNT" -gt 0 ]; then
  echo -e "${RED}DO NOT PUBLISH until all FAIL items are fixed.${NC}"
  exit 1
fi

echo -e "${GREEN}All automated checks passed. Ready to publish.${NC}"
