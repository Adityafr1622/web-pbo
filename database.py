import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# path absolut, jadi nggak peduli app dijalankan dari folder mana
DB_NAME = os.path.join(BASE_DIR, 'fluenglo.db')

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def migrasi():
    """Samain fluenglo.db lama dengan schema terbaru (aman dijalankan berulang kali).
    - tabel yang belum ada (pengumpulan, komentar, catatan_akhir, dst) dibuat dari schema.sql
    - kelas.pengajar_id2 : guru kedua (opsional) tiap kelas
    - jadwal.tanggal / jadwal.materi : dipakai form Buat Jadwal & tabel jadwal
    - users.alamat / users.nik / users.email : data profil (revisi dosen)
    """
    conn = get_connection()
    try:
        with open(os.path.join(BASE_DIR, 'schema.sql'), 'r', encoding='utf-8') as f:
            conn.executescript(f.read())

        def kolom(tabel):
            return [r['name'] for r in conn.execute(f'PRAGMA table_info({tabel})')]
        tambahan = [
            ('kelas', 'pengajar_id2', 'INTEGER'),
            ('jadwal', 'tanggal', 'TEXT'),
            ('jadwal', 'materi', 'TEXT'),
            ('users', 'alamat', 'TEXT'),
            ('users', 'nik', 'TEXT'),
            ('users', 'email', 'TEXT'),
            ('kelas', 'deskripsi', 'TEXT'),
        ]
        for tabel, nama, tipe in tambahan:
            ada = kolom(tabel)
            if ada and nama not in ada:
                conn.execute(f'ALTER TABLE {tabel} ADD COLUMN {nama} {tipe}')
        conn.commit()
    finally:
        conn.close()

# --- USER FUNCTIONS ---
def ambil_user_by_id(user_id):
    conn = get_connection()
    row = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return row

def ambil_user_by_username(username):
    conn = get_connection()
    row = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return row

def ambil_semua_user():
    conn = get_connection()
    rows = conn.execute('''
        SELECT u.*, k.nama AS kelas_nama
        FROM users u
        LEFT JOIN kelas k ON u.kelas_id = k.id
    ''').fetchall()
    conn.close()
    return rows

def ambil_semua_pengajar():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM users WHERE role = 'pengajar'").fetchall()
    conn.close()
    return rows

def tambah_user(nama, username, password, role, foto=None, no_whatsapp=None, biodata=None,
                kelas_id=None, alamat=None, nik=None, email=None):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (nama, username, password, role, foto, no_whatsapp, biodata,
                               kelas_id, alamat, nik, email)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (nama, username, password, role, foto or 'default_avatar.png', no_whatsapp,
              biodata, kelas_id, alamat, nik, email))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("Username sudah digunakan.")
    finally:
        conn.close()


