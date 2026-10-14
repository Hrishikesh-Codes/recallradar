#!/usr/bin/env bash
# Deploy the latest commit on main, but only once its CI run has passed. Run every 10 minutes by
# recallradar-update.timer, so no deploy keys or SSH access are needed in GitHub.
set -euo pipefail

home=/opt/recallradar
repo=Hrishikesh-Codes/recallradar
cd "$home/src"

git fetch -q origin main
target=$(git rev-parse origin/main)
if [[ "$(cat "$home/deployed" 2>/dev/null || true)" == "$target" ]]; then
  exit 0
fi
if grep -q CHANGE_ME "$home/.env"; then
  echo "Fill in $home/.env before the first deploy."
  exit 0
fi

# The CI workflow's run for this exact commit must have finished successfully.
ci=$(curl -fsS "https://api.github.com/repos/$repo/actions/runs?head_sha=$target&per_page=50" |
  jq -r '[.workflow_runs[] | select(.name == "CI")] | first | "\(.status) \(.conclusion)"')
if [[ "$ci" != "completed success" ]]; then
  echo "Not deploying ${target:0:7}: CI is '$ci'."
  exit 0
fi

echo "Deploying ${target:0:7}…"
git checkout -q --detach "$target"
compose=(docker compose -f deploy/oracle/compose.yaml)
"${compose[@]}" build api
# Migrate before the new API starts: it may expect new columns.
"${compose[@]}" run --rm --no-deps api alembic -c packages/core/alembic.ini upgrade head
"${compose[@]}" up -d --remove-orphans
docker image prune -f >/dev/null
echo "$target" >"$home/deployed"
echo "Deployed ${target:0:7}."
