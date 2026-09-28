# Ekspor Data POS ke Google Sheets

Alat ini menyalin tabel **dinamis** POS dari PostgreSQL ke satu spreadsheet
Google, masing-masing ke tabnya sendiri, dan dijalankan lewat
`Export ke Google Sheets.bat`.

Repo ini **berdiri sendiri, terpisah dari repo POS**: aplikasi POS tidak ikut
berjalan dan tidak perlu ada di komputer yang menjalankan ekspor, sehingga
seluruh foldernya bisa diserahkan ke client atau dipindahkan ke mesin lain tanpa
ikut membawa server POS.

Alasan alat ini ada: client tidak perlu masuk ke console database, tetapi tetap
perlu melihat data penjualan — dan kadang perlu data terbaru tanpa menunggu
pemilik. Sejak 2026-09-28 program ini **diserahkan ke client** untuk dijalankan
di komputernya sendiri, bersama berkas kunci Google-nya; akses database yang
diserahkan tetap read-only. Rinciannya di bagian 11.

**Status: sudah dijalankan sungguhan.** Ekspor berjalan ke spreadsheet `Shadow DB`
(`1kB02M_4asD38-7Qna6N9cSws5EHpP3VglXLw2nrHC0A`) sejak 2026-09-28: lima tab data
terisi (lihat bagian 2), tab bawaan `Sheet1` dihapus, header tebal dan
dibekukan, kolom uang berformat `Rp`, dan lebar kolom menyesuaikan isi (bagian
3). Tab `device` juga diberi stempel waktu jalan di sel `D1` — bagian 7.

Tab `Kontrol` beserta tombol "minta data terbaru" **sudah dipensiunkan**
(2026-09-28): alat ini kini hanya berjalan kalau ada yang menjalankannya, jadi
tidak ada lagi pengawas yang membaca centangan. Tab `Kontrol` yang masih tersisa
di spreadsheet boleh dihapus dengan tangan — alat ini tidak lagi membuat atau
menyentuhnya.

---

## 1. Siapa yang menjalankannya, dan dengan kredensial apa

Alat ini dijalankan **manual**: satu orang, di satu komputer, dengan dua
kredensial di tangannya.

| | Isinya |
| --- | --- |
| `DATABASE_URL` | koneksi PostgreSQL, di `.env` akar repo ini. Sebaiknya pengguna **read-only** (bagian 11.1) supaya ekspor tidak mungkin mengubah data POS |
| Kredensial Google | berkas kunci service account di `.secrets\service-account.json` (bagian 4.3), atau `--auth oauth` kalau kunci itu tidak ingin disimpan di mesin tersebut |
| Yang dikerjakan | klik dua kali `Export ke Google Sheets.bat`, pilih **1** |

Kalau yang menjalankannya adalah komputer client, langkah lengkapnya ada di
bagian 11 — termasuk apa saja yang perlu diserahkan ke sana.

## 2. Yang diekspor dan yang sengaja tidak

| Tabel | Isi | Diekspor |
| --- | --- | --- |
| `transactions` | header nota | ya |
| `transaction_detail` | baris barang per nota | ya |
| `payment_proof` | metadata bukti transfer | ya |
| `device` | daftar device terdaftar | ya |
| `device_transaction_sequence` | posisi nomor nota per device | ya |
| `transaction_daily_sequence` | sisa desain nomor nota harian, tidak dipakai kode mana pun | **tidak** |
| `item` | 2917 master barang | **tidak** |
| `worker` | 2 baris karyawan | **tidak** |

`transaction_daily_sequence` sengaja **tidak** diekspor sejak 2026-09-28: nomor
nota yang berlaku sekarang dibagikan per device lewat
`device_transaction_sequence`, dan tabel itu—bersama kolom `last_sequence` di
dalamnya—tidak pernah dibaca kode mana pun. Selama tabelnya masih ada di
database, mengekspornya hanya menghasilkan satu tab kosong. Tab lamanya di
spreadsheet harus dihapus sekali dengan tangan; alat ini hanya tidak lagi
menyentuhnya.

