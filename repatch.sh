#!/bin/bash
# repatch.sh — One-shot repatch: builds lobehub/lobehub:canary-antipollute
#
# Combines two independent patches in sequence:
#   1. mcpfix   — MCP session reuse fix (5 patch points)
#   2. antipollute — Disable polluted builtin tools/skills (6 patch points)
#
# Toggle via .env file:
#   ENABLE_MCPFIX=true       # Apply MCP session fix
#   ENABLE_ANTIPOLLUTE=true  # Apply builtin tool blacklist
#
# Image tag produced:
#   lobehub/lobehub:canary-antipollute (contains all enabled patches)
#
# ⚠️  Official LobeHub fix:
#   MCP session reuse: branch `fix/mcp-session-retry` (5a0d13f)
#   Builtin tool control: no official fix yet; this project is the workaround
set -euo pipefail

cd /opt/lobehub
SCRIPT_DIR=${SCRIPT_DIR:-/opt/lobehub/lobehub-builtin-blocker}

# Load .env if present
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

ENABLE_MCPFIX=${ENABLE_MCPFIX:-true}
ENABLE_ANTIPOLLUTE=${ENABLE_ANTIPOLLUTE:-true}
WORK=/tmp/repatch-work

echo "=== repatch.sh ==="
echo "  ENABLE_MCPFIX     = $ENABLE_MCPFIX"
echo "  ENABLE_ANTIPOLLUTE = $ENABLE_ANTIPOLLUTE"

if [ "$ENABLE_MCPFIX" != "true" ] && [ "$ENABLE_ANTIPOLLUTE" != "true" ]; then
  echo "ERROR: both patches are disabled. Nothing to do." >&2
  exit 1
fi

echo ""
echo "[1/6] 拉取官方 canary..."
docker pull lobehub/lobehub:canary

echo "[2/6] 起临时容器..."
docker rm -f repatch-tmp 2>/dev/null || true
docker run -d --name repatch-tmp --entrypoint sleep lobehub/lobehub:canary infinity

cleanup() {
  docker rm -f repatch-tmp 2>/dev/null || true
  rm -rf "$WORK"
}
trap cleanup EXIT

# ─── MCP session fix ───────────────────────────────────────────────────────────
if [ "$ENABLE_MCPFIX" = "true" ]; then
  echo ""
  echo "[3/6] (mcpfix) 发现 MCP chunk (含 serializeParams)..."
  mapfile -t CHUNKS < <(docker exec repatch-tmp sh -c 'grep -rl serializeParams /app/.next/server/chunks/ 2>/dev/null')
  if [ "${#CHUNKS[@]}" -eq 0 ]; then
    echo "ERROR: 没找到含 serializeParams 的 chunk" >&2
    exit 1
  fi
  echo "  发现 ${#CHUNKS[@]} 个 chunk"

  rm -rf "$WORK"; mkdir -p "$WORK"
  for chunk in "${CHUNKS[@]}"; do
    base=$(basename "$chunk")
    docker cp "repatch-tmp:$chunk" "$WORK/$base"
  done

  echo "  打补丁 + 语法校验..."
  python3 "$SCRIPT_DIR/mcp_patch.py" "$WORK"/*.js --apply
  for f in "$WORK"/*.js; do
    docker run --rm -v "$f":/check.js node:22-alpine node --check /check.js
  done
  for chunk in "${CHUNKS[@]}"; do
    base=$(basename "$chunk")
    docker cp "$WORK/$base" "repatch-tmp:$chunk"
  done
  echo "  (mcpfix) 5 个补丁点全部完成"
else
  echo ""
  echo "[3/6] (mcpfix) 跳过 (ENABLE_MCPFIX=false)"
fi

# ─── Builtin tool blacklist ────────────────────────────────────────────────────
if [ "$ENABLE_ANTIPOLLUTE" = "true" ]; then
  echo ""
  echo "[4/6] (antipollute) 发现 getToolManifests chunk..."
  mapfile -t CHUNKS < <(docker exec repatch-tmp sh -c 'grep -rl getToolManifests /app/.next/server/chunks/ 2>/dev/null')
  if [ "${#CHUNKS[@]}" -eq 0 ]; then
    echo "ERROR: 没找到含 getToolManifests 的 chunk" >&2
    exit 1
  fi
  echo "  发现 ${#CHUNKS[@]} 个 chunk"

  rm -rf "$WORK"; mkdir -p "$WORK"
  for chunk in "${CHUNKS[@]}"; do
    base=$(basename "$chunk")
    docker cp "repatch-tmp:$chunk" "$WORK/$base"
  done

  echo "  打补丁 + 语法校验..."
  python3 "$SCRIPT_DIR/antipollute_patch.py" "$WORK"/*.js --apply
  for f in "$WORK"/*.js; do
    docker run --rm -v "$f":/check.js node:22-alpine node --check /check.js
  done
  for chunk in "${CHUNKS[@]}"; do
    base=$(basename "$chunk")
    docker cp "$WORK/$base" "repatch-tmp:$chunk"
  done
  echo "  (antipollute) 7 个补丁点全部完成"
else
  echo ""
  echo "[4/6] (antipollute) 跳过 (ENABLE_ANTIPOLLUTE=false)"
fi

echo ""
echo "[5/6] commit 成 lobehub/lobehub:canary-antipollute..."
NEW_ID=$(docker commit \
  --change 'ENTRYPOINT ["/bin/node"]' \
  --change 'CMD ["/app/startServer.js"]' \
  repatch-tmp lobehub/lobehub:canary-antipollute)
echo "  新镜像: $NEW_ID"

EP=$(docker inspect lobehub/lobehub:canary-antipollute --format '{{json .Config.Entrypoint}}')
if [ "$EP" != '["/bin/node"]' ]; then
  echo "ERROR: commit 后 entrypoint 异常: $EP (期望 [\"/bin/node\"])" >&2
  exit 1
fi
echo "  entrypoint 已恢复: $EP"

echo ""
echo "[6/6] 用 override compose recreate lobe..."
docker compose -f docker-compose.yml -f docker-compose.antipollute.yml up -d --force-recreate lobe

echo ""
echo "✅ 完成！补丁镜像: lobehub/lobehub:canary-antipollute"
echo ""
echo "验证命令:"
echo "  # 检查补丁是否存活"
if [ "$ENABLE_MCPFIX" = "true" ]; then
  echo "  docker exec lobehub sh -c 'grep -rl reinitializing /app/.next/server/chunks/'"
fi
if [ "$ENABLE_ANTIPOLLUTE" = "true" ]; then
  echo "  docker exec lobehub sh -c 'grep -rl DISABLED_BUILTIN_TOOLS /app/.next/server/chunks/ | wc -l'"
fi
