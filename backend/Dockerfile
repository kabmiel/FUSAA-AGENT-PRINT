FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY app ./app
RUN pip install --no-cache-dir .
COPY alembic.ini .
COPY alembic ./alembic
RUN addgroup --system fusaa && adduser --system --ingroup fusaa fusaa && mkdir -p /data/storage && chown -R fusaa:fusaa /app /data
USER fusaa
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
