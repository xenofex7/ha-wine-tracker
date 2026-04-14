#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────
# deploy.sh — Automated release pipeline for Wine Tracker
#
# Usage:
#   ./scripts/deploy.sh v1.8.0
#   ./scripts/deploy.sh v2.0.0
#
# Steps:
#   1. Validate version argument (must be semver: vX.Y.Z)
#   2. Check for clean working tree
#   3. Run all tests (pytest)
#   4. Update version in 7 files (incl. docs/llm.txt)
#   5. Generate CHANGELOG entry from git log
#   6. Commit version bump + changelog
#   7. Create git tag
#   8. Push commit + tag to origin
#   9. Create GitHub Release (triggers Docker/GHCR build)
# ─────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# Project root (one level up from scripts/)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# ── 1. Validate version argument ──────────────────────────
VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
  error "Usage: ./scripts/deploy.sh v1.8.0"
fi

# Strip leading 'v' for file updates, keep it for git tag
if [[ "$VERSION" =~ ^v?([0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
  SEMVER="${BASH_REMATCH[1]}"
  TAG="v${SEMVER}"
else
  error "Invalid version format: $VERSION (expected vX.Y.Z)"
fi

CURRENT_VERSION=$(sed -n 's/^version: "\([0-9]*\.[0-9]*\.[0-9]*\)"/\1/p' wine-tracker/config.yaml)
info "Current version: ${CURRENT_VERSION}"
info "New version:     ${SEMVER} (tag: ${TAG})"
echo ""

# ── 2. Check working tree ─────────────────────────────────
if [[ -n "$(git status --porcelain)" ]]; then
  error "Working tree is not clean. Commit or stash your changes first."
fi

BRANCH=$(git branch --show-current)
if [[ "$BRANCH" != "main" ]]; then
  warn "You are on branch '${BRANCH}', not 'main'. Continue? (y/N)"
  read -r CONFIRM
  [[ "$CONFIRM" =~ ^[yY]$ ]] || exit 0
fi

ok "Working tree is clean (branch: ${BRANCH})"

# ── 3. Run tests ──────────────────────────────────────────
info "Running tests..."
.venv/bin/python -m pytest wine-tracker/tests/ -v
ok "All tests passed"

# ── 4. Update version in 7 files ──────────────────────────
info "Updating version to ${SEMVER} in all files..."

# 4a. wine-tracker/config.yaml — version: "X.Y.Z"
sed -i '' "s/^version: \"${CURRENT_VERSION}\"/version: \"${SEMVER}\"/" wine-tracker/config.yaml
ok "wine-tracker/config.yaml updated"

# 4b. wine-tracker/app/app.py — APP_VERSION = "X.Y.Z"
sed -i '' "s/APP_VERSION = \"${CURRENT_VERSION}\"/APP_VERSION = \"${SEMVER}\"/" wine-tracker/app/app.py
ok "wine-tracker/app/app.py updated"

# 4c. wine-tracker/tests/test_routes.py — assert "vX.Y.Z"
sed -i '' "s/\"v${CURRENT_VERSION}\"/\"v${SEMVER}\"/" wine-tracker/tests/test_routes.py
ok "wine-tracker/tests/test_routes.py updated"

# 4d. README.md — version badge
sed -i '' "s/version-v${CURRENT_VERSION}-blue/version-v${SEMVER}-blue/" README.md
ok "README.md updated"

# 4e. wine-tracker/README.md — version badge
sed -i '' "s/version-v${CURRENT_VERSION}-blue/version-v${SEMVER}-blue/" wine-tracker/README.md
ok "wine-tracker/README.md updated"

# 4f. wine-tracker/DOCS.md — version badge
sed -i '' "s/version-v${CURRENT_VERSION}-blue/version-v${SEMVER}-blue/" wine-tracker/DOCS.md
ok "wine-tracker/DOCS.md updated"

# 4g. docs/llm.txt — bump version only. Content regeneration is handled
# separately (post-release) because the claude --print CLI call tends to hang
# or require auth prompts that break non-interactive deploys.
if [[ -f "docs/llm.txt" ]]; then
  sed -i '' "s/v${CURRENT_VERSION}/v${SEMVER}/g" docs/llm.txt
  ok "docs/llm.txt version bumped to ${SEMVER} (content regen deferred to post-release)"
fi

# ── 5. Read CHANGELOG entry ───────────────────────────────
# We no longer auto-generate the changelog via claude --print (hangs in
# practice). Instead the caller must have written a `## X.Y.Z` section into
# CHANGELOG.md manually before running this script.
info "Reading changelog entry for ${SEMVER} from CHANGELOG.md..."

CHANGELOG_ENTRY=$(awk -v ver="## ${SEMVER}" '
  $0 == ver { found=1; print; next }
  found && /^## [0-9]/ { exit }
  found { print }
' CHANGELOG.md)

if [[ -z "$CHANGELOG_ENTRY" ]]; then
  error "No '## ${SEMVER}' section found in CHANGELOG.md. Add it manually before running deploy."
fi

# Mirror the root CHANGELOG.md into wine-tracker/CHANGELOG.md so both stay in sync
if [[ -f "wine-tracker/CHANGELOG.md" ]]; then
  cp CHANGELOG.md wine-tracker/CHANGELOG.md
  ok "wine-tracker/CHANGELOG.md synced from root CHANGELOG.md"
fi

# Show the entry
echo ""
echo -e "${CYAN}── Changelog Entry ──────────────────────${NC}"
echo "$CHANGELOG_ENTRY"
echo -e "${CYAN}─────────────────────────────────────────${NC}"
echo ""

# ── 6. Commit ─────────────────────────────────────────────
info "Committing version bump..."
git add \
  wine-tracker/config.yaml \
  wine-tracker/app/app.py \
  wine-tracker/tests/test_routes.py \
  README.md \
  wine-tracker/README.md \
  wine-tracker/DOCS.md \
  CHANGELOG.md \
  wine-tracker/CHANGELOG.md \
  docs/llm.txt
git commit -m "$(cat <<EOF
Release ${TAG}

- Bump version to ${SEMVER} in all 7 files
- Update both CHANGELOGs with release notes
- Update docs/llm.txt version
EOF
)"
ok "Committed"

# ── 7. Create git tag ─────────────────────────────────────
info "Creating tag ${TAG}..."
git tag -a "$TAG" -m "Release ${TAG}"
ok "Tag ${TAG} created"

# ── 8. Push and create GitHub Release ────────────────────
info "Pushing to origin..."
git push origin "$BRANCH"
git push origin "$TAG"
ok "Pushed commit and tag"

# ── 9. Create GitHub Release ─────────────────────────────
if command -v gh &> /dev/null; then
  info "Creating GitHub Release..."

  gh release create "$TAG" \
    --title "Release ${TAG}" \
    --notes "$CHANGELOG_ENTRY" \
    --latest

  ok "GitHub Release created"
else
  warn "gh CLI not installed — create the release manually on GitHub"
  warn "Go to: https://github.com/xenofex7/ha-wine-tracker/releases/new?tag=${TAG}"
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Release ${TAG} complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  Docker/GHCR image will be built by GitHub Actions."
echo "  Monitor the build: https://github.com/xenofex7/ha-wine-tracker/actions"
echo ""
