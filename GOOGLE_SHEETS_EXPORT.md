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
menunggu pemilik. Sejak 2026-09-28 program ini **diserahkan ke client** untuk
dijalankan di komputernya sendiri, bersama berkas kunci Google-nya; akses
database yang diserahkan tetap read-only. Rinciannya di bagian 11.

**Status: sudah dijalankan sungguhan.** Ekspor pertama berhasil ke spreadsheet
`Shadow DB` (`1kB02M_4asD38-7Qna6N9cSws5EHpP3VglXLw2nrHC0A`) pada 2026-09-28:
enam tab data terisi (sejak `transaction_daily_sequence` tidak lagi diekspor,
angkanya menjadi lima — lihat bagian 2), tab `Kontrol` dibuat beserta kotak
centangnya, tab bawaan `Sheet1` dihapus, header tebal dan dibekukan, dan kolom
uang berformat `Rp`. Lebar kolom sudah menyesuaikan isi (lihat bagian 3). Alur
tombol client juga sudah dicoba sungguhan: mengcentang `Kontrol!B3` membuat
pengawas mengosongkan kotak itu, menjalankan ekspor, lalu mengisi status,
waktu, dan ringkasan per tabel.

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
# GOOGLE_SERVICE_ACCOUNT_FILE=D:\DB-to-sheets\.secrets\service-account.json

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

Host yang berbasis jadwal (runner CI, cron, Task Scheduler) memanggil skripnya
langsung,
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
terulang terus), menulis status "Sedang memproses", menjalankan ekspor kelima
tab data, lalu menulis status, waktu, dan ringkasan baris. Kotak yang sudah kosong itu
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

Satu spreadsheet, enam tab:

```
transactions                    <- satu tab per tabel
transaction_detail
payment_proof
device
device_transaction_sequence
Kontrol                          <- tombol dan status permintaan
```

Tab bawaan `Sheet1` dihapus otomatis, tetapi hanya kalau memang masih kosong.
Tab `transaction_daily_sequence` dari ekspor-ekspor sebelumnya **tidak** ikut
terhapus — alat ini tidak pernah menghapus tab yang tidak ia kelola, supaya
catatan yang client tempelkan di sebuah tab tidak hilang tanpa sengaja. Kalau
tab itu masih ada, hapus sekali lewat menu klik kanan → *Delete* di Google
Sheets.

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
  itu batasi ke lima tabel di 11.1.

## 12. Menjalankan pengawas tanpa komputer siapa pun menyala

Tujuan bagian ini: permintaan client tetap dilayani tanpa **komputer mana pun
milik pengelola menyala**, dan tanpa kartu kredit.

Bagian ini tidak diperlukan kalau program sudah dijalankan di komputer client
sendiri (bagian 11) dan komputer itu memang hidup pada jam yang diinginkan.
Isinya untuk kondisi sebaliknya: tidak ada komputer yang boleh dibiarkan menyala.

Urutannya penting. Hampir semua platform yang menjalankan proses **selalu
nyala** gratis kini meminta metode pembayaran: Northflank (Sandbox gratis tapi
kartu wajib), Koyeb (sejak Februari 2026 kartu + otorisasi $29), Fly.io, Oracle
Cloud, Google Cloud, AWS. Yang benar-benar tidak meminta kartu justru platform
**terjadwal**, dan pengawas ini memang hanya perlu dipanggil berkala — ia hanya
*keluar* menghubungi Google dan Aiven, tidak pernah menerima permintaan dari
luar. Karena itu jalur utamanya adalah GitHub Actions (12.1).

**Jalur kontainer sudah dihapus** dari repo ini pada 2026-09-28. `Dockerfile`,
`.dockerignore`, dan langkah Northflank-nya dibuang karena tidak satu pun host
selalu-nyala gratis bisa dipakai tanpa kartu, sementara dua cara yang tersisa —
komputer client (bagian 11) dan GitHub Actions (12.1) — tidak membutuhkannya.
Kalau nanti kartu sudah siap, berkasnya masih bisa diambil dari riwayat git:

```bash
git log --oneline -- Dockerfile
git show <commit>:Dockerfile > Dockerfile
```

### 12.1 GitHub Actions: gratis, tanpa kartu, tanpa layanan baru

Dua berkas sudah disertakan di `.github/workflows/`:

| Berkas | Jadwal | Tugasnya |
| --- | --- | --- |
| `refresh-sheets.yml` | tiap 5 menit | memanggil `--if-requested` — melayani centangan di tab Kontrol |
| `keepalive.yml` | tgl 1 dan 15 | satu commit kosong, supaya GitHub tidak mematikan jadwalnya |

Yang perlu dilakukan sekali saja:

