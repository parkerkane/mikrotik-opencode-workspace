#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
REPO_ROOT=$(readlink -f "$SCRIPT_DIR/..")
IMAGE_NAME=${OPENCODE_DOCKER_IMAGE:-mikrotik-manager-opencode}
CONTAINER_HOME=/home/node
HOST_CONFIG_DIR=${OPENCODE_HOST_CONFIG_DIR:-$HOME/.config/opencode}
HOST_AUTH_FILE=${OPENCODE_HOST_AUTH_FILE:-$HOME/.local/share/opencode/auth.json}
SHARE_VOLUME=${OPENCODE_SHARED_DATA_VOLUME:-mikrotik-manager-opencode-shared-data}
STATE_VOLUME=${OPENCODE_SHARED_STATE_VOLUME:-mikrotik-manager-opencode-shared-state}
CACHE_VOLUME=${OPENCODE_SHARED_CACHE_VOLUME:-mikrotik-manager-opencode-shared-cache}

if [[ ! -d "$HOST_CONFIG_DIR" ]]; then
    printf 'Missing OpenCode config directory: %s\n' "$HOST_CONFIG_DIR" >&2
    exit 1
fi

if [[ ! -f "$HOST_AUTH_FILE" ]]; then
    printf 'Missing OpenCode auth file: %s\n' "$HOST_AUTH_FILE" >&2
    exit 1
fi

docker build -t "$IMAGE_NAME" "$REPO_ROOT" >/dev/null

if [[ $# -gt 0 ]]; then
    COMMAND=("$@")
else
    COMMAND=(opencode /workspace)
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

exec docker run --rm --init "${DOCKER_TTY_ARGS[@]}" \
    --workdir /workspace \
    --user 1000:1000 \
    --cap-drop=ALL \
    --security-opt no-new-privileges:true \
    --tmpfs /tmp:rw,exec,nosuid,nodev \
    --mount type=bind,src="$REPO_ROOT",dst=/workspace \
    --mount type=bind,src="$HOST_CONFIG_DIR",dst="$CONTAINER_HOME/.config/opencode",readonly \
    --mount type=bind,src="$HOST_AUTH_FILE",dst="$CONTAINER_HOME/.local/share/opencode/auth.json",readonly \
    --mount type=volume,src="$SHARE_VOLUME",dst="$CONTAINER_HOME/.local/share/opencode" \
    --mount type=volume,src="$STATE_VOLUME",dst="$CONTAINER_HOME/.local/state/opencode" \
    --mount type=volume,src="$CACHE_VOLUME",dst="$CONTAINER_HOME/.cache/opencode" \
    -e HOME="$CONTAINER_HOME" \
    -e GIT_TERMINAL_PROMPT=0 \
    -e GIT_ASKPASS=/bin/false \
    -e SSH_ASKPASS=/bin/false \
    -e GCM_INTERACTIVE=never \
    "${TERMINAL_ENV_ARGS[@]}" \
    "$IMAGE_NAME" \
    "${COMMAND[@]}"
