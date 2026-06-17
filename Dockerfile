# syntax=docker/dockerfile:1

# ---- Stage 1: build the React frontend ----
FROM node:20-slim AS web-build
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm install
COPY web/ ./
RUN npm run build

# ---- Stage 2: Python runtime serving API + built frontend ----
FROM python:3.12-slim
WORKDIR /app

# gh CLI is required to query github.com release metadata (non-GitHub hosts
# such as Gitea are reached directly over HTTPS and need no extra tooling).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
       -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
       > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# Install the Python runtime dependency (kept in sync with pyproject.toml).
# Installed before the app code so this layer stays cached across code changes.
RUN pip install --no-cache-dir "fastapi[standard]>=0.115.0"

# Application code + data.
COPY mirror_core.py add_payload.py update_payloads.py ./
COPY server/ ./server/
COPY payloads.json README.md ./

# Built frontend from stage 1 (FastAPI serves it as static files).
COPY --from=web-build /web/dist ./web/dist

EXPOSE 8000

# gh authenticates from the GH_TOKEN / GITHUB_TOKEN env var at runtime:
#   docker run -p 8000:8000 -e GH_TOKEN=ghp_xxx <image>
CMD ["fastapi", "run", "server/main.py", "--host", "0.0.0.0", "--port", "8000"]
