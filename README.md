# DB-to-sheets

Repo: <https://github.com/ApCPT42/DB-to-sheets>

Menyalin tabel **dinamis** POS dari database PostgreSQL (Aiven) ke satu
spreadsheet Google: satu tab per tabel, isi setiap tab diganti setiap kali
ekspor berjalan.

Repo ini sengaja **berdiri sendiri, terpisah dari repo POS**. Aplikasi POS,
frontend, Django, dan seluruh migrasinya tidak ada di sini dan tidak dibutuhkan
untuk menjalankan ekspor. Yang dibutuhkan hanya dua hal: akses **baca** ke
database, dan kredensial Google untuk spreadsheet tujuan.

Pemisahan ini juga yang membuat pengawasnya bisa diletakkan di host yang selalu
menyala (cloud) **tanpa ikut membawa server POS ke sana**. Yang naik ke cloud
hanya proses kecil ini; POS tetap berjalan seperti sekarang.

## Isi repo

| Berkas | Gunanya |
| --- | --- |
| `tools/export_to_google_sheets.py` | Seluruh logikanya: baca database → tulis spreadsheet |
| `tools/requirements-export.txt` | Semua dependensinya (`gspread`, `google-auth`, `psycopg`, `python-dotenv`) |
| `Export ke Google Sheets.bat` | Peluncur Windows: menu 1 ekspor, 2 uji, 3 periksa, 4 pengawas |
| `GOOGLE_SHEETS_EXPORT.md` | Panduan lengkap: penyiapan Google, tombol client, mode client, menjalankan di cloud |
| `.github/workflows/refresh-sheets.yml` | Pengawas terjadwal di GitHub Actions — melayani tombol Kontrol tanpa kartu kredit |
| `.github/workflows/keepalive.yml` | Dua commit kosong sebulan, supaya GitHub tidak mematikan jadwalnya |
| `Dockerfile`, `.dockerignore` | Untuk host yang memakai proses menunggu terus (VPS, Cloud Run, PaaS) |
| `.env`, `.secrets/` | Konfigurasi dan kredensial — **tidak pernah masuk git** |

## Mulai dari nol di mesin baru

```bat
python -m venv venv
venv\Scripts\python.exe -m pip install -r tools\requirements-export.txt
```

Lalu siapkan `.env` dan kunci Google (lihat `GOOGLE_SHEETS_EXPORT.md` bagian 4),
dan periksa hasilnya:

```bat
"Export ke Google Sheets.bat" 3
```

Pilihan itu memeriksa kunci Google, sambungan database beserta hak aksesnya, dan
daftar tab di spreadsheet tujuan — tanpa menulis apa pun. Sesudahnya pilihan
**1** untuk ekspor sungguhan, atau **2** untuk mencoba tanpa menulis ke Google.

## Yang sengaja tidak diekspor

`item` (2917 baris, memuat `cost_amount` yang tidak boleh dibaca client) dan
`worker` (memuat hash PIN). Hanya lima tabel dinamis yang disalin:
`transactions`, `transaction_detail`, `payment_proof`, `device`, dan
`device_transaction_sequence`. Tabel `transaction_daily_sequence` — sisa desain
nomor nota harian yang tidak dibaca kode mana pun — juga dilewatkan sejak
2026-09-28; memasukkannya kembali ke daftar akan menghasilkan tab kosong lagi.

## Tiga cara menjalankannya

1. **Sekali jalan** — menu **1**, atau langsung:
   `venv\Scripts\python.exe tools\export_to_google_sheets.py`
2. **Pengawas tombol** — menu **4** membiarkan jendela terbuka dan memantau
   kotak centang di tab `Kontrol`; client cukup mencentangnya di spreadsheet.
3. **Terjadwal di GitHub Actions** — cara yang berjalan tanpa komputer siapa pun
   menyala dan **tanpa kartu kredit**. Workflow-nya sudah ada di repo ini; yang
   perlu diisi hanya tiga rahasia di Settings → Secrets and variables → Actions,
   lalu client mencentang seperti biasa. Jeda pelayanan 5–15 menit.

Hampir semua platform yang menjalankan proses selalu-nyala gratis (Northflank,
Koyeb, Fly.io, Oracle, Google Cloud, AWS) meminta metode pembayaran, jadi jalur
GitHub Actions inilah yang dipakai. Pengawas ini hanya *keluar* menghubungi
Google dan Aiven, jadi tidak perlu menerima kunjungan dari luar — dan itu yang
membuat pola terjadwal cukup.

Dua cara masuk Google yang didukung: `--auth service-account` (bawaan; mesin
pengelola memakai berkas kunci JSON) dan `--auth oauth` (client masuk dengan akun
Google-nya sendiri, jadi tidak ada kunci penulis yang berpindah tangan).

Dokumentasi lengkapnya ada di [`GOOGLE_SHEETS_EXPORT.md`](GOOGLE_SHEETS_EXPORT.md).
