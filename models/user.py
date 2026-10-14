# PEMBAGIAN TUGAS DI models/user.py
# Penanggung jawab utama: JULPA (Backend Auth) untuk class User & Admin.
# Perubahan terbaru ditandai komentar "# BARU" / "# DIUBAH".

from abc import ABC, abstractmethod
import re
from datetime import date, datetime
import database

# ABSTRACTION: User jadi kerangka dasar, ga boleh dibuat objeknya langsung (ABC)
class User(ABC):
    def __init__(self, id, nama, username, password, role):
        self.id = id
        self.nama = nama
        self.username = username
        # ENCAPSULATION: password private (__), dari luar class ga bisa diutak-atik
        self.__password = password
        self.role = role

    # ENCAPSULATION: pencocokan password cuma lewat method ini, bukan dengan membandingkan
    # atribut dari luar class.
    # DIUBAH: password disimpan apa adanya supaya admin bisa membukanya lewat tombol mata
    # di Kelola Akun (keputusan kelompok: skala kursus kecil, admin yang membagikan akun).
    def cek_password(self, password):
        if not database.password_sudah_hash(self.__password):
            return self.__password == password

        # Akun lama yang terlanjur tersimpan ter-hash: dicocokkan lewat hash SEKALI ini saja,
        # lalu passwordnya ditulis ulang apa adanya. Jadi akun lama tetap bisa login dan
        # otomatis kebaca admin setelah pemiliknya login sekali, tanpa perlu di-reset manual.
        if not database.cocok_hash_lama(self.__password, password):
            return False
        database.edit_user(self.id, password=password)
        self.__password = password
        return True

    # ENCAPSULATION: satu-satunya pintu buat ganti password, lama diverifikasi dulu
    def ganti_password(self, password_lama, password_baru):
        if not self.cek_password(password_lama):
            raise ValueError("Password lama salah.")
        if not User.validasi_password(password_baru):
            raise ValueError("Password minimal 8 karakter dan wajib kombinasi huruf + angka.")
        if password_baru == password_lama:
            raise ValueError("Password baru tidak boleh sama dengan password lama.")
        database.edit_user(self.id, password=password_baru)
        # DIUBAH: password lama & barunya ikut dicatat, dipakai kartu Riwayat Perubahan Password
        database.catat_riwayat_password(self.id, password_lama, password_baru)
        self.__password = password_baru

    @staticmethod
    def validasi_username(username):
        return len(username or "") >= 5

    @staticmethod
    def validasi_password(password):
        pwd = password or ""
        if len(pwd) < 8:
            return False
        has_letter = re.search(r'[a-zA-Z]', pwd)
        has_digit = re.search(r'\d', pwd)
        return bool(has_letter and has_digit)

    @staticmethod
    def rapikan_whatsapp(nomor):
        return re.sub(r'[\s-]', '', nomor or "")

    @staticmethod
    def validasi_whatsapp(nomor):
        # aturannya sama dengan validasi di app.js (08xxxxxxxxx / 628xxxxxxxxx / +628xxxxxxxxx)
        return bool(re.fullmatch(r'(\+62|62|0)8[1-9]\d{6,10}', User.rapikan_whatsapp(nomor)))

    @staticmethod
    def validasi_email(email):
        return bool(re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email or ""))

    @staticmethod
    def cek_kontak(whatsapp, email):
        """Aturan Ubah Profil (siswa & pengajar sama): WA wajib & valid, email boleh kosong
        tapi kalau diisi harus valid. Balikin (wa_rapi, email_rapi_atau_None)."""
        whatsapp = (whatsapp or "").strip()
        email = (email or "").strip()
        if not User.validasi_whatsapp(whatsapp):
            raise ValueError("Nomor WhatsApp wajib diisi dengan format valid (contoh: 08123456789).")
        if email and not User.validasi_email(email):
            raise ValueError("Format email tidak valid.")
        return User.rapikan_whatsapp(whatsapp), (email or None)

    # POLYMORPHISM: hak akses dicek lewat method yang sama, tiap role override sendiri,
    # jadi route cukup panggil user.boleh_akses_kelas(...) tanpa if role == ...
    def boleh_akses_kelas(self, kelas_id):
        return False

    def boleh_lihat_siswa(self, siswa_row):
        return False

    def boleh_lihat_pengajar(self, pengajar_id):
        return False

    # ABSTRACTION: wajib ditulis ulang di tiap subclass
    @abstractmethod
    def tampilkan_menu(self):
        pass

