#!/bin/bash
# ---------------------------------------------------------------------------
# The repo is already initialised and committed. This only pushes it to
# https://github.com/Hildacmd/planting_pipeline
#
#   cd ~/Downloads/planting_pipeline && bash push_to_github.sh
# ---------------------------------------------------------------------------
set -e
cd "$(dirname "$0")"

# clear any stale lock left by the sandbox that prepared this repo
rm -f .git/index.lock .git/HEAD.lock .git/objects/maintenance.lock

if ! git lfs version >/dev/null 2>&1; then
  echo "==> Git LFS is required to upload the large files."
  if command -v brew >/dev/null 2>&1; then
    brew install git-lfs
  else
    echo "    Homebrew not found. Install Git LFS from https://git-lfs.com and re-run."
    exit 1
  fi
fi
git lfs install --local

echo "==> Commit ready:"
git log --oneline -1
echo "==> LFS files: $(git lfs ls-files | wc -l | tr -d ' ')   Repo size: $(du -sh .git | cut -f1)"

echo "==> Pushing (uploads ~700 MB, expect a while)"
git push -u origin main

echo
echo "Done -> https://github.com/Hildacmd/planting_pipeline"
