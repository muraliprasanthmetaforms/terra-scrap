# Gunicorn configuration file for Terra Scrap
import multiprocessing

# Server socket
bind = "127.0.0.1:5000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Restart workers after this many requests
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "/var/log/terrascrap/access.log"
errorlog = "/var/log/terrascrap/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = "terrascrap"

# Daemonize the Gunicorn process (detach & enter background)
daemon = False

# The path to a UNIX socket to bind to
# bind = "unix:/tmp/terrascrap.sock"

# Environment variables
raw_env = [
    'FLASK_ENV=production',
]