# INHERITANCE: Siswa turunan User, id/nama/username/cek_password/ganti_password ikut diwarisi
class Siswa(User):
    def __init__(self, id, nama, username, password, kelas_id=None,
                 foto=None, whatsapp=None, alamat=None, email=None):
        super().__init__(id, nama, username, password, role="siswa")
        self.kelas_id = kelas_id
        self.foto = foto or "default_avatar.png"
        self.whatsapp = whatsapp
        self.alamat = alamat
        self.email = email

    # BARU: data siswa yang diisi admin (tambah/edit akun): WA & alamat wajib
    @staticmethod
    def cek_data_admin(whatsapp, alamat):
        whatsapp = (whatsapp or "").strip()
        alamat = (alamat or "").strip()
        if not User.validasi_whatsapp(whatsapp):
            raise ValueError("Nomor WhatsApp wajib diisi dengan format valid (contoh: 08123456789).")
        if not alamat:
            raise ValueError("Alamat siswa wajib diisi.")
        return User.rapikan_whatsapp(whatsapp), alamat

    # POLYMORPHISM: Siswa, Pengajar, dan Admin sama-sama punya lihat_profil(), tapi isi
    # dict yang dikembalikan beda. Route /profil cukup memanggilnya tanpa cek role.
    # ENCAPSULATION: yang keluar cuma data yang memang boleh dilihat — password tidak ikut.
    def lihat_profil(self):
        kelas = database.ambil_kelas_siswa(self.id)
        return {
            "id": self.id,
            "nama": self.nama,
            "username": self.username,
            "foto": self.foto,
            "whatsapp": self.whatsapp,
            "email": self.email,
            "alamat": self.alamat,
            "kelas": kelas["nama"] if kelas else "-",
        }

    def edit_profil(self, whatsapp, email="", foto=None, alamat=None):
        """Ubah Profil siswa. WA wajib valid, email opsional, alamat boleh dikosongkan.
        alamat=None artinya alamat tidak diubah. Ganti password lewat ganti_password() (warisan User)."""
        whatsapp, email = User.cek_kontak(whatsapp, email)  # INHERITANCE: aturan kontak dipakai bareng Pengajar

        perubahan = {"no_whatsapp": whatsapp, "email": email}
        if alamat is not None:
            perubahan["alamat"] = alamat.strip() or None
        if foto:
            perubahan["foto"] = foto
        database.edit_user(self.id, **perubahan)

        self.whatsapp = whatsapp
        self.email = email
        if alamat is not None:
            self.alamat = perubahan["alamat"]
        if foto:
            self.foto = foto

    def lihat_semua_kelas(self):
        """BARU: kelas aktif + kelas-kelas yang sudah ditamatkan (bertanda 'selesai').
        Dipakai halaman Kelas dan pemilih kelas di halaman Jadwal."""
        hasil, sudah = [], set()
        aktif = self.lihat_kelas()
        if aktif:
            hasil.append(dict(aktif, selesai=False))
            sudah.add(aktif["id"])
        for row in database.ambil_kelas_lulus_siswa(self.id):
            if row["id"] not in sudah:
                hasil.append(dict(database.kelas_jadi_dict(row), selesai=True))
                sudah.add(row["id"])
        return hasil

    def id_kelas_saya(self):
        """BARU: semua kelas_id yang boleh dibuka siswa ini (aktif + yang sudah lulus)."""
        return [k["id"] for k in self.lihat_semua_kelas()]

    # ABSTRACTION: siswa cukup bilang "tunjukkan kelasku"; join tabel users-kelas dan
    # pengumpulan daftar pengajarnya disembunyikan di database.py.
    def lihat_kelas(self):
        """Melihat kelas yang diikuti beserta nama pengajarnya (key pengajar_list)."""
        kelas = database.ambil_kelas_siswa(self.id)
        if not kelas:
            return None
        return database.kelas_jadi_dict(kelas)

    def lihat_jadwal(self, kelas_id=None):
        """DIUBAH: tanpa argumen = jadwal kelas aktif (diprioritaskan). Kalau siswa memilih
        kelas lain yang pernah dia ikuti, jadwal kelas itu yang ditampilkan."""
        pilihan = self.id_kelas_saya()
        if not pilihan:
            return []
        if kelas_id is None or kelas_id not in pilihan:
            kelas_id = self.kelas_id if self.kelas_id in pilihan else pilihan[0]
        return database.ambil_jadwal_by_kelas(kelas_id)

    def kumpul_tugas(self, tugas, jawaban):
        """Mengumpulkan atau memperbarui jawaban tugas siswa."""
        from models.akademik import Pengumpulan

        tugas_id = getattr(tugas, "id", tugas)

        try:
            tugas_id = int(tugas_id)
        except (TypeError, ValueError):
            raise ValueError("Tugas tidak valid.")

        if not (jawaban or "").strip():
            raise ValueError("File jawaban wajib dipilih.")

        data_tugas = database.ambil_tugas_by_id(tugas_id)

        if not data_tugas:
            raise ValueError("Tugas tidak ditemukan.")

        # Pastikan tugas tersebut milik kelas siswa.
        if not self.boleh_akses_kelas(data_tugas["kelas_id"]):
            raise ValueError("Tugas ini bukan untuk kelas kamu.")

        pengumpulan = Pengumpulan(
            id=None,
            tugas_id=tugas_id,
            siswa_id=self.id
        )
        pengumpulan.submit_jawaban(jawaban)

        return pengumpulan

    def komentar_tugas(self, tugas, isi):
        """Siswa memberikan komentar atau pertanyaan pada tugas.
        DIUBAH: komentar masuk ke percakapan privat milik siswa ini sendiri (siswa_id = id-nya),
        jadi yang bisa membaca cuma dia dan pengajar kelasnya."""
        from models.akademik import Komentar

        tugas_id = getattr(tugas, "id", tugas)

        try:
            tugas_id = int(tugas_id)
        except (TypeError, ValueError):
            raise ValueError("Tugas tidak valid.")

        isi = (isi or "").strip()
        if not isi:
            raise ValueError("Komentar tidak boleh kosong.")

        data_tugas = database.ambil_tugas_by_id(tugas_id)
        if not data_tugas:
            raise ValueError("Tugas tidak ditemukan.")

        if not self.boleh_akses_kelas(data_tugas["kelas_id"]):
            raise ValueError("Kamu tidak memiliki akses ke tugas ini.")

        komentar = Komentar(
            id=None,
            tugas_id=tugas_id,
            user_id=self.id,
            isi_komentar=isi,
            waktu=None,
            siswa_id=self.id  # DIUBAH: percakapan ini milik siswa ybs
        )
        komentar.tambah_komentar()

        return komentar

    def lihat_monitoring(self):
        """Satu menu monitoring: rekap presensi, rekap nilai, dan catatan akhir dari pengajar."""
        # (rekap presensi, rekap nilai, daftar nilai, catatan akhir) digabung di sini.
        presensi = {"hadir": 0, "izin": 0, "sakit": 0, "alfa": 0}
        for r in database.rekap_presensi_siswa(self.id):
            status = (r["status"] or "").lower()
            if status == "alpha":
                status = "alfa"
            if status in presensi:
                presensi[status] += r["jumlah"]

        rekap_nilai = database.rekap_nilai_siswa(self.id)
        daftar_nilai = database.ambil_daftar_nilai_siswa(self.id)
        catatan = database.ambil_catatan_akhir_by_siswa(self.id)

        return {
            "presensi": presensi,
            "nilai": dict(rekap_nilai) if rekap_nilai else {},
            "daftar_nilai": [dict(item) for item in daftar_nilai],
            "catatan_akhir": [dict(item) for item in catatan],
        }

    # DIUBAH: termasuk kelas lama yang sudah dia tamatkan (masih boleh dilihat, bukan diubah)
    def boleh_akses_kelas(self, kelas_id):
        return kelas_id in self.id_kelas_saya()

    def boleh_lihat_siswa(self, siswa_row):
        return siswa_row["id"] == self.id

    def boleh_lihat_pengajar(self, pengajar_id):
        # siswa cuma boleh lihat profil pengajar dari kelas-kelas yang pernah dia ikuti
        for kelas_id in self.id_kelas_saya():
            kelas = database.ambil_kelas_by_id(kelas_id)
            if kelas and pengajar_id in [p["id"] for p in database.ambil_pengajar_kelas(kelas)]:
                return True
        return False

    # DIUBAH: "Materi" & "Tugas" dikeluarkan dari navbar karena dua halaman itu selalu
    # dibuka dari dalam sebuah kelas (butuh kelas_id), bukan dari menu atas. Sekarang
    # isinya persis seperti dokumen: Kelas, Jadwal, Monitoring Anak.
    def tampilkan_menu(self):
        # DIUBAH: "Profil" dikeluarkan dari navbar, dibuka lewat dropdown nama pengguna
        return ["Kelas", "Jadwal", "Monitoring Anak"]

