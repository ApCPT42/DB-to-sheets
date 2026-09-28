# Ekspor Data POS ke Google Sheets

Alat ini menyalin tabel **dinamis** POS dari PostgreSQL ke satu spreadsheet
Google, masing-masing ke tabnya sendiri, dan dijalankan lewat
`Export ke Google Sheets.bat`.

Repo ini **berdiri sendiri, terpisah dari repo POS**: aplikasi POS tidak ikut
berjalan, tidak ikut di-deploy ke cloud, dan tidak perlu ada di komputer yang
menjalankan ekspor. Ketika nanti pengawasnya diletakkan di cloud, yang naik ke
sana hanyalah program ini — server POS tetap berjalan seperti sekarang.

Alasan alat ini ada: client tidak perlu masuk ke console database, tetapi tetap
perlu melihat data penjualan — dan kadang perlu meminta data terbaru tanpa
menunggu pemilik. Alat ini juga bisa dijalankan di komputer client sendiri, tanpa
kredensial database yang bisa menulis; itu yang dijelaskan di bagian 11.

**Status: sudah dijalankan sungguhan.** Ekspor pertama berhasil ke spreadsheet
`Shadow DB` (`1kB02M_4asD38-7Qna6N9cSws5EHpP3VglXLw2nrHC0A`) pada 2026-09-28:
enam tab data terisi, tab `Kontrol` dibuat beserta kotak centangnya, tab bawaan
`Sheet1` dihapus, header tebal dan dibekukan, dan kolom uang berformat `Rp`.
Lebar kolom sudah menyesuaikan isi (lihat bagian 3). Alur tombol client juga
sudah dicoba sungguhan: mengcentang `Kontrol!B3` membuat pengawas mengosongkan
kotak itu, menjalankan ekspor, lalu mengisi status
`Selesai. 6 tab diperbarui, total 37 baris.`, waktu, dan ringkasan per tabel.

---

## 1. Dua peran

| | Pemilik POS | Client |
| --- | --- | --- |
| `DATABASE_URL` | ada, di `.env` akar repo ini | tidak ada di model tombol; **ada dan read-only** di mode client (bagian 11) |
| Kredensial Google | berkas kunci service account di disk mesin pengelola | tidak perlu di model tombol; di mode client, login akun Google sendiri |
| Menjalankan `.bat` | ya | tidak di model tombol; **ya** di mode client |
| Akses ke spreadsheet | pemilik berkas | dibagikan sebagai **Editor**, untuk mencentang tombol |
| Yang client lakukan | — | mencentang satu kotak di tab `Kontrol`, atau menjalankan ekspor sendiri (bagian 11) |

Ada dua model, dan keduanya memakai kode yang sama:

1. **Model tombol (bawaan).** Client tidak memegang kredensial apa pun. Permintaan
   mereka berupa centang di spreadsheet, dan pengawas di mesin pengelola yang
   mengerjakannya. Syaratnya mesin itu menyala — lihat bagian 6.
2. **Mode client.** Client memegang `DATABASE_URL` read-only dan menjalankan
   ekspor sendiri di komputernya, memakai login akun Google-nya sendiri. Mesin
   pengelola tidak perlu ikut hidup. Langkahnya ada di bagian 11.

## 2. Yang diekspor dan yang sengaja tidak

| Tabel | Isi | Diekspor |
| --- | --- | --- |
| `transactions` | header nota | ya |
| `transaction_detail` | baris barang per nota | ya |
| `payment_proof` | metadata bukti transfer | ya |
| `device` | daftar device terdaftar | ya |
| `device_transaction_sequence` | posisi nomor nota per device | ya |
| `transaction_daily_sequence` | jatah nomor per tanggal | ya |
| `item` | 2917 master barang | **tidak** |
| `worker` | 2 baris karyawan | **tidak** |

Dua tabel terakhir dikecualikan karena isinya, bukan karena kepraktisan:
`worker.pin` berisi hash kredensial (keamanannya bergantung pada kekuatan PIN
enam digit saja), dan `item.cost_amount` termasuk data terlarang menurut aturan
repo — harga pokok dan margin tidak boleh keluar dari server. Keduanya juga data
referensi yang tidak berubah harian.

## 3. Cara kerjanya

