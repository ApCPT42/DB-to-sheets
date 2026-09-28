# Kontainer pengawas ekspor database ke Google Sheets.
#
# Gunanya: pengawas berjalan di host yang selalu menyala, sehingga permintaan
# client dilayani tanpa komputer pengelola maupun komputer client menyala.
#
# Berbeda dari repo POS, di sini konteks build adalah akar repo ini sendiri —
# tidak ada aplikasi lain yang perlu ada untuk menjalankan ekspor.
#
# Konfigurasi diisi lewat variabel lingkungan, bukan berkas .env:
#   DATABASE_URL                 - koneksi PostgreSQL (boleh pengguna read-only)
#   GOOGLE_SPREADSHEET_ID        - ID atau link spreadsheet tujuan
#   GOOGLE_SERVICE_ACCOUNT_JSON  - isi kunci service account, ditempel apa adanya
# Opsional:
#   GOOGLE_SHEETS_WATCH_INTERVAL - jeda periksa kotak Kontrol dalam detik (bawaan 60)
#   GOOGLE_SHEETS_SHARE_WITH     - email yang otomatis diberi akses Editor

# Versi Python disamakan dengan venv pengembangan supaya perilakunya sama.
FROM python:3.11-slim

# Tanpa penyangga supaya log pengawas langsung muncul di log platform.
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependensi dipasang lebih dulu supaya cache build tidak batal setiap kali
# skripnya berubah.
COPY tools/requirements-export.txt tools/
RUN python -m pip install --no-cache-dir -r tools/requirements-export.txt

COPY tools/ tools/

# Bawaan: pengawas yang melayani kotak centang di tab Kontrol.
# Untuk host berbasis cron, ganti perintahnya menjadi "--if-requested".
CMD ["python", "tools/export_to_google_sheets.py", "--watch", "--interval", "60"]
