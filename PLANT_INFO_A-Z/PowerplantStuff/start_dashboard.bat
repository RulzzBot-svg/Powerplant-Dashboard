@echo off
cd /d "C:\Users\AFC5admin\Documents\Powerplant-Dashboard\PLANT_INFO_A-Z\PowerplantStuff"

call "C:\Users\AFC5admin\Documents\POWERPLANT-DASHBOARD\PLANT_INFO_A-Z\PowerplantStuff\myenv\Scripts\activate.bat"

:loop
echo Starting Streamlit PowerPlant Dashboard...
streamlit run test.py >> dashboard_log.txt 2>&1

echo Streamlit stopped or crashed. Restarting in 5 seconds...
timeout /t 5
goto loop