- **Hanya membaca database.** Tidak ada `INSERT`, `UPDATE`, `DELETE`, atau DDL.
- **Isi setiap tab diganti, bukan ditambah.** Seluruh isi tab ditulis dalam satu
  permintaan lalu tampilannya dirapikan dalam satu permintaan terpisah, jadi
  tidak ada tab yang setengah terisi dan tidak ada baris kembar walau dijalankan
  berapa kali pun.
- **Waktu dalam WIB (UTC+7)**, memakai offset tetap supaya tidak bergantung pada
  basis data zona waktu Windows.
- **Kredensial tidak pernah dicetak.** `DATABASE_URL` memuat password; yang
  ditampilkan hanya host dan nama database. Berkas service account juga tidak
  pernah isinya ditulis ke layar.
- **Lebar kolom menyesuaikan isi setiap kali ekspor.** Setiap tab dirapikan
  dalam satu langkah: baris pertama (nama kolom) dibuat tebal dengan latar gelap
  dan dibekukan supaya tetap terlihat saat menggulir, kolom uang berformat
  `Rp 141.000`, kolom angka lain berformat ribuan, lalu lebar seluruh kolom
  dipas-kan ke isinya. Autofit dijalankan **paling akhir** dengan sengaja:
  Google menghitung lebar dari teks yang tampil, dan teks kolom uang baru punya
  awalan `Rp` setelah formatnya terpasang — kalau urutannya dibalik, kolom uang
  terhitung sempit lalu terpotong. Sesudah autofit, setiap kolom yang belum lebar
  ditambah 18 piksel supaya huruf terakhir tidak menempel garis kolom; kolom yang
  sudah lapang (di atas 220 piksel, mis. kolom catatan) dibiarkan apa adanya.
  Contoh hasil sungguhan di tab `transactions`: `107, 81, 143, 101, 126, 125,
  118, 101, 125, 251` piksel untuk sepuluh kolomnya, dan tab `Kontrol`
  `526, 735, 100`.
- **Kalau perapian tampilan gagal, data tetap tersimpan.** Penulisan data dan
  perapian adalah dua permintaan terpisah, dan kegagalan penambahan lebar kolom
  hanya dicatat sebagai catatan — bukan alasan untuk menggagalkan ekspor.

## 4. Persiapan sekali saja

### 4.1 Google Cloud

1. Buka <https://console.cloud.google.com/> dan pakai project yang sudah ada,
   atau buat project baru.
2. Menu **APIs & Services → Library**, aktifkan **Google Sheets API**.
   **Google Drive API** hanya perlu bila Anda memilih mencari spreadsheet lewat
   judul, bukan lewat ID (lihat 4.4).
3. Menu **APIs & Services → Credentials → Create credentials → Service
   account**, beri nama bebas.
4. Buka service account itu, salin **email**-nya — bentuknya
   `nama@project-id.iam.gserviceaccount.com`.
5. Tab **Keys → Add key → Create new key → JSON**. Berkas terunduh memuat
   private key dan merupakan satu-satunya salinan; Google tidak menyimpannya
   untuk Anda.

### 4.2 Bagikan spreadsheet tujuan

Buka spreadsheet tujuan di Google Drive, tekan **Share**, tempelkan email
service account dari 4.1 nomor 4, dan beri peran **Editor**. Editor wajib: tanpa
itu alat ini hanya bisa membaca, dan pembuatan tab akan ditolak.

### 4.3 Letakkan berkas kunci

Simpan berkas JSON dari 4.1 nomor 5 di salah satu lokasi berikut, dari yang
paling dulu dicari:

1. path yang ditulis di `GOOGLE_SERVICE_ACCOUNT_FILE` (kalau diisi), atau
2. `.secrets/service-account.json` (di akar repo ini), atau
3. `C:\Users\<nama-anda>\.pos-sheets\service-account.json`

Nama berkas unduhan Google berpola `<project-id>-<12 karakter heksadesimal>.json`
(mis. `pos-21733-2459738c0acc.json`), dan berkas itulah yang memuat private key.
**Jangan** meletakkannya di sembarang tempat di dalam repo. Sebagai jaring
pengaman, `.gitignore` di akar repo mengabaikan pola nama unduhan itu dan
`*service-account*.json`, tapi jangan mengandalkannya: `.secrets/` adalah
satu-satunya lokasi di dalam repo yang disediakan untuk kunci, dan lokasi di
luar repo lebih baik lagi karena tidak bergantung pada aturan mana pun.

