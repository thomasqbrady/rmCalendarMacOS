#!/bin/bash
set -euo pipefail

# Deploy rmCalendarMacOS: commit, tag, push, update tap
# Usage: ./deploy.sh --version 0.1.4
#        ./deploy.sh --version 0.1.4 --message "Fix dependency installation"

TAP_DIR="$HOME/Developer/homebrew-remarkable"
VERSION=""
MESSAGE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --version|-v)  VERSION="$2"; shift 2 ;;
        --message|-m)  MESSAGE="$2"; shift 2 ;;
        *)             echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ -z "$VERSION" ]]; then
    echo "Usage: ./deploy.sh --version X.Y.Z [--message \"commit message\"]"
    exit 1
fi

TAG="v${VERSION}"

if [[ -z "$MESSAGE" ]]; then
    MESSAGE="Release ${TAG}"
fi

echo "==> Deploying rmCalendarMacOS ${TAG}"
echo ""

# 1. Update version in pyproject.toml
echo "--- Updating version in pyproject.toml to ${VERSION}"
sed -i '' "s/^version = \".*\"/version = \"${VERSION}\"/" pyproject.toml

# 2. Stage all changes and commit
echo "--- Committing changes"
git add -A
if git diff --cached --quiet 2>/dev/null; then
    echo "    No changes to commit"
else
    git commit -m "${MESSAGE}"
fi

# 3. Tag
echo "--- Tagging ${TAG}"
git tag "${TAG}"

# 4. Push commit and tag
echo "--- Pushing to origin"
git push
git push origin "${TAG}"

# 5. Wait for the tarball to be available, then compute SHA
echo "--- Computing SHA256 for release tarball"
TARBALL_URL="https://github.com/thomasqbrady/rmCalendarMacOS/archive/refs/tags/${TAG}.tar.gz"

# Give GitHub a moment to generate the tarball
sleep 3

SHA=$(curl -sL "${TARBALL_URL}" | shasum -a 256 | cut -d' ' -f1)
echo "    SHA256: ${SHA}"

# 6. Update the formula
echo "--- Updating Homebrew formula"
sed -i '' "s|sha256 \".*\"|sha256 \"${SHA}\"|" Formula/rmcal.rb
sed -i '' "s|/tags/v[0-9.]*\.tar\.gz|/tags/${TAG}.tar.gz|" Formula/rmcal.rb

# 7. Copy formula to tap repo and push
echo "--- Updating tap repo"
cp Formula/rmcal.rb "${TAP_DIR}/Formula/rmcal.rb"
cd "${TAP_DIR}"
git add Formula/rmcal.rb
git commit -m "Update rmcal to ${TAG}"
git push

# 8. Go back to source repo and commit the updated formula
cd - > /dev/null
git add Formula/rmcal.rb
git commit -m "Update formula SHA for ${TAG}"
git push

# 9. Update the local Homebrew tap so brew sees the new version immediately
echo "--- Updating local Homebrew tap"
BREW_TAP="/opt/homebrew/Library/Taps/thomasqbrady/homebrew-remarkable"
if [[ -d "$BREW_TAP" ]]; then
    cd "$BREW_TAP"
    git pull --rebase
    cd - > /dev/null
else
    brew tap thomasqbrady/remarkable
fi

echo ""
echo "==> Done! Deployed ${TAG}"
echo ""
echo "To install/upgrade:"
echo "  brew reinstall rmcal"
