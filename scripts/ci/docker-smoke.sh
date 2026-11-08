#!/bin/sh
set -eu

: "${CI_JOB_ID:?This script must run in an isolated CI checkout with CI_JOB_ID set}"
case "$CI_JOB_ID" in
  *[!0-9]*|'') echo "CI_JOB_ID must be numeric" >&2; exit 1 ;;
esac
export COMPOSE_PROJECT_NAME="testforge-ci-${CI_JOB_ID}"
mkdir -p .ci-artifacts

# Never overwrite a developer's real configuration, even during a local rehearsal.
if [ -e backend/.env ]; then
  echo "Refusing to replace existing backend/.env; use a clean CI checkout" >&2
  exit 1
fi
cp backend/.env.example backend/.env

compose() {
  docker compose -f compose.yaml -f compose.ci.yaml "$@"
}

cleanup() {
  status=$?
  trap - EXIT
  compose logs --no-color > .ci-artifacts/compose.log 2>&1 || true
  compose ps --all > .ci-artifacts/compose-ps.txt 2>&1 || true
  compose down --volumes --remove-orphans > .ci-artifacts/cleanup.log 2>&1 || true
  rm -f backend/.env
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# The DinD service may still be finishing startup after its TCP healthcheck.
attempt=0
until docker info > /dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    echo "Docker unavailable: check privileged runner and shared /certs/client TLS volume" >&2
    docker info
    exit 1
  fi
  sleep 1
done

docker version
docker compose version
compose config --quiet
compose build
docker run --rm --init "${COMPOSE_PROJECT_NAME}-backend" python -m backend.tests.container_smoke --image-only
compose up -d --wait --wait-timeout 120
compose exec -T backend python -m backend.tests.container_smoke
# Probe inside the Compose network: localhost in the job is not the DinD service.
compose exec -T backend python - < scripts/ci/check_http.py