### 4.4 Isi `.env` di akar repo ini

Tambahkan di bawah `DATABASE_URL`:

```env
# Wajib: ID spreadsheet tujuan. ID mentah maupun link penuh sama-sama diterima.
GOOGLE_SPREADSHEET_ID=https://docs.google.com/spreadsheets/d/<ID>/edit

# Opsional: sebagai gantinya, cari spreadsheed lewat judul. Butuh Google Drive
# API, dan kalau ada dua berkas berjudul sama, alat ini berhenti dan meminta ID.
# GOOGLE_SPREADSHEET_TITLE=Shadow DB

# Opsional: lokasi berkas kunci kalau tidak diletakkan di lokasi baku.
# GOOGLE_SERVICE_ACCOUNT_FILE=D:\pos-sheets-sync\.secrets\service-account.json

# Opsional: email yang otomatis diberi akses Editor ke spreadsheet ini.
# Isi dengan email client kalau Anda ingin alat ini yang membagikannya.
# GOOGLE_SHEETS_SHARE_WITH=client@example.com

# Opsional: jeda pemeriksaan tombol oleh pengawas, dalam detik. Bawaan 60,
# minimal 10.
# GOOGLE_SHEETS_WATCH_INTERVAL=60

# Opsional: cara masuk Google. Bawaan service-account (berkas kunci JSON).
# Di komputer client isi dengan oauth, lihat bagian 11.2.
# GOOGLE_AUTH_MODE=oauth
```

## 5. Menjalankan

Klik dua kali `Export ke Google Sheets.bat`, lalu pilih:

| Pilihan | Artinya |
| --- | --- |
| `1` | Ekspor sekarang — mengganti isi setiap tab |
| `2` | Uji tanpa menulis (dry run) — membaca database dan menampilkan rencananya |
| `3` | Periksa kredensial — cek kunci Google, sambungan database + hak aksesnya, spreadsheet tujuan, dan daftar tab |
| `4` | Pengawas permintaan — melayani tombol client (bagian 6), biarkan jendelanya terbuka |

Tanpa menu, argumennya bisa langsung diberikan:

```bat
"Export ke Google Sheets.bat" 3
"Export ke Google Sheets.bat" 1 --only transactions
"Export ke Google Sheets.bat" 2
"Export ke Google Sheets.bat" 4 --interval 30
"Export ke Google Sheets.bat" 3 --auth oauth
```

Argumen `--auth oauth` membuat skrip masuk memakai akun Google Anda sendiri
(bukan kunci service account) — itulah yang dipakai di komputer client, lihat
bagian 11.2.

Host yang berbasis jadwal (cron, kontainer, PaaS) memanggil skripnya langsung,
tanpa menu, dengan mode sekali-jalan:

```bat
venv\Scripts\python.exe tools\export_to_google_sheets.py --if-requested
```

Mode itu memeriksa kotak di tab Kontrol satu kali: kalau dicentang ia mengekspor
lalu keluar, kalau tidak ia keluar tanpa menyentuh Google Sheets. Di host
terjadwal, konfigurasinya boleh datang dari variabel lingkungan saja tanpa berkas
`.env` — lihat bagian 12.

Urutan yang disarankan pada kali pertama: **3** dulu (memastikan kunci dan
spreadsheet benar), lalu **2** (melihat data yang akan dikirim tanpa menyentuh
Google), baru **1**.

Kalau `gspread` belum ada, skrip memasangnya sendiri dari
`tools/requirements-export.txt`. Berkas itu memuat seluruh dependensi yang
dibutuhkan ekspor — `psycopg` dan `python-dotenv` sekaligus — sehingga repo ini
tidak bergantung pada `requirements.txt` backend POS.

## 6. Tombol untuk client

Client diberi akses **Editor** ke spreadsheet ini, dan satu-satunya hal yang
perlu mereka sentuh adalah kotak centang di tab **`Kontrol`**:

```
A1  Kontrol ekspor data POS
A3  Minta data terbaru        B3  <- kotak centang, dicentang client
A4  Status terakhir           B4  <- diisi pengawas
A5  Waktu permintaan diproses B5  <- diisi pengawas
A6  Ringkasan data terakhir   B6  <- diisi pengawas
A8  Cara pakai
A9    1. Centang kotak di sel B3.
A10   2. Tunggu. Status dan Waktu terisi sendiri, biasanya di bawah satu menit.
A11   3. Isi tab lain tergantikan dengan data terbaru dari database.
A14   Permintaan dilayani otomatis oleh pengawas ekspor. Kalau pengawasnya sedang tidak berjalan, centangan baru diproses setelah pengawas dinyalakan lagi.
A15   Data diambil dari database pada saat permintaan dilayani, bukan salinan lama.
```

**Cara kerjanya.** Pengawas memeriksa `B3` setiap 60 detik. Begitu kotaknya
dicentang, ia langsung mengosongkannya kembali (supaya kegagalan tidak
terulang terus), menulis status "Sedang memproses", menjalankan ekspor keenam
tab, lalu menulis status, waktu, dan ringkasan baris. Kotak yang sudah kosong itu
siap dicentang lagi kapan pun client mau.

**Yang dilakukan pengelola supaya ini hidup.** Jalankan `.bat` pilihan **4** dan
biarkan jendelanya terbuka. Supaya tidak perlu diingat setiap hari, daftarkan di
**Task Scheduler** Windows: pemicu *At log on*, aksi menjalankan
`POS\Export ke Google Sheets.bat` dengan argumen `4`. Pengawas lalu aktif sendiri
setiap kali Anda masuk Windows. Langkah pengawas ini sama saja di komputer mana
pun ia dijalankan — di komputer pengelola maupun di komputer client.

**Syarat yang tidak bisa dihindari.** Kredensial ada di mesin yang menjalankan
pengawas, jadi permintaan client hanya dilayani saat **mesin itu menyala dan
pengawasnya berjalan**. Kalau mesinnya mati atau Windows sedang tidur,
centangannya tinggal menunggu — client bisa melihat itu dari baris *Status* dan
*Waktu* yang tidak berubah.

Dua cara menyelesaikannya, dan **yang kedua sudah dipilih** (2026-09-28):

1. **Pindahkan pengawas ke mesin yang selalu menyala** (VPS kecil atau Raspberry
   Pi). Kodenya sama, yang perlu ada di sana hanya `DATABASE_URL`, kredensial
   Google, dan Python. Aiven bisa dijangkau dari luar jaringan toko, jadi tidak
   ada perubahan kode.
2. **Serahkan ke client: biarkan client menjalankan pengawas di komputernya**
   dengan `DATABASE_URL` read-only. Mesin pengelola tidak perlu ikut hidup, dan
   jam hidup pengawas menjadi tanggung jawab client. Langkah lengkapnya ada di
   **bagian 11**.

**Soal client punya akses Editor.** Editor pada spreadsheet ini berarti client
juga bisa mengubah tab data. Itu tidak berbahaya di praktiknya: setiap tab
ditulis ulang setiap kali ekspor berjalan, jadi perubahan mereka hilang sendiri,
dan tab yang terhapus akan dibuat ulang. Yang tidak bisa mereka lakukan adalah
menghapus berkasnya, karena pemiliknya akun Anda. Kalau tetap ingin dikunci,
di Google Sheets pakai **Data → Protect sheets and ranges** pada tab data; itu
tidak perlu diatur oleh alat ini.

## 7. Hasilnya

Satu spreadsheet, tujuh tab:

```
transactions                    <- satu tab per tabel
transaction_detail
payment_proof
device
device_transaction_sequence
transaction_daily_sequence
Kontrol                          <- tombol dan status permintaan
```

Tab bawaan `Sheet1` dihapus otomatis, tetapi hanya kalau memang masih kosong.

## 8. Yang client belum bisa lihat dari sini

- **Gambar bukti transfer tidak ikut.** Tabel `payment_proof` hanya berisi
  metadata (`object_key`, ukuran, sha256). Menampilkan gambarnya butuh endpoint
  baca di server, dan itu keputusan terpisah yang masih terbuka.
- **Harga pokok dan margin tidak ada**, karena tabel `item` dikecualikan.
- **Datanya setua ekspor terakhir.** Kalau pengawas tidak berjalan dan tidak ada
  yang mencentang, tab tetap berisi hasil jalan sebelumnya.
- **Device pembuat nota tidak terlihat langsung.** Tabel `transactions` tidak
  punya kolom `device_id`; asal device hanya bisa dibaca dari tiga huruf pertama
  `transaction_id` (mis. `T01-`).

