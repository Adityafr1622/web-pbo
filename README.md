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

## Pembaruan dashboard dan riwayat kelas (2026-10-23)

Project lama dipertahankan. Route `/dashboard` sekarang menampilkan halaman berbeda
untuk admin, pengajar, dan siswa dengan data dari SQLite. Halaman-halaman kelas,
materi, tugas, presensi, jadwal, monitoring, profil, dan pengelolaan akun lama masih dipakai.

- **Admin:** filter tahun hanya menawarkan tahun yang benar-benar memiliki data
  jadwal, materi, atau tugas; siswa dihitung per keanggotaan `riwayat_kelas` yang
  meliputi jadwal pembelajaran. Tabel membandingkan hingga tiga tahun *yang
  memiliki data*, tanpa mengisi tahun kosong. Materi dan tugas dihitung menurut
  tanggal unggah/buat.
- **Pengajar:** filter kelas hanya mengizinkan kelas yang diajarnya; statistik,
  daftar pengumpulan, grafik, aktivitas dan progres mengikuti filter.
  Data *rata-rata nilai mingguan* memakai minggu **pengumpulan** tugas karena
  tabel lama belum menyimpan waktu ketika pengajar memberikan nilai. Jangan
  ditafsirkan sebagai waktu penilaian.
- **Siswa:** kelas aktif tetap di `users.kelas_id`, riwayat di tabel baru
  `riwayat_kelas`; filter kelas juga tersedia di Monitoring. Seluruh nilai,
  presensi dan tugas dihitung per kelas. Grafik presensi: Hadir 1, Izin/Sakit
  0,5, Alfa 0, hanya untuk jadwal lampau yang sudah dicatat.
- **Kelulusan:** pindah kelas dan melepas siswa dari kelas diproses oleh
  `database.edit_user()`; jika kelas lama belum ditandai `lulus=1` pada
  `catatan_akhir`, transaksi ditolak. Rekaman kelas lama tidak dihapus.
- **UI:** latar `#E8F0FB`, navbar Dashboard, foto profil dengan fallback inisial,
  tombol Back pada sisi kanan dengan tujuan halaman yang tetap (tidak bergantung
  pada riwayat browser), dan aksi edit/buka kelas lebih menonjol. Dashboard sendiri tidak punya tombol Back.

### Menjalankan pembaruan pada database lama

1. Simpan cadangan `fluenglo.db` terlebih dahulu.
2. Jalankan `pip install -r requirements.txt`, lalu `python app.py` seperti biasa.
3. `database.migrasi()` membuat tabel `riwayat_kelas` secara otomatis tanpa
   menghapus data lama. Tidak perlu menjalankan `seed.py`.
4. Jalankan pengujian regresi: `python -m unittest discover -s tests -v`.