def edit_user(user_id, **kwargs):
    """Memperbarui kolom user yang diizinkan saja."""
    kolom_diizinkan = {
        "nama", "username", "password", "role", "foto",
        "no_whatsapp", "biodata", "kelas_id", "alamat",
        "nik", "email"
    }

    if not kwargs:
        return False

    kolom_tidak_valid = set(kwargs) - kolom_diizinkan
    if kolom_tidak_valid:
        raise ValueError(
            "Kolom user tidak diizinkan: "
            + ", ".join(sorted(kolom_tidak_valid))
        )

    kolom = list(kwargs.keys())
    assignments = ", ".join(f"{nama} = ?" for nama in kolom)
    values = [kwargs[nama] for nama in kolom]
    values.append(user_id)

    conn = get_connection()
    try:
        cursor = conn.execute(
            f"UPDATE users SET {assignments} WHERE id = ?",
            values
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.IntegrityError as exc:
        raise ValueError(
            "Username sudah digunakan atau data melanggar aturan database."
        ) from exc
    finally:
        conn.close()


def hapus_user(user_id):
    conn = get_connection()
    try:
        # data turunan ikut dibersihkan supaya tidak ada data yatim
        # (SQLite nggak otomatis nolak/ngikut hapus lewat FOREIGN KEY)
        conn.execute('DELETE FROM presensi WHERE siswa_id = ?', (user_id,))
        conn.execute('DELETE FROM pengumpulan WHERE siswa_id = ?', (user_id,))
        conn.execute('DELETE FROM catatan_akhir WHERE siswa_id = ?', (user_id,))
        conn.execute('DELETE FROM komentar WHERE user_id = ?', (user_id,))
        conn.execute('DELETE FROM riwayat_password WHERE user_id = ?', (user_id,))
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
    finally:
        conn.close()

def hitung_keterkaitan_pengajar(pengajar_id):
    """Berapa kelas / jadwal / materi / tugas yang masih nunjuk ke pengajar ini.
    Dipakai buat nolak hapus akun pengajar yang masih punya data."""
    conn = get_connection()
    try:
        return {
            'kelas': conn.execute('SELECT COUNT(*) FROM kelas WHERE pengajar_id = ? OR pengajar_id2 = ?',
                                  (pengajar_id, pengajar_id)).fetchone()[0],
            'jadwal': conn.execute('SELECT COUNT(*) FROM jadwal WHERE pengajar_id = ?',
                                   (pengajar_id,)).fetchone()[0],
            'materi': conn.execute('SELECT COUNT(*) FROM materi WHERE pengajar_id = ?',
                                   (pengajar_id,)).fetchone()[0],
            'tugas': conn.execute('SELECT COUNT(*) FROM tugas WHERE pengajar_id = ?',
                                  (pengajar_id,)).fetchone()[0],
        }
    finally:
        conn.close()

def catat_riwayat_password(user_id):
    conn = get_connection()
    try:
        conn.execute('INSERT INTO riwayat_password (user_id) VALUES (?)', (user_id,))
        conn.commit()
    finally:
        conn.close()

def ambil_riwayat_password(limit=50):
    """Riwayat terbaru di atas: waktu, nama, role, username."""
    conn = get_connection()
    try:
        return conn.execute('''
            SELECT r.id, r.waktu, u.nama, u.role, u.username
            FROM riwayat_password r JOIN users u ON u.id = r.user_id
            ORDER BY r.id DESC LIMIT ?
        ''', (limit,)).fetchall()
    finally:
        conn.close()

def ambil_terakhir_ubah_password():
    """{user_id: waktu perubahan terakhir}, buat kolom 'Password Diubah'."""
    conn = get_connection()
    try:
        rows = conn.execute('SELECT user_id, MAX(waktu) AS waktu FROM riwayat_password GROUP BY user_id').fetchall()
        return {r['user_id']: r['waktu'] for r in rows}
    finally:
        conn.close()

# --- KELAS FUNCTIONS ---
def ambil_kelas_by_id(kelas_id):
    conn = get_connection()
    row = conn.execute('SELECT *, nama AS nama_kelas FROM kelas WHERE id = ?', (kelas_id,)).fetchone()
    conn.close()
    return row

def ambil_kelas_by_nama(nama):
    conn = get_connection()
    row = conn.execute('SELECT * FROM kelas WHERE nama = ?', (nama,)).fetchone()
    conn.close()
    return row

def ambil_pengajar_kelas(kelas_row):
    """Daftar guru sebuah kelas (1 atau 2), tiap item: id, nama, username, no_whatsapp, foto."""
    ids = [kelas_row['pengajar_id']]
    if 'pengajar_id2' in kelas_row.keys() and kelas_row['pengajar_id2']:
        ids.append(kelas_row['pengajar_id2'])
    hasil = []
    for uid in ids:
        u = ambil_user_by_id(uid)
        if u:
            hasil.append({'id': u['id'], 'nama': u['nama'], 'username': u['username'],
                          'no_whatsapp': u['no_whatsapp'], 'foto': u['foto']})
    return hasil

def kelas_jadi_dict(row):
    """Row kelas -> dict + pengajar_list (1-2 guru) + nama_pengajar (nama guru digabung)."""
    k = dict(row)
    k['pengajar_list'] = ambil_pengajar_kelas(row)
    k['nama_pengajar'] = ', '.join(p['nama'] for p in k['pengajar_list'])
    return k

def ambil_semua_kelas():
    """Tiap kelas dikembalikan sebagai dict: id, nama, nama_kelas, pengajar_id, pengajar_id2,
    pengajar_list (1-2 guru) dan nama_pengajar (nama guru digabung)."""
    conn = get_connection()
    rows = conn.execute('SELECT *, nama AS nama_kelas FROM kelas ORDER BY id').fetchall()
    conn.close()
    return [kelas_jadi_dict(r) for r in rows]

def ambil_kelas_by_pengajar(pengajar_id):
    """Kelas yang diajar seorang pengajar (jadi guru 1 maupun guru 2), format sama dgn ambil_semua_kelas."""
    conn = get_connection()
    rows = conn.execute('''
        SELECT *, nama AS nama_kelas FROM kelas
        WHERE pengajar_id = ? OR pengajar_id2 = ? ORDER BY id
    ''', (pengajar_id, pengajar_id)).fetchall()
    conn.close()
    return [kelas_jadi_dict(r) for r in rows]

def tambah_kelas(nama, pengajar_id, pengajar_id2=None, deskripsi=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO kelas (nama, pengajar_id, pengajar_id2, deskripsi) VALUES (?, ?, ?, ?)',
                   (nama, pengajar_id, pengajar_id2, deskripsi))
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    return last_id

def edit_kelas(kelas_id, nama, pengajar_id, pengajar_id2=None, deskripsi=None):
    conn = get_connection()
    conn.execute('UPDATE kelas SET nama = ?, pengajar_id = ?, pengajar_id2 = ?, deskripsi = ? WHERE id = ?',
                 (nama, pengajar_id, pengajar_id2, deskripsi, kelas_id))
    conn.commit()
    conn.close()

def hapus_kelas(kelas_id):
    conn = get_connection()
    # jadwal & catatan akhir kelas ikut dihapus, siswa dilepas dari kelas, supaya tidak ada data yatim
    conn.execute('DELETE FROM jadwal WHERE kelas_id = ?', (kelas_id,))
    conn.execute('DELETE FROM catatan_akhir WHERE kelas_id = ?', (kelas_id,))
    conn.execute('UPDATE users SET kelas_id = NULL WHERE kelas_id = ?', (kelas_id,))
    conn.execute('DELETE FROM kelas WHERE id = ?', (kelas_id,))
    conn.commit()
    conn.close()

def ambil_siswa_by_kelas(kelas_id):
    conn = get_connection()
    rows = conn.execute('SELECT * FROM users WHERE role = "siswa" AND kelas_id = ?', (kelas_id,)).fetchall()
    conn.close()
    return rows

def ambil_kelas_siswa(siswa_id):
    conn = get_connection()
    row = conn.execute('''
        SELECT k.* FROM kelas k
        JOIN users u ON u.kelas_id = k.id
        WHERE u.id = ?
    ''', (siswa_id,)).fetchone()
    conn.close()
    return row

def tambah_siswa_ke_kelas(kelas_id, siswa_id):
    conn = get_connection()
    conn.execute('UPDATE users SET kelas_id = ? WHERE id = ?', (kelas_id, siswa_id))
    conn.commit()
    conn.close()

def hapus_siswa_dari_kelas(kelas_id, siswa_id):
    conn = get_connection()
    conn.execute('UPDATE users SET kelas_id = NULL WHERE id = ? AND kelas_id = ?', (siswa_id, kelas_id))
    conn.commit()
    conn.close()

def hitung_data_terkait_kelas(kelas_id):
    conn = get_connection()
    materi = conn.execute('SELECT COUNT(*) FROM materi WHERE kelas_id = ?', (kelas_id,)).fetchone()[0]
    tugas = conn.execute('SELECT COUNT(*) FROM tugas WHERE kelas_id = ?', (kelas_id,)).fetchone()[0]
    presensi = conn.execute('SELECT COUNT(*) FROM presensi WHERE kelas_id = ?', (kelas_id,)).fetchone()[0]
    conn.close()
    return {'materi': materi, 'tugas': tugas, 'presensi': presensi}

# --- JADWAL FUNCTIONS ---
_SELECT_JADWAL = '''
    SELECT j.*, k.nama AS kelas_nama, u.nama AS pengajar_nama
    FROM jadwal j
    JOIN kelas k ON j.kelas_id = k.id
    JOIN users u ON j.pengajar_id = u.id
'''

def ambil_jadwal_by_id(jadwal_id):
    conn = get_connection()
    row = conn.execute('SELECT * FROM jadwal WHERE id = ?', (jadwal_id,)).fetchone()
    conn.close()
    return row

def ambil_semua_jadwal():
    conn = get_connection()
    rows = conn.execute(_SELECT_JADWAL).fetchall()
    conn.close()
    return rows

def ambil_jadwal_by_hari(hari):
    conn = get_connection()
    rows = conn.execute(_SELECT_JADWAL + ' WHERE j.hari = ?', (hari,)).fetchall()
    conn.close()
    return rows

def ambil_jadwal_by_tanggal(tanggal):
    conn = get_connection()
    rows = conn.execute(_SELECT_JADWAL + ' WHERE j.tanggal = ?', (tanggal,)).fetchall()
    conn.close()
    return rows

def ambil_jadwal_by_kelas(kelas_id):
    # sudah di-JOIN, jadi ada kelas_nama & pengajar_nama (buat tampil nama pengajar di jadwal siswa)
    conn = get_connection()
    rows = conn.execute(_SELECT_JADWAL + ' WHERE j.kelas_id = ?', (kelas_id,)).fetchall()
    conn.close()
    return rows

def ambil_jadwal_by_pengajar(pengajar_id):
    conn = get_connection()
    rows = conn.execute(_SELECT_JADWAL + ' WHERE j.pengajar_id = ?', (pengajar_id,)).fetchall()
    conn.close()
    return rows

def tambah_jadwal(hari, jam, kelas_id, pengajar_id, tanggal=None, materi=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO jadwal (hari, jam, kelas_id, pengajar_id, tanggal, materi) VALUES (?, ?, ?, ?, ?, ?)',
                   (hari, jam, kelas_id, pengajar_id, tanggal, materi))
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    return last_id

def edit_jadwal(jadwal_id, hari, jam, kelas_id, pengajar_id, tanggal=None, materi=None):
    conn = get_connection()
    conn.execute('''
        UPDATE jadwal SET hari = ?, jam = ?, kelas_id = ?, pengajar_id = ?, tanggal = ?, materi = ?
        WHERE id = ?
    ''', (hari, jam, kelas_id, pengajar_id, tanggal, materi, jadwal_id))
    conn.commit()
    conn.close()

def hapus_jadwal(jadwal_id):
    conn = get_connection()
    conn.execute('DELETE FROM jadwal WHERE id = ?', (jadwal_id,))
    conn.commit()
    conn.close()

# --- MATERI, TUGAS, PENGUMPULAN, DAN KOMENTAR ---

def _cek_pengajar_kelas(conn, kelas_id, pengajar_id):
    """Pastikan kelas ada dan pengajar ini guru 1 / guru 2 di kelas tsb."""
    kelas = conn.execute(
        "SELECT pengajar_id, pengajar_id2 FROM kelas WHERE id = ?",
        (kelas_id,)
    ).fetchone()

    if not kelas:
        raise ValueError("Kelas tidak ditemukan.")

    if pengajar_id not in (kelas["pengajar_id"], kelas["pengajar_id2"]):
        raise ValueError("Pengajar tidak memiliki akses ke kelas ini.")

def tambah_materi(kelas_id, pengajar_id, judul, kategori, file_path):
    """Menyimpan materi baru. Pengajar harus ditugaskan pada kelas tersebut."""
    conn = get_connection()
    try:
        _cek_pengajar_kelas(conn, kelas_id, pengajar_id)

        cursor = conn.execute("""
            INSERT INTO materi
                (kelas_id, pengajar_id, judul, kategori, file_path)
            VALUES (?, ?, ?, ?, ?)
        """, (kelas_id, pengajar_id, judul, kategori, file_path))

        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def ambil_materi_by_kelas(kelas_id):
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT m.*, u.nama AS nama_pengajar
            FROM materi m
            LEFT JOIN users u ON u.id = m.pengajar_id
            WHERE m.kelas_id = ?
            ORDER BY m.id DESC
        """, (kelas_id,)).fetchall()
    finally:
        conn.close()


def ambil_materi_by_id(materi_id):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM materi WHERE id = ?",
            (materi_id,)
        ).fetchone()
    finally:
        conn.close()


def edit_materi(materi_id, judul, kategori, file_path=None):
    """Ubah judul/kategori materi. file_path diisi kalau pengajar upload file pengganti."""
    conn = get_connection()
    try:
        if file_path:
            cursor = conn.execute(
                "UPDATE materi SET judul = ?, kategori = ?, file_path = ? WHERE id = ?",
                (judul, kategori, file_path, materi_id))
        else:
            cursor = conn.execute(
                "UPDATE materi SET judul = ?, kategori = ? WHERE id = ?",
                (judul, kategori, materi_id))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def hapus_materi(materi_id):
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM materi WHERE id = ?",
            (materi_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def tambah_tugas(kelas_id, pengajar_id, judul, deskripsi, deadline):
    """Menyimpan tugas baru untuk kelas yang diajar pengajar."""
    conn = get_connection()
    try:
        _cek_pengajar_kelas(conn, kelas_id, pengajar_id)

        cursor = conn.execute("""
            INSERT INTO tugas
                (kelas_id, pengajar_id, judul, deskripsi, deadline)
            VALUES (?, ?, ?, ?, ?)
        """, (kelas_id, pengajar_id, judul, deskripsi, deadline))

        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def ambil_tugas_by_kelas(kelas_id):
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT t.*, u.nama AS nama_pengajar
            FROM tugas t
            LEFT JOIN users u ON u.id = t.pengajar_id
            WHERE t.kelas_id = ?
            ORDER BY t.id DESC
        """, (kelas_id,)).fetchall()
    finally:
        conn.close()


