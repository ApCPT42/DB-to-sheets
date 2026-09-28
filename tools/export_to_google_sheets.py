"""Ekspor tabel dinamis POS ke satu Google Sheets: satu tab per tabel.

Kegunaan: pemilik database (Aiven) tidak selalu bisa memberi client akses
langsung ke console, sedangkan client butuh melihat data penjualan. Skrip ini
membaca tabel yang **ditulis backend** dari PostgreSQL lalu menyalin isinya ke
satu spreadsheet, masing-masing ke tabnya sendiri.

Aturan yang mengikat skrip ini:

- **Hanya baca database.** Tidak ada pernyataan INSERT/UPDATE/DELETE/DDL.
- **Hanya tabel dinamis.** `item` dan `worker` sengaja tidak ikut: keduanya
  referensi yang tidak berubah, dan `worker.pin` berisi hash kredensial.
- **Tulis ulang, bukan menambah.** Setiap kali dijalankan, isi setiap tab
  diganti dengan isi database saat itu, jadi skrip ini boleh dijalankan berapa
  kali pun tanpa menghasilkan baris kembar.
- **Tampilan dirapikan setiap kali menulis.** Nama kolom tebal dan dibekukan,
  kolom uang berformat `Rp`, lalu lebar kolom dipaskan ke isi. Autofit dijalankan
  paling akhir supaya teks `Rp` ikut terhitung, dan sesudahnya setiap kolom
  ditambah sedikit ruang supaya isinya tidak menempel garis kolom.
- **Kredensial tidak pernah dicetak.** `DATABASE_URL` memuat password; yang
  ditampilkan hanya host dan nama database.

Ada dua cara pakai, dan keduanya memakai kode yang sama. Pengawasnya sendiri
boleh berjalan di mesin pengelola, di komputer client, atau di host cloud —
selama ia bisa menjangkau database dan punya kredensial Google:

1. **Tombol di spreadsheet (bawaan).** Client tidak diberi kredensial apa pun.
   Mereka meminta data terbaru dengan **mencentang satu kotak di tab Kontrol**;
   pengawas (`--watch`) di mesin pengelola membaca kotak itu lalu menjalankan
   ekspor. Karena itu pengawas wajib berjalan di mesin yang punya `DATABASE_URL`
   dan kredensial Google, dan permintaan hanya dilayani selama mesin itu hidup.
2. **Client menjalankan sendiri.** Client diberi `DATABASE_URL` **read-only**
   (disetujui pemilik: isi database memang milik client) dan menjalankan skrip
   ini di komputernya sendiri. Untuk cara ini jangan pakai kunci service account:
   pakai `--auth oauth`, yaitu client masuk dengan **akun Google-nya sendiri**
   lewat peramban, sehingga tidak ada kunci penulis yang perlu diserahkan.

Cara masuk Google dipilih lewat `--auth` atau `GOOGLE_AUTH_MODE`:
`service-account` (bawaan, untuk mesin pengelola) atau `oauth` (untuk client).

Konfigurasi boleh datang dari berkas `.env` di akar repo ini, atau dari variabel
lingkungan kalau berkasnya tidak ada. Di host yang tidak nyaman menyimpan berkas
rahasia (kontainer, PaaS, cron cloud) isi kunci service account bisa diisi
langsung ke `GOOGLE_SERVICE_ACCOUNT_JSON`, sehingga tidak ada kunci yang perlu
ditulis ke disk.

Repo ini berdiri sendiri dan tidak membutuhkan aplikasi POS: yang diperlukan
hanya akses baca ke database dan kredensial Google. Jalankan lewat
`Export ke Google Sheets.bat`, atau langsung:

    venv\\Scripts\\python.exe tools\\export_to_google_sheets.py --check
    venv\\Scripts\\python.exe tools\\export_to_google_sheets.py --dry-run
    venv\\Scripts\\python.exe tools\\export_to_google_sheets.py
    venv\\Scripts\\python.exe tools\\export_to_google_sheets.py --watch
    venv\\Scripts\\python.exe tools\\export_to_google_sheets.py --if-requested
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import psycopg
from dotenv import load_dotenv

SCRIPT_VERSION = "2.1"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
ENV_FILE = PROJECT_DIR / ".env"

# Waktu ditampilkan dalam WIB (UTC+7). Offset tetap dipakai, bukan zona
# `Asia/Jakarta`, supaya tidak bergantung pada basis data zona waktu sistem
# (Windows tidak menyediakannya) dan tidak menambah dependensi.
WIB = timezone(timedelta(hours=7), "WIB")

# Tabel yang ditulis backend, beserta urutan baris yang stabil supaya hasil
# ekspor bisa dibandingkan antar-jalan.
#
# `item` dan `worker` TIDAK ada di sini dengan sengaja:
# - keduanya data referensi yang tidak berubah setiap hari;
# - `worker.pin` berisi hash bcrypt (kredensial), dan `item.cost_amount`
#   termasuk data terlarang menurut aturan repo.
TABLES: dict[str, str] = {
    "transactions": "transaction_time, transaction_id",
    "transaction_detail": "sync_id, item_name, variant",
    "payment_proof": "uploaded_at, proof_id",
    "device": "device_code",
    "device_transaction_sequence": "device_id",
    "transaction_daily_sequence": "transaction_date",
}

# --- Tab Kontrol: satu-satunya bagian yang disentuh client -------------------
CONTROL_TAB_TITLE = "Kontrol"
CONTROL_BUTTON_CELL = "B3"
CONTROL_STATUS_CELL = "B4"
CONTROL_UPDATED_CELL = "B5"
CONTROL_SUMMARY_CELL = "B6"

CONTROL_LAYOUT = [
    ["Kontrol ekspor data POS", "", ""],
    ["", "", ""],
    ["Minta data terbaru", "", "centang kotaknya, lalu tunggu"],
    ["Status terakhir", "(belum ada permintaan)", ""],
    ["Waktu permintaan diproses", "-", ""],
    ["Ringkasan data terakhir", "-", ""],
    ["", "", ""],
    ["Cara pakai", "", ""],
    ["1. Centang kotak di sel B3.", "", ""],
    ["2. Tunggu. Baris Status dan Waktu terisi sendiri, biasanya di bawah satu menit.", "", ""],
    ["3. Isi tab lain akan tergantikan dengan data terbaru dari database.", "", ""],
    ["", "", ""],
    ["Catatan", "", ""],
    [
        "Permintaan dilayani otomatis oleh pengawas ekspor. Kalau pengawasnya sedang tidak berjalan, centangan baru diproses setelah pengawas dinyalakan lagi.",
        "",
        "",
    ],
    ["Data diambil dari database pada saat permintaan dilayani, bukan salinan lama.", "", ""],
    ["", "", ""],
    ["Nama tab, satu untuk setiap tabel", "", ""],
]

# Sel petunjuk yang teksnya disegarkan setiap kali skrip dijalankan. Dengan
# begitu kalimat yang sudah tidak sesuai (mis. catatan soal komputer pemilik)
# bisa diperbaiki tanpa menghapus tab dan tanpa kehilangan isinya. Sel B3:B6
# sengaja TIDAK termasuk: di situlah kotak centang, status, waktu, dan
# ringkasan, sehingga tulisan ulang petunjuk tidak boleh menimpa permintaan
# client yang belum diproses.
CONTROL_NOTE_CELLS: dict[str, str] = {
    "A1": CONTROL_LAYOUT[0][0],
    "A3": CONTROL_LAYOUT[2][0],
    "C3": CONTROL_LAYOUT[2][2],
    "A4": CONTROL_LAYOUT[3][0],
    "A5": CONTROL_LAYOUT[4][0],
    "A6": CONTROL_LAYOUT[5][0],
    "A8": CONTROL_LAYOUT[7][0],
    "A9": CONTROL_LAYOUT[8][0],
    "A10": CONTROL_LAYOUT[9][0],
    "A11": CONTROL_LAYOUT[10][0],
    "A13": CONTROL_LAYOUT[12][0],
    "A14": CONTROL_LAYOUT[13][0],
    "A15": CONTROL_LAYOUT[14][0],
    "A17": CONTROL_LAYOUT[16][0],
}

# Nilai kotak centang yang dianggap BUKAN permintaan.
NOT_A_REQUEST = {"", "FALSE", "0", "0.0", "NO", "TIDAK", "-"}

DEFAULT_WATCH_INTERVAL_SECONDS = 60
MIN_WATCH_INTERVAL_SECONDS = 10

# Batas panjang judul spreadsheet dan nama tab di Google Sheets.
MAX_TITLE_LENGTH = 100
MAX_SHEET_NAME_LENGTH = 100

# Lokasi berkas service account yang dicoba berurutan bila
# `GOOGLE_SERVICE_ACCOUNT_FILE` tidak diisi.
CREDENTIAL_CANDIDATES = (
    PROJECT_DIR / ".secrets" / "service-account.json",
    Path.home() / ".pos-sheets" / "service-account.json",
)

# --- Cara masuk Google ------------------------------------------------------
# `service-account`: mesin memakai berkas kunci JSON. Dipakai di mesin pengelola.
# `oauth`: orang yang menjalankan skrip masuk memakai akun Google-nya sendiri
# lewat peramban, sekali saja, lalu tokennya disimpan. Dipakai kalau client
# menjalankan ekspor sendiri: tidak ada kunci penulis yang berpindah tangan, dan
# spreadsheet yang sudah ia miliki otomatis bisa dipakai.
AUTH_SERVICE_ACCOUNT = "service-account"
AUTH_OAUTH = "oauth"

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Berkas client-secret OAuth (jenis "Desktop app") dan berkas token hasil login.
# Keduanya hanya dipakai pada mode `oauth`.
OAUTH_CLIENT_CANDIDATES = (
    PROJECT_DIR / ".secrets" / "oauth-client.json",
    Path.home() / ".pos-sheets" / "oauth-client.json",
)

DEFAULT_OAUTH_TOKEN_PATH = PROJECT_DIR / ".secrets" / "oauth-token.json"

# Format angka. Google Sheets memakai sintaks pola sendiri; "Rp" dalam tanda
# kutip diperlakukan sebagai teks, sehingga tampil sebagai Rp 141.000.
MONEY_PATTERN = '"Rp" #,##0'
NUMBER_PATTERN = "#,##0"

MONEY_COLUMNS = {
    "total_amount",
    "payment_amount",
    "change_amount",
    "item_amount",
    "shipping_amount",
    "unit_price",
    "subtotal",
    "discount",
}

NUMBER_COLUMNS = {"quantity", "byte_size", "next_sequence", "last_sequence"}

# Ukuran grid minimum tiap tab. Google menolak membekukan baris kalau seluruh
# baris yang terlihat dibekukan, dan itu terjadi pada tabel yang sedang kosong
# (mis. transaction_daily_sequence dengan nol baris). Grid yang lega juga
# membuat tab tetap enak dipakai walau datanya sedikit.
MIN_GRID_ROWS = 20
MIN_GRID_COLS = 4

# Lebar kolom: setelah Google menghitung lebar pas untuk isi kolom, tiap kolom
# ditambah sedikit ruang supaya huruf terakhir tidak menempel garis kolom.
# Kolom yang sudah lebar (mis. kolom catatan) dibiarkan apa adanya.
COLUMN_PADDING_PIXELS = 18
MAX_PADDED_WIDTH_PIXELS = 220

HEADER_FORMAT = {
    "textFormat": {"bold": True, "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}},
    "backgroundColor": {"red": 0.20, "green": 0.22, "blue": 0.26},
}


class ExportError(Exception):
    """Kesalahan yang pesannya sudah ditujukan untuk pemilik POS."""


def timestamp() -> str:
    return datetime.now(WIB).strftime("%Y-%m-%d %H:%M:%S WIB")


def log(message: str) -> None:
    # `flush` supaya keluaran pengawas langsung terlihat di berkas log saat ia
    # dijalankan sebagai layanan: tanpa itu Python menahannya sampai penyangga
    # penuh, dan log yang dihentikan mendadak jadi kosong.
    print(f"[{timestamp()}] {message}", flush=True)


# --------------------------------------------------------------------------
# Konfigurasi
# --------------------------------------------------------------------------


def environment_file() -> Path:
    """Berkas .env yang dibaca: bawaan `.env` di akar repo ini.

    Bisa diarahkan ke lokasi lain lewat `EXPORT_ENV_FILE`, mis. kalau konfigurasi
    diletakkan di luar folder repo.
    """
    explicit = os.environ.get("EXPORT_ENV_FILE", "").strip()

    return Path(explicit).expanduser() if explicit else ENV_FILE


def load_environment() -> None:
    """Muat berkas .env kalau ada.

    Di host yang mengisi konfigurasi lewat variabel lingkungan (kontainer, PaaS,
    cron cloud) berkas itu memang tidak ada, jadi ketiadaannya bukan kesalahan.
    """
    path = environment_file()

    if not path.is_file():
        log(f"Berkas {path} tidak ada - memakai variabel lingkungan yang sudah diisi.")
        return

    load_dotenv(path)


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()

    if not url:
        raise ExportError(
            "DATABASE_URL kosong di .env.\n"
            "  Isi dengan koneksi PostgreSQL yang sama seperti dipakai backend."
        )

    return url


def describe_database(url: str) -> str:
    """Host dan nama database saja — tanpa pengguna, tanpa password."""
    parsed = urlparse(url)

    return f"{parsed.hostname or '?'}:{parsed.port or '?'}/{parsed.path.lstrip('/') or '?'}"


def credentials_path() -> Path:
    explicit = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()

    if explicit:
        path = Path(explicit).expanduser()

        if not path.is_file():
            raise ExportError(
                f"GOOGLE_SERVICE_ACCOUNT_FILE menunjuk ke berkas yang tidak ada:\n  {path}"
            )

        return path

    for candidate in CREDENTIAL_CANDIDATES:
        if candidate.is_file():
            return candidate

    dicoba = "\n".join(f"  - {path}" for path in CREDENTIAL_CANDIDATES)

    raise ExportError(
        "Berkas service account Google tidak ditemukan. Dicari di:\n"
        f"{dicoba}\n"
        "  Cara membuatnya ada di GOOGLE_SHEETS_EXPORT.md, langkah 1-3.\n"
        "  Setelah berkasnya ada, letakkan di salah satu lokasi di atas, atau\n"
        "  isi GOOGLE_SERVICE_ACCOUNT_FILE di .env dengan path lengkapnya."
    )


def read_service_account_email(path: Path) -> str:
    """Email service account dari berkas JSON; dipakai untuk pesan bantuan saja."""
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise ExportError(
            f"Berkas service account tidak bisa dibaca sebagai JSON: {path}\n  {error}"
        ) from error

    email = data.get("client_email")

    if not email:
        raise ExportError(
            f"Berkas {path} tidak memuat `client_email`. Pastikan itu kunci JSON\n"
            "  dari service account, bukan jenis kredensial lain."
        )

    return str(email)


def service_account_info_from_env() -> dict[str, Any] | None:
    """Isi kunci service account dari variabel lingkungan, kalau ada.

    Dipakai host yang tidak menyimpan berkas rahasia: platform menyuntikkan isi
    JSON-nya sebagai `GOOGLE_SERVICE_ACCOUNT_JSON`. Mengembalikan `None` bila
    variabelnya kosong, sehingga jalur berkas tetap dipakai seperti biasa.
    """
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()

    if not raw:
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ExportError(
            "GOOGLE_SERVICE_ACCOUNT_JSON tidak bisa dibaca sebagai JSON.\n"
            f"  {error}"
        ) from error

    if not isinstance(data, dict):
        raise ExportError("GOOGLE_SERVICE_ACCOUNT_JSON harus berupa objek JSON.")

    if not data.get("client_email"):
        raise ExportError(
            "GOOGLE_SERVICE_ACCOUNT_JSON tidak memuat `client_email`.\n"
            "  Pastikan isinya kunci JSON service account, bukan jenis kredensial lain."
        )

    return data


def auth_mode(override: str | None = None) -> str:
    """Cara masuk Google: dari argumen `--auth`, atau `GOOGLE_AUTH_MODE`, atau bawaan."""
    raw = (override or os.environ.get("GOOGLE_AUTH_MODE", "")).strip().lower()

    if not raw:
        return AUTH_SERVICE_ACCOUNT

    pilihan = {
        "service-account": AUTH_SERVICE_ACCOUNT,
        "service_account": AUTH_SERVICE_ACCOUNT,
        "kunci": AUTH_SERVICE_ACCOUNT,
        "oauth": AUTH_OAUTH,
        "google": AUTH_OAUTH,
        "akun": AUTH_OAUTH,
    }

    if raw not in pilihan:
        raise ExportError(
            f"Cara masuk Google \"{raw}\" tidak dikenal.\n"
            f"  Pilihan yang ada: {AUTH_SERVICE_ACCOUNT} atau {AUTH_OAUTH}."
        )

    return pilihan[raw]


def oauth_client_path() -> Path:
    """Berkas client-secret OAuth milik pemilik project Google Cloud."""
    explicit = os.environ.get("GOOGLE_OAUTH_CLIENT_FILE", "").strip()

    if explicit:
        path = Path(explicit).expanduser()

        if not path.is_file():
            raise ExportError(
                f"GOOGLE_OAUTH_CLIENT_FILE menunjuk ke berkas yang tidak ada:\n  {path}"
            )

        return path

    for candidate in OAUTH_CLIENT_CANDIDATES:
        if candidate.is_file():
            return candidate

    dicoba = "\n".join(f"  - {path}" for path in OAUTH_CLIENT_CANDIDATES)

    raise ExportError(
        "Berkas client-secret OAuth tidak ditemukan. Dicari di:\n"
        f"{dicoba}\n"
        "  Berkas itu yang membuat peramban bisa meminta izin akun Google.\n"
        "  Cara membuatnya ada di GOOGLE_SHEETS_EXPORT.md, bagian "
        "\"Mode client\".\n"
        "  Kalau Anda memakai kunci service account, jalankan tanpa `--auth oauth`."
    )


def oauth_token_path() -> Path:
    explicit = os.environ.get("GOOGLE_OAUTH_TOKEN_FILE", "").strip()

    return Path(explicit).expanduser() if explicit else DEFAULT_OAUTH_TOKEN_PATH


def oauth_login_state() -> str:
    token = oauth_token_path()

    if token.is_file():
        return f"sudah pernah masuk, token di {token}"

    return "belum pernah masuk: peramban akan terbuka sekali untuk minta izin"


def credentials_source(path: Path | None) -> str:
    """Keterangan untuk log: kredensial datang dari berkas atau dari variabel."""
    return str(path) if path else "GOOGLE_SERVICE_ACCOUNT_JSON (variabel lingkungan)"


def google_credentials(override: str | None = None) -> tuple[str, Path | None, str]:
    """Siapkan cara masuk Google: (mode, berkas kredensial, identitas untuk log).

    Berkasnya bernilai `None` kalau kuncinya datang sebagai isi variabel
    lingkungan.
    """
    mode = auth_mode(override)

    if mode == AUTH_OAUTH:
        return mode, oauth_client_path(), "akun Google Anda sendiri"

    info = service_account_info_from_env()

    if info is not None:
        return mode, None, str(info["client_email"])

    path = credentials_path()

    return mode, path, read_service_account_email(path)


def spreadsheet_id_from_env() -> str | None:
    """Terima ID spreadsheet mentah maupun URL lengkapnya."""
    raw = os.environ.get("GOOGLE_SPREADSHEET_ID", "").strip()

    if not raw:
        return None

    if "docs.google.com" in raw:
        potongan = [bagian for bagian in urlparse(raw).path.split("/") if bagian]

        if "d" in potongan:
            index = potongan.index("d")

            if index + 1 < len(potongan):
                return potongan[index + 1]

        raise ExportError(
            "Link spreadsheet itu tidak memuat ID.\n"
            "  Format yang dikenali: https://docs.google.com/spreadsheets/d/<ID>/edit"
        )

    return raw


def spreadsheet_title_from_env() -> str | None:
    raw = os.environ.get("GOOGLE_SPREADSHEET_TITLE", "").strip()

    return raw or None


def share_with_from_env() -> list[str]:
    raw = os.environ.get("GOOGLE_SHEETS_SHARE_WITH", "")

    return [email.strip() for email in raw.split(",") if email.strip()]


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------


def read_table(
    connection: psycopg.Connection, table: str, order_by: str
) -> tuple[list[str], list[list[Any]]]:
    """Baca seluruh baris satu tabel. `select *` mengikuti urutan kolom asli tabel."""
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT * FROM "{table}" ORDER BY {order_by}')

        columns = [description.name for description in cursor.description]
        rows = [[normalize(value) for value in row] for row in cursor.fetchall()]

    return columns, rows


def normalize(value: Any) -> Any:
    """Ubah nilai PostgreSQL menjadi tipe yang bisa dikirim ke Sheets.

    `None` menjadi sel kosong, bukan teks "None" — sel kosong dan teks "None"
    terlihat berbeda bagi pembaca, dan yang kedua salah.
    """
    if value is None:
        return ""

    if isinstance(value, datetime):
        return value.astimezone(WIB).strftime("%Y-%m-%d %H:%M:%S")

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, (int, float, str, bool)):
        return value

    return str(value)


# --------------------------------------------------------------------------
# Google
# --------------------------------------------------------------------------


def disabled_api_hint(teks: str) -> str | None:
    """Kenali balasan "API belum diaktifkan" dan susun instruksinya.

    Google menyertakan tautan aktivasi langsung di dalam pesannya; tautan itu
    dipakai apa adanya supaya pemilik tidak perlu mencari sendiri di console.
    """
    if not (
        "has not been used in project" in teks
        or "SERVICE_DISABLED" in teks
        or "accessNotConfigured" in teks
    ):
        return None

    # Tautan diambil dengan pola, bukan dengan memotong spasi: pesan Google
    # kadang memuat potongan tautan yang lebih pendek, dan itu bukan alamat
    # yang bisa diklik.
    tautan = list(dict.fromkeys(re.findall(r"https://console[\w./?=&%#+-]+", teks)))
    tautan = [
        alamat
        for alamat in tautan
        if not any(alamat != lain and lain.startswith(alamat) for lain in tautan)
    ]

    baris = [
        "API Google-nya belum diaktifkan di project tempat service account dibuat.",
        "Aktifkan di console.cloud.google.com > APIs & Services > Library:",
    ]

    # Nama API diambil dari tautan yang dikirim Google, jadi yang dicetak hanya
    # API yang memang belum aktif.
    if not tautan or any("sheets.googleapis.com" in alamat for alamat in tautan):
        baris.append("  - Google Sheets API")

    if not tautan or any("drive.googleapis.com" in alamat for alamat in tautan):
        baris.append("  - Google Drive API")

    for alamat in tautan[:2]:
        baris.append(f"  {alamat}")

    baris.append("Setelah diaktifkan, tunggu beberapa menit lalu jalankan lagi.")

    return "\n".join(baris)


def translate_google_error(
    error: Exception, identitas: str, spreadsheet_id: str | None
) -> ExportError:
    """Ubah balasan Google menjadi instruksi yang bisa ditindaklanjuti."""
    teks = str(error)
    petunjuk_api = disabled_api_hint(teks)

    if petunjuk_api:
        return ExportError(petunjuk_api)

    if "insufficientFilePermissions" in teks or "The caller does not have permission" in teks:
        return ExportError(
            "Akses ditolak: spreadsheet tujuan belum boleh dipakai oleh\n"
            f"    {identitas}\n"
            "  Bagikan spreadsheet itu dengan peran Editor, atau masuk memakai\n"
            "  akun Google yang sudah punya akses ke sana."
        )

    if "File not found" in teks or "notFound" in teks or "Unable to parse range" in teks:
        return ExportError(
            "Spreadsheet tujuan tidak ditemukan.\n"
            f"    ID: {spreadsheet_id or '(kosong)'}\n"
            f"  Pastikan ID-nya benar dan sudah dibagikan ke {identitas}\n"
            "  sebagai Editor."
        )

    if "Quota exceeded" in teks or "RATE_LIMIT_EXCEEDED" in teks:
        return ExportError(
            "Kuota Google Sheets API sedang tercapai. Tunggu sekitar satu menit\n"
            "  lalu jalankan ulang; setiap tab ditulis dalam satu permintaan sehingga\n"
            "  tidak ada tab yang setengah terisi."
        )

    return ExportError(f"Google menolak permintaan: {teks}")


def build_client(mode: str, path: Path | None = None):
    try:
        import gspread
    except ImportError as error:  # pragma: no cover - hanya bila dependensi hilang
        raise ExportError(
            "Paket `gspread`/`google-auth` belum terpasang di venv.\n"
            "  Jalankan: venv\\Scripts\\python.exe -m pip install -r "
            "tools\\requirements-export.txt"
        ) from error

    if mode == AUTH_OAUTH:
        try:
            # Login akun pribadi: token disimpan setelah sekali masuk, dan
            # sesudah itu tidak ada peramban yang terbuka lagi.
            return gspread.oauth(
                scopes=GOOGLE_SCOPES,
                credentials_filename=str(path),
                authorized_user_filename=str(oauth_token_path()),
            )
        except Exception as error:  # pragma: no cover - izin/peramban gagal
            raise ExportError(
                f"Gagal masuk dengan akun Google lewat {path}:\n  {error}\n"
                "  Saat pertama kali, jalankan ini dari komputer yang ada "
                "perambannya:\n"
                "  Google akan membuka jendela persetujuan sekali saja."
            ) from error

    try:
        from google.oauth2.service_account import Credentials
    except ImportError as error:  # pragma: no cover - hanya bila dependensi hilang
        raise ExportError(
            "Paket `google-auth` belum terpasang di venv.\n"
            "  Jalankan: venv\\Scripts\\python.exe -m pip install -r "
            "tools\\requirements-export.txt"
        ) from error

    try:
        info = service_account_info_from_env()

        if info is not None:
            # Kunci dari variabel lingkungan tidak butuh berkas sama sekali, jadi
            # tidak ada rahasia yang perlu ditulis ke disk host.
            credentials = Credentials.from_service_account_info(info, scopes=GOOGLE_SCOPES)
        else:
            credentials = Credentials.from_service_account_file(str(path), scopes=GOOGLE_SCOPES)

        return gspread.authorize(credentials)
    except Exception as error:  # pragma: no cover - kredensial tidak sah
        raise ExportError(
            f"Gagal masuk ke Google memakai {credentials_source(path)}:\n  {error}"
        ) from error


def open_spreadsheet(client, identitas: str):
    """Buka spreadsheet tujuan lewat ID, atau lewat judul bila ID tidak diisi."""
    spreadsheet_id = spreadsheet_id_from_env()

    if spreadsheet_id:
        try:
            return client.open_by_key(spreadsheet_id)
        except Exception as error:
            raise translate_google_error(error, identitas, spreadsheet_id) from error

    judul = spreadsheet_title_from_env()

    if not judul:
        raise ExportError(
            "Spreadsheet tujuan belum ditentukan.\n"
            "  Tambahkan satu baris di .env:\n"
            "    GOOGLE_SPREADSHEET_ID=<ID atau link spreadsheet>\n"
            "  Opsional, sebagai gantinya: GOOGLE_SPREADSHEET_TITLE=<judul>"
        )

    try:
        kandidat = client.list_spreadsheet_files(title=judul, folder_id=None)
    except Exception as error:
        raise translate_google_error(error, identitas, None) from error

    if not kandidat:
        raise ExportError(
            f"Tidak ada spreadsheet berjudul \"{judul}\" yang bisa dilihat {identitas}.\n"
            f"  Bagikan spreadsheet itu dengan peran Editor, atau isi\n"
            "  GOOGLE_SPREADSHEET_ID dengan ID-nya (lebih pasti daripada judul)."
        )

    if len(kandidat) > 1:
        daftar = "\n".join(f"    - {item['name']} ({item['id']})" for item in kandidat)

        raise ExportError(
            f"Ada {len(kandidat)} spreadsheet berjudul \"{judul}\". Pakai ID supaya pasti:\n"
            f"{daftar}\n"
            "  Isi GOOGLE_SPREADSHEET_ID dengan salah satu ID di atas."
        )

    return client.open_by_key(kandidat[0]["id"])


def get_or_create_worksheet(spreadsheet, title: str, min_rows: int, min_cols: int):
    try:
        return spreadsheet.worksheet(title)
    except Exception:
        return spreadsheet.add_worksheet(
            title=title[:MAX_SHEET_NAME_LENGTH],
            rows=max(min_rows, 100),
            cols=max(min_cols, 8),
        )


def styling_requests(sheet_id: int, columns: list[str], row_count: int) -> list[dict[str, Any]]:
    """Permintaan batch: header, bekukan baris pertama, lebar kolom, format angka."""
    requests: list[dict[str, Any]] = [
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                "cell": {"userEnteredFormat": HEADER_FORMAT},
                "fields": "userEnteredFormat.textFormat,userEnteredFormat.backgroundColor",
            }
        },
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
                "fields": "gridProperties.frozenRowCount",
            }
        },
    ]

    # Format angka hanya menyentuh baris data, supaya judul kolom tetap teks.
    if row_count > 0:
        for index, kolom in enumerate(columns):
            if kolom in MONEY_COLUMNS:
                pola = MONEY_PATTERN
            elif kolom in NUMBER_COLUMNS:
                pola = NUMBER_PATTERN
            else:
                continue

            requests.append(
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 1,
                            "startColumnIndex": index,
                            "endColumnIndex": index + 1,
                        },
                        "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": pola}}},
                        "fields": "userEnteredFormat.numberFormat",
                    }
                }
            )

    # Autofit diletakkan **paling akhir**: Google menghitung lebar berdasarkan
    # teks yang tampil, dan teks kolom uang baru punya awalan "Rp" setelah
    # format angka di atas dipasang. Kalau autofit dijalankan lebih dulu, kolom
    # uang bisa terhitung sempit (hanya angka mentahnya) lalu terpotong.
    requests.append(
        {
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": len(columns),
                }
            }
        }
    )

    return requests


def write_tab(spreadsheet, table: str, columns: list[str], rows: list[list[Any]]) -> str:
    """Ganti seluruh isi satu tab: header + data, lalu rapikan tampilannya."""
    worksheet = get_or_create_worksheet(
        spreadsheet, table, min_rows=len(rows) + 1, min_cols=len(columns)
    )

    if worksheet.title != table[:MAX_SHEET_NAME_LENGTH]:
        worksheet.update_title(table[:MAX_SHEET_NAME_LENGTH])

    # Dibersihkan dulu supaya kalau isi lama lebih panjang, sisa barisnya tidak
    # tertinggal di bawah data baru.
    worksheet.clear()
    worksheet.resize(
        rows=max(len(rows) + 1, MIN_GRID_ROWS),
        cols=max(len(columns), MIN_GRID_COLS),
    )

    # Satu panggilan untuk header dan seluruh data: tidak ada keadaan setengah
    # jadi kalau jaringan putus di tengah jalan.
    worksheet.update([columns, *rows], "A1")

    spreadsheet.batch_update({"requests": styling_requests(worksheet.id, columns, len(rows))})
    pad_columns(spreadsheet, worksheet, len(columns))

    return worksheet.title


def pad_columns(spreadsheet, worksheet, column_count: int) -> None:
    """Tambah sedikit ruang pada kolom sesudah autofit.

    Langkah ini murni kosmetik: kalau pembacaan lebar gagal, tab tetap terpakai
    dengan hasil autofit saja, jadi kegagalannya hanya dicatat sebagai catatan.
    """
    try:
        # `columnMetadata` hanya ikut terkirim kalau diminta lewat `fields`;
        # tanpa itu Google menjawab tanpa data lebar kolom sama sekali.
        metadata = spreadsheet.fetch_sheet_metadata(
            {"fields": "sheets(properties.sheetId,data.columnMetadata)"}
        )
    except Exception as error:
        log(f"  Catatan: lebar kolom tidak bisa ditambah sedikit: {error}")
        return

    for sheet in metadata.get("sheets", []):
        if sheet.get("properties", {}).get("sheetId") != worksheet.id:
            continue

        blok = (sheet.get("data") or [{}])[0]
        dimensi = blok.get("columnMetadata") or []
        permintaan: list[dict[str, Any]] = []

        for index in range(min(column_count, len(dimensi))):
            lebar = dimensi[index].get("pixelSize")

            if not lebar or lebar >= MAX_PADDED_WIDTH_PIXELS:
                continue

            permintaan.append(
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": worksheet.id,
                            "dimension": "COLUMNS",
                            "startIndex": index,
                            "endIndex": index + 1,
                        },
                        "properties": {"pixelSize": lebar + COLUMN_PADDING_PIXELS},
                        "fields": "pixelSize",
                    }
                }
            )

        if permintaan:
            try:
                spreadsheet.batch_update({"requests": permintaan})
            except Exception as error:
                log(f"  Catatan: lebar kolom tab {worksheet.title} dibiarkan apa adanya: {error}")

        return


def is_request(value: str) -> bool:
    """Kotak centang bernilai TRUE saat dicentang; teks apa pun juga dianggap permintaan."""
    return (value or "").strip().upper() not in NOT_A_REQUEST


def cell_value(worksheet, cell: str) -> str:
    try:
        nilai = worksheet.acell(cell).value
    except Exception:
        return ""

    return "" if nilai is None else str(nilai).strip()


def write_cells(worksheet, values: dict[str, str]) -> None:
    for cell, value in values.items():
        try:
            worksheet.update_acell(cell, value)
        except Exception as error:
            log(f"  GAGAL menulis {cell}: {error}")


def ensure_control_tab(spreadsheet, tables: dict[str, str]):
    """Siapkan tab Kontrol beserta tombol kotak centangnya.

    Petunjuknya hanya ditulis saat tab baru dibuat, tetapi tombol dan
    perapiannya selalu dipasang ulang. Dengan begitu tab yang sudah ada tetap
    bisa diperbaiki tanpa menghapus isinya dan tanpa membuat ulang tabnya.
    """
    created = False

    try:
        worksheet = spreadsheet.worksheet(CONTROL_TAB_TITLE)
    except Exception:
        worksheet = spreadsheet.add_worksheet(
            title=CONTROL_TAB_TITLE, rows=len(CONTROL_LAYOUT) + len(tables), cols=3
        )
        created = True

    if created:
        layout = [baris[:] for baris in CONTROL_LAYOUT]

        for nama in tables:
            layout.append([nama, "", ""])

        worksheet.update(layout, "A1")
        log(f"Tab Kontrol dibuat di spreadsheet \"{spreadsheet.title}\".")
    else:
        refresh_control_notes(worksheet)

    try:
        from gspread.utils import ValidationConditionType

        # Kotak centang: TRUE berarti client meminta data terbaru. Tipe kondisinya
        # wajib berupa anggota enum gspread, bukan string "BOOLEAN".
        worksheet.add_validation(
            CONTROL_BUTTON_CELL,
            ValidationConditionType.boolean,
            [],
            strict=False,
            inputMessage="Centang untuk meminta data terbaru dari database.",
        )
        worksheet.format("A1", {"textFormat": {"bold": True, "fontSize": 14}})
        worksheet.format("A3:B5", {"textFormat": {"bold": True}})
        worksheet.format("A9:A11", {"textFormat": {"italic": True}})
        worksheet.format("A14:A15", {"textFormat": {"italic": True}})
        worksheet.freeze(rows=1)
        worksheet.columns_auto_resize(0, 2)
    except Exception as error:
        log(f"  Catatan: sebagian tampilan tab Kontrol tidak bisa dirapikan: {error}")

    return worksheet


def refresh_control_notes(worksheet) -> None:
    """Tulis ulang kalimat petunjuk di tab Kontrol tanpa menyentuh statusnya."""
    nilai = [
        {"range": sel, "values": [[teks]]} for sel, teks in CONTROL_NOTE_CELLS.items()
    ]

    try:
        worksheet.batch_update(nilai)
    except Exception as error:
        log(f"  Catatan: petunjuk tab Kontrol tidak bisa disegarkan: {error}")


def remove_default_empty_tab(spreadsheet) -> None:
    """Buang tab `Sheet1` bawaan Google kalau memang belum pernah diisi."""
    try:
        worksheet = spreadsheet.worksheet("Sheet1")
    except Exception:
        return

    try:
        if worksheet.get_all_values():
            return

        spreadsheet.del_worksheet(worksheet)
        log('Tab kosong "Sheet1" dihapus.')
    except Exception as error:
        log(f"  Catatan: tab Sheet1 tidak bisa dihapus: {error}")


def share_spreadsheet(spreadsheet, log_prefix: str = "  ") -> None:
    for alamat in share_with_from_env():
        try:
            spreadsheet.share(alamat, perm_type="user", role="writer", notify=False)
            log(f"{log_prefix}spreadsheet dibagikan ke {alamat} sebagai Editor")
        except Exception as error:
            log(f"{log_prefix}GAGAL membagikan ke {alamat}: {error}")


# --------------------------------------------------------------------------
# Ekspor
# --------------------------------------------------------------------------


def export_tables(
    connection,
    spreadsheet,
    tables: dict[str, str],
    identitas: str,
):
    """Tulis ulang setiap tab. Mengembalikan ringkasan per tabel.

    Satu tab yang gagal tidak menghentikan tab berikutnya: data yang bisa
    diselamatkan tetap dituliskan, lalu di akhir seluruh kegagalan dilaporkan
    sekaligus. Pelaporannya tetap membuat kode keluar bukan nol supaya pengawas
    menuliskannya sebagai permintaan yang gagal.
    """
    ringkasan: list[tuple[str, int, int, str]] = []
    kegagalan: list[str] = []

    for table, order_by in tables.items():
        columns, rows = read_table(connection, table, order_by)

        try:
            write_tab(spreadsheet, table, columns, rows)
        except Exception as error:
            if not isinstance(error, ExportError):
                error = translate_google_error(error, identitas, spreadsheet_id_from_env())

            pesan = str(error).splitlines()[0]
            log(f"  {table}: GAGAL - {pesan}")
            kegagalan.append(f"{table}: {pesan}")
            continue

        ringkasan.append((table, len(columns), len(rows), spreadsheet.url))
        log(f"  {table}: {len(rows)} baris, {len(columns)} kolom -> tab \"{table}\"")

    if kegagalan:
        rincian = "\n".join(f"  - {baris}" for baris in kegagalan)

        raise ExportError(
            f"{len(kegagalan)} dari {len(tables)} tab gagal diperbarui:\n{rincian}"
        )

    return ringkasan


def print_summary(ringkasan: list[tuple[str, int, int, str]], dry_run: bool) -> None:
    print()
    print("Ringkasan")
    print(f"{'Tabel (tab)':<32}{'Kolom':>7}{'Baris':>8}")
    for table, kolom, baris, _ in ringkasan:
        print(f"{table:<32}{kolom:>7}{baris:>8}")

    if not dry_run and ringkasan:
        print(f"\nSpreadsheet: {ringkasan[0][3]}")

    if dry_run:
        print("\nDry run selesai: tidak ada tab yang dibuat atau diubah.")
    else:
        print("\nEkspor selesai. Isi setiap tab sudah diganti dengan data terbaru.")


def check_database_access(url: str) -> None:
    """Buktikan `DATABASE_URL` bisa menyambung, lalu laporkan hak aksesnya.

    Dua hal yang diperiksa: pengguna database memang bisa membaca keenam tabel
    (mode client memakai pengguna read-only yang berbeda dari pengguna backend),
    dan pengguna itu tidak punya hak tulis ke tabel ekspor.
    """
    try:
        with psycopg.connect(url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "select c.relname,"
                    " has_table_privilege(current_user, c.oid, 'SELECT'),"
                    " has_table_privilege(current_user, c.oid, 'INSERT'),"
                    " has_table_privilege(current_user, c.oid, 'UPDATE'),"
                    " has_table_privilege(current_user, c.oid, 'DELETE')"
                    " from pg_class c"
                    " join pg_namespace n on n.oid = c.relnamespace"
                    " where n.nspname = 'public' and c.relkind = 'r'"
                    " and c.relname = any(%s)"
                    " order by c.relname",
                    (list(TABLES),),
                )
                hak = {baris[0]: baris[1:] for baris in cursor.fetchall()}

                cursor.execute("select current_user")
                pengguna = cursor.fetchone()[0]
    except Exception as error:
        raise ExportError(
            "Database tidak bisa dihubungi memakai DATABASE_URL di .env.\n"
            f"  {error}"
        ) from error

    log(f"Pengguna database      : {pengguna}")

    hilang = [nama for nama in TABLES if nama not in hak]

    if hilang:
        raise ExportError(
            "Pengguna database tidak bisa melihat tabel berikut:\n"
            + "\n".join(f"  - {nama}" for nama in hilang)
            + "\n  Minta pemilik database memberi hak baca ke pengguna ini."
        )

    tanpa_baca = [nama for nama, (baca, _, _, _) in hak.items() if not baca]

    if tanpa_baca:
        raise ExportError(
            "Pengguna database belum punya hak baca (SELECT) ke tabel:\n"
            + "\n".join(f"  - {nama}" for nama in tanpa_baca)
        )

    bisa_tulis = [
        nama for nama, (_, tambah, ubah, hapus) in hak.items() if tambah or ubah or hapus
    ]

    if bisa_tulis:
        log(f"PERINGATAN             : pengguna ini bisa MENULIS ke {', '.join(bisa_tulis)}.")
        log(
            "                         Mode client sebaiknya memakai pengguna read-only, "
            "supaya alat ini tidak mungkin mengubah data POS."
        )
    else:
        log("Hak tulis              : tidak ada (read-only) - sesuai untuk client")


def run_check(auth_override: str | None = None) -> int:
    url = database_url()
    mode, path, identitas = google_credentials(auth_override)

    log(f"Cara masuk Google      : {mode}")
    log(f"Sumber kredensial      : {credentials_source(path)}")
    log(f"Mesin Google           : {identitas}")

    if mode == AUTH_OAUTH:
        log(f"Status login           : {oauth_login_state()}")

    log(f"Database               : {describe_database(url)}")

    check_database_access(url)

    client = build_client(mode, path)
    spreadsheet = open_spreadsheet(client, identitas)

    log(f"Spreadsheet            : {spreadsheet.title} ({spreadsheet.id})")
    log(f"Tautan                 : {spreadsheet.url}")

    tab = [worksheet.title for worksheet in spreadsheet.worksheets()]
    log(f"Tab yang ada           : {', '.join(tab)}")

    kurang = [nama for nama in TABLES if nama not in tab]
    log(f"Tab yang belum ada     : {', '.join(kurang) if kurang else '(tidak ada)'}")
    log("Pemeriksaan selesai: kredensial, database, dan spreadsheet siap.")

    return 0


def run_export(dry_run: bool, only: str | None, auth_override: str | None = None) -> int:
    url = database_url()
    tables = selected_tables(only)

    log(f"Database: {describe_database(url)}")

    if dry_run:
        log("Mode DRY RUN: database dibaca, Google Sheets tidak disentuh.")

        ringkasan: list[tuple[str, int, int, str]] = []

        with psycopg.connect(url) as connection:
            for table, order_by in tables.items():
                columns, rows = read_table(connection, table, order_by)
                log(f"  {table}: {len(rows)} baris, {len(columns)} kolom -> tab \"{table}\"")
                log(f"    kolom : {', '.join(columns)}")

                for baris in rows[:2]:
                    log(f"    contoh: {baris}")

                ringkasan.append((table, len(columns), len(rows), "(dry run)"))

        print_summary(ringkasan, dry_run=True)

        return 0

    mode, path, identitas = google_credentials(auth_override)
    client = build_client(mode, path)
    spreadsheet = open_spreadsheet(client, identitas)

    log(f"Spreadsheet: {spreadsheet.title} ({spreadsheet.id})")

    if mode == AUTH_SERVICE_ACCOUNT:
        share_spreadsheet(spreadsheet)

    with psycopg.connect(url) as connection:
        ringkasan = export_tables(connection, spreadsheet, tables, identitas)

    ensure_control_tab(spreadsheet, tables)
    remove_default_empty_tab(spreadsheet)

    print_summary(ringkasan, dry_run=False)

    return 0


# --------------------------------------------------------------------------
# Pengawas: tombol permintaan untuk client
# --------------------------------------------------------------------------


def watch_interval_seconds(override: int | None) -> int:
    if override is not None:
        nilai = override
    else:
        raw = os.environ.get("GOOGLE_SHEETS_WATCH_INTERVAL", "").strip()

        if not raw:
            return DEFAULT_WATCH_INTERVAL_SECONDS

        try:
            nilai = int(raw)
        except ValueError as error:
            raise ExportError(
                f"GOOGLE_SHEETS_WATCH_INTERVAL harus angka detik, bukan \"{raw}\"."
            ) from error

    if nilai < MIN_WATCH_INTERVAL_SECONDS:
        raise ExportError(
            f"Jeda pemeriksaan minimal {MIN_WATCH_INTERVAL_SECONDS} detik supaya "
            f"kuota Google Sheets API tidak terbuang percuma. Nilai sekarang: {nilai}."
        )

    return nilai


def serve_request(
    worksheet, spreadsheet, url: str, tables: dict[str, str], identitas: str
) -> int:
    """Layani satu permintaan client: kosongkan kotak, ekspor, lalu tulis status.

    Kotak dikosongkan **sebelum** ekspor: kalau ekspornya gagal, permintaan lama
    tidak ikut terulang terus setiap putaran. Kegagalan tetap dilaporkan sebagai
    kode keluar bukan nol supaya host penjadwal mencatatnya.
    """
    write_cells(worksheet, {CONTROL_BUTTON_CELL: "FALSE"})
    log("Permintaan baru dari tab Kontrol - menjalankan ekspor.")

    # Petunjuk ikut disegarkan di sini, bukan hanya saat pengawas mulai:
    # pengawas yang menyala berminggu-minggu di host lain tetap memakai kalimat
    # terbaru dari kode tanpa perlu dijalankan ulang.
    refresh_control_notes(worksheet)
    write_cells(worksheet, {CONTROL_STATUS_CELL: "Sedang memproses permintaan..."})

    try:
        with psycopg.connect(url) as connection:
            ringkasan = export_tables(connection, spreadsheet, tables, identitas)
    except Exception as error:
        pesan = str(error).splitlines()[0] if str(error) else error.__class__.__name__
        log(f"Ekspor gagal: {pesan}")
        write_cells(worksheet, {CONTROL_STATUS_CELL: f"Gagal: {pesan}"})

        return 1

    total = sum(baris for _, _, baris, _ in ringkasan)
    ringkas = ", ".join(f"{nama} {baris}" for nama, _, baris, _ in ringkasan)

    write_cells(
        worksheet,
        {
            CONTROL_STATUS_CELL: f"Selesai. {len(ringkasan)} tab diperbarui, total {total} baris.",
            CONTROL_UPDATED_CELL: timestamp(),
            CONTROL_SUMMARY_CELL: ringkas,
        },
    )
    log(f"Permintaan selesai: {total} baris di {len(ringkasan)} tab.")

    return 0


def run_watch(
    interval_override: int | None, only: str | None, auth_override: str | None = None
) -> int:
    url = database_url()
    tables = selected_tables(only)
    interval = watch_interval_seconds(interval_override)

    mode, path, identitas = google_credentials(auth_override)

    log("Mode pengawas. Biarkan jendela ini terbuka; hentikan dengan Ctrl+C.")
    log(f"Masuk sebagai  : {identitas} ({mode})")
    log(f"Kredensial     : {credentials_source(path)}")
    log(f"Database       : {describe_database(url)}")

    if mode == AUTH_OAUTH:
        log(f"Status login   : {oauth_login_state()}")

    check_database_access(url)

    client = build_client(mode, path)
    spreadsheet = open_spreadsheet(client, identitas)
    log(f"Spreadsheet    : {spreadsheet.title} ({spreadsheet.id})")
    log(f"Tautan         : {spreadsheet.url}")

    if mode == AUTH_SERVICE_ACCOUNT:
        share_spreadsheet(spreadsheet)
    worksheet = ensure_control_tab(spreadsheet, tables)
    remove_default_empty_tab(spreadsheet)
    log(f"Diperiksa setiap {interval} detik.")

    while True:
        try:
            if is_request(cell_value(worksheet, CONTROL_BUTTON_CELL)):
                serve_request(worksheet, spreadsheet, url, tables, identitas)
        except Exception as error:
            # Kesalahan membaca kotaknya sendiri (mis. jaringan) tidak boleh
            # menghentikan pengawas: dicatat, lalu dicoba lagi putaran berikutnya.
            pesan = str(error).splitlines()[0] if str(error) else error.__class__.__name__
            log(f"Pemeriksaan tab Kontrol gagal: {pesan}")

        time.sleep(interval)


def run_once(only: str | None, auth_override: str | None = None) -> int:
    """Periksa sekali saja: ekspor kalau kotaknya dicentang, lalu keluar.

    Dipakai host yang menjalankan skrip secara terjadwal (cron di PaaS, Cloud
    Scheduler, GitHub Actions), bukan pengawas yang menunggu di satu proses.
    Tanpa permintaan, skrip keluar dengan kode nol tanpa menyentuh Google Sheets.
    """
    url = database_url()
    tables = selected_tables(only)

    mode, path, identitas = google_credentials(auth_override)

    log(f"Masuk sebagai: {identitas} ({mode})")
    log(f"Kredensial   : {credentials_source(path)}")
    log(f"Database     : {describe_database(url)}")

    client = build_client(mode, path)
    spreadsheet = open_spreadsheet(client, identitas)

    worksheet = ensure_control_tab(spreadsheet, tables)
    remove_default_empty_tab(spreadsheet)

    if not is_request(cell_value(worksheet, CONTROL_BUTTON_CELL)):
        log("Tidak ada permintaan baru di tab Kontrol.")

        return 0

    return serve_request(worksheet, spreadsheet, url, tables, identitas)


def selected_tables(only: str | None) -> dict[str, str]:
    if not only:
        return TABLES

    if only not in TABLES:
        raise ExportError(
            f"Tabel `{only}` bukan bagian dari ekspor ini.\n"
            f"  Pilihan yang ada: {', '.join(TABLES)}"
        )

    return {only: TABLES[only]}


# --------------------------------------------------------------------------
# Titik masuk
# --------------------------------------------------------------------------


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Salin tabel dinamis POS ke satu Google Sheets, satu tab per tabel."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="baca database dan tampilkan rencananya, tanpa menyentuh Google Sheets",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="periksa kredensial Google, sambungan database, dan daftar tabnya",
    )
    mode.add_argument(
        "--watch",
        action="store_true",
        help="pengawas: jalankan ekspor setiap kali kotak di tab Kontrol dicentang",
    )
    mode.add_argument(
        "--if-requested",
        action="store_true",
        help=(
            "sekali periksa: ekspor kalau kotak di tab Kontrol dicentang, lalu "
            "keluar (untuk host berbasis cron)"
        ),
    )
    parser.add_argument(
        "--only",
        metavar="TABEL",
        help="batasi ke satu tabel saja, mis. --only transactions",
    )
    parser.add_argument(
        "--auth",
        metavar="MODE",
        choices=[AUTH_SERVICE_ACCOUNT, AUTH_OAUTH],
        help=(
            "cara masuk Google: service-account (bawaan, berkas kunci JSON) "
            "atau oauth (akun Google Anda sendiri, untuk mode client)"
        ),
    )
    parser.add_argument(
        "--interval",
        type=int,
        metavar="DETIK",
        help=f"jeda pemeriksaan tab Kontrol saat --watch (bawaan {DEFAULT_WATCH_INTERVAL_SECONDS} detik)",
    )

    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    try:
        load_environment()

        if arguments.check:
            return run_check(arguments.auth)

        if arguments.watch:
            return run_watch(arguments.interval, arguments.only, arguments.auth)

        if arguments.if_requested:
            return run_once(arguments.only, arguments.auth)

        return run_export(arguments.dry_run, arguments.only, arguments.auth)
    except ExportError as error:
        print(file=sys.stderr)
        print("GAGAL:", file=sys.stderr)
        for baris in str(error).splitlines():
            print(f"  {baris}", file=sys.stderr)
        print(file=sys.stderr)

        return 1
    except KeyboardInterrupt:
        print("\nDibatalkan oleh pengguna.", file=sys.stderr)

        return 130


if __name__ == "__main__":
    raise SystemExit(main())
