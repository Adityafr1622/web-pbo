# Fluenglo — Sistem Kursus Bahasa Inggris SMA

Proyek UTS PBO — Kelompok B3

## Cara menjalankan

```
pip install -r requirements.txt
python seed.py       # SEKALI SAJA untuk database baru (menghapus data lama!)
python app.py
```

Buka `http://127.0.0.1:5000` — akun admin pertama: `admin` / `admin123`.

> **Sudah punya `fluenglo.db` dari sebelumnya? JANGAN jalankan `seed.py`.**
> Cukup `python app.py`. Fungsi `database.migrasi()` otomatis menambahkan tabel dan
> kolom baru tanpa menghapus data, dan password lama yang masih polos otomatis
> berubah jadi hash begitu pemiliknya login sekali.

## Keamanan password

Password **tidak pernah disimpan apa adanya**. `database.tambah_user()` dan
`database.edit_user()` meng-hash lewat `werkzeug.security.generate_password_hash`,
dan `User.cek_password()` memverifikasinya dengan `check_password_hash`. Artinya
password asli tidak bisa dibaca siapa pun — termasuk admin.

Di halaman Kelola Akun, kolom Password menampilkan titik-titik; ikon mata membuka
**hash** yang tersimpan (bukan password asli, karena password aslinya memang sudah
tidak ada). Untuk mengganti password pengguna, admin memakai tombol Edit. Waktu
pengguna mengganti passwordnya sendiri dicatat di tabel `riwayat_password` —
yang disimpan hanya waktunya, bukan isinya.

Lupa password **tidak memakai OTP WhatsApp**: pengguna menghubungi admin lewat
kontak di tab "Tentang Kami". Alasannya skala kursus kecil, tanpa biaya dan
ketergantungan pihak ketiga; OTP tetap butuh jalur admin kalau nomornya salah.

NIK pengajar hanya dikirim ke admin dan pengajar yang bersangkutan, tidak pernah
ke siswa (`Pengajar.profil_publik()` memang tidak memuatnya). Di tabel Kelola Akun
NIK tampil 4 digit awal saja; lengkapnya di halaman Profil Lengkap. Fotokopi KTP
sengaja tidak disimpan (prinsip minimisasi data).

## Struktur folder

```
fluenglo/
├── app.py                 # route Flask + filter tampilan (samar, tgl, tgl_jam, ...)
├── database.py            # SATU-SATUNYA tempat SQL ditulis
├── schema.sql             # struktur tabel
├── seed.py                # bikin database + akun admin pertama
├── models/
│   ├── user.py            # User (ABC) -> Siswa, Pengajar, Admin
│   ├── akademik.py        # Kelas, Jadwal, Materi, Tugas, Pengumpulan, Komentar
│   └── presensi.py        # Presensi, CatatanPengajar
├── templates/             # Jinja; _macros.html berisi macro bersama
└── static/                # style.css, app.js, images/, uploads/
```

## 4 pilar OOP — di mana melihatnya

Cari komentar bertanda di kode (`grep -rn ENCAPSULATION .`):

| Pilar | Contoh paling jelas |
|---|---|
| **Encapsulation** | `User.__password` private; hanya bisa diperiksa lewat `cek_password()` dan diubah lewat `ganti_password()`. `database.edit_user()` punya daftar putih kolom. |
| **Abstraction** | `User` adalah Abstract Base Class dengan `@abstractmethod tampilkan_menu()`. `database.py` menyembunyikan seluruh SQL dari models dan route. |
| **Inheritance** | `Siswa`, `Pengajar`, `Admin` mewarisi `User` beserta `cek_password()`, `ganti_password()`, dan aturan kontak `cek_kontak()`. |
| **Polymorphism** | `tampilkan_menu()`, `lihat_profil()`, `boleh_akses_kelas()`, `boleh_lihat_siswa()`, `boleh_lihat_pengajar()` di-override tiap role — route memanggilnya tanpa `if role == ...`. |

## Alur halaman

- **Admin**: Kelola Akun → Kelola Kelas → Kelola Jadwal → Monitoring
- **Pengajar**: Profil, Kelas, Jadwal. Materi/Tugas/Presensi dibuka dari dalam kelas.
- **Siswa**: Profil, Kelas, Jadwal, Monitoring Anak.
- Di dalam sebuah kelas ada tiga tab: **Materi | Tugas | Presensi**.
- Komentar tugas adalah **percakapan privat** antara satu siswa dan pengajarnya
  (kolom `komentar.siswa_id`); siswa lain tidak bisa membacanya.

## Pembagian backend per modul

- **Julpa**: arsitektur PBO, auth, `app.py`, Kelola Akun
- **Aya**: UI/UX, template HTML, CSS
- **Anggota 1**: Kelola Kelas & Jadwal → `Kelas`, `Jadwal` di `akademik.py`
- **Larry**: Materi & Tugas → `Materi`, `Tugas`, `Komentar`, `Pengumpulan`
- **Anggota 3**: Penilaian & Monitoring → `beri_nilai()`, `monitoring_sistem()`, `lihat_monitoring()`
- **Anggota 4**: Presensi & Catatan Akhir → `presensi.py`