`item` dan `worker` dikecualikan karena isinya, bukan karena kepraktisan:
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
  118, 101, 125, 251` piksel untuk sepuluh kolomnya. Perapian itu dibatasi ke
  sel yang berisi data: latar gelap hanya selebar kolom data, format angka hanya
  setinggi baris data, dan seluruh sel di luar data dikembalikan ke tampilan
  baku setiap kali ekspor. Tanpa itu, tab `device` (dua kolom) dan
  `device_transaction_sequence` (tiga kolom) terlihat punya kolom tambahan yang
  ikut dirapikan, dan sisa format dari jalan sebelumnya tetap menempel di baris
  yang sudah kosong.
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
# GOOGLE_SERVICE_ACCOUNT_FILE=D:\DB-to-sheets\.secrets\service-account.json

# Opsional: email yang otomatis diberi akses Editor ke spreadsheet ini.
# Isi dengan email client kalau Anda ingin alat ini yang membagikannya.
# GOOGLE_SHEETS_SHARE_WITH=client@example.com

# Opsional: cara masuk Google. Bawaan service-account (berkas kunci JSON).
# Isi dengan oauth kalau kunci itu tidak ingin disimpan di mesin ini; lihat
# bagian 11.2.
# GOOGLE_AUTH_MODE=oauth
```

## 5. Menjalankan

Klik dua kali `Export ke Google Sheets.bat`, lalu pilih:

| Pilihan | Artinya |
| --- | --- |
| `1` | Ekspor sekarang — mengganti isi setiap tab |
| `2` | Uji tanpa menulis (dry run) — membaca database dan menampilkan rencananya |
| `3` | Periksa kredensial — cek kunci Google, sambungan database + hak aksesnya, spreadsheet tujuan, dan daftar tab |

Tanpa menu, argumennya bisa langsung diberikan:

```bat
"Export ke Google Sheets.bat" 3
"Export ke Google Sheets.bat" 1 --only transactions
"Export ke Google Sheets.bat" 2
"Export ke Google Sheets.bat" 3 --auth oauth
```

Argumen `--auth oauth` membuat skrip masuk memakai akun Google Anda sendiri,
bukan kunci service account — lihat bagian 11.2. Itu berlaku untuk semua pilihan
di atas.

Penjadwal (Windows Task Scheduler, cron) memanggil skripnya langsung, tanpa menu:

```bat
venv\Scripts\python.exe tools\export_to_google_sheets.py
```

Konfigurasinya boleh datang dari variabel lingkungan saja tanpa berkas `.env`.
Bedanya dengan memakai `.bat`: skripnya keluar sendiri tanpa menunggu tombol
ditekan, sehingga cocok untuk jadwal — lihat bagian 12.

Urutan yang disarankan pada kali pertama: **3** dulu (memastikan kunci dan
spreadsheet benar), lalu **2** (melihat data yang akan dikirim tanpa menyentuh
Google), baru **1**.

Kalau `gspread` belum ada, skrip memasangnya sendiri dari
`tools/requirements-export.txt`. Berkas itu memuat seluruh dependensi yang
dibutuhkan ekspor — `psycopg` dan `python-dotenv` sekaligus — sehingga repo ini
tidak bergantung pada `requirements.txt` backend POS.

## 6. Kalau ada yang ingin data terbaru

Dulu client bisa mencentang kotak di tab `Kontrol`, dan pengawas di mesin lain
yang mengerjakannya. Cara itu **sudah dipensiunkan** (2026-09-28): ekspor
sekarang hanya berjalan kalau ada yang menjalankannya.

- **Anda sendiri:** klik dua kali `.bat`, pilih **1**. Untuk ukuran data sekarang
  (37 baris di lima tab) seluruhnya selesai dalam beberapa detik.
- **Client:** serahkan foldernya beserta kredensialnya sekali, lalu client
  menjalankan menu **1** kapan pun ia butuh — bagian 11.
- **Tanpa ada yang mengklik:** jadwalkan menu 1 di Task Scheduler — bagian 12.