1. Buka repo di GitHub → **Settings** → **Secrets and variables** → **Actions**
   → **New repository secret**, lalu isi ketiganya:

   | Nama | Isi |
   | --- | --- |
   | `DATABASE_URL` | koneksi PostgreSQL, boleh pengguna read-only |
   | `GOOGLE_SPREADSHEET_ID` | ID atau link spreadsheet tujuan |
   | `GOOGLE_SERVICE_ACCOUNT_JSON` | seluruh isi `service-account.json`, ditempel apa adanya |

   Isi berkas kunci bisa dimasukkan ke clipboard tanpa tampil di layar:
   `Get-Content ".secrets\service-account.json" -Raw | Set-Clipboard` lalu tempel.
   Sesudahnya, bersihkan clipboard dengan menyalin teks lain.
2. Buka tab **Actions** → pilih **Ekspor ke Google Sheets** → **Run workflow**
   untuk mencobanya sekarang tanpa menunggu jadwal. Log yang benar berisi
   `Tidak ada permintaan baru di tab Kontrol.` beserta nama database dan
   spreadsheet — sama seperti mode sekali-jalan di komputer sendiri.
3. Centang `Kontrol!B3` dari mana saja, lalu tunggu satu putaran jadwal. Kolom
   status, waktu, dan ringkasan terisi seperti biasa.

### 12.2 Menjalankan mode terjadwal di host lain

Host terjadwal mana pun bisa memakai mode sekali-jalan: perintahnya
`--if-requested`, lalu diatur jadwalnya (mis. tiap 5 menit).

Bedanya dengan pengawas: prosesnya tidak menunggu, hanya bangun saat jadwalnya
tiba. Kalau kotaknya belum dicentang, skrip keluar tanpa menyentuh Google Sheets;
kalau dicentang, ekspor berjalan. Permintaan client dilayani dengan jeda sampai
satu interval, bukan di bawah satu menit.

```bash
python tools/export_to_google_sheets.py --if-requested
```

Mode inilah yang dipakai GitHub Actions di 12.1. Task Scheduler di komputer yang
menyala terus dan cron di VPS memakainya dengan cara yang sama; yang berbeda
hanya jadwalnya. Tidak ada berkas di repo ini yang perlu diubah untuk itu.

### 12.3 Batas yang perlu disadari

- **Jeda GitHub Actions 5-15 menit, bukan 60 detik.** Cron GitHub tidak menerima
  jadwal lebih rapat dari lima menit, dan saat servernya sibuk jadwalnya bisa
  terlambat. Untuk sebuah tombol "minta data terbaru" itu biasanya tidak masalah;
  kalau client butuh kesegaran detik, jawabannya pengawas `--watch` di komputer
  yang menyala terus (bagian 11.3).
- **Jadwal mati kalau repo 60 hari tanpa commit.** GitHub mematikan workflow
  terjadwal secara diam-diam di repo publik yang menganggur; itu yang dijaga
  `keepalive.yml`. Kalau ternyata commit bot tidak dihitung sebagai aktivitas,
  GitHub akan mengirim email dan tombol *Enable workflow* bisa diklik sekali lagi.
- **Menit gratis Actions tidak terbatas hanya selama repo ini publik.** Kalau repo
  dijadikan privat, jatahnya 2.000 menit/bulan — jadwal tiap 5 menit akan
  menghabiskannya, jadi ubah `cron` di `refresh-sheets.yml` menjadi tiap 30 menit
  (jatahnya jadi sekitar 480 menit sebulan).
- Paketnya **portabel**: kalau nanti berpindah host, yang berubah hanya cara ia
  dijalankan — cukup `python tools/export_to_google_sheets.py --watch` plus
  `systemd` atau Task Scheduler, atau mode terjadwal di 12.2. Kode dan
  kredensialnya tidak berubah.

### 12.4 Keamanan

- `GOOGLE_SERVICE_ACCOUNT_JSON` adalah **kredensial penulis** untuk setiap
  spreadsheet yang dibagikan ke service account itu. Simpan sebagai secret di
  GitHub (Settings → Secrets and variables → Actions), jangan pernah di repo.
- **Dua berkas di repo ini sengaja kosong (0 byte):** `.env` dan
  `.secrets/service-account.json`. Keduanya hanya penanda susunan berkas. Karena
  sudah terlacak git, `.gitignore` tidak lagi melindungi dua path itu — isi
  aslinya tinggal di komputer dan **tidak boleh** ditempel ke sana lalu di-commit;
  repo ini publik. Berkas kosong diperlakukan sebagai "belum diisi", jadi pesan
  galatnya tetap menjelaskan ke mana kuncinya harus diletakkan.
- Kalau nanti yang menjalankan pengawas adalah client, arah yang lebih aman tetap
  `--auth oauth` di komputernya sendiri (bagian 11.2): kunci penulis tidak perlu
  berpindah tangan.