**Batasan riwayat database lama:** sebelum pembaruan tidak ada tanggal siswa
mulai mengikuti kelas ataupun log perpindahan. Migrasi mengisi keanggotaan kelas
aktif dari jadwal pertama yang ada sebagai titik awal **perkiraan**, dan mengambil
catatan kelulusan sebelumnya jika tersedia. Keanggotaan yang tidak pernah
tercatat tidak dapat direkonstruksi. Perpindahan setelah pembaruan akan tersimpan
sebagai riwayat dan data lama tetap tersedia. Karena `presensi` lama unik per
siswa/kelas/**tanggal** (belum per ID jadwal), jika satu kelas memiliki dua
pertemuan di tanggal yang sama grafik menghitungnya sebagai satu tanggal tercatat.

Pengujian template dan query SQLite dapat dilakukan tanpa server, tetapi
pengujian UI end-to-end tetap perlu dilakukan di lingkungan yang memasang Flask.

## Revisi lanjutan dashboard (2026-10-23)

1. **Rekap Admin:** diagram cincin menggunakan 6 warna untuk Siswa, Pengajar,
   Kelas, Materi, Tugas, dan Pertemuan. Luas irisan dihitung dari jumlah
   kategori pada tahun yang dipilih; kategori bernilai nol tetap tercantum
   di legenda, tetapi tidak menempati irisan. Angka di tengah adalah jumlah
   **Siswa**, sesuai label (bukan penjumlahan semua kategori).
2. **Sisa Pertemuan Pengajar (direvisi kembali):** tiap kelas memiliki target
   **8 pertemuan**. Sisa = 8 dikurangi jumlah tanggal kelas yang memiliki
   catatan presensi sah (`hadir`, `izin`, `sakit`, `alfa`/`alpha`/`alpa`),
   terlepas dari apakah tanggal jadwal sudah berlalu. Progress pengajar memakai
   aturan yang sama; tidak menghitung siswa dua kali pada tanggal yang sama.
   Struktur database masih menyimpan presensi per kelas + siswa + tanggal,
   belum per `jadwal_id`, sehingga dua sesi pada tanggal yang sama tidak bisa
   dibedakan secara otomatis.
3. **Daftar Siswa Pengajar:** card mengarahkan ke panel daftar dengan anchor
   `#dashboard-daftar`, sama seperti daftar tugas dan materi.
4. **Back:** posisinya di kanan. Di fitur utama selalu menuju Dashboard;
   detail materi → daftar materi → daftar/kelola kelas → Dashboard,
   detail tugas → daftar tugas → daftar/kelola kelas → Dashboard,
   presensi kelas → daftar/kelola kelas → Dashboard, dan presensi khusus
   guru pengganti → Jadwal → Dashboard. Halaman profil → Dashboard.
5. **Ikon menu:** Dashboard menggunakan ikon rumah, Monitoring menggunakan
   ikon grafik agar keduanya mudah dibedakan.

Pengujian tambahan tersedia di `tests/test_revisi_dashboard.py`. Jalankan
`python -m unittest discover -s tests -v` setelah dependensi terpasang.

## Revisi Dashboard Siswa dan Admin — 8 pertemuan per kelas (2026-10-23)

- **Konstanta target:** `TOTAL_PERTEMUAN_KELAS = 8` di `database.py`.
  Total pertemuan pada kartu Siswa = **8**. Sisa = **8 − jumlah tanggal
  presensi sah yang unik untuk kelas tersebut**, paling sedikit 0.
  Tanggal jadwal yang telah lewat tanpa presensi tidak mengurangi sisa.
  Untuk siswa satu kelas, 16 baris presensi pada tanggal yang sama tetap
  dihitung **satu pertemuan**. Rekap admin dan pengajar konsisten dengan
  denominator 8. Kehadiran individu tetap berdasarkan catatannya sendiri.
- **Kartu tugas Siswa:** empat kategori (Sudah Dikerjakan, Belum Dikerjakan,
  Dinilai, Belum Dinilai) mengarah ke panel daftar di bagian bawah
  `/dashboard?kelas=...&panel=...#dashboard-daftar` seperti dashboard Pengajar.
  Item panel hanya mencantumkan tugas kelas terpilih dan pengumpulan
  siswa yang login. Tugas Dinilai = pengumpulan sudah ada nilai;
  Tugas Belum Dinilai = pengumpulan sudah ada tetapi belum diberi nilai,
  *bukan* tugas yang belum dikumpulkan.
- **Dropdown tahun Admin:** daftar tahun bersumber dari tahun data `jadwal`,
  `materi`, atau `tugas` yang benar-benar tersedia. Tahun kosong, termasuk
  2024/2025 jika belum punya catatan, tidak ditawarkan. Bila URL meminta
  tahun tidak valid atau tidak tersedia, dashboard memakai tahun terbaru
  yang memiliki data. Perbandingan menampilkan **maksimal tiga tahun tersedia
  hingga tahun terpilih**, tidak memaksakan tahun yang berurutan.
- **Progress Kelas Admin:** tampil sebagai `X dari 8 pertemuan`.
  X adalah jumlah tanggal kelas yang memiliki presensi sah, bukan
  jadwal yang sudah lewat; maksimum 8.
- **Pengujian:** `tests/test_dashboard_pertemuan8.py` menguji hitung presensi,
  siswa lebih dari satu pada tanggal yang sama, batas maksimum 8, tahun kosong,
  serta isolasi tugas per siswa. Pengujian database menggunakan database
  sementara, bukan mengubah `fluenglo.db` asli.

### Catatan teknis

Aplikasi belum menyimpan entitas `pertemuan_id` yang menghubungkan satu
presensi ke satu jadwal. Sistem memaknai *satu tanggal dengan presensi sah*
sebagai *satu pertemuan terlaksana*. Ketika dua pertemuan kelas dibuat pada
satu hari, data lama belum dapat menghitungnya secara terpisah tanpa
penambahan struktur. Tidak ada migrasi besar atau penghapusan data pada
revisi ini.

### Revisi Monitoring dan Status Jadwal (2026-10-23)

- Ringkasan angka di atas tabel **Monitoring Admin** dihapus karena angka-angka
  tersebut sudah tersedia di Dashboard Admin. Tabel monitoring siswa tetap ada.
- Kolom **Status** ditambahkan sebagai kolom paling kanan pada tabel Jadwal untuk
  Admin, Pengajar, dan Siswa. Status **Selesai** bila sudah terdapat setidaknya
  satu catatan presensi valid (`Hadir`, `Izin`, `Sakit`, `Alfa`/`Alpha`/`Alpa`)
  dengan kelas dan tanggal yang sama; selebihnya **Belum Selesai**.
  Jadwal lampau tanpa presensi tetap **Belum Selesai**, sedangkan jadwal mendatang
  yang sudah diisi presensi menjadi **Selesai**. Status mengambil data SQLite,
  bukan angka dummy atau pembandingan dengan tanggal hari ini.
- **Batasan struktur lama:** `presensi` mengacu pada `kelas_id` dan `tanggal`,
  tanpa `jadwal_id`. Jika ada dua jadwal kelas yang sama pada tanggal yang sama,
  sistem belum bisa membedakan catatan presensi keduanya. Tidak ada perubahan
  skema atau penghapusan data untuk revisi ini.
- Pengujian tambahan: `python -m unittest discover -s tests -v`.

## Revisi lanjutan — Light Mode dan Dark Mode

- Tambahan **Tema Tampilan: Light / Dark** pada dropdown foto profil kanan atas untuk Admin, Pengajar dan Siswa. Tidak ada opsi "Ikuti Sistem".
- **Light Mode** tetap menjadi default saat belum ada pilihan. Styling light lama tetap dipakai dan tidak diubah.
- **Dark Mode** memakai background navy gelap serta penyesuaian warna pada navbar, dashboard, Monitoring, kelas, jadwal, materi, tugas, presensi, profil, tabel, grafik, popup/modal, dan formulir. Ikon serta gambar kelas tetap digunakan.
- Tema langsung berubah tanpa memuat ulang halaman. Preferensi tersimpan di `localStorage` browser dengan kunci `fluenglo-theme-v1:<user_id>`. Pengguna lain pada browser yang sama mempunyai pilihan sendiri. Halaman login memakai tema terakhir di browser tersebut.
- File baru: `static/css/themes.css` dan `static/js/theme.js`. Perubahan terbatas pada `templates/base.html` (tombol + pengait tema) dan `templates/_macros.html` (ikon sun dan moon). Tidak ada perubahan route, query, skema, model, atau data SQLite.
- Untuk mencoba: masuk ke Fluenglo → klik foto profil kanan atas → **Tema Tampilan** → **Light** atau **Dark**. Jika tampilan lama masih muncul, lakukan hard refresh browser agar stylesheet baru terambil.
- **Pemeriksaan:** 20 template dapat dikompilasi dengan Jinja2; CSS baru lolos pemeriksaan parser; `theme.js` lolos sintaks Node; smoke test browser untuk menu dan pergantian tema, perubahan warna, serta penyimpanan tema setelah render ulang berhasil. Pengujian end-to-end Flask tidak dijalankan karena Flask/Werkzeug tidak tersedia di lingkungan pembuatan; jalankan tes di lingkungan proyek dengan `pip install -r requirements.txt` sebelum deploy.

**Data:** Gunakan database yang sudah berisi data. Jangan jalankan `seed.py` pada database produksi.


### Penyempurnaan tampilan Light / Dark (23 Oktober 2026)
- Warna nama kelas pada kartu/banner dipertahankan sama untuk Light dan Dark (navy pada foto terang, putih pada banner gradasi).
- Nama kelas di kartu, pemilih kelas, dan progres dashboard mempertahankan warna biru aslinya dengan latar teks terang khusus Dark Mode agar tetap terbaca.
- Kotak putih di belakang logo pada Dark Mode dihilangkan; diganti sorotan kuning transparan dari CSS, tanpa mengubah berkas logo asli.
- Tidak ada perubahan pada model, database, route, atau JavaScript tema.

## Revisi terarah (13 poin) — 23 Oktober 2026
- **Kelola Akun**: judul terlihat lagi. Tombol Back sejajar dengan Tambah Siswa/Pengajar; di Kelas/Jadwal sejajar tombol tambah.
- **Navigasi**: Back profil akun sendiri menuju Dashboard; jika profil dibuka lewat **Kelola Akun → Buka Profil**, Back kembali ke Kelola Akun.
- **Tabel**: bentuk kotak/sudut siku-siku; scroll vertikal pada daftar panjang dengan header tabel tetap terlihat serta scroll horizontal pada layar sempit.
- **Presensi**: hanya tanggal yang terdaftar di Jadwal tampil di pilihan pertemuan. Catatan presensi lama yang tanggalnya tidak cocok **tidak dihapus**.
- **Monitoring**: diagram donat tetap tampil abu-abu ketika belum ada catatan; pada Dashboard Siswa kondisi kosong grafik juga memiliki indikator donat abu-abu.
- **Layout**: panel dashboard/monitoring sejajar, memenuhi area konten tersedia; komponen responsif dipertahankan.
- **Form profil**: Batal mengembalikan isian sebelum edit dan menutup modal.
- **Password**: pergantian dan reset via admin yang benar-benar mengubah password kini dicatat satu kali secara atomik, sementara penggantian dengan password identik ditolak. Histori password sebelumnya tidak dimodifikasi.
- **Logo**: navbar menggunakan `static/images/logo_light.png` pada tema terang dan `static/images/logo_dark.png` pada tema gelap. Karena tidak ada dua aset baru yang terpisah pada unggahan, kedua file mula-mula **salinan logo PNG lama**; keduanya bebas diganti gambar final dengan nama yang sama. Efek cahaya kuning mengikuti bentuk logo di tema gelap.
- **Foto pengajar & username**: validasi keunikan username dijalankan di browser sebelum mengirim data sehingga file foto yang dipilih tidak hilang ketika username bentrok; server juga memverifikasi username sebelum menyimpan foto.
- **Navbar**: jarak antar menu diperkecil tanpa mengubah route atau ikon.

Pengujian: 18 regresi database berhasil, 20 template lolos parsing Jinja, JavaScript lolos pemeriksaan sintaks Node, dua pengujian interaksi browser mock berhasil (Batal/duplikat foto). **Pengujian Flask end-to-end penuh masih harus dilakukan** di mesin dengan Flask dan Werkzeug terinstal; `requirements.txt` tetap sama. Untuk database berisi data, jangan jalankan `seed.py`.

## Revisi Jadwal, Ruangan, dan Presensi per Pertemuan — Oktober 2026

Revisi ini **menggantikan keterbatasan `kelas + tanggal`** yang disebut pada catatan revisi-revisi sebelumnya. Struktur yang sudah ada tetap dipakai, hanya menambah `jadwal.ruangan` dan `presensi.jadwal_id` untuk membedakan dua sesi kelas pada tanggal sama.

- **Jadwal:** dropdown `Semua Kelas` atau kelas tertentu, untuk Admin/Pengajar/Siswa sesuai hak akses. Kolom **Ruangan** pada tabel jadwal dan opsi wajib **A01 / A02 / A03** pada form tambah/edit.
- **Monitoring:** dropdown seluruh kelas/kelas tertentu. Pengajar hanya melihat kelas yang berhak ia ajar; siswa memakai pilihan riwayat kelas lama seperti sebelumnya.
- **Validasi bentrok:** tanggal yang sama dan rentang jam yang saling *overlap* akan ditolak jika kelas sama, ruangan sama, atau pengajar yang **benar-benar bertugas** sama. Jadwal yang berdempetan tanpa tumpang tindih boleh. Dua ruang berbeda pada jam sama boleh **selama kelas dan pengajar yang bertugas juga berbeda**. Penolakan berlaku untuk tambah dan edit; pemeriksaan tambahan dalam transaksi `BEGIN IMMEDIATE` mencegah dua penyimpanan serentak meloloskan bentrok.
- **Pengajar pengganti:** jika terisi, ia yang dianggap bertugas pada sesi tersebut. Pengajar tetap hanya menjadi keterangan untuk penjadwalan tersebut dan boleh mengajar kelas lain pada jam yang sama, asalkan kelas lain itu memang menjadi tanggung jawabnya. Pengganti tidak boleh bentrok dengan kelas/jadwal lain sebagai pengajar tetap maupun pengganti.
- **Presensi:** setiap catatan kini mengacu ke **`jadwal.id`**. Presensi pagi dan sore, meski tanggal dan siswa sama, masing-masing memiliki panel, jam, ruangan, status serta record tersendiri. Ketika tidak ada catatan valid, status sesi belum selesai. Progres kelas (maksimum 8) dan grafik siswa mengikuti ID sesi, bukan jumlah tanggal berbeda. Jam dan ruangan terlihat pada pemilih presensi dan riwayat siswa.
- **Perlindungan histori:** jadwal yang sudah memiliki presensi tidak boleh dihapus, dan kelas, tanggal, serta jamnya tidak boleh diubah. Untuk jadwal lama yang tidak memiliki ruangan, `ruangan` tetap kosong sampai dipilih admin saat mengedit; sistem tidak menebaknya.
- **Migrasi:** `database.migrasi()` otomatis bekerja saat Flask dijalankan, termasuk migrasi dari `UNIQUE(tanggal, siswa_id, kelas_id)` ke `UNIQUE(jadwal_id, siswa_id)`, tanpa menghapus baris presensi. Baris lama dipasangkan ke **jadwal pertama berdasarkan jam** pada kelas/tanggal yang cocok. Bila dulu sudah ada dua sesi satu hari, tidak ada informasi jam per catatan lama untuk mengetahui sesi aslinya; **periksa hasil pemasangannya secara manual**. Baris lama tanpa jadwal yang cocok tetap tersimpan dengan `jadwal_id` kosong, tetapi tidak dihitung sebagai sesi selesai. Buat **cadangan `fluenglo.db`** sebelum menjalankan versi ini dengan data nyata. Jangan jalankan `seed.py`.
- **Logo Dark Mode:** navbar kini mencari `static/images/dark_logo.png`. Karena berkas tersebut tidak terdapat pada ZIP sumber yang diterima, proyek menggunakan **fallback `logo_dark.png`** jika `dark_logo.png` belum ada. Salin file asli `dark_logo.png` milikmu ke `web-pbo/static/images/` tanpa mengubah nama agar tampil seperti yang kamu inginkan. Light tetap menggunakan `logo_light.png`.

Uji perubahan: `python -m unittest discover -s tests -v` di lingkungan yang sudah menginstal dependensi. Pengujian dilakukan pada database sementara, tidak pada berkas data yang akan dipakai pengguna. Pengujian server Flask lengkap dengan semua interaksi browser **belum dilakukan** di lingkungan ini.


### Revisi Dashboard & Profil (24 Oktober 2026)
- Kartu **Jumlah Kelas Terjadwal** tetap mengikuti filter tahun. Kartu **Jumlah Pengajar** mencerminkan seluruh akun role pengajar di Kelola Akun, sedangkan rekap historis hanya menghitung pengajar yang terjadwal.
- Siswa dan admin bisa **menghapus foto siswa** melalui halaman profil (POST, pengajar tidak memiliki izin; admin tidak mendapat fitur ganti foto). File upload lama tidak dihapus dari storage.
- Tombol **Batal** pada modal formulir memulihkan isian awal **tanpa menutup modal**. Gunakan tombol X untuk menutup.
- Navbar kembali berbentuk pill. Glow kuning logo Dark Mode dihapus. Tombol diberi hover/focus subtle serta dukungan reduced motion.


### Catatan paket revisi: gambar lokal tetap milik pengguna
- Paket ZIP revisi ini sengaja **tidak menyertakan `static/images/`** supaya gambar dan logo milik Anda tidak tertimpa.
- Ekstrak atau salin revisi ke project Fluenglo yang **sudah memiliki folder `static/images/`**. Jangan menghapus folder tersebut.
- Untuk Dark Mode, project menggunakan `static/images/dark_logo.png`; untuk Light Mode, `static/images/logo_light.png`.
- Tombol tautan teks **Kembali ke tugas** dan **Kembali ke materi** di detail dihapus karena sudah ada tombol **Back**.

### Revisi 24 Oktober 2026 — Satu Back & lima Aktivitas Terbaru
- Halaman **Kelas** (`/kelas`, untuk Siswa/Pengajar) kini hanya menampilkan tombol Back milik header yang sejajar judul. Tombol Back otomatis tambahan pada `base.html` tidak lagi muncul untuk endpoint `lihat_kelas`.
- Halaman **Jadwal** (`/jadwal`) menggunakan template bersama seperti Kelola Jadwal; tombol Back otomatis tambahan juga dihindari agar tidak muncul dua kali.
- Bagian **Aktivitas Terbaru** Dashboard Admin/Pengajar/Siswa dibatasi maksimal **5 aktivitas terbaru**, urut waktu menurun. Aktivitas baru menggeser entri tertua dari daftar tampilan, **tanpa menghapus histori** di database. Pengajar sudah membatasi 5; Admin diubah 6 → 5 dan Siswa 4 → 5.
- Perubahan kode hanya di `templates/base.html` dan `database.py`; tambahan pengujian berada di `tests/test_back_aktivitas.py`.
- **Folder `static/images/` sengaja tidak dikirimkan dalam ZIP**. Biarkan aset logo dan gambar pribadi tetap berada di folder images pada project lokal saat menyalin revisi.

---

## Revisi gabungan UTS — 24 Oktober 2026

Paket ini **dimaksudkan untuk digabungkan** ke folder project Fluenglo yang sudah ada. **Jangan hapus data lama.** Sebelum menyalin, backup project dan khususnya `fluenglo.db`, `static/uploads/`, serta `static/images/`.

Paket ZIP revisi ini sengaja **tidak menyertakan**:

- `static/images/` — logo (termasuk `logo_light.png` / `logo_dark.png`) dan background milik pengguna tetap dipertahankan;
- `static/uploads/` — file materi, foto, jawaban, dan lampiran yang telah diunggah tidak akan tertimpa;
- `fluenglo.db` — data akun, kelas, presensi, dan nilai pengguna tidak akan tertimpa.

Jika menjalankan project di folder yang benar-benar baru (bukan merge), perlu menyalin ketiga aset lokal di atas dari project milik sendiri. **Jangan menjalankan `seed.py` pada database yang sudah berisi data.** Perintah menjalankan aplikasi tetap `python app.py` setelah dependensi di `requirements.txt` diinstal.

Perubahan yang dibatasi pada kebutuhan UTS:

1. Enam kartu Dashboard Admin dipadatkan, tidak mengubah judul dan sumber query statistik.
2. Status kelas otomatis `Belum Mulai` (0/8), `Berlangsung` (1–7/8), `Selesai` (8/8) berdasarkan **ID jadwal dengan presensi tercatat**, bukan jumlah siswa atau tanggal yang lewat.
3. Filter kelas di Jadwal serta Monitoring mengutamakan kelas yang belum selesai dan meletakkan kelas selesai di bawah, tanpa menghapus histori.
4. Jawaban tugas siswa tetap maksimal satu file. Sebelum dinilai, siswa boleh menghapusnya dan mengumpulkan lagi; sesudah dinilai harus menghubungi pengajar.
5. Pengajar boleh memasang satu file lampiran opsional ketika membuat tugas, dan mengganti atau menghapusnya saat mengedit. File terpisah dari berkas jawaban siswa.
6. Search pada Kelola Akun, Monitoring, Kelola Kelas, Jadwal, daftar pengumpulan pengajar, Materi/Tugas kelas; menggunakan data yang sudah dimuat sesuai hak akses.
7. Pagination 8 baris/item per halaman pada daftar/tabel besar. Search memfilter seluruh data pada daftar sebelum paginasi, bukan hanya halaman yang sedang terlihat.
8. Tombol Back di header halaman, sejajar judul, tanpa duplikasi tombol dari layout utama. Di detail tugas/materi, tujuan Back mengikuti halaman induknya.
9. Halaman publik/Login selalu Light Mode. Setelah login, preferensi tema masing-masing akun tetap berlaku.

**Migrasi minimal**: startup `database.migrasi()` menambahkan kolom `tugas.file_lampiran` bila belum ada. Tidak menghapus data historis. File lama tetap digunakan saat formulir edit tidak memilih lampiran baru.

**Verifikasi terbatas**: pengujian regresi database, parsing 20 template Jinja, sintaks JavaScript, browser mock-up untuk Search/pagination. Pengujian Flask end-to-end pada data produksi harus dijalankan di komputer tempat dependensi Flask tersedia; lingkungan penyusunan ZIP ini tidak dapat menginstal Flask karena jaringan terblokir.
