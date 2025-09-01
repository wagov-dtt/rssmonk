FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

LABEL org.opencontainers.image.source=https://github.com/wagov-dtt/rssmonk
LABEL org.opencontainers.image.title="Listmonk API"
LABEL org.opencontainers.image.description="API proxy for Listmonk with RSS feeds"
LABEL org.opencontainers.image.licenses=Apache-2.0

# Copy only the required source into the image
ADD ./src /app
# Need a few files from the parent directory
COPY ./pyproject.toml ./uv.lock /app

# Sync the project into a new environment, using the frozen lockfile
WORKDIR /app

# Switch to a non root user
RUN  adduser --uid 10001 appuser && chown appuser:appuser -R .
USER 10001:10001

RUN ["uv", "sync", "--frozen"]

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT ["python", "/app/rssmonk/api.py"]