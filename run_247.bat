@echo off
REM ============================================
REM  Rain Alert Bot - 24/7 watchdog
REM  รัน bot ตลอดเวลา ถ้า bot หยุดจะเริ่มใหม่ใน 10 วินาที
REM  ล็อกทุกอย่างลง bot_watchdog.log
REM ============================================
cd /d "%~dp0"
set PYEXE=C:\Users\patyawat\AppData\Local\Programs\Python\Python311\python.exe
if not exist "%PYEXE%" set PYEXE=python

:loop
echo [%date% %time%] starting bot... >> bot_watchdog.log
"%PYEXE%" bot.py >> bot_watchdog.log 2>&1
echo [%date% %time%] bot exited (code %ERRORLEVEL%), restarting in 10s... >> bot_watchdog.log
ping -n 11 127.0.0.1 > nul
goto loop