def ambil_tugas_by_id(tugas_id):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM tugas WHERE id = ?",
            (tugas_id,)
        ).fetchone()
    finally:
        conn.close()


def simpan_pengumpulan(tugas_id, siswa_id, file_jawaban):
    """Simpan pengumpulan baru atau perbarui jawaban siswa."""
    conn = get_connection()
    try:
        tugas = conn.execute(
            "SELECT id, kelas_id FROM tugas WHERE id = ?",
            (tugas_id,)
        ).fetchone()

        siswa = conn.execute(
            "SELECT id, kelas_id, role FROM users WHERE id = ?",
            (siswa_id,)
        ).fetchone()

        if not tugas:
            raise ValueError("Tugas tidak ditemukan.")

        if not siswa or siswa["role"] != "siswa":
            raise ValueError("Akun siswa tidak ditemukan.")

        if siswa["kelas_id"] != tugas["kelas_id"]:
            raise ValueError("Siswa bukan anggota kelas tugas ini.")

        existing = conn.execute("""
            SELECT id FROM pengumpulan
            WHERE tugas_id = ? AND siswa_id = ?
        """, (tugas_id, siswa_id)).fetchone()

        if existing:
            # jawaban diganti = nilai lama nggak berlaku lagi, pengajar perlu menilai ulang
            conn.execute("""
                UPDATE pengumpulan
                SET file_jawaban = ?,
                    nilai = NULL,
                    waktu_kumpul = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (file_jawaban, existing["id"]))
            pengumpulan_id = existing["id"]
        else:
            cursor = conn.execute("""
                INSERT INTO pengumpulan
                    (tugas_id, siswa_id, file_jawaban, waktu_kumpul)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (tugas_id, siswa_id, file_jawaban))
            pengumpulan_id = cursor.lastrowid

        conn.commit()
        return pengumpulan_id
    finally:
        conn.close()