**Datanya setua ekspor terakhir.** Kalau tidak ada yang menjalankan, isi tab
tidak berubah. Satu-satunya cara melihat kapan terakhir kali dijalankan dari
dalam spreadsheet adalah stempel waktu di `device!D1` (bagian 7).

**Soal client diberi akses Editor.** Editor pada spreadsheet ini berarti client
juga bisa mengubah tab data. Itu tidak berbahaya di praktiknya: setiap tab
ditulis ulang setiap kali ekspor berjalan, jadi perubahan mereka hilang sendiri,
dan tab yang terhapus akan dibuat ulang. Yang tidak bisa mereka lakukan adalah
menghapus berkasnya, karena pemiliknya akun Anda. Kalau tetap ingin dikunci,
di Google Sheets pakai **Data → Protect sheets and ranges** pada tab data; itu
tidak perlu diatur oleh alat ini.

## 7. Hasilnya

Satu spreadsheet, lima tab:

```
transactions                    <- satu tab per tabel
transaction_detail
payment_proof
device                          <- stempel waktu di sel D1
device_transaction_sequence
```

**Stempel waktu jalan.** Tab `device` hanya memakai kolom A dan B, jadi sel `D1`
diisi waktu (WIB) saat tab itu terakhir ditulis, mis. `2026-09-28 20:56:11 WIB`.
Itu satu-satunya penanda kapan ekspor terakhir berjalan, dan sengaja dipasang di
tab yang kolomnya masih lapang supaya tidak menimpa data. Kalau nanti ada tabel
lain yang punya kolom kosong, selnya ditambahkan di `RUN_STAMP_CELLS` pada
`tools/export_to_google_sheets.py`. Bila suatu saat tabel `device` memakai kolom
D, stempelnya dilewati sendiri — bukan header kolom yang tertimpa.

Tab bawaan `Sheet1` dihapus otomatis, tetapi hanya kalau memang masih kosong.
Tab sisa ekspor lama — `transaction_daily_sequence` dan `Kontrol` — **tidak**
ikut terhapus: alat ini tidak pernah menghapus tab yang tidak ia kelola, supaya
catatan yang client tempelkan di sebuah tab tidak hilang tanpa sengaja. Hapus
keduanya sekali lewat klik kanan → *Delete* di Google Sheets.

## 8. Yang client belum bisa lihat dari sini

- **Gambar bukti transfer tidak ikut.** Tabel `payment_proof` hanya berisi
  metadata (`object_key`, ukuran, sha256). Menampilkan gambarnya butuh endpoint
  baca di server, dan itu keputusan terpisah yang masih terbuka.
- **Harga pokok dan margin tidak ada**, karena tabel `item` dikecualikan.
- **Datanya setua ekspor terakhir.** Kalau tidak ada yang menjalankan ekspor,
  tab tetap berisi hasil jalan sebelumnya (lihat `device!D1`).
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
| Berkas client-secret OAuth tidak ditemukan | `--auth oauth` dipakai tetapi berkas OAuth belum ada | bagian 11.2 |
| Database tidak bisa dihubungi memakai DATABASE_URL | `DATABASE_URL` salah, atau IP mesin ini diblokir di Aiven | periksa isi `.env`; di console Aiven, bagian *Allowed IP addresses* |
| Pengguna database tidak bisa melihat tabel ... | pengguna read-only belum diberi hak | bagian 11.1 |
| Pengguna database belum punya hak baca (SELECT) ... | `GRANT SELECT` belum dijalankan | bagian 11.1 |
| Catatan: lebar kolom tidak bisa ditambah sedikit | pembacaan metadata kolom gagal | bukan kegagalan; jalankan ulang, tab tetap berisi data |

Kegagalan selalu dicetak di akhir keluaran bersama langkah perbaikannya, dan kode
keluarnya bukan nol. Satu tab yang gagal tidak menghentikan tab lain: tab yang
bisa ditulis tetap ditulis, lalu kegagalannya dilaporkan sekaligus.

## 10. Batas keamanan yang perlu disadari

