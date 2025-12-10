@echo off
REM Go to project folder
cd /d "C:\Users\AFC5admin\Documents\POWERPLANTDASHBOARD\Powerplant-Dashboard\PLANT_INFO_A-Z\PowerplantStuff"

REM Activate virtual environment
call "C:\Users\AFC5admin\Documents\POWERPLANTDASHBOARD\Powerplant-Dashboard\PLANT_INFO_A-Z\PowerplantStuff\myenv\Scripts\activate.bat"

REM Run Streamlit app
streamlit run test.py --server.address 192.168.1.131 --server.port 8502
