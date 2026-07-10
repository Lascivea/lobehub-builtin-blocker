#!/usr/bin/env bash
# Add the discovery-layer filter to an existing final image.
# Used when Docker Hub cannot provide a fresh official canary.
set -euo pipefail

cd /opt/lobehub
SCRIPT_DIR=${SCRIPT_DIR:-/opt/lobehub/lobehub-builtin-blocker}
BASE_IMAGE=${BASE_IMAGE:-lobehub/lobehub:canary-antipollute}
FINAL_IMAGE=${FINAL_IMAGE:-lobehub/lobehub:canary-antipollute}
WORK=/tmp/antipollute-discovery-work

docker image inspect "$BASE_IMAGE" >/dev/null
docker rm -f antipollute-discovery-tmp 2>/dev/null || true
docker run -d --name antipollute-discovery-tmp --entrypoint sleep "$BASE_IMAGE" infinity >/dev/null
cleanup() { docker rm -f antipollute-discovery-tmp >/dev/null 2>&1 || true; rm -rf "$WORK"; }
trap cleanup EXIT

mapfile -t CHUNKS < <(docker exec antipollute-discovery-tmp sh -c 'grep -rl "title:e.manifest?.meta?.title})),eE=" /app/.next/server/chunks/ 2>/dev/null')
[[ "${#CHUNKS[@]}" -gt 0 ]] || { echo "No discovery chunk found" >&2; exit 1; }

mkdir -p "$WORK"
for chunk in "${CHUNKS[@]}"; do
  base=$(basename "$chunk")
  docker cp "antipollute-discovery-tmp:$chunk" "$WORK/$base"
done

python3 "$SCRIPT_DIR/antipollute_patch.py" --only=P7 --apply "$WORK"/*.js
for file in "$WORK"/*.js; do
  docker cp "$file" antipollute-discovery-tmp:/tmp/check.js
  docker exec antipollute-discovery-tmp /bin/node --check /tmp/check.js
done
for chunk in "${CHUNKS[@]}"; do
  base=$(basename "$chunk")
  docker cp "$WORK/$base" "antipollute-discovery-tmp:$chunk"
done

docker commit --change 'ENTRYPOINT ["/bin/node"]' --change 'CMD ["/app/startServer.js"]' \
  antipollute-discovery-tmp "$FINAL_IMAGE" >/dev/null
docker compose -f docker-compose.yml -f docker-compose.mcpfix.yml -f docker-compose.antipollute.yml \
  up -d --force-recreate lobe
echo "Discovery filter applied to $FINAL_IMAGE"
