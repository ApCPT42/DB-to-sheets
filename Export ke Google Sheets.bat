@echo off
setlocal EnableExtensions

:: ==========================================================
::  Ekspor database Aiven ke Google Sheets
::
::  Menyalin tabel dinamis POS ke satu spreadsheet Google, satu
::  tab per tabel. Isi setiap tab diganti, bukan ditambah, jadi
::  berkas ini boleh dijalankan berapa kali pun.
::
::  Repo ini berdiri sendiri: aplikasi POS tidak ikut jalan dan
::  tidak perlu ada di mesin ini. Yang dibutuhkan hanya akses baca
::  ke database dan kredensial Google.
::
::  Prasyarat sekali saja di mesin ini:
::    - paket Python sudah terpasang
::    - venv di folder ini (lihat pesan galat kalau belum ada)
::    - berkas service account Google, dan spreadsheet tujuan
::      sudah dibagikan ke email service account itu sebagai Editor.
::      Cara membuatnya ada di GOOGLE_SHEETS_EXPORT.md
::      Di komputer client, jangan pakai kunci service account: tambahkan
::      --auth oauth supaya client masuk dengan akun Google-nya sendiri
::      (lihat bagian "Mode client" di dokumen yang sama).
::    - di .env ada baris DATABASE_URL dan GOOGLE_SPREADSHEET_ID
::
::  Pemakaian tanpa menu:
::    "Export ke Google Sheets.bat" 1 --only transactions
::    "Export ke Google Sheets.bat" 2      uji tanpa menulis
::    "Export ke Google Sheets.bat" 3      periksa kredensial & tab
::    "Export ke Google Sheets.bat" 3 --auth oauth   login akun Google client
::    "Export ke Google Sheets.bat" 4      pengawas permintaan client
::    "Export ke Google Sheets.bat" 4 --interval 30
::
::  Berkas ini wajib berakhir baris CRLF. Aturan `*.bat` di
::  .gitattributes yang menjaminnya, karena cmd salah membaca
::  label dan blok `if` kalau berkasnya LF.
:: ==========================================================

set "ROOT=%~dp0"
set "TOOLS=%ROOT%tools"
set "PY=%ROOT%venv\Scripts\python.exe"
set "SCRIPT=%TOOLS%\export_to_google_sheets.py"

echo ==========================================================
echo   Ekspor database ke Google Sheets
echo ==========================================================
echo(

if not exist "%SCRIPT%" goto :skrip_hilang
if not exist "%PY%" goto :venv_hilang

:: Dependensi ekspor hanya dipasang sekali, saat pertama dijalankan.
"%PY%" -c "import gspread" >nul 2>nul
if errorlevel 1 goto :pasang_dependensi
goto :pilih

:pasang_dependensi
echo Paket gspread belum ada di venv. Memasang dari tools\requirements-export.txt...
"%PY%" -m pip install -r "%TOOLS%\requirements-export.txt"
if errorlevel 1 goto :pip_gagal
echo(

:pilih
if not "%~1"=="" goto :dari_argumen

echo  Pilihan:
echo    [1] Ekspor sekarang        - mengganti isi spreadsheet
echo    [2] Uji tanpa menulis      - dry run, tidak menyentuh Google
echo    [3] Periksa kredensial     - cek kredensial Google, database, dan tab
echo    [4] Pengawas permintaan    - melayani tombol client, biarkan terbuka
echo(
set "PILIHAN=1"
set /p "PILIHAN=Pilihan [1/2/3/4], Enter = 1: "
if not defined PILIHAN set "PILIHAN=1"
goto :jalankan

:dari_argumen
set "PILIHAN=%~1"

:jalankan
set "ARGS="
if "%PILIHAN%"=="2" set "ARGS=--dry-run"
if "%PILIHAN%"=="3" set "ARGS=--check"
if "%PILIHAN%"=="4" set "ARGS=--watch"
if not "%PILIHAN%"=="1" if not "%PILIHAN%"=="2" if not "%PILIHAN%"=="3" if not "%PILIHAN%"=="4" goto :pilihan_salah

:: Sisa argumen diteruskan apa adanya, mis. --only transactions.
shift
:lanjutan_argumen
if "%~1"=="" goto :argumen_selesai
set "ARGS=%ARGS% %1"
shift
goto :lanjutan_argumen

:argumen_selesai
echo(
"%PY%" "%SCRIPT%" %ARGS%
if errorlevel 1 goto :gagal

echo(
echo Selesai.
pause
exit /b 0

:skrip_hilang
echo [X] Berkas tools\export_to_google_sheets.py tidak ditemukan.
echo     Pastikan "Export ke Google Sheets.bat" berada di akar repo ini.
echo(
pause
exit /b 1

:venv_hilang
echo [X] Virtual environment belum ada di folder ini.
echo     Jalankan dua perintah ini sekali, dari folder tempat berkas .bat ini berada:
echo(
echo         python -m venv venv
echo         venv\Scripts\python.exe -m pip install -r tools\requirements-export.txt
echo(
pause
exit /b 1

:pip_gagal
echo [X] Pemasangan paket gspread gagal. Periksa koneksi internet lalu coba lagi.
echo(
pause
exit /b 1

:pilihan_salah
echo [X] Pilihan "%PILIHAN%" tidak dikenal. Jalankan lagi dan pilih 1 sampai 4.
echo(
pause
exit /b 1

:gagal
echo(
echo [X] Ekspor gagal. Pesan di atas menyebutkan langkah yang perlu diperbaiki.
echo     Kalau menyangkut kredensial Google, lihat GOOGLE_SHEETS_EXPORT.md.
echo(
pause
exit /b 1
