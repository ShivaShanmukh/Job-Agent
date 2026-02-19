@echo off
echo ============================================
echo   Job Application Agent - Easy Installer
echo ============================================
echo.

echo [1/4] Upgrading pip...
python -m pip install --upgrade pip --quiet

echo [2/4] Installing greenlet (pre-built, no compiler needed)...
pip install "greenlet>=3.1" --only-binary :all: --quiet
if %ERRORLEVEL% neq 0 (
    echo ERROR: greenlet install failed. Trying alternative...
    pip install greenlet --pre --only-binary :all: --quiet
)

echo [3/4] Installing all other packages...
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client apscheduler python-dotenv jinja2 pytest playwright --quiet
if %ERRORLEVEL% neq 0 (
    echo ERROR: Package install failed. See above for details.
    pause
    exit /b 1
)

echo [4/4] Installing Chromium browser for automation...
playwright install chromium

echo.
echo ============================================
echo   SUCCESS! All packages installed.
echo   You can now follow SETUP.md from Step 2.
echo ============================================
pause
