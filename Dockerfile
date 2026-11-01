# Versions may be updated only through a reviewed infrastructure PR.
# Digest pinning is desirable after the first verified Mac ARM64 build.
FROM ghcr.io/astral-sh/uv:0.10.0 AS uv
FROM python:3.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_DEV=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    CAREER_DATA_DIR=/data

COPY --from=uv /uv /uvx /usr/local/bin/
WORKDIR /app

# Lock file is a required build input. Do not replace this with an unlocked install.
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
RUN uv sync --frozen --no-dev --no-editable \
    && useradd --uid 10001 --create-home --shell /usr/sbin/nologin career \
    && mkdir -p /data && chown career:career /data

USER career
EXPOSE 8000
CMD ["career", "serve", "--host", "0.0.0.0", "--port", "8000"]
