@echo off
rem o神套装-屏幕录制 V0.1 — 双击启动（无控制台窗口）
rem 使用 Anaconda 自带的 pythonw.exe，避免 WindowsApps 的 Store 存根。
set "PYW=C:\ProgramData\Anaconda3\pythonw.exe"
if not exist "%PYW%" set "PYW=pythonw"
cd /d "%~dp0"
start "" "%PYW%" "%~dp0main.py"
