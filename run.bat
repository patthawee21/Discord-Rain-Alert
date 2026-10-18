@echo off
cd /d "%~dp0"
echo ============================================
echo  TMD Rain Alert Bot
echo  ============================================
echo.
echo Installing dependencies...
python -m pip install -r requirements.txt --quiet
echo.
echo Starting bot...
python bot.py
pause
