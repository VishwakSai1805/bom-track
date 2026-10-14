@echo off
REM Rebuild BOM-Track on Windows (PostgreSQL 18 default install path). Set PGPASSWORD first if your postgres user has a password:
REM    set PGPASSWORD=yourpassword
setlocal
set PSQL="C:\Program Files\PostgreSQL\18\bin\psql.exe" -h localhost -U postgres -v ON_ERROR_STOP=1 -q
cd /d "%~dp0"
%PSQL% -d postgres -c "DROP DATABASE IF EXISTS bomtrack WITH (FORCE)" -c "CREATE DATABASE bomtrack" || goto :err
for %%f in (sql\01_schema.sql sql\02_views.sql sql\03_plpgsql.sql sql\03b_trg_build_complete.sql sql\06_indexes.sql) do (
  %PSQL% -d bomtrack -f %%f || goto :err
)
python tools\import_boms.py data || goto :err
python tools\load_quotes.py data || goto :err
echo.
echo Database ready. Start the app with:  python -m streamlit run app.py
exit /b 0
:err
echo FAILED - see the message above.
exit /b 1