- Berkas kunci JSON adalah **kredensial penuh**: siapa pun yang memilikinya bisa
  menulis ke setiap spreadsheet yang dibagikan ke service account itu. Jangan
  dikirim lewat chat, jangan ditaruh di repo.
- **Kunci penulis itu memang diserahkan ke client, dan itu keputusan yang
  disadari** (2026-09-28, bagian 11.2). Yang perlu diingat: hak yang berpindah
  bukan hanya "menulis ke `Shadow DB`", melainkan menulis ke **setiap**
  spreadsheet yang dibagikan ke service account itu. Jadi jangan membagikan
  spreadsheet lain — apalagi spreadsheet pribadi — ke email service account yang
  sama. Kalau nanti client berhenti memakai program ini, cabut kuncinya di Cloud
  Console (tab **Keys** → hapus) dan buat kunci baru kalau masih dibutuhkan.
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
11.1 di bawah sebaiknya dibatasi ke lima tabel yang memang diekspor.

Di hari yang sama pemilik POS juga memutuskan **program ini beserta berkas kunci
service account-nya dikirim langsung ke client**, jadi client menjalankannya
sendiri di komputernya. Konsekuensinya dua: client memegang kredensial penulis
Google (lihat 11.2), dan jalur cloud di bagian 12 menjadi tidak diperlukan
selama komputer client hidup pada jam yang diinginkan.

Dengan mode ini **komputer pengelola tidak perlu menyala**. Yang perlu hidup
adalah komputer yang menjalankan `.bat`, dan itu komputer client sendiri.

### 11.1 Buat pengguna database read-only

Ini perubahan hak akses, bukan perubahan skema, tetapi tetap dijalankan oleh
pemilik database (butuh izin pemilik). Alat ini **tidak pernah** membuat atau
mengubah role sendiri.

