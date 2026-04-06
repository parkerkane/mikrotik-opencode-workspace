#!/usr/bin/env bash

set -euo pipefail

VOLUMES=(
    mikrotik-manager-opencode-shared-data
    mikrotik-manager-opencode-shared-state
    mikrotik-manager-opencode-shared-cache
    mikrotik-manager-opencode-isolated-config
    mikrotik-manager-opencode-isolated-data
    mikrotik-manager-opencode-isolated-state
    mikrotik-manager-opencode-isolated-cache
)

existing_volumes=()
for volume in "${VOLUMES[@]}"; do
    if docker volume inspect "$volume" >/dev/null 2>&1; then
        existing_volumes+=("$volume")
    fi
done

if [[ ${#existing_volumes[@]} -eq 0 ]]; then
    printf 'No OpenCode Docker volumes to remove.\n'
    exit 0
fi

failed=0
for volume in "${existing_volumes[@]}"; do
    if docker volume rm "$volume" >/dev/null 2>&1; then
        printf 'Removed %s\n' "$volume"
        continue
    fi

    printf 'Could not remove %s\n' "$volume" >&2
    attached_containers=$(docker ps -a --filter volume="$volume" --format '{{.ID}} {{.Names}}')
    if [[ -n "$attached_containers" ]]; then
        printf 'Attached containers:\n%s\n' "$attached_containers" >&2
    fi
    failed=1
done

exit "$failed"
