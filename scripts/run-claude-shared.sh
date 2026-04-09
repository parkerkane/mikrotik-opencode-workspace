#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
REPO_ROOT=$(readlink -f "$SCRIPT_DIR/..")
IMAGE_NAME=${CLAUDE_DOCKER_IMAGE:-mikrotik-manager-claude}
CONTAINER_HOME=/home/node
CLAUDE_HOME=${CLAUDE_CONTAINER_HOME:-$CONTAINER_HOME/claude-home}
HOST_CONFIG_DIR=${CLAUDE_HOST_CONFIG_DIR:-$HOME/.claude}
HOST_STATE_FILE=${CLAUDE_HOST_STATE_FILE:-$HOME/.claude.json}
HOME_VOLUME=${CLAUDE_SHARED_HOME_VOLUME:-mikrotik-manager-claude-shared-home}

mkdir -p "$HOST_CONFIG_DIR"

if [[ ! -e "$HOST_STATE_FILE" ]]; then
    printf '{}\n' > "$HOST_STATE_FILE"
elif [[ -d "$HOST_STATE_FILE" ]]; then
    printf 'Claude Code state path is a directory, expected a file: %s\n' "$HOST_STATE_FILE" >&2
    exit 1
fi

printf 'Building Docker image: %s\n' "$IMAGE_NAME"
docker build -t "$IMAGE_NAME" "$REPO_ROOT"

if [[ $# -gt 0 ]]; then
    COMMAND=("$@")
else
    COMMAND=(claude)
fi

DOCKER_TTY_ARGS=()
if [[ -t 0 && -t 1 ]]; then
    DOCKER_TTY_ARGS=(-it)
fi

TERMINAL_ENV_ARGS=()
for var_name in TERM COLORTERM LANG LC_ALL COLUMNS LINES; do
    if [[ -n ${!var_name:-} ]]; then
        TERMINAL_ENV_ARGS+=(-e "$var_name=${!var_name}")
    fi
done

printf 'Starting Claude Code container with HOME=%s\n' "$CLAUDE_HOME"

exec docker run --rm --init "${DOCKER_TTY_ARGS[@]}" \
    --workdir /workspace \
    --user 1000:1000 \
    --cap-drop=ALL \
    --security-opt no-new-privileges:true \
    --tmpfs /tmp:rw,exec,nosuid,nodev \
    --mount type=bind,src="$REPO_ROOT",dst=/workspace \
    --mount type=volume,src="$HOME_VOLUME",dst="$CLAUDE_HOME" \
    --mount type=bind,src="$HOST_CONFIG_DIR",dst="$CLAUDE_HOME/.claude" \
    --mount type=bind,src="$HOST_STATE_FILE",dst="$CLAUDE_HOME/.claude.json" \
    -e HOME="$CLAUDE_HOME" \
    -e GIT_TERMINAL_PROMPT=0 \
    -e GIT_ASKPASS=/bin/false \
    -e SSH_ASKPASS=/bin/false \
    -e GCM_INTERACTIVE=never \
    "${TERMINAL_ENV_ARGS[@]}" \
    "$IMAGE_NAME" \
    "${COMMAND[@]}"