def ambil_pengumpulan_by_tugas_siswa(tugas_id, siswa_id):
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT *
            FROM pengumpulan
            WHERE tugas_id = ? AND siswa_id = ?
        """, (tugas_id, siswa_id)).fetchone()
    finally:
        conn.close()


def ambil_pengumpulan_by_tugas(tugas_id):
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT p.*, u.nama AS siswa_nama,
                   u.username AS siswa_username
            FROM pengumpulan p
            JOIN users u ON u.id = p.siswa_id
            WHERE p.tugas_id = ?
            ORDER BY u.nama
        """, (tugas_id,)).fetchall()
    finally:
        conn.close()


def ambil_pengumpulan_by_id(pengumpulan_id):
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM pengumpulan WHERE id = ?",
            (pengumpulan_id,)
        ).fetchone()
    finally:
        conn.close()


def update_nilai_pengumpulan(pengumpulan_id, nilai):
    """Memperbarui kolom nilai pada tabel pengumpulan."""
    try:
        nilai = float(nilai)
    except (TypeError, ValueError):
        raise ValueError("Nilai harus berupa angka.")

    if not 0 <= nilai <= 100:
        raise ValueError("Nilai harus berada antara 0 sampai 100.")

    conn = get_connection()
    try:
        cursor = conn.execute("""
            UPDATE pengumpulan
            SET nilai = ?
            WHERE id = ?
        """, (nilai, pengumpulan_id))

        conn.commit()

        if cursor.rowcount == 0:
            raise ValueError("Data pengumpulan tidak ditemukan.")

        return True
    finally:
        conn.close()


