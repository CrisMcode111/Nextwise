# Version pins match the existing local Python and Node runtime family.
# Image digests and a clean Linux build still require verification before release.
FROM node:24.22.2-bookworm-slim AS node
FROM python:3.11.9-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 nextwise \
    && useradd --uid 10001 --gid 10001 --no-create-home nextwise
COPY --from=node /usr/local/bin/node /usr/local/bin/node
WORKDIR /app
COPY scripts/ ./scripts/
COPY web/ ./web/
COPY vendor/meterless/ ./vendor/meterless/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    NEXTWISE_HOST=0.0.0.0 NEXTWISE_PORT=8765 NEXTWISE_UNATTENDED=true \
    NEXTWISE_ARTIFACT_ROOT=/artifacts NEXTWISE_MEMORY_ROOT=/memory
USER 10001:10001
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=90s --start-period=30s --retries=3 \
    CMD ["python", "-B", "scripts/probe_runtime.py"]
CMD ["python", "-B", "scripts/serve_runtime.py"]
