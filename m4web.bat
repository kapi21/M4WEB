@echo off
setlocal
cd /d "%~dp0"
if not defined M4_HOST set M4_HOST=http://cpc6128
echo M4WEB — proxy local de la M4 Board
echo M4_HOST=%M4_HOST%
python -m m4web --m4 "%M4_HOST%" %*