def tambah_komentar(tugas_id, user_id, isi):
    isi = (isi or "").strip()
    if not isi:
        raise ValueError("Isi komentar tidak boleh kosong.")

    conn = get_connection()
    try:
        tugas = conn.execute(
            "SELECT id FROM tugas WHERE id = ?",
            (tugas_id,)
        ).fetchone()

        pengguna = conn.execute(
            "SELECT id FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        if not tugas:
            raise ValueError("Tugas tidak ditemukan.")

        if not pengguna:
            raise ValueError("Pengguna tidak ditemukan.")

        cursor = conn.execute("""
            INSERT INTO komentar (tugas_id, user_id, isi_komentar)
            VALUES (?, ?, ?)
        """, (tugas_id, user_id, isi))

        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def ambil_komentar_tugas(tugas_id):
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT k.*, u.nama AS user_nama, u.role AS user_role
            FROM komentar k
            JOIN users u ON u.id = k.user_id
            WHERE k.tugas_id = ?
            ORDER BY k.id ASC
        """, (tugas_id,)).fetchall()
    finally:
        conn.close()


# --- PRESENSI FUNCTIONS ---
def ambil_presensi_by_id(presensi_id):
    conn = get_connection()
    row = conn.execute('SELECT * FROM presensi WHERE id = ?', (presensi_id,)).fetchone()
    conn.close()
    return row

def ambil_presensi_kelas_tanggal(kelas_id, tanggal):
    conn = get_connection()
    rows = conn.execute('SELECT * FROM presensi WHERE kelas_id = ? AND tanggal = ?',
                        (kelas_id, tanggal)).fetchall()
    conn.close()
    return rows

def ambil_presensi_siswa(siswa_id):
    conn = get_connection()
    rows = conn.execute('SELECT * FROM presensi WHERE siswa_id = ? ORDER BY tanggal DESC',
                        (siswa_id,)).fetchall()
    conn.close()
    return rows

def ambil_tanggal_jadwal_kelas(kelas_id):
    """Daftar tanggal (string YYYY-MM-DD) pertemuan kelas menurut tabel jadwal."""
    conn = get_connection()
    rows = conn.execute('''
        SELECT DISTINCT tanggal FROM jadwal
        WHERE kelas_id = ? AND tanggal IS NOT NULL AND tanggal != ''
    ''', (kelas_id,)).fetchall()
    conn.close()
    return [r['tanggal'] for r in rows]

def ambil_tanggal_presensi_kelas(kelas_id):
    conn = get_connection()
    rows = conn.execute('SELECT DISTINCT tanggal FROM presensi WHERE kelas_id = ?', (kelas_id,)).fetchall()
    conn.close()
    return [r['tanggal'] for r in rows]

def _simpan_presensi(conn, tanggal, siswa_id, kelas_id, status):
    """Upsert: satu siswa hanya punya satu presensi per kelas per tanggal."""
    row = conn.execute('SELECT id FROM presensi WHERE tanggal = ? AND siswa_id = ? AND kelas_id = ?',
                       (tanggal, siswa_id, kelas_id)).fetchone()
    if row:
        conn.execute('UPDATE presensi SET status = ? WHERE id = ?', (status, row['id']))
        return row['id']
    cur = conn.execute('INSERT INTO presensi (tanggal, siswa_id, kelas_id, status) VALUES (?, ?, ?, ?)',
                       (tanggal, siswa_id, kelas_id, status))
    return cur.lastrowid

def simpan_presensi(tanggal, siswa_id, kelas_id, status):
    conn = get_connection()
    try:
        presensi_id = _simpan_presensi(conn, tanggal, siswa_id, kelas_id, status)
        conn.commit()
        return presensi_id
    finally:
        conn.close()

def simpan_presensi_massal(kelas_id, tanggal, data_status):
    """data_status: {siswa_id: status}. Semua disimpan dalam satu transaksi."""
    conn = get_connection()
    try:
        for siswa_id, status in data_status.items():
            _simpan_presensi(conn, tanggal, siswa_id, kelas_id, status)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def update_status_presensi(presensi_id, status):
    conn = get_connection()
    conn.execute('UPDATE presensi SET status = ? WHERE id = ?', (status, presensi_id))
    conn.commit()
    conn.close()

def rekap_presensi_siswa(siswa_id):
    conn = get_connection()
    rows = conn.execute('SELECT status, COUNT(*) AS jumlah FROM presensi WHERE siswa_id = ? GROUP BY status',
                        (siswa_id,)).fetchall()
    conn.close()
    return rows

def rekap_presensi_kelas(kelas_id):
    conn = get_connection()
    rows = conn.execute('''
        SELECT siswa_id, status, COUNT(*) AS jumlah FROM presensi
        WHERE kelas_id = ? GROUP BY siswa_id, status
    ''', (kelas_id,)).fetchall()
    conn.close()
    return rows

# ============================================================
# Penilaian tugas, Rekap nilai, dan Catatan akhir Pengajar
# Nilai disimpan di pengumpulan.nilai (satu-satunya sumber nilai).
# ============================================================

def beri_nilai(tugas_id, siswa_id, pengajar_id, nilai, komentar=None):
    """Memberi / memperbarui nilai pengumpulan siswa pada sebuah tugas.
    komentar nggak dipakai lagi: masukan ke siswa lewat tabel komentar (Komentar Tugas)."""
    try:
        nilai = float(nilai)
    except (TypeError, ValueError):
        raise ValueError("Nilai harus berupa angka.")

    if not 0 <= nilai <= 100:
        raise ValueError("Nilai harus berada antara 0 sampai 100.")

    conn = get_connection()
    try:
        tugas = conn.execute(
            'SELECT id, kelas_id FROM tugas WHERE id = ?',
            (tugas_id,)
        ).fetchone()
        if not tugas:
            raise ValueError("Tugas tidak ditemukan.")

        # guru 1 maupun guru 2 kelas tsb boleh menilai, nggak cuma yang bikin tugas
        _cek_pengajar_kelas(conn, tugas['kelas_id'], pengajar_id)

        pengumpulan = conn.execute(
            'SELECT id FROM pengumpulan WHERE tugas_id = ? AND siswa_id = ?',
            (tugas_id, siswa_id)
        ).fetchone()
        if not pengumpulan:
            raise ValueError("Siswa ini belum mengumpulkan tugas, jadi belum bisa dinilai.")

        conn.execute('UPDATE pengumpulan SET nilai = ? WHERE id = ?', (nilai, pengumpulan['id']))
        conn.commit()
        return pengumpulan['id']
    finally:
        conn.close()

def ambil_penilaian_by_id(penilaian_id):
    """penilaian_id = id pengumpulan yang sudah dinilai."""
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT p.*, u.nama AS nama_siswa,
                   t.judul AS judul_tugas,
                   g.nama AS nama_pengajar
            FROM pengumpulan p
            JOIN users u ON u.id = p.siswa_id
            JOIN tugas t ON t.id = p.tugas_id
            JOIN users g ON g.id = t.pengajar_id
            WHERE p.id = ? AND p.nilai IS NOT NULL
        """, (penilaian_id,)).fetchone()
    finally:
        conn.close()

