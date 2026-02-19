#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
#  set_version_nr.sh – Wine Tracker Version Updater
#  Updates the version number in all relevant project files.
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# Project root = directory where this script lives
ROOT="$(cd "$(dirname "$0")" && pwd)"

# Files that contain the version number
CONFIG="$ROOT/wine-tracker/config.yaml"
README="$ROOT/README.md"
DOCS="$ROOT/wine-tracker/DOCS.md"

# ── Read current version from config.yaml ─────────────────────────────────────
CURRENT=$(sed -n 's/^version: "\(.*\)"/\1/p' "$CONFIG" 2>/dev/null)
CURRENT="${CURRENT:-unknown}"

echo ""
echo "  🍷 Wine Tracker – Version Updater"
echo "  ──────────────────────────────────"
echo ""
echo "  Aktuelle Version:  $CURRENT"
echo ""

# ── Ask for new version ───────────────────────────────────────────────────────
read -rp "  Neue Version [$CURRENT]: " NEW_VERSION
NEW_VERSION="${NEW_VERSION:-$CURRENT}"

if [[ "$NEW_VERSION" == "$CURRENT" ]]; then
  echo ""
  echo "  ✓ Version bleibt bei $CURRENT – nichts geändert."
  echo ""
  exit 0
fi

# ── Validate format (semver-ish: X.Y.Z or X.Y) ──────────────────────────────
if ! [[ "$NEW_VERSION" =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?$ ]]; then
  echo ""
  echo "  ✗ Ungültiges Format: '$NEW_VERSION'"
  echo "    Erwartet: X.Y.Z oder X.Y (z.B. 0.4.1, 1.0.0)"
  echo ""
  exit 1
fi

# ── Update config.yaml ───────────────────────────────────────────────────────
sed -i '' -e "s/^version: \".*\"/version: \"$NEW_VERSION\"/" "$CONFIG"
echo "  ✓ config.yaml          → $NEW_VERSION"

# ── Update README.md badge ────────────────────────────────────────────────────
sed -i '' -e "s|version-v[0-9.]*-blue|version-v${NEW_VERSION}-blue|g" "$README"
echo "  ✓ README.md (badge)    → v$NEW_VERSION"

# ── Update DOCS.md badge ─────────────────────────────────────────────────────
sed -i '' -e "s|version-v[0-9.]*-blue|version-v${NEW_VERSION}-blue|g" "$DOCS"
echo "  ✓ DOCS.md (badge)      → v$NEW_VERSION"

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "  ──────────────────────────────────"
echo "  ✅ Version aktualisiert: $CURRENT → $NEW_VERSION"
echo ""
echo "  Vergiss nicht:"
echo "    git add -A && git commit -m \"Bump version to v$NEW_VERSION\""
echo ""
