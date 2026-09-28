# pos-sheets-sync

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
| `GOOGLE_SHEETS_EXPORT.md` | Panduan lengkap: penyiapan Google, tombol client, mode client, deploy cloud |
| `Dockerfile`, `.dockerignore` | Untuk host nonstop (Northflank, VPS, Cloud Run) |
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
3. **Terjadwal / cloud** — `--if-requested` memeriksa kotak itu satu kali lalu
   keluar, cocok untuk cron, Cloud Run + Scheduler, atau kontainer.

Dua cara masuk Google yang didukung: `--auth service-account` (bawaan; mesin
pengelola memakai berkas kunci JSON) dan `--auth oauth` (client masuk dengan akun
Google-nya sendiri, jadi tidak ada kunci penulis yang berpindah tangan).

Dokumentasi lengkapnya ada di [`GOOGLE_SHEETS_EXPORT.md`](GOOGLE_SHEETS_EXPORT.md).