# INHERITANCE: Pengajar juga turunan User, plus atribut sendiri (foto, wa, alamat, email, nik)
class Pengajar(User):
    def __init__(self, id, nama, username, password, foto=None, whatsapp=None,
                 biodata=None, alamat=None, email=None, nik=None):
        super().__init__(id, nama, username, password, role="pengajar")
        self.foto = foto or "default_avatar.png"
        self.whatsapp = whatsapp
        self.biodata = biodata
        self.alamat = alamat
        self.email = email
        self.nik = nik

    @staticmethod
    def validasi_nik(nik):
        return bool(re.fullmatch(r'\d{16}', (nik or "").strip()))

    @staticmethod
    def cek_data_admin(whatsapp, alamat, nik):
        """Data pengajar yang diisi admin: WA, alamat, NIK semuanya wajib."""
        whatsapp = (whatsapp or "").strip()
        alamat = (alamat or "").strip()
        nik = (nik or "").strip()
        if not User.validasi_whatsapp(whatsapp):
            raise ValueError("Nomor WhatsApp wajib diisi dengan format valid (contoh: 08123456789).")
        if not alamat:
            raise ValueError("Alamat pengajar wajib diisi.")
        if not Pengajar.validasi_nik(nik):
            raise ValueError("Nomor KTP harus 16 digit angka.")
        return User.rapikan_whatsapp(whatsapp), alamat, nik

    def lihat_profil(self):
        """Profil lengkap (NIK ikut). Hanya buat admin dan pengajar ybs."""
        return {
            "id": self.id, "nama": self.nama, "username": self.username,
            "foto": self.foto, "whatsapp": self.whatsapp, "email": self.email,
            "biodata": self.biodata, "alamat": self.alamat, "nik": self.nik,
        }

    # (ada NIK) khusus admin & pengajar ybs, profil_publik() versi aman buat siswa.
    # NIK tidak pernah bocor ke siswa karena memang nggak pernah dimasukkan ke dict ini.
    def profil_publik(self):
        """Versi buat siswa: nama, username, WA, email, alamat, tanpa NIK."""
        return {
            "id": self.id, "nama": self.nama, "username": self.username,
            "foto": self.foto, "whatsapp": self.whatsapp, "email": self.email,
            "biodata": self.biodata, "alamat": self.alamat,
        }

    def edit_profil(self, whatsapp, email="", foto=None, alamat=None):
        """Ubah Profil pengajar: WA wajib valid, email opsional, alamat tidak boleh kosong.
        alamat=None artinya alamat tidak diubah. NIK cuma bisa diubah admin."""
        whatsapp, email = User.cek_kontak(whatsapp, email)
        if alamat is not None:
            alamat = alamat.strip()
            if not alamat:
                raise ValueError("Alamat tidak boleh dikosongkan.")

        perubahan = {"no_whatsapp": whatsapp, "email": email}
        if alamat is not None:
            perubahan["alamat"] = alamat
        if foto:
            perubahan["foto"] = foto
        database.edit_user(self.id, **perubahan)

        self.whatsapp = whatsapp
        self.email = email
        if alamat is not None:
            self.alamat = alamat
        if foto:
            self.foto = foto

    def lihat_kelas_diajar(self):
        return database.ambil_kelas_by_pengajar(self.id)

    def lihat_jadwal_mengajar(self):
        return database.ambil_jadwal_by_pengajar(self.id)

    @staticmethod
    def _ke_int(nilai, nama):
        try:
            return int(getattr(nilai, "id", nilai))
        except (TypeError, ValueError):
            raise ValueError(f"{nama} tidak valid.")

    def upload_materi(self, kelas, judul, kategori, file):
        """Menyimpan materi untuk kelas yang diajar."""
        # ENCAPSULATION: syarat sah sebuah materi (judul & file wajib, pengajarnya harus
        # memang mengajar kelas itu) dikunci di method ini, bukan dititip ke route.
        kelas_id = Pengajar._ke_int(kelas, "Kelas")

        judul = (judul or "").strip()
        kategori = (kategori or "").strip() or "Umum"
        file = (file or "").strip()

        if not judul:
            raise ValueError("Judul materi wajib diisi.")
        if not file:
            raise ValueError("File materi wajib diisi.")
        if not self.mengajar_kelas(kelas_id):
            raise ValueError("Kamu bukan pengajar di kelas ini.")

        return database.tambah_materi(
            judul=judul,
            kategori=kategori,
            file_path=file,
            kelas_id=kelas_id,
            pengajar_id=self.id
        )

    def edit_materi(self, materi, judul, kategori, file=None):
        """Mengubah judul/kategori materi, file boleh diganti (kosong = file lama dipakai terus)."""
        materi_id = Pengajar._ke_int(materi, "Materi")
        data = database.ambil_materi_by_id(materi_id)
        if not data:
            raise ValueError("Materi tidak ditemukan.")
        if not self.mengajar_kelas(data["kelas_id"]):
            raise ValueError("Kamu bukan pengajar di kelas ini.")

        judul = (judul or "").strip()
        kategori = (kategori or "").strip() or "Umum"
        if not judul:
            raise ValueError("Judul materi wajib diisi.")

        database.edit_materi(materi_id, judul, kategori, (file or "").strip() or None)
        return data["kelas_id"]

    def hapus_materi(self, materi):
        """Menghapus materi di kelas yang diajar. Balikin kelas_id-nya (buat redirect)."""
        materi_id = Pengajar._ke_int(materi, "Materi")
        data = database.ambil_materi_by_id(materi_id)
        if not data:
            raise ValueError("Materi tidak ditemukan.")
        if not self.mengajar_kelas(data["kelas_id"]):
            raise ValueError("Kamu bukan pengajar di kelas ini.")
        database.hapus_materi(materi_id)
        return data["kelas_id"]

    @staticmethod
    def _cek_deadline(teks):
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"):
            try:
                datetime.strptime(teks, fmt)
                return teks
            except ValueError:
                continue
        raise ValueError("Format deadline tidak valid.")

    def buat_tugas(self, kelas, judul, deskripsi, deadline):
        """Membuat tugas untuk kelas yang diajar."""
        kelas_id = Pengajar._ke_int(kelas, "Kelas")

        judul = (judul or "").strip()
        deskripsi = (deskripsi or "").strip()
        deadline = (deadline or "").strip()

        if not judul:
            raise ValueError("Judul tugas wajib diisi.")
        if not deadline:
            raise ValueError("Deadline tugas wajib diisi.")
        Pengajar._cek_deadline(deadline)
        if not self.mengajar_kelas(kelas_id):
            raise ValueError("Kamu bukan pengajar di kelas ini.")

        return database.tambah_tugas(
            judul=judul,
            deskripsi=deskripsi,
            deadline=deadline,
            kelas_id=kelas_id,
            pengajar_id=self.id
        )

    def beri_nilai(self, pengumpulan, nilai):
        """Memberi atau memperbarui nilai tugas siswa. pengumpulan boleh objek atau id pengumpulan."""
        pengumpulan_id = Pengajar._ke_int(pengumpulan, "Data pengumpulan")

        try:
            nilai = float(nilai)
        except (TypeError, ValueError):
            raise ValueError("Nilai harus berupa angka.")

        if not 0 <= nilai <= 100:
            raise ValueError("Nilai harus antara 0 sampai 100.")

        data = database.ambil_pengumpulan_by_id(pengumpulan_id)
        if not data:
            raise ValueError("Pengumpulan tugas tidak ditemukan.")

        tugas = database.ambil_tugas_by_id(data["tugas_id"])
        if not tugas:
            raise ValueError("Tugas tidak ditemukan.")

        # guru 1 & guru 2 kelas tsb boleh menilai, bukan cuma yang bikin tugasnya
        if not self.mengajar_kelas(tugas["kelas_id"]):
            raise ValueError("Kamu tidak berhak menilai tugas ini.")

        return database.beri_nilai(
            tugas_id=data["tugas_id"],
            siswa_id=data["siswa_id"],
            pengajar_id=self.id,
            nilai=nilai
        )

    def komentar_tugas(self, tugas, isi, siswa=None):
        """Pengajar memberikan masukan pada tugas SEORANG siswa.
        DIUBAH: wajib menyebut siswanya, karena komentar sekarang percakapan privat
        pengajar <-> satu siswa, bukan papan komentar sekelas."""
        from models.akademik import Komentar

        tugas_id = Pengajar._ke_int(tugas, "Tugas")
        siswa_id = Pengajar._ke_int(siswa, "Siswa")

        isi = (isi or "").strip()
        if not isi:
            raise ValueError("Komentar tidak boleh kosong.")

        data_tugas = database.ambil_tugas_by_id(tugas_id)
        if not data_tugas:
            raise ValueError("Tugas tidak ditemukan.")

        if not self.mengajar_kelas(data_tugas["kelas_id"]):
            raise ValueError("Kamu tidak berhak mengomentari tugas ini.")

        komentar = Komentar(
            id=None,
            tugas_id=tugas_id,
            user_id=self.id,
            isi_komentar=isi,
            waktu=None,
            siswa_id=siswa_id
        )
        komentar.tambah_komentar()

        return komentar

    def edit_tugas(self, tugas, judul, deskripsi, deadline):
        """BARU: ubah tugas di kelas yang diajar. Balikin kelas_id-nya (buat redirect)."""
        tugas_id = Pengajar._ke_int(tugas, "Tugas")
        data = database.ambil_tugas_by_id(tugas_id)
        if not data:
            raise ValueError("Tugas tidak ditemukan.")
        if not self.mengajar_kelas(data["kelas_id"]):
            raise ValueError("Kamu bukan pengajar di kelas ini.")

        judul = (judul or "").strip()
        deskripsi = (deskripsi or "").strip()
        deadline = (deadline or "").strip()
        if not judul:
            raise ValueError("Judul tugas wajib diisi.")
        if not deadline:
            raise ValueError("Deadline tugas wajib diisi.")
        Pengajar._cek_deadline(deadline)

        database.edit_tugas(tugas_id, judul, deskripsi, deadline)
        return data["kelas_id"]

    def hapus_tugas(self, tugas):
        """BARU: hapus tugas di kelas yang diajar. Balikin kelas_id-nya (buat redirect)."""
        tugas_id = Pengajar._ke_int(tugas, "Tugas")
        data = database.ambil_tugas_by_id(tugas_id)
        if not data:
            raise ValueError("Tugas tidak ditemukan.")
        if not self.mengajar_kelas(data["kelas_id"]):
            raise ValueError("Kamu bukan pengajar di kelas ini.")
        database.hapus_tugas(tugas_id)
        return data["kelas_id"]

    def mengajar_kelas(self, kelas_id):
        # di dalam objek Pengajar sendiri, bukan ditulis ulang di setiap route.
        """True jika pengajar ini adalah guru 1 atau guru 2 di kelas tsb."""
        row = database.ambil_kelas_by_id(kelas_id)
        return row is not None and self.id in (row["pengajar_id"], row["pengajar_id2"])

    # BARU: pertemuan di mana dia jadi GURU PENGGANTI. Dua method, dua pertanyaan berbeda:
    # "kelas apa saja yang boleh dia buka" dan "tanggal mana saja yang boleh dia isi".
    def kelas_pengganti(self):
        return {j["kelas_id"] for j in database.ambil_jadwal_pengganti(self.id)}

    def tanggal_pengganti(self, kelas_id):
        return {j["tanggal"] for j in database.ambil_jadwal_pengganti(self.id)
                if j["kelas_id"] == kelas_id and j["tanggal"]}

    def boleh_akses_kelas(self, kelas_id):
        return self.mengajar_kelas(kelas_id) or kelas_id in self.kelas_pengganti()

    def boleh_lihat_siswa(self, siswa_row):
        return siswa_row["kelas_id"] is not None and self.mengajar_kelas(siswa_row["kelas_id"])

    def boleh_lihat_pengajar(self, pengajar_id):
        return True

    def catat_presensi(self, kelas, siswa, status, tanggal=None):
        """Catat presensi satu siswa. kelas/siswa boleh objek atau id.
        tanggal format YYYY-MM-DD, default hari ini (harus ada di jadwal kelas)."""
        kelas_id = getattr(kelas, "id", kelas)
        siswa_id = getattr(siswa, "id", siswa)
        tanggal = tanggal or date.today().isoformat()
        return self.catat_presensi_kelas(kelas_id, tanggal, {siswa_id: status})

    def catat_presensi_kelas(self, kelas, tanggal, data_status, kosongkan=None):
        """Catat presensi banyak siswa sekaligus. data_status: {siswa_id: status}.
        DIUBAH: + kosongkan, daftar siswa yang centangnya dilepas pengajar supaya
        presensinya ikut terhapus, bukan tertinggal memakai status lama."""
        from models.presensi import Presensi
        kelas_id = getattr(kelas, "id", kelas)
        try:
            kelas_id = int(kelas_id)
        except (TypeError, ValueError):
            raise ValueError("Kelas tidak valid.")
        # DIUBAH: guru pengganti boleh mengisi presensi, TAPI cuma pada tanggal pertemuan
        # yang memang dijadwalkan untuk dia. Di luar tanggal itu tetap ditolak.
        if not self.mengajar_kelas(kelas_id):
            if str(tanggal or "").strip() not in self.tanggal_pengganti(kelas_id):
                raise ValueError("Kamu bukan pengajar di kelas ini.")

        kosongkan = list(kosongkan or [])
        if not data_status and not kosongkan:
            raise ValueError("Belum ada status kehadiran yang dipilih.")

        jumlah = Presensi.simpan_massal(kelas_id, tanggal, data_status) if data_status else 0
        if kosongkan:
            Presensi.hapus_banyak(kelas_id, tanggal, kosongkan)
        return jumlah

    def beri_catatan_akhir(self, kelas, siswa, isi, lulus=False):
        """Membuat atau memperbarui catatan akhir siswa (satu siswa satu catatan per kelas).
        DIUBAH: + lulus. Pengajar mencentangnya kalau siswa sudah menamatkan seluruh
        pertemuan kelas ini dan boleh lanjut ke tahap berikutnya."""
        kelas_id = getattr(kelas, "id", kelas)
        siswa_id = getattr(siswa, "id", siswa)

        try:
            kelas_id = int(kelas_id)
            siswa_id = int(siswa_id)
        except (TypeError, ValueError):
            raise ValueError("Kelas atau siswa tidak valid.")

        isi = (isi or "").strip()
        if not isi:
            raise ValueError("Catatan akhir tidak boleh kosong.")

        if not self.mengajar_kelas(kelas_id):
            raise ValueError("Kamu bukan pengajar di kelas ini.")

        return database.tambah_catatan_akhir(
            siswa_id=siswa_id,
            kelas_id=kelas_id,
            pengajar_id=self.id,
            catatan=isi,
            lulus=lulus
        )

    def hapus_catatan_akhir(self, catatan):
        """BARU: pengajar menghapus catatan akhir di kelas yang dia ajar.
        Balikin siswa_id-nya, buat redirect balik ke halaman monitoring anak itu."""
        # lagi di query database.hapus_catatan_akhir() yang ikut menyaring kelas miliknya.
        catatan_id = Pengajar._ke_int(catatan, "Catatan akhir")
        data = database.ambil_catatan_akhir_by_id(catatan_id)
        if not data:
            raise ValueError("Catatan akhir tidak ditemukan.")
        if not self.mengajar_kelas(data["kelas_id"]):
            raise ValueError("Kamu bukan pengajar di kelas ini.")
        if not database.hapus_catatan_akhir(catatan_id, self.id):
            raise ValueError("Catatan akhir gagal dihapus.")
        return data["siswa_id"]

    def lihat_monitoring_siswa(self, siswa_id):
        """Buka monitoring seorang siswa dari profil siswa (cuma siswa di kelas yang diajar)."""
        # siswa mana pun sedangkan versi Pengajar ini dibatasi kelas yang dia ajar.
        row = database.ambil_user_by_id(siswa_id)
        if not row or row["role"] != "siswa" or not self.boleh_lihat_siswa(row):
            raise ValueError("Siswa tidak ditemukan di kelas yang kamu ajar.")
        return buat_objek_user(row).lihat_monitoring()

    # POLYMORPHISM: nama method sama, isi menu beda dari Siswa.
    # DIUBAH: label disamakan dengan daftar menu di base.html ("Kelas", "Jadwal"). Sebelumnya
    # labelnya "Kelas dan Jadwal Mengajar" dkk yang tidak dikenal navbar, jadi pengajar cuma
    # kebagian menu Profil. Materi/Tugas/Presensi/Catatan Akhir tetap diakses dari dalam kelas.
    def tampilkan_menu(self):
        # DIUBAH: "Profil" dikeluarkan dari navbar, dibuka lewat dropdown nama pengguna
        return ["Kelas", "Jadwal"]

