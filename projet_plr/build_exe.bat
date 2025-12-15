@echo off
echo ==========================================
echo      CREATION DE L'EXECUTABLE PLR VET
echo ==========================================
echo.

:: 1. Activation Environnement (Adapter si besoin)
if exist "C:\Users\siemb\miniconda3\Scripts\activate.bat" (
    call "C:\Users\siemb\miniconda3\Scripts\activate.bat" plr_env
)

:: 2. Nettoyage
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
if exist "*.spec" del "*.spec"

:: 3. Lancement PyInstaller
:: --onedir : Crée un dossier (plus propre pour les fichiers config/db externes)
:: --noconsole : Pas de fenêtre noire
:: --name : Nom de l'exe
:: --add-data : Inclut les dossiers de ressources (format: "source;dest")
:: --collect-all : Force l'inclusion complète de packages complexes

echo Generation en cours...
pyinstaller --noconfirm --clean --onedir --noconsole --name "PLR_Vet_App" ^
    --paths "C:\Users\siemb\miniconda3\envs\plr_env\Lib\site-packages" ^
    --add-data "translations;translations" ^
    --hidden-import "PySide6" ^
    --hidden-import "PySide6.QtCore" ^
    --hidden-import "PySide6.QtGui" ^
    --hidden-import "PySide6.QtWidgets" ^
    --hidden-import "shiboken6" ^
    --hidden-import "backports" ^
    --hidden-import "jaraco" ^
    --hidden-import "jaraco.text" ^
    --hidden-import "jaraco.context" ^
    --hidden-import "jaraco.functools" ^
    --hidden-import "jaraco.classes" ^
    --hidden-import "more_itertools" ^
    --hidden-import "platformdirs" ^
    --collect-all "backports" ^
    --collect-all "platformdirs" ^
    --collect-all "jaraco" ^
    --collect-all "reportlab" ^
    --collect-all "PySide6" ^
    --collect-all "shiboken6" ^
    main_application.py

echo.
echo [TERMINE] L'application est dans le dossier 'dist/PLR_Vet_App'
pause