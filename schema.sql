CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama TEXT NOT NULL,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'pengajar', 'siswa')),
    kelas_id INTEGER,
    foto TEXT DEFAULT 'default_avatar.png',
    no_whatsapp TEXT,
    biodata TEXT,
    alamat TEXT,
    nik TEXT,
    email TEXT,
    FOREIGN KEY(kelas_id) REFERENCES kelas(id)
);

CREATE TABLE IF NOT EXISTS kelas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama TEXT UNIQUE NOT NULL,
    pengajar_id INTEGER NOT NULL,
    pengajar_id2 INTEGER,
    deskripsi TEXT,
    -- BARU (revisi 2): gambar latar kartu kelas, dipilih admin dari 3 pilihan yang ada
    -- di static/images (header_winter.png / header_autum.png / header_spring.png).
    header TEXT,
    FOREIGN KEY(pengajar_id) REFERENCES users(id),
    FOREIGN KEY(pengajar_id2) REFERENCES users(id)
);

-- BARU (revisi 3): pendidikan TERAKHIR pengajar, diisi admin waktu membuat/mengedit akun.
-- Satu pengajar cuma punya satu baris di sini (UNIQUE), jadi memang "pendidikan terakhir",
-- bukan daftar riwayat pendidikan.
CREATE TABLE IF NOT EXISTS pendidikan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pengajar_id INTEGER NOT NULL UNIQUE,
    gelar TEXT NOT NULL,
    jurusan TEXT NOT NULL,
    institusi TEXT NOT NULL,
    FOREIGN KEY (pengajar_id) REFERENCES users(id)
);

-- Log penggantian password yang dilakukan siswa/pengajar sendiri.
-- DIUBAH: password lama & barunya ikut dicatat supaya admin bisa melihat
-- perubahannya di kartu "Riwayat Perubahan Password".
CREATE TABLE IF NOT EXISTS riwayat_password (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    waktu TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    password_lama TEXT,
    password_baru TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS jadwal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hari TEXT NOT NULL,
    jam TEXT NOT NULL,
    kelas_id INTEGER NOT NULL,
    pengajar_id INTEGER NOT NULL,
    tanggal TEXT,
    materi TEXT,
    -- BARU: 1 kalau pengajarnya guru pengganti (bukan guru tetap kelas tsb)
    pengganti INTEGER DEFAULT 0,
    FOREIGN KEY(kelas_id) REFERENCES kelas(id),
    FOREIGN KEY(pengajar_id) REFERENCES users(id)
);

-- tanggal_upload & tanggal_edit dipakai feed kelas: "02 Oktober (Diedit 03 Oktober)"
CREATE TABLE IF NOT EXISTS materi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    judul TEXT NOT NULL,
    kategori TEXT,
    file_path TEXT,
    kelas_id INTEGER NOT NULL,
    pengajar_id INTEGER NOT NULL,
    tanggal_upload TEXT,
    tanggal_edit TEXT,
    FOREIGN KEY(kelas_id) REFERENCES kelas(id),
    FOREIGN KEY(pengajar_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS tugas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    judul TEXT NOT NULL,
    deskripsi TEXT,
    deadline TEXT,
    kelas_id INTEGER NOT NULL,
    pengajar_id INTEGER NOT NULL,
    tanggal_dibuat TEXT,
    tanggal_edit TEXT,
    FOREIGN KEY(kelas_id) REFERENCES kelas(id),
    FOREIGN KEY(pengajar_id) REFERENCES users(id)
);

-- Pengumpulan tugas siswa. Nilai disimpan di kolom nilai di sini (class Pengumpulan),
-- jadi nggak ada tabel penilaian terpisah lagi biar nggak ada dua sumber nilai.
CREATE TABLE IF NOT EXISTS pengumpulan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tugas_id INTEGER NOT NULL,
    siswa_id INTEGER NOT NULL,
    file_jawaban TEXT NOT NULL,
    nilai REAL CHECK (nilai IS NULL OR (nilai >= 0 AND nilai <= 100)),
    waktu_kumpul TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tugas_id) REFERENCES tugas(id),
    FOREIGN KEY (siswa_id) REFERENCES users(id),
    UNIQUE (tugas_id, siswa_id)
);

-- Komentar tugas = percakapan PRIVAT antara satu siswa dan pengajar kelasnya.
-- siswa_id menandai percakapan ini milik siapa; user_id tetap penulis komentarnya
-- (bisa siswa itu sendiri, bisa pengajar). Jadi siswa lain tidak ikut membaca.
CREATE TABLE IF NOT EXISTS komentar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tugas_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    siswa_id INTEGER,
    isi_komentar TEXT NOT NULL,
    waktu TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (tugas_id) REFERENCES tugas(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (siswa_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS presensi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tanggal TEXT NOT NULL,
    siswa_id INTEGER NOT NULL,
    kelas_id INTEGER NOT NULL,
    status TEXT DEFAULT 'Belum Hadir',
    UNIQUE (tanggal, siswa_id, kelas_id)
);

-- Catatan akhir pengajar: satu siswa satu catatan per kelas (bisa diedit),
-- walaupun kelasnya punya 2 pengajar.
CREATE TABLE IF NOT EXISTS catatan_akhir (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    siswa_id INTEGER NOT NULL,
    kelas_id INTEGER NOT NULL,
    pengajar_id INTEGER NOT NULL,
    catatan TEXT NOT NULL,
    tanggal_dibuat TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    lulus INTEGER DEFAULT 0,
    FOREIGN KEY (siswa_id) REFERENCES users(id),
    FOREIGN KEY (kelas_id) REFERENCES kelas(id),
    FOREIGN KEY (pengajar_id) REFERENCES users(id),
    UNIQUE (siswa_id, kelas_id)
);