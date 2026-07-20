@echo off
setlocal
cd /d "%~dp0"
if not exist venv (
  python -m venv venv
  if errorlevel 1 goto error
)
call venv\Scripts\activate.bat
python -m pip install -r requirements.txt
if errorlevel 1 goto error
python main.py
if errorlevel 1 goto error
python -m streamlit run app.py
exit /b 0
:error
echo.
echo The project stopped. Review the error above.
pause
exit /b 1
