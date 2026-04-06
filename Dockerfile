FROM node:24-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:/home/node/.local/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates ripgrep \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY requirements.txt /tmp/requirements.txt

RUN python3 -m venv "$VIRTUAL_ENV" \
    && "$VIRTUAL_ENV/bin/pip" install --no-cache-dir --upgrade pip \
    && "$VIRTUAL_ENV/bin/pip" install --no-cache-dir -r /tmp/requirements.txt \
    && npm install -g opencode-ai \
    && rm -f /tmp/requirements.txt

RUN mkdir -p \
        /workspace \
        /tmp \
        /home/node/.cache/opencode \
        /home/node/.config/opencode \
        /home/node/.local/share/opencode \
        /home/node/.local/state/opencode \
    && chown -R node:node /workspace /tmp /home/node

USER node
ENV HOME=/home/node

CMD ["opencode", "/workspace"]