```sql
create role pos_pembaca login password '<password-panjang>';
grant connect on database "DBengkulu" to pos_pembaca;
grant usage on schema public to pos_pembaca;

-- Varian yang disarankan: hanya lima tabel yang memang diekspor.
grant select on transactions, transaction_detail, payment_proof,
  device, device_transaction_sequence
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

### 11.2 Kredensial Google: kunci penulis atau login sendiri

**Yang dipakai sekarang: kunci service account ikut dikirim ke client**
(keputusan pemilik POS, 2026-09-28). Kolom kanan tetap didokumentasikan karena
itulah jalur pengganti kalau nanti ingin kunci penulis ditarik kembali dari
komputer client.

| | Berkas kunci service account (**dipakai sekarang**) | Login akun Google sendiri (`--auth oauth`) |
| --- | --- | --- |
| Yang dipegang client | kunci JSON penulis | `oauth-client.json` (bukan rahasia; cuma penanda aplikasi) |
| Cara masuk | otomatis dari berkas, tidak ada langkah tambahan | peramban terbuka sekali, lalu tersimpan |
| Kalau bocor | siapa pun bisa menulis ke **setiap** spreadsheet milik service account itu | tidak bisa dipakai tanpa persetujuan akun Google client |
| Syarat di Google | spreadsheet dibagikan ke email service account | spreadsheet dibagikan ke **email Google client** |

Dua hal yang membuat jalur ini tetap terkendali:

1. **Kuncinya tidak masuk git di kedua sisi.** `.gitignore` repo ini mengabaikan
   `.secrets/` beserta pola nama unduhan Google, dan salinan yang pernah ada di
   repo POS sudah dihapus. Berkasnya dikirim **di luar git** — bukan lewat repo,
   bukan lewat chat grup; sebaiknya sebagai arsip berpassword atau tautan yang
   bisa kedaluwarsa, dengan catatan bahwa berkas itu adalah kredensial.
2. **Database-nya tetap read-only.** Yang berpindah tangan hanya hak tulis ke
   Google Sheets; client tetap tidak bisa mengubah data POS (11.1 dan 11.4).

Langkah OAuth (hanya kalau ingin memakai kolom kanan), sekali saja:

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

Untuk beralih ke model itu, tambahkan di `.env`:

```env
GOOGLE_AUTH_MODE=oauth
# Opsional, kalau berkasnya tidak diletakkan di lokasi baku:
# GOOGLE_OAUTH_CLIENT_FILE=D:\DB-to-sheets\.secrets\oauth-client.json
```

### 11.3 Yang perlu ada di komputer client

**Yang dikirim ke client**, dan ini dua paket terpisah:

1. **Seluruh isi folder repo ini**, kecuali `venv\` dan `.env` (dua-duanya
   diabaikan git, jadi menyalin dari git memang tidak membawanya; `venv` bisa
   dibuat ulang di komputer client, dan lebih baik begitu supaya jalan di sana).
2. **Dua berkas rahasia, di luar git:** `.env` berisi `DATABASE_URL` read-only
   (11.1) dan `GOOGLE_SPREADSHEET_ID` spreadsheet tujuan, serta
   `.secrets\service-account.json` — kunci penulis dari 4.1 nomor 5, atau kunci
   yang sedang dipakai di mesin pengelola.

Di komputer client:

1. **Python 3.11 atau lebih baru**, dipasang dari <https://www.python.org/> dengan
   **Add python.exe to PATH** dicentang saat pemasangan.
2. **Salinan folder repo ini** (paket 1 di atas). Aplikasi POS tidak perlu ada di
   komputer client. Yang wajib ada: `Export ke Google Sheets.bat` di akar folder,
   dan `tools\` berisi `export_to_google_sheets.py` beserta
   `requirements-export.txt`.
3. **`.env` di akar folder berisi dua hal:** `DATABASE_URL` read-only dari 11.1
   dan `GOOGLE_SPREADSHEET_ID` spreadsheet tujuan. **Berkas kunci**
   `service-account.json` diletakkan di `.secrets\` di akar folder yang sama
   (lokasi pertama yang dicari alat ini — lihat 4.3; kalau foldernya belum ada,
   buat dulu). Jangan ditaruh di lokasi lain di dalam folder itu.
4. **Periksa sekali:** jalankan `.bat` pilihan **3**. Yang diharapkan muncul:
   `Cara masuk Google : service-account`, `Mesin Google :
   miaw-38@pos-21733.iam.gserviceaccount.com`, `Pengguna database :
   pos_pembaca`, dan `Hak tulis : tidak ada (read-only)`. Kalau semua itu benar
   dan semua tab terbaca, mesin client siap. Kalau `Mesin Google` menunjuk email
   yang tidak dikenal, berarti berkas kunci yang terpasang bukan yang dimaksud.
5. **Jalankan kapan perlu:** `.bat` pilihan **1** setiap kali client ingin data
   terbaru. Kalau ingin berjalan sendiri, jadwalkan pilihan 1 di **Task
   Scheduler** komputer client (bagian 12) — tidak ada tombol di spreadsheet yang
   perlu dilayani, jadi tidak ada proses yang harus dibiarkan menunggu.

Kalau `venv` belum ada di salinan itu (mis. karena venv sengaja tidak ikut
disalin), buat sekali di akar folder:

```bat
python -m venv venv
```

Paket-paketnya tidak perlu dipasang manual: `.bat` ekspor memasang sendiri
`gspread`, `google-auth`, `google-auth-oauthlib`, `psycopg`, dan `python-dotenv`
dari `tools\requirements-export.txt` saat pertama dijalankan.

Kalau client ingin ekspornya berjalan tanpa ada yang mengklik, langkahnya sama:
pindahkan folder ini ke VPS kecil dan jadwalkan menu **1** di sana (cron atau
Timer systemd).

### 11.4 Yang tetap dibatasi

- Client **tidak bisa mengubah data POS** kalau `DATABASE_URL`-nya benar-benar
  read-only; alat ini sendiri pun hanya menjalankan `SELECT`.
- Client **tidak bisa merusak spreadsheet**: setiap tab ditulis ulang saat
  ekspor berjalan, dan tab yang terhapus akan dibuat ulang. Yang tidak bisa
  mereka lakukan adalah menghapus berkasnya, karena pemiliknya akun pengelola.
- Client **bisa** membaca tabel yang diberikan haknya di luar alat ini (mis.
  lewat DB client apa pun). Batasnya ada di `GRANT`, bukan di alat ini — karena
  itu batasi ke lima tabel di 11.1.

## 12. Menjalankan berkala di komputer sendiri

Ekspor tidak lagi dipicu tombol, jadi satu-satunya cara membuatnya berjalan
sendiri adalah menjadwalkannya di komputer yang menyimpan kredensial.

**Windows (Task Scheduler).** Perintah berikut membuat satu tugas harian jam
08:00, dijalankan sekali dari Command Prompt:

```bat
schtasks /Create /TN "Ekspor POS ke Sheets" /SC DAILY /ST 08:00 ^
  /TR "D:\DB-to-sheets\venv\Scripts\python.exe D:\DB-to-sheets\tools\export_to_google_sheets.py"
