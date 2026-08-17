@echo off
cd /d "%~dp0"
echo Starting IDSR Dashboard...
echo (A browser tab will open automatically. Close this window to stop the app.)
python -m streamlit run app.py
pause
