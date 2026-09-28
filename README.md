# DB-to-sheets

Repo: <https://github.com/ApCPT42/DB-to-sheets>

Menyalin tabel **dinamis** POS dari database PostgreSQL (Aiven) ke satu
spreadsheet Google: satu tab per tabel, isi setiap tab diganti setiap kali
ekspor berjalan.

Repo ini sengaja **berdiri sendiri, terpisah dari repo POS**. Aplikasi POS,
frontend, Django, dan seluruh migrasinya tidak ada di sini dan tidak dibutuhkan
untuk menjalankan ekspor. Yang dibutuhkan hanya dua hal: akses **baca** ke
database, dan kredensial Google untuk spreadsheet tujuan.

Pemisahan ini juga yang membuat seluruh foldernya bisa diserahkan ke client atau
dipindahkan ke mesin lain **tanpa ikut membawa server POS**. Yang berpindah hanya
proses kecil ini; POS tetap berjalan seperti sekarang.

## Isi repo

| Berkas | Gunanya |
| --- | --- |
| `tools/export_to_google_sheets.py` | Seluruh logikanya: baca database → tulis spreadsheet |
| `tools/requirements-export.txt` | Semua dependensinya (`gspread`, `google-auth`, `psycopg`, `python-dotenv`) |
| `Export ke Google Sheets.bat` | Peluncur Windows: menu 1 ekspor, 2 uji, 3 periksa |
| `GOOGLE_SHEETS_EXPORT.md` | Panduan lengkap: penyiapan Google, mode client, menjalankan berkala |
| `.env`, `.secrets/` | Konfigurasi dan kredensial. Di repo keduanya hanya penanda; **isinya tidak pernah masuk git** |

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

## Cara menjalankannya

1. **Sekali jalan** — menu **1**, atau langsung:
   `venv\Scripts\python.exe tools\export_to_google_sheets.py`
2. **Terjadwal di komputer sendiri** — daftarkan perintah di atas ke Task
   Scheduler (Windows) atau cron (Linux); resepnya ada di bagian 12 panduan.
   Untuk jadwal otomatis jangan pakai `.bat`-nya, karena ia berhenti menunggu
   tombol ditekan di akhir.

Setiap kali ekspor selesai, tab `device` diberi label `Last Update` di `D1` dan
waktu jalannya di `D2` (latar kuning) — itu penanda kapan data terakhir
disegarkan.

Dua jalur yang pernah ada sudah dipensiunkan pada 2026-09-28, dan berkasnya tidak
ada lagi di repo ini:

- **Tombol di tab `Kontrol`** beserta pengawas `--watch`. Karena ekspor kini
dijalankan manual, tidak ada lagi yang perlu menunggu centangan; tab `Kontrol`
yang masih tersisa di spreadsheet boleh dihapus.
- **Cloud.** `Dockerfile` dan langkah Northflank dibuang karena tidak satu pun
host selalu-nyala gratis bisa dipakai tanpa kartu kredit, dan workflow GitHub
Actions dibuang bersama tombolnya. Keduanya masih bisa diambil dari riwayat git
kalau nanti diperlukan lagi.

Dua cara masuk Google yang didukung: `--auth service-account` (bawaan; memakai
berkas kunci JSON) dan `--auth oauth` (masuk dengan akun Google sendiri, sehingga
tidak ada kunci penulis yang berpindah tangan).

## Penyerahan ke client

Sejak **2026-09-28** program ini diserahkan ke client untuk dijalankan di
komputernya sendiri, **bersama berkas kunci service account-nya**. Paket yang
dikirim ada dua: folder ini (tanpa `venv\`, dan tanpa `.env` — keduanya memang
tidak ikut git), lalu dua berkas rahasia yang dikirim terpisah di luar git —
`.env` berisi `DATABASE_URL` **read-only** dan ID spreadsheet, serta
`.secrets\service-account.json`.

Yang berpindah tangan hanya hak tulis ke Google Sheets; isi database tetap
terbaca lewat pengguna read-only, dan alat ini sendiri hanya menjalankan
`SELECT`. Yang perlu disadari: kunci itu berlaku untuk **setiap** spreadsheet
yang dibagikan ke service account tersebut — jadi jangan membagikan spreadsheet
lain ke email itu, dan cabut kuncinya kalau client berhenti memakainya.

Di komputer client: pilihan **3** untuk memeriksa, lalu pilihan **1** setiap kali
client ingin data terbaru. Kalau ingin berjalan sendiri, jadwalkan pilihan 1
lewat Task Scheduler seperti di bagian 12 panduan — tidak ada tombol di
spreadsheet yang perlu dilayani, jadi tidak ada proses yang harus dibiarkan
menyala.

Dokumentasi lengkapnya ada di [`GOOGLE_SHEETS_EXPORT.md`](GOOGLE_SHEETS_EXPORT.md).
