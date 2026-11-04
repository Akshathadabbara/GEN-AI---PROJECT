import os

# Render supplies PORT dynamically (defaults to 10000 on Render, 5000 locally)
port = os.getenv("PORT", "5000")
bind = f"0.0.0.0:{port}"

# Worker configuration:
# 1 worker with gthread prevents SQLite multi-process locking on Render free tier (512MB RAM)
workers = int(os.getenv("WEB_CONCURRENCY", "1"))
threads = int(os.getenv("GUNICORN_THREADS", "2"))
worker_class = "gthread"

# Timeout: 120s prevents premature SIGKILL during cold start or AI inference
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

# Logging: pipe to stdout/stderr so Render captures all output
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
capture_output = True
