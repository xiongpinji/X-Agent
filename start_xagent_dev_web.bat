@echo off
REM ============================================================================
REM start_xagent_dev_web.bat  (原名 start_xagent_desktop.bat)
REM
REM 注意: 这不是真正的桌面客户端!
REM 本脚本只是 dev 便捷入口: 通过 scripts/one_click_desktop.py 在本地起
REM uvicorn 后端 (127.0.0.1:8003) 并用系统默认浏览器打开 Web 控制台,
REM 全程没有 Tauri 应用参与。
REM
REM 真正的桌面客户端在 desktop/ 目录 (Tauri v1):
REM   前置: 安装 Rust 工具链 + Tauri CLI (cargo install tauri-cli --version ^1)
REM   开发: cd desktop ^&^& cargo tauri dev
REM   打包: cd desktop ^&^& cargo tauri build
REM 桌面端前端资源复用主前端 frontend/dist (React), 见 desktop/tauri.conf.json。
REM ============================================================================
setlocal
cd /d %~dp0
python -m scripts.one_click_desktop