def ambil_penilaian_by_siswa(siswa_id):
    """Semua nilai milik seorang siswa (yang sudah dinilai saja)."""
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT p.*, t.judul AS judul_tugas,
                   g.nama AS nama_pengajar
            FROM pengumpulan p
            JOIN tugas t ON t.id = p.tugas_id
            JOIN users g ON g.id = t.pengajar_id
            WHERE p.siswa_id = ? AND p.nilai IS NOT NULL
            ORDER BY p.waktu_kumpul DESC
        """, (siswa_id,)).fetchall()
    finally:
        conn.close()

def ambil_penilaian_by_tugas(tugas_id):
    """Nilai seluruh siswa pada sebuah tugas (yang sudah dinilai saja)."""
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT p.*, u.nama AS nama_siswa,
                   u.username AS username_siswa
            FROM pengumpulan p
            JOIN users u ON u.id = p.siswa_id
            WHERE p.tugas_id = ? AND p.nilai IS NOT NULL
            ORDER BY u.nama
        """, (tugas_id,)).fetchall()
    finally:
        conn.close()

def ambil_daftar_nilai_siswa(siswa_id):
    """Semua tugas di kelas siswa + nilainya. Tugas yang belum dikumpul/dinilai nilainya None."""
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT t.id AS tugas_id, t.judul AS judul_tugas, t.deadline,
                   p.file_jawaban, p.nilai, p.waktu_kumpul
            FROM users u
            JOIN tugas t ON t.kelas_id = u.kelas_id
            LEFT JOIN pengumpulan p ON p.tugas_id = t.id AND p.siswa_id = u.id
            WHERE u.id = ?
            ORDER BY t.id DESC
        """, (siswa_id,)).fetchall()
    finally:
        conn.close()

def rekap_nilai_siswa(siswa_id):
    """Menghitung jumlah nilai, rata-rata, tertinggi, dan terendah."""
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT
                COUNT(nilai) AS jumlah_tugas_dinilai,
                ROUND(AVG(nilai), 2) AS rata_rata,
                MAX(nilai) AS nilai_tertinggi,
                MIN(nilai) AS nilai_terendah
            FROM pengumpulan
            WHERE siswa_id = ?
        """, (siswa_id,)).fetchone()
    finally:
        conn.close()

