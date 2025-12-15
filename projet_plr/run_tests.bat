@echo off
echo ==========================================
echo      LANCEMENT DES TESTS PLR VET
echo ==========================================
echo.

:: 1. Tentative d'activation automatique de l'environnement Conda
:: Chemin détecté d'après vos logs précédents
if exist "C:\Users\siemb\miniconda3\Scripts\activate.bat" (
    echo Activation de l'environnement 'plr_env'...
    call "C:\Users\siemb\miniconda3\Scripts\activate.bat" plr_env
)

:: Lancement de pytest avec couverture
call pytest --cov=. --cov-report=html

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCES] Tous les tests sont passes !
    echo Ouverture du rapport de couverture...
    start htmlcov/index.html
) else (
    echo.
    echo [ECHEC] Une erreur est survenue.
    echo.
    echo Si 'pytest' n'est toujours pas reconnu :
    echo 1. Verifiez que Miniconda est bien installe dans C:\Users\siemb\miniconda3
    echo 2. Ou lancez ce script depuis 'Anaconda Prompt'
    pause
)