## 9. Kalau gagal

| Pesan | Penyebab | Tindakan |
| --- | --- | --- |
| Berkas service account tidak ditemukan | kunci belum diletakkan | bagian 4.3 |
| API belum diaktifkan | API belum dinyalakan di project | buka tautan aktivasi yang dicetak alat ini, tunggu beberapa menit, ulangi |
| Akses ditolak / spreadsheet tidak ditemukan | spreadsheet belum dibagikan ke email service account | bagian 4.2, peran harus Editor |
| Spreadsheet tujuan belum ditentukan | `GOOGLE_SPREADSHEET_ID` belum diisi | bagian 4.4 |
| Ada dua spreadsheet berjudul sama | pencarian lewat judul menemukan lebih dari satu | pakai `GOOGLE_SPREADSHEET_ID` |
| Kuota Google Sheets API tercapai | terlalu sering dijalankan | tunggu sekitar satu menit, ulangi; tidak ada tab yang setengah terisi |
| Permintaan client tidak pernah diproses | mesin pengawas mati atau pengawas tidak berjalan | bagian 6 |
| Berkas client-secret OAuth tidak ditemukan | `--auth oauth` dipakai tetapi berkas OAuth belum ada | bagian 11.2 |
| Database tidak bisa dihubungi memakai DATABASE_URL | `DATABASE_URL` salah, atau IP mesin ini diblokir di Aiven | periksa isi `.env`; di console Aiven, bagian *Allowed IP addresses* |
| Pengguna database tidak bisa melihat tabel ... | pengguna read-only belum diberi hak | bagian 11.1 |
| Pengguna database belum punya hak baca (SELECT) ... | `GRANT SELECT` belum dijalankan | bagian 11.1 |
| Catatan: lebar kolom tidak bisa ditambah sedikit | pembacaan metadata kolom gagal | bukan kegagalan; jalankan ulang, tab tetap berisi data |
| Jeda pemeriksaan minimal 10 detik | `--interval` terlalu kecil | pakai 10 detik atau lebih |

Kegagalan selalu dicetak di akhir keluaran bersama langkah perbaikannya, kode
keluar bukan nol, dan status di tab `Kontrol` ikut mencatat pesan gagalnya
supaya client tahu permintaannya tidak berhasil. Satu tab yang gagal tidak
menghentikan tab lain: tab yang bisa ditulis tetap ditulis, lalu kegagalannya
dilaporkan sekaligus.

## 10. Batas keamanan yang perlu disadari

- Berkas kunci JSON adalah **kredensial penuh**: siapa pun yang memilikinya bisa
  menulis ke setiap spreadsheet yang dibagikan ke service account itu. Jangan
  dikirim lewat chat, jangan ditaruh di repo.
- **Jangan serahkan kunci JSON itu ke client.** Di mode client (bagian 11) yang
  diserahkan adalah `DATABASE_URL` read-only dan `oauth-client.json`, bukan kunci
  penulis. Kalau client perlu menjalankan ekspor, pakai `--auth oauth`.
- Kalau kunci itu bocor: buka Cloud Console, hapus kuncinya, buat kunci baru, dan
  ganti berkasnya. Tidak ada data POS yang ikut bocor karena itu — yang bocor
  hanya kemampuan menulis ke spreadsheet.
- Alat ini hanya membaca database, jadi menjalankannya tidak bisa merusak data
  POS, dan menjalankannya berulang kali tidak menumpuk baris. Pada mode client,
  jaminan itu diperkuat dua kali: perintahnya `SELECT` saja, dan `--check`
  memperingatkan kalau pengguna database yang dipakai masih punya hak tulis.

## 11. Mode client: client menjalankan sendiri

Dipilih **2026-09-28** oleh pemilik POS: client boleh memegang kredensial
database **read-only**. Dasarnya: isi database ini memang data milik client.
Konsekuensi yang disadari dan diterima: pengguna read-only itu bisa membaca
**seluruh tabel yang diberikan haknya** — kalau hak bacanya diberikan ke semua
tabel, termasuk `item.cost_amount` dan hash PIN di `worker`. Karena itu langkah
11.1 di bawah sebaiknya dibatasi ke enam tabel yang memang diekspor.

