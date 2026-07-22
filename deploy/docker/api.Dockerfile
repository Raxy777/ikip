FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN pip install --no-cache-dir uv==0.8.22
COPY pyproject.toml uv.lock README.md ./
COPY packages ./packages
COPY services ./services
COPY db ./db
RUN uv sync --frozen --package ikip-api --no-dev
RUN useradd --create-home --uid 10001 ikip && chown -R ikip:ikip /app
USER ikip
EXPOSE 8000
CMD ["sh","-c","uv run --package ikip-api python db/migrate.py up && exec uv run --package ikip-api uvicorn ikip_api.app:app --host 0.0.0.0 --port 8000"]