# INHERITANCE: Admin turunan User juga
class Admin(User):
    def __init__(self, id, nama, username, password):
        super().__init__(id, nama, username, password, role="admin")

    def lihat_profil(self):
        return {"id": self.id, "nama": self.nama, "username": self.username}

    def kelola_akun(self, aksi, **data):
        if aksi == "tambah":
            username = (data.get("username") or "").strip()
            password = data.get("password")
            role = data.get("role")

            if role not in ("siswa", "pengajar"):
                raise ValueError("Role harus siswa atau pengajar.")
            if not (data.get("nama") or "").strip():
                raise ValueError("Nama lengkap wajib diisi.")
            if not User.validasi_username(username):
                raise ValueError("Username minimal 5 karakter.")
            if not User.validasi_password(password):
                raise ValueError("Password minimal 8 karakter dan wajib kombinasi huruf + angka.")

            no_wa = alamat = nik = None
            if role == "pengajar":
                no_wa, alamat, nik = Pengajar.cek_data_admin(
                    data.get("whatsapp"), data.get("alamat"), data.get("nik")
                )
            else:  # DIUBAH: siswa sekarang juga wajib WA + alamat (sesuai desain)
                no_wa, alamat = Siswa.cek_data_admin(data.get("whatsapp"), data.get("alamat"))

            kelas_id = None
            if role == "siswa":
                if not database.ambil_semua_kelas():
                    raise ValueError("Belum ada kelas. Buat kelas terlebih dahulu sebelum membuat akun siswa.")
                try:
                    kelas_id = int(data.get("kelas_id"))
                except (TypeError, ValueError):
                    raise ValueError("Pilih kelas untuk siswa.")
                if database.ambil_kelas_by_id(kelas_id) is None:
                    raise ValueError("Kelas yang dipilih tidak ditemukan.")

            return database.tambah_user(
                nama=data["nama"].strip(),
                username=username,
                password=password,
                role=role,
                foto=data.get("foto"),
                no_whatsapp=no_wa,
                biodata=data.get("biodata"),
                kelas_id=kelas_id,
                alamat=alamat,
                nik=nik,
            )
        elif aksi == "edit":
            try:
                user_id = int(data["user_id"])
            except (KeyError, TypeError, ValueError):
                raise ValueError("Akun tidak valid.")
            target = database.ambil_user_by_id(user_id)
            if target is None or target["role"] == "admin":
                raise ValueError("Akun tidak ditemukan.")

            username = (data.get("username") or "").strip()
            password = data.get("password")
            nama = (data.get("nama") or "").strip()

            if not nama:
                raise ValueError("Nama lengkap wajib diisi.")
            if not User.validasi_username(username):
                raise ValueError("Username minimal 5 karakter.")
            if password and not User.validasi_password(password):
                raise ValueError("Password minimal 8 karakter dan wajib kombinasi huruf + angka.")

            perubahan = {"nama": nama, "username": username}
            if password:  # kosong = password tidak diubah
                perubahan["password"] = password
            if target["role"] == "pengajar":
                no_wa, alamat, nik = Pengajar.cek_data_admin(
                    data.get("whatsapp"), data.get("alamat"), data.get("nik")
                )
                perubahan["no_whatsapp"] = no_wa
                perubahan["alamat"] = alamat
                perubahan["nik"] = nik
                if data.get("foto"):
                    perubahan["foto"] = data["foto"]
            if target["role"] == "siswa":  # BARU: admin bisa ubah WA, alamat, dan kelas siswa
                no_wa, alamat = Siswa.cek_data_admin(data.get("whatsapp"), data.get("alamat"))
                try:
                    kelas_id = int(data.get("kelas_id"))
                except (TypeError, ValueError):
                    raise ValueError("Pilih kelas untuk siswa.")
                if database.ambil_kelas_by_id(kelas_id) is None:
                    raise ValueError("Kelas yang dipilih tidak ditemukan.")
                perubahan.update(no_whatsapp=no_wa, alamat=alamat, kelas_id=kelas_id)
            return database.edit_user(user_id, **perubahan)
        elif aksi == "hapus":
            try:
                user_id = int(data["user_id"])
            except (KeyError, TypeError, ValueError):
                raise ValueError("Akun tidak valid.")
            target = database.ambil_user_by_id(user_id)
            if target is None or target["role"] == "admin":
                raise ValueError("Akun tidak ditemukan.")
            if target["role"] == "pengajar":
                # pengajar yang masih dipakai kelas/jadwal/materi/tugas nggak boleh dihapus,
                # kalau nggak datanya jadi nunjuk ke akun yang sudah nggak ada
                terkait = database.hitung_keterkaitan_pengajar(user_id)
                if any(terkait.values()):
                    raise ValueError(
                        f"{target['nama']} tidak bisa dihapus karena masih terdaftar di "
                        f"{terkait['kelas']} kelas, {terkait['jadwal']} jadwal, "
                        f"{terkait['materi']} materi, dan {terkait['tugas']} tugas."
                    )
            return database.hapus_user(user_id)
        else:
            raise ValueError(f"Aksi tidak dikenal: {aksi}")

    def kelola_kelas(self, aksi, **data):
        from models.akademik import Kelas
        if aksi == "tambah":
            nama, pengajar_id, pengajar_id2 = Kelas.cek_input(
                data["nama_kelas"], data["pengajar_id"], data.get("pengajar_id2")
            )
            return database.tambah_kelas(nama, pengajar_id, pengajar_id2)

        kelas = Kelas.muat(data["kelas_id"])

        if aksi == "edit":
            nama, pengajar_id, pengajar_id2 = Kelas.cek_input(
                data["nama_kelas"], data["pengajar_id"], data.get("pengajar_id2"), exclude_id=kelas.id
            )
            return database.edit_kelas(kelas.id, nama, pengajar_id, pengajar_id2)

        elif aksi == "hapus":
            terkait = database.hitung_data_terkait_kelas(kelas.id)
            if any(terkait.values()):
                raise ValueError(
                    f"Kelas '{kelas.nama_kelas}' tidak bisa dihapus karena masih punya "
                    f"{terkait['materi']} materi, {terkait['tugas']} tugas, dan "
                    f"{terkait['presensi']} data presensi."
                )
            return database.hapus_kelas(kelas.id)

        elif aksi == "tambah_siswa":
            return kelas.tambah_siswa(data["siswa_id"])

        elif aksi == "hapus_siswa":
            return kelas.hapus_siswa(data["siswa_id"])

        else:
            raise ValueError(f"Aksi tidak dikenal: {aksi}")

    def kelola_jadwal(self, aksi, **data):
        from models.akademik import Jadwal
        if aksi == "tambah":
            # DIUBAH: + pengganti, ikut dicek di Jadwal.cek_input dan ikut disimpan
            kelas_id, pengajar_id, jam, tanggal, materi, pengganti = Jadwal.cek_input(
                data["hari"], data["jam_mulai"], data["jam_selesai"],
                data["kelas_id"], data["pengajar_id"],
                tanggal=data.get("tanggal"), materi=data.get("materi"),
                pengganti=data.get("pengganti"),
            )
            return database.tambah_jadwal(data["hari"], jam, kelas_id, pengajar_id, tanggal,
                                          materi, pengganti)

        try:
            jadwal_id = int(data["jadwal_id"])
        except (TypeError, ValueError):
            raise ValueError("Jadwal tidak valid.")

        if database.ambil_jadwal_by_id(jadwal_id) is None:
            raise ValueError("Jadwal tidak ditemukan.")

        if aksi == "edit":
            kelas_id, pengajar_id, jam, tanggal, materi, pengganti = Jadwal.cek_input(
                data["hari"], data["jam_mulai"], data["jam_selesai"],
                data["kelas_id"], data["pengajar_id"], exclude_id=jadwal_id,
                tanggal=data.get("tanggal"), materi=data.get("materi"),
                pengganti=data.get("pengganti"),
            )
            return database.edit_jadwal(jadwal_id, data["hari"], jam, kelas_id, pengajar_id,
                                        tanggal, materi, pengganti)

        elif aksi == "hapus":
            return database.hapus_jadwal(jadwal_id)

        else:
            raise ValueError(f"Aksi tidak dikenal: {aksi}")

    def monitoring_sistem(self):
        """Ringkasan data sistem + daftar monitoring tiap siswa (nilai, presensi, jumlah catatan akhir)."""
        conn = database.get_connection()

        try:
            hasil = {}

            tabel = {
                "total_siswa": """
                    SELECT COUNT(*) FROM users WHERE role = 'siswa'
                """,
                "total_pengajar": """
                    SELECT COUNT(*) FROM users WHERE role = 'pengajar'
                """,
                "total_kelas": "SELECT COUNT(*) FROM kelas",
                "total_materi": "SELECT COUNT(*) FROM materi",
                "total_tugas": "SELECT COUNT(*) FROM tugas",
                "total_pengumpulan": "SELECT COUNT(*) FROM pengumpulan",
                "total_presensi": "SELECT COUNT(*) FROM presensi",
                # nilai ada di kolom pengumpulan.nilai, jadi yang dihitung pengumpulan yang sudah dinilai
                "total_penilaian": "SELECT COUNT(nilai) FROM pengumpulan",
                "total_catatan_akhir": "SELECT COUNT(*) FROM catatan_akhir"
            }

            for nama, query in tabel.items():
                hasil[nama] = conn.execute(query).fetchone()[0]
        finally:
            conn.close()

        hasil["daftar_siswa"] = [dict(r) for r in database.ambil_monitoring_semua_siswa()]
        return hasil

    def lihat_monitoring_siswa(self, siswa_id):
        """Monitoring satu siswa (rekap presensi, nilai, catatan akhir), dibuka dari profil siswa."""
        row = database.ambil_user_by_id(siswa_id)
        if not row or row["role"] != "siswa":
            raise ValueError("Siswa tidak ditemukan.")
        return buat_objek_user(row).lihat_monitoring()

    # POLYMORPHISM: admin boleh akses semua kelas, siswa, dan pengajar
    def boleh_akses_kelas(self, kelas_id):
        return True

    def boleh_lihat_siswa(self, siswa_row):
        return True

    def boleh_lihat_pengajar(self, pengajar_id):
        return True

    # POLYMORPHISM: lagi-lagi override, menu admin
    def tampilkan_menu(self):
        return ["Kelola Akun", "Kelola Jadwal", "Kelola Kelas", "Monitoring"]