```

Sesuaikan folder `D:\DB-to-sheets\` dengan tempat folder ini diletakkan. Yang
dipanggil adalah **python-nya langsung**, bukan `.bat`-nya: `.bat` berhenti
menunggu tombol ditekan di akhir, dan penantian itu tidak ada yang menjawabnya
dalam tugas otomatis. Untuk mencobanya sekarang tanpa menunggu jamnya:
`schtasks /Run /TN "Ekspor POS ke Sheets"`, lalu lihat waktu terakhir di
`device!D1`.

**Linux (cron).** Satu baris, tiap hari jam 08:00, keluaran dicatat ke berkas:

```
0 8 * * * cd /path/ke/DB-to-sheets && venv/bin/python tools/export_to_google_sheets.py >> ekspor.log 2>&1
```

Yang perlu disadari:

- **Komputernya harus menyala** pada jam yang dijadwalkan. Kalau jadwalnya
  terlewat, tidak ada yang mengejar — data terbaru baru ada pada jalan berikutnya.
- **Tidak ada jalur cloud di repo ini.** Jalur kontainer (Dockerfile + Northflank)
  dihapus 2026-09-28 karena tidak satu pun host selalu-nyala gratis bisa dipakai
  tanpa kartu kredit, dan jalur GitHub Actions dihapus di hari yang sama setelah
  tombolnya dipensiunkan — penjadwal tidak lagi punya alasan untuk menunggu
  permintaan dari luar. Kalau nanti salah satunya dibutuhkan lagi, keduanya
  masih ada di riwayat git:
  `git log --oneline -- Dockerfile .github/workflows`.
- Paketnya **portabel**: memindahkannya ke VPS kecil pun cukup menaruh folder ini,
  membuat venv, lalu menjadwalkannya dengan cron atau timer systemd. Tidak ada
  berkas yang perlu diubah.

### 12.1 Keamanan

- Kunci service account adalah **kredensial penulis** untuk setiap spreadsheet
  yang dibagikan ke akun itu. Simpan hanya di `.secrets\` atau di luar repo
  (`%USERPROFILE%\.pos-sheets\`), dan jangan pernah menempelkan isinya ke berkas
  yang terlacak git.
- **Dua berkas di repo ini cuma penanda, bukan kredensial:** `.env` berisi teks
  contoh dan `.secrets/service-account.json` berisi `{}`. Keduanya ada supaya
  susunan berkasnya terlihat. Karena sudah terlacak git, `.gitignore` tidak lagi
  melindungi dua path itu — isi aslinya tinggal di komputer dan **tidak boleh**
  ditempel ke sana lalu di-commit; repo ini publik. Berkas penanda yang belum
  diisi ditolak sebagai "belum diisi", jadi pesan galatnya tetap menunjukkan
  lokasi kunci yang dicari.
- Kalau nanti yang menjalankan ekspor adalah client, arah yang lebih aman tetap
  `--auth oauth` di komputernya sendiri (bagian 11.2): kunci penulis tidak perlu
  berpindah tangan.
