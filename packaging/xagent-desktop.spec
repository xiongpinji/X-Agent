# X-Agent desktop packaging blueprint
# Intended to be consumed by a native bundler in a future packaging pass.

[app]
name = "X-Agent"
entry = "backend.app.main:app"
startup_page = "frontend/startup.html"
index_page = "frontend/index.html"
icon = "D:/办公/dj5g6-6xetg-002.ico"
logo = "D:/办公/LOGO.png"
mode = "desktop_single_user"
launch_url = "http://127.0.0.1:8000/"
