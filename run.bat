@echo off
:menu
cls
echo ===================================================
echo AI Incident Response Engineer - Execution Manager
echo ===================================================
echo 1) Setup and Start Dev Environment (Docker)
echo 2) Run Backend Tests (Local Python)
echo 3) Stop Dev Environment
echo 4) Pull Ollama Model (Ensure Docker is running first)
echo 5) Exit
echo ===================================================
set /p choice="Enter your choice (1-5): "

if "%choice%"=="1" goto setup_start
if "%choice%"=="2" goto run_tests
if "%choice%"=="3" goto stop_env
if "%choice%"=="4" goto pull_ollama
if "%choice%"=="5" goto exit
goto menu

:setup_start
echo Checking if .env exists...
if not exist .env (
    echo .env file not found. Copying .env.example to .env...
    copy .env.example .env
    echo Please edit the .env file to add your API keys!
)
echo Starting docker containers in development mode...
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
echo.
echo Application running!
echo Frontend: http://localhost:3000
echo Backend:  http://localhost:8000
pause
goto menu

:run_tests
echo Navigating to backend folder and setting up...
pushd backend
echo Installing dependencies...
python -m pip install -r requirements.txt pytest pytest-asyncio aiosqlite
if %errorlevel% neq 0 (
    echo PIP installation failed. Please verify Python is installed and in your PATH.
    popd
    pause
    goto menu
)
echo Running tests...
set DATABASE_URL=sqlite+aiosqlite:///./test.db
set APP_ENV=test
python -m pytest tests/ -v --asyncio-mode=auto
set DATABASE_URL=
set APP_ENV=
popd
pause
goto menu

:stop_env
echo Stopping docker containers...
docker compose down
pause
goto menu

:pull_ollama
echo Pulling Ollama Model llama3.2:3b...
docker exec incident_ollama ollama pull llama3.2:3b
pause
goto menu

:exit
exit /b