Dengan mode ini **komputer pengelola tidak perlu menyala**. Yang perlu hidup
adalah komputer yang menjalankan `.bat`, dan itu bisa komputer client sendiri.

### 11.1 Buat pengguna database read-only

Ini perubahan hak akses, bukan perubahan skema, tetapi tetap dijalankan oleh
pemilik database (butuh izin pemilik). Alat ini **tidak pernah** membuat atau
mengubah role sendiri.

```sql
create role pos_pembaca login password '<password-panjang>';
grant connect on database "DBengkulu" to pos_pembaca;
grant usage on schema public to pos_pembaca;

-- Varian yang disarankan: hanya enam tabel yang memang diekspor.
grant select on transactions, transaction_detail, payment_proof,
  device, device_transaction_sequence, transaction_daily_sequence
  to pos_pembaca;

-- Varian lain: seluruh isi database. Pilih ini hanya kalau memang dikehendaki,
-- karena ikut membuka item.cost_amount dan hash PIN di worker.
-- grant select on all tables in schema public to pos_pembaca;
```

**Status: belum dijalankan.** Nama pengguna, password, dan varian mana yang
dipilih belum diputuskan. Yang bisa dipakai untuk memastikan hasilnya benar
adalah pilihan **3** pada `.bat` (`--check`): alat ini menyambung dengan
`DATABASE_URL` yang ada, menyebut nama pengguna database, menolak jalan kalau
ada tabel yang tidak bisa dibaca, dan memperingatkan kalau pengguna itu ternyata
masih punya hak tulis.

Pengguna yang dibuat lewat menu **Users → Add user** di console Aiven belum
tentu langsung terbatas; yang pasti, jalankan `--check` setelahnya untuk melihat
hak apa yang benar-benar dimilikinya.

`DATABASE_URL` untuk client bentuknya:

```env
DATABASE_URL=postgres://pos_pembaca:<password>@pg-e5b9d28-pos-21733.l.aivencloud.com:20806/DBengkulu?sslmode=require
```

### 11.2 Kredensial Google: pilih login sendiri, jangan kunci service account

Dua pilihan, dan yang pertama lebih baik untuk client:

| | Login akun Google sendiri (`--auth oauth`) | Berkas kunci service account |
| --- | --- | --- |
| Yang dipegang client | `oauth-client.json` (bukan rahasia; cuma penanda aplikasi) | kunci JSON penulis |
| Cara masuk | peramban terbuka sekali, lalu tersimpan | otomatis dari berkas |
| Kalau bocor | tidak bisa dipakai tanpa persetujuan akun Google client | siapa pun bisa menulis ke **setiap** spreadsheet milik service account itu |
| Syarat di Google | spreadsheet dibagikan ke **email Google client** | spreadsheet dibagikan ke email service account |

Langkah OAuth, sekali saja:

1. Di Google Cloud project yang sama, buka **APIs & Services → Credentials →
   Create credentials → OAuth client ID**, pilih jenis **Desktop app**.
