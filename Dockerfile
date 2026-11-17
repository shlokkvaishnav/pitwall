# Rebuild all pitwall results from public data in a clean environment.
# Usage: make docker-reproduce
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends make git libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml requirements.lock ./
COPY src ./src
RUN pip install --no-cache-dir -c requirements.lock -e ".[model]"
COPY scripts ./scripts
COPY Makefile ./
COPY .git ./.git
CMD ["make", "reproduce"]
