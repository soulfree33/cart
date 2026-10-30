@echo off
setlocal
cd /d "%~dp0"

python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo PyInstaller is not installed.
    echo Install build dependencies with: python -m pip install -r requirements-build.txt
    exit /b 1
)

python -m PyInstaller --clean --noconfirm --onedir --windowed ^
    --specpath build ^
    --name KartBoardGame ^
    --add-data "%CD%\images;images" ^
    --add-data "%CD%\maps;maps" ^
    --add-data "%CD%\item_cards.json;." ^
    --add-data "%CD%\shop_cards.json;." ^
    --collect-all PIL ^
    main.py
if errorlevel 1 exit /b 1

python -c "import os,shutil; shutil.make_archive(os.path.join('dist','KartBoardGame-Windows'),'zip',root_dir=os.path.join('dist','KartBoardGame'))"
if errorlevel 1 exit /b 1

echo.
echo Build complete:
echo   dist\KartBoardGame\KartBoardGame.exe
echo   dist\KartBoardGame-Windows.zip