2. Unduh berkas JSON-nya, ganti namanya menjadi `oauth-client.json`.
3. Bagikan spreadsheet `Shadow DB` ke **email Google client** sebagai Editor.
4. Letakkan `oauth-client.json` di `.secrets/` di komputer client
   (atau di `C:\Users\<client>\.pos-sheets\`). Letaknya diabaikan `.gitignore`,
   jadi jangan taruh di tempat lain di dalam repo.
5. Di komputer client, jalankan `.bat` pilihan **3** sekali. Peramban terbuka,
   client memilih akun Google-nya dan menyetujui izin; tokennya disimpan di
   `.secrets/oauth-token.json` dan tidak ditanya lagi setelah itu.
   Kalau komputer itu tidak punya peramban (mis. VPS), lakukan langkah ini dulu
   di komputer yang punya, lalu salin `oauth-token.json` ke sana bersama
   kunci-kunci lain.

Untuk memakai mode ini, tambahkan di `.env`:

```env
GOOGLE_AUTH_MODE=oauth
# Opsional, kalau berkasnya tidak diletakkan di lokasi baku:
# GOOGLE_OAUTH_CLIENT_FILE=D:\pos-sheets-sync\.secrets\oauth-client.json
```

### 11.3 Yang perlu ada di komputer client

1. **Python 3.11 atau lebih baru**, dipasang dari <https://www.python.org/> dengan
   **Add python.exe to PATH** dicentang saat pemasangan.
2. **Salinan folder repo ini.** Aplikasi POS tidak perlu ada di komputer client —
   yang disalin hanya folder ini, tanpa `venv` (nomor 4). Yang wajib ada:
   `Export ke Google Sheets.bat` di akar folder, dan `tools\`
   berisi `export_to_google_sheets.py` beserta `requirements-export.txt`.
3. **`.env` di akar folder berisi dua hal:** `DATABASE_URL` read-only dari 11.1
   dan `GOOGLE_SPREADSHEET_ID` spreadsheet tujuan. Kredensial Google diletakkan
   di `.secrets\` (11.2).
4. **Periksa sekali:** jalankan `.bat` pilihan **3**. Kalau keluarnya menyebut
   `Pengguna database : pos_pembaca`, `Hak tulis : tidak ada (read-only)`, dan
   semua tab terbaca, mesin client siap.
5. **Biarkan hidup:** jalankan `.bat` pilihan **4**. Supaya nyala sendiri,
   daftarkan di **Task Scheduler** komputer client dengan pemicu *At log on* dan
   argumen `4`. Kalau komputer client dimatikan di luar jam kerja, permintaan di
   luar jam itu baru dilayani saat komputernya dinyalakan lagi.

Kalau `venv` belum ada di salinan itu (mis. karena venv sengaja tidak ikut
disalin), buat sekali di akar folder:

```bat
python -m venv venv
```

Paket-paketnya tidak perlu dipasang manual: `.bat` ekspor memasang sendiri
`gspread`, `google-auth`, `google-auth-oauthlib`, `psycopg`, dan `python-dotenv`
dari `tools\requirements-export.txt` saat pertama dijalankan.

Kalau client ingin 24 jam tanpa bergantung komputernya, langkahnya sama: pindahkan
folder ini ke VPS kecil dan jalankan menu **4** di sana (bisa juga dijadwalkan
lewat cron atau Task Scheduler Linux).

### 11.4 Yang tetap dibatasi

- Client **tidak bisa mengubah data POS** kalau `DATABASE_URL`-nya benar-benar
  read-only; alat ini sendiri pun hanya menjalankan `SELECT`.
- Client **tidak bisa merusak spreadsheet**: setiap tab ditulis ulang saat
  ekspor berjalan, dan tab yang terhapus akan dibuat ulang. Yang tidak bisa
  mereka lakukan adalah menghapus berkasnya, karena pemiliknya akun pengelola.
- Client **bisa** membaca tabel yang diberikan haknya di luar alat ini (mis.
  lewat DB client apa pun). Batasnya ada di `GRANT`, bukan di alat ini — karena
  itu batasi ke enam tabel di 11.1.

## 12. Menjalankan pengawas di cloud (Northflank, gratis)

Tujuan bagian ini: permintaan client tetap dilayani tanpa **komputer mana pun
milik pengelola menyala**. Yang berjalan terus adalah pengawas di cloud, dan
konfigurasinya diisi lewat variabel lingkungan — bukan berkas.

### 12.1 Apa yang perlu disiapkan

- Akun [Northflank](https://northflank.com/) yang terhubung ke GitHub.
- Repo ini di GitHub. **Tidak ada folder yang disalin manual**: Northflank
  membangun image langsung dari repo, memakai `Dockerfile` di akarnya — itulah
  gunanya repo ini dipisah dari repo POS, yang dibangun hanyalah alat ekspor.
- Perubahan terakhir (Dockerfile, mode `--if-requested`, dukungan variabel
  lingkungan) harus sudah ter-push ke branch yang dipilih, karena yang dibangun
  adalah isi repo — bukan folder di komputer.
- `venv` Windows tidak disalin dan tidak dibutuhkan. `tools/requirements-export.txt`
  sekarang sudah memuat `psycopg` dan `python-dotenv` sekaligus, jadi host cukup
  memasang berkas itu.

### 12.2 Langkah membuat service

1. Masuk Northflank, buat project baru (mis. `pos-ekspor`).
2. **Create service** → sumber **GitHub** → pilih repo ini dan branch `main`.
3. Isi bagian build:
   - **Build context**: akar repo ini (`.`) — di banyak formulir cukup dibiarkan
     kosong atau diisi `/`.
   - **Dockerfile**: `Dockerfile`, tepat di akar repo.
   - Jenis: **Service** (proses yang berjalan terus), **bukan** Job.
   - Port publik **tidak perlu**: pengawas ini tidak melayani HTTP, ia hanya
     membaca spreadsheet dan database.
4. Ukuran instance: yang terkecil sudah lebih dari cukup
   (`nf-compute-10`: 0.1 vCPU, 256 MB).
5. Isi variabel lingkungan (di Northflank: bagian *Environment*/*Secrets*),
   ketiganya sebagai secret:

   | Variabel | Isi |
   | --- | --- |
   | `DATABASE_URL` | koneksi PostgreSQL, boleh pengguna read-only |
   | `GOOGLE_SPREADSHEET_ID` | ID atau link spreadsheet tujuan |
   | `GOOGLE_SERVICE_ACCOUNT_JSON` | seluruh isi `service-account.json`, ditempel apa adanya |

6. Deploy, lalu buka **Logs**. Yang harus terlihat:

   ```
   Berkas /app/.env tidak ada - memakai variabel lingkungan yang sudah diisi.
   Masuk sebagai  : miaw-38@pos-21733.iam.gserviceaccount.com (service-account)
   Kredensial     : GOOGLE_SERVICE_ACCOUNT_JSON (variabel lingkungan)
   Database       : pg-e5b9d28-pos-21733.l.aivencloud.com:20806/DBengkulu
   Spreadsheet    : Shadow DB (...)
   Diperiksa setiap 60 detik.
   ```

7. Uji dari spreadsheet: centang `Kontrol!B3`. Paling lambat satu menit kemudian
   baris *Status* dan *Waktu* terisi, dan isi tab lain sudah data terbaru.
8. Aiven: buka **Allowed IP addresses**. Host PaaS tidak punya IP tetap, jadi
   biarkan daftar itu **kosong**. Kalau Aiven menolak koneksi dari host ini,
   permintaannya gagal dan pesannya muncul di baris *Status*.

### 12.3 Kalau ingin lebih hemat lagi: cron, bukan proses menunggu

Free tier Northflank menyediakan **2 cron job**. Untuk memakainya, ubah
perintahnya menjadi `--if-requested` dan atur jadwalnya (mis. tiap 5 menit).

Bedanya dengan pengawas: prosesnya tidak menunggu, hanya bangun saat jadwalnya
tiba. Kalau kotaknya belum dicentang, skrip keluar tanpa menyentuh Google Sheets;
kalau dicentang, ekspor berjalan. Permintaan client dilayani dengan jeda sampai
satu interval, bukan di bawah satu menit.

Mode yang sama dipakai host terjadwal lain (Cloud Run + Cloud Scheduler, GitHub
Actions, cron di VPS):

```bash
python tools/export_to_google_sheets.py --if-requested
```

### 12.4 Catatan gratis dan batasnya

- Tier **Sandbox** Northflank menyebut komputernya selalu nyala (tidak tidur)
  dengan 2 service + 2 cron job gratis. Kalau nanti butuh service lain (mis. API
  POS produksi), hitungannya terpisah.
- Hal yang mudah berubah — apakah kartu kredit wajib saat mendaftar, jeda
  minimum cron, dan kuota gratisnya sendiri — periksa di halaman mereka saat
  mendaftar. Bagian ini mencatat cara yang berhasil, bukan janji platform.
- Paketnya **portabel**: image yang sama bisa dijalankan di VPS mana pun dengan
  `docker run`, atau tanpa kontainer cukup
  `python tools/export_to_google_sheets.py --watch` plus `systemd`. Berpindah host
  tidak mengubah kode.

### 12.5 Keamanan

- `GOOGLE_SERVICE_ACCOUNT_JSON` adalah **kredensial penulis** untuk setiap
  spreadsheet yang dibagikan ke service account itu. Simpan sebagai secret di
  platform, jangan di `Dockerfile`, jangan di repo.
- `.dockerignore` sengaja mengecualikan `.env` dan `.secrets/` supaya kredensial
  lokal tidak ikut terbawa ke dalam image.
- Kalau nanti yang menjalankan pengawas adalah client, arah yang lebih aman tetap
  `--auth oauth` di komputernya sendiri (bagian 11.2): kunci penulis tidak perlu
  berpindah tangan.
