@echo off
REM ============================================================
REM  Compile SolarSound.exe avec PyInstaller, depuis le venv
REM  du projet. A placer/lancer depuis la RACINE du projet
REM  (le dossier qui contient main.py).
REM
REM  Utilisation :
REM    1) Copier ce fichier + solarsound.spec dans le dossier
REM       racine du projet SolarSound (a cote de main.py), ou
REM       lancer depuis n'importe ou en ajustant les chemins.
REM    2) Double-cliquer sur ce .bat (le venv doit deja exister
REM       dans .venv, comme d'habitude pour le projet).
REM ============================================================

setlocal

REM --- Aller a la racine du projet (dossier de ce script) ---
cd /d "%~dp0"

REM --- Activer le venv du projet ---
if not exist ".venv\Scripts\activate.bat" (
    echo [ERREUR] .venv introuvable a cote de ce script.
    echo Lance ce .bat depuis la racine du projet SolarSound,
    echo ou copie-le a cote de ton dossier .venv existant.
    pause
    exit /b 1
)
call ".venv\Scripts\activate.bat"

REM --- Installer PyInstaller si absent ---
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installation de PyInstaller dans le venv...
    python -m pip install --upgrade pyinstaller
)

REM --- Nettoyage des anciens builds ---
if exist "build_pyinstaller" rmdir /s /q "build_pyinstaller"
if exist "dist" rmdir /s /q "dist"

REM --- Compilation ---
echo.
echo [INFO] Compilation de SolarSound.exe ...
pyinstaller solarsound.spec --noconfirm --distpath dist --workpath build_pyinstaller

if errorlevel 1 (
    echo.
    echo [ERREUR] La compilation a echoue. Regarde les messages ci-dessus.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Termine ! L'exe se trouve dans : dist\SolarSound.exe
echo  Passe maintenant a l'etape 2 : compiler l'installateur
echo  avec Inno Setup (voir README_INSTALLATION.md).
echo ============================================================
pause
