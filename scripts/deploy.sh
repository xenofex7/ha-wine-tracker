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

# 4g. docs/llm.txt — update version + regenerate content via Claude CLI
if [[ -f "docs/llm.txt" ]]; then
  # Always bump the version string first
  sed -i '' "s/v${CURRENT_VERSION}/v${SEMVER}/g" docs/llm.txt
  ok "docs/llm.txt version bumped to ${SEMVER}"

  if command -v claude &> /dev/null; then
    info "Regenerating docs/llm.txt with Claude..."

    LLM_PROMPT="You are updating the llm.txt file for Wine Tracker v${SEMVER}, a wine cellar management app (Home Assistant add-on + standalone Docker).

Use the existing llm.txt as your structural template — keep the same sections and writing style.
Update all content that has changed: version number, AI providers, API endpoints, config options, features, and any other details that differ from the source code.

--- CURRENT llm.txt ---
$(cat docs/llm.txt)

--- app.py (source of truth for endpoints, providers, config) ---
$(grep -E 'def |@app\.route|ai_provider|load_options|APP_VERSION|HA_OPTIONS' wine-tracker/app/app.py | head -120)

--- config.yaml (source of truth for options schema) ---
$(cat wine-tracker/config.yaml)

Rules:
- Keep the exact same structure and section headings as the current llm.txt
- Update version to v${SEMVER} everywhere
- Add any new AI providers, endpoints, config options, features that appear in the source code but are missing from llm.txt
- Remove or correct anything that no longer matches the source code
- Keep descriptions concise and factual — this file is read by LLMs, not humans
- Output ONLY the updated llm.txt content, no explanation, no markdown fences"

    NEW_LLM=$(echo "$LLM_PROMPT" | claude --print 2>/dev/null || echo "")

    if [[ -n "$NEW_LLM" ]]; then
      # Show diff before overwriting
      echo ""
      echo -e "${CYAN}── docs/llm.txt diff ────────────────────${NC}"
      diff <(cat docs/llm.txt) <(echo "$NEW_LLM") || true
      echo -e "${CYAN}─────────────────────────────────────────${NC}"
      echo ""
      warn "Apply this updated llm.txt? (y/N — N keeps the version-only bump)"
      read -r CONFIRM_LLM
      if [[ "$CONFIRM_LLM" =~ ^[yY]$ ]]; then
        echo "$NEW_LLM" > docs/llm.txt
        ok "docs/llm.txt regenerated by Claude"
      else
        warn "Skipped Claude update — version bump kept, content unchanged"
        warn "Remember to update docs/llm.txt manually before the next release"
      fi
    else
      warn "Claude generation failed — version bump kept, please review docs/llm.txt manually"
    fi
  else
    # No Claude CLI — fall back to manual reminder
    echo ""
    warn "┌─────────────────────────────────────────────────────────┐"
    warn "│  ACTION REQUIRED: Review docs/llm.txt for new features  │"
    warn "│  Version was bumped automatically, but new features,    │"
    warn "│  providers, endpoints or config options must be added   │"
    warn "│  manually. Install claude CLI to automate this step.    │"
    warn "│                                                          │"
    warn "│  Open: docs/llm.txt                                     │"
    warn "└─────────────────────────────────────────────────────────┘"
    echo ""
    warn "Press Enter to continue (or Ctrl+C to abort and edit first)..."
    read -r
  fi
fi

# ── 5. Generate CHANGELOG entry ───────────────────────────
info "Generating changelog entry..."

# Find the previous tag (if any)
PREV_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")

if [[ -n "$PREV_TAG" ]]; then
  COMMIT_RANGE="${PREV_TAG}..HEAD"
  info "Commits since ${PREV_TAG}:"
else
  COMMIT_RANGE="HEAD"
  info "All commits (no previous tag found):"
fi

# Collect raw commit messages
COMMITS=""
while IFS= read -r line; do
  msg="${line#* }" # strip hash
  # Skip release commits and trivial changes
  case "$msg" in
    Release\ v*|Merge\ *) continue ;;
  esac
  COMMITS+="${msg}"$'\n'
done < <(git log "$COMMIT_RANGE" --oneline --no-merges 2>/dev/null || git log --oneline --no-merges)

# Use Claude CLI to generate a user-friendly changelog (if available)
if command -v claude &> /dev/null && [[ -n "$COMMITS" ]]; then
  info "Generating user-friendly changelog with Claude..."

  PROMPT="You are writing a changelog for Wine Tracker, a wine cellar management app (Home Assistant add-on and Docker standalone).

Based on these git commits, write a concise changelog section in English.

Commits:
${COMMITS}

Rules:
- Write from the user's perspective, NOT technical (no code, no frameworks, no database internals)
- Each entry starts with '- **Title** - description' (use bold title, hyphen, then explanation)
- Max 5-8 entries total, consolidate if needed
- No duplicates, no trivial changes (e.g. .gitignore, lint fixes)
- No introductory text, just the list of entries
- Do NOT include a heading — just the bullet points
- Example good entry: '- **Bottle format support** - track different wine bottle sizes from Piccolo to Nebuchadnezzar with a new dropdown in the wine form'
- Example bad entry: '- Fix TypeScript types in allocation reducer'"

  CHANGELOG_BODY=$(echo "$PROMPT" | claude --print 2>/dev/null || echo "")

  if [[ -n "$CHANGELOG_BODY" ]]; then
    CHANGELOG_ENTRY="## ${SEMVER}"$'\n\n'"${CHANGELOG_BODY}"
    ok "Changelog generated by Claude"
  else
    warn "Claude generation failed, falling back to commit-based changelog"
    CHANGELOG_ENTRY="## ${SEMVER}"$'\n'
    while IFS= read -r line; do
      [[ -n "$line" ]] && CHANGELOG_ENTRY+=$'\n'"- ${line}"
    done <<< "$COMMITS"
  fi
else
  # Fallback: use commit messages directly
  CHANGELOG_ENTRY="## ${SEMVER}"$'\n'
  while IFS= read -r line; do
    [[ -n "$line" ]] && CHANGELOG_ENTRY+=$'\n'"- ${line}"
  done <<< "$COMMITS"
fi

# Insert new entry after "# Changelog" header in BOTH changelog files
for CL_FILE in CHANGELOG.md wine-tracker/CHANGELOG.md; do
  if [[ -f "$CL_FILE" ]]; then
    TEMP_FILE=$(mktemp)
    ENTRY_FILE=$(mktemp)
    echo "$CHANGELOG_ENTRY" > "$ENTRY_FILE"

    # Insert after "# Changelog" line, before the first "## " entry
    awk -v entry_file="$ENTRY_FILE" '
      /^# Changelog/ {
        print $0
        print ""
        while ((getline line < entry_file) > 0) print line
        next
      }
      { print }
    ' "$CL_FILE" > "$TEMP_FILE"

    mv "$TEMP_FILE" "$CL_FILE"
    rm -f "$ENTRY_FILE"
    ok "${CL_FILE} updated"
  fi
done

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
