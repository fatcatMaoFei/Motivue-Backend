@echo off
REM Convenience launcher for the Readiness Daily Simulator GUI
REM Double-click this file to run the GUI using the default python on PATH.

python -m readiness.gui_daily_sim
if %ERRORLEVEL% NEQ 0 (
  echo.
  echo Failed to launch with `python` on PATH. Trying `py -3`...
  py -3 -m readiness.gui_daily_sim
)
echo.
echo [Press any key to close]
pause >nul

