
#!/usr/bin/env bash
set -Eeuo pipefail

EXPECTED_SHA="${1:?Missing commit SHA}"
DEPLOY_PATH="${2:?Missing deployment path}"

echo "=== TESTFORGE DEPLOYMENT ==="

cd "$DEPLOY_PATH"

echo "1. Checking Git working tree..."

if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "ERROR: Tracked local changes exist."
    exit 1
fi

echo "2. Fetching latest code..."
git fetch origin main

REMOTE_SHA="$(git rev-parse FETCH_HEAD)"

if [ "$REMOTE_SHA" != "$EXPECTED_SHA" ]; then
    echo "ERROR: GitLab and VM remote commits differ."
    echo "Expected: $EXPECTED_SHA"
    echo "Remote:   $REMOTE_SHA"
    echo "Check GitHub/GitLab synchronization."
    exit 1
fi

echo "3. Updating code..."
git merge --ff-only FETCH_HEAD

echo "4. Validating Docker configuration..."
docker compose --profile public config --quiet

echo "5. Building and starting containers..."
docker compose --profile public up \
    -d --build --wait --wait-timeout 180

echo "6. Checking service status..."
docker compose --profile public ps

echo "7. Deployment successful!"
echo "Deployed commit: $(git rev-parse HEAD)"