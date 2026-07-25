"""Gunicorn configuration for X-Agent production deployment.

Usage:
    gunicorn -c gunicorn.conf.py backend.app.main:app

This configuration uses Uvicorn workers for async support and is optimized
for production deployments with multiple workers.
"""

import multiprocessing
import os

# Server socket
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")

# Worker processes
# Use 2-4 workers per CPU core for I/O-bound async workloads
workers = int(os.getenv("API_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
timeout = int(os.getenv("GUNICORN_TIMEOUT", 120))
graceful_timeout = 30
keepalive = 5

# Restart workers after this many requests (prevent memory leaks)
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", 1000))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", 50))

# Logging
accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-")
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "xagent-api"

# Server mechanics
daemon = False
pidfile = os.getenv("GUNICORN_PIDFILE", "/tmp/xagent-api.pid")
tmp_upload_dir = None

# Security
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190

# Preload app for faster worker startup (shares memory via copy-on-write)
# Disable if app has issues with fork() or uses non-fork-safe resources
preload_app = os.getenv("GUNICORN_PRELOAD", "false").lower() == "true"

# Worker tmp dir (use RAM for faster heartbeats)
worker_tmp_dir = "/dev/shm" if os.path.exists("/dev/shm") else None


def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("Starting X-Agent API server...")


def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    server.log.info("Reloading X-Agent API server...")


def when_ready(server):
    """Called just after the server is started."""
    server.log.info(f"X-Agent API server ready. Workers: {server.cfg.workers}")


def worker_int(worker):
    """Called when a worker receives SIGINT or SIGQUIT."""
    worker.log.info(f"Worker {worker.pid} received SIGINT/SIGQUIT")


def worker_abort(worker):
    """Called when a worker receives SIGABRT."""
    worker.log.info(f"Worker {worker.pid} received SIGABRT")


def child_exit(server, worker):
    """Called when a worker exits."""
    server.log.info(f"Worker {worker.pid} exited")