# dipanggil pas login / get_current_user, tinggal kasih row, objek yang cocok keluar sendiri.
# atau Admin. Setelah keluar dari sini, pemanggil memperlakukan ketiganya sama saja
# (semuanya User), dan tiap objek sendiri yang tahu versi method miliknya.
# INHERITANCE: ketiga class yang dibuat di sini sama-sama turunan User, jadi apa pun
# hasilnya pasti punya cek_password(), ganti_password(), dan tampilkan_menu().
def buat_objek_user(row):
    if not row:
        return None
    keys = row.keys()
    role = row["role"]
    no_wa = row["no_whatsapp"] if "no_whatsapp" in keys else (row["whatsapp"] if "whatsapp" in keys else None)
    foto = row["foto"] if "foto" in keys else "default_avatar.png"
    biodata = row["biodata"] if "biodata" in keys else None
    kelas_id = row["kelas_id"] if "kelas_id" in keys else None
    alamat = row["alamat"] if "alamat" in keys else None
    email = row["email"] if "email" in keys else None
    nik = row["nik"] if "nik" in keys else None

    if role == "siswa":
        return Siswa(row["id"], row["nama"], row["username"], row["password"], kelas_id,
                     foto, no_wa, alamat, email)
    elif role == "pengajar":
        return Pengajar(row["id"], row["nama"], row["username"], row["password"],
                        foto, no_wa, biodata, alamat, email, nik)
    elif role == "admin":
        return Admin(row["id"], row["nama"], row["username"], row["password"])
    raise ValueError(f"Role tidak dikenal: {role}")