def rekap_nilai_kelas(kelas_id):
    """Rekap nilai setiap siswa dalam suatu kelas."""
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT
                u.id AS siswa_id,
                u.nama AS nama_siswa,
                COUNT(p.nilai) AS jumlah_tugas_dinilai,
                ROUND(AVG(p.nilai), 2) AS rata_rata,
                MAX(p.nilai) AS nilai_tertinggi,
                MIN(p.nilai) AS nilai_terendah
            FROM users u
            LEFT JOIN pengumpulan p ON p.siswa_id = u.id
            WHERE u.role = 'siswa' AND u.kelas_id = ?
            GROUP BY u.id, u.nama
            ORDER BY u.nama
        """, (kelas_id,)).fetchall()
    finally:
        conn.close()

def ambil_monitoring_semua_siswa():
    """Satu baris per siswa buat Monitoring admin: kelas, rata-rata nilai, rekap presensi, jumlah catatan akhir."""
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT u.id AS siswa_id, u.nama AS nama_siswa, k.nama AS nama_kelas,
                   (SELECT ROUND(AVG(nilai), 2) FROM pengumpulan WHERE siswa_id = u.id) AS rata_rata,
                   (SELECT COUNT(*) FROM presensi WHERE siswa_id = u.id AND LOWER(status) = 'hadir') AS hadir,
                   (SELECT COUNT(*) FROM presensi WHERE siswa_id = u.id AND LOWER(status) = 'izin') AS izin,
                   (SELECT COUNT(*) FROM presensi WHERE siswa_id = u.id AND LOWER(status) = 'sakit') AS sakit,
                   (SELECT COUNT(*) FROM presensi WHERE siswa_id = u.id
                        AND LOWER(status) IN ('alfa', 'alpha')) AS alfa,
                   (SELECT COUNT(*) FROM catatan_akhir WHERE siswa_id = u.id) AS jumlah_catatan
            FROM users u
            LEFT JOIN kelas k ON k.id = u.kelas_id
            WHERE u.role = 'siswa'
            ORDER BY k.nama, u.nama
        """).fetchall()
    finally:
        conn.close()

def tambah_catatan_akhir(siswa_id, kelas_id, pengajar_id, catatan):
    """Satu siswa satu catatan akhir per kelas. Sudah ada = diedit (guru 1 & guru 2 sama-sama bisa edit)."""
    catatan = (catatan or "").strip()
    if not catatan:
        raise ValueError("Catatan akhir tidak boleh kosong.")

    conn = get_connection()
    try:
        kelas = conn.execute("""
            SELECT pengajar_id, pengajar_id2
            FROM kelas WHERE id = ?
        """, (kelas_id,)).fetchone()

        siswa = conn.execute("""
            SELECT id, kelas_id, role
            FROM users WHERE id = ?
        """, (siswa_id,)).fetchone()

        if not kelas:
            raise ValueError("Kelas tidak ditemukan.")
        if pengajar_id not in (
            kelas["pengajar_id"], kelas["pengajar_id2"]
        ):
            raise ValueError("Kamu bukan pengajar di kelas ini.")
        if not siswa or siswa["role"] != "siswa":
            raise ValueError("Siswa tidak ditemukan.")
        if siswa["kelas_id"] != kelas_id:
            raise ValueError("Siswa bukan anggota kelas ini.")

        catatan_lama = conn.execute("""
            SELECT id FROM catatan_akhir
            WHERE siswa_id = ? AND kelas_id = ?
        """, (siswa_id, kelas_id)).fetchone()

        if catatan_lama:
            conn.execute("""
                UPDATE catatan_akhir
                SET catatan = ?, pengajar_id = ?, tanggal_dibuat = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (catatan, pengajar_id, catatan_lama["id"]))
            hasil = catatan_lama["id"]
        else:
            cursor = conn.execute("""
                INSERT INTO catatan_akhir
                    (siswa_id, kelas_id, pengajar_id, catatan)
                VALUES (?, ?, ?, ?)
            """, (siswa_id, kelas_id, pengajar_id, catatan))
            hasil = cursor.lastrowid

        conn.commit()
        return hasil
    finally:
        conn.close()

def ambil_catatan_akhir_by_siswa(siswa_id):
    conn = get_connection()
    try:
        return conn.execute("""
            SELECT c.*, u.nama AS nama_pengajar,
                   k.nama AS nama_kelas
            FROM catatan_akhir c
            JOIN users u ON u.id = c.pengajar_id
            JOIN kelas k ON k.id = c.kelas_id
            WHERE c.siswa_id = ?
            ORDER BY c.tanggal_dibuat DESC
        """, (siswa_id,)).fetchall()
    finally:
        conn.close()

def hapus_catatan_akhir(catatan_id, pengajar_id):
    """Guru 1 / guru 2 kelas tsb boleh menghapus catatan akhir di kelasnya."""
    conn = get_connection()
    try:
        cursor = conn.execute("""
            DELETE FROM catatan_akhir
            WHERE id = ? AND kelas_id IN (
                SELECT id FROM kelas WHERE pengajar_id = ? OR pengajar_id2 = ?
            )
        """, (catatan_id, pengajar_id, pengajar_id))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()