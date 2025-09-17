FROM python:3.12-slim

# Ensure system packages (if later needed) can be installed quickly; minimal now
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first (better layer caching)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Create non-root user (optional but recommended)
RUN useradd -m botuser && chown -R botuser:botuser /app
USER botuser

# Default DB path can be overridden at runtime with -e DB_PATH=/data/data.db
ENV DB_PATH=/app/data.db

# No ports exposed (Telegram bot uses outbound only)

# Healthcheck: simple python DB touch
HEALTHCHECK --interval=1m --timeout=10s --retries=3 CMD python -c "import os,sqlite3,pathlib; db=os.getenv('DB_PATH','/app/data.db'); pathlib.Path(db).touch(exist_ok=True); sqlite3.connect(db).close(); print('OK')" || exit 1

# Entry point
CMD ["python", "run.py"]
