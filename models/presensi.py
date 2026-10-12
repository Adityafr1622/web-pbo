# PEMBAGIAN TUGAS DI models/presensi.py
# Presensi -> ANGGOTA 4
# CatatanPengajar (Catatan Akhir) -> ANGGOTA 3 (Monitoring)

# 4 PILAR OOP di bagian Presensi (cari komentar ENCAPSULATION / ABSTRACTION / INHERITANCE / POLYMORPHISM):
#  - ENCAPSULATION : class Presensi membungkus data + aturan validasi + perilakunya
#  - ABSTRACTION   : pemanggil (route / Pengajar) cukup panggil method, tanpa tahu SQL-nya
#  - INHERITANCE   : lewat Pengajar(User) di models/user.py yang memakai class ini
#  - POLYMORPHISM  : lewat Pengajar.catat_presensi() di models/user.py (menerima objek atau id)

from datetime import datetime
import database

HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember"]


def _ke_int(nilai, nama):
    try:
        return int(nilai)
    except (TypeError, ValueError):
        raise ValueError(f"{nama} tidak valid.")


class Presensi:
    # ENCAPSULATION: Data kehadiran (id, tanggal, siswa_id, kelas_id, status) dan
    # perilakunya (simpan, update_status, rekap) dibungkus dalam SATU class.
    # Aturan status (STATUS_VALID/_ALIAS) disimpan di dalam class, bukan tersebar di route.
    STATUS_DEFAULT = "Belum Hadir"
    STATUS_VALID = ["Hadir", "Izin", "Sakit", "Alfa"]
    # ENCAPSULATION: Awalan underscore (_ALIAS) = detail internal, tidak untuk dipakai dari luar.
    # nilai dari form (huruf kecil) -> nilai yang disimpan di database
    _ALIAS = {"hadir": "Hadir", "izin": "Izin", "sakit": "Sakit",
              "alfa": "Alfa", "alpha": "Alfa", "alpa": "Alfa"}

    def __init__(self, id, tanggal, siswa_id, kelas_id, status="Belum Hadir"):
        self.id = id
        self.tanggal = tanggal
        self.siswa_id = siswa_id
        self.kelas_id = kelas_id
        self.status = status

    # ---------- pembuatan objek ----------
    # ABSTRACTION: dari_row / muat / ambil_kelas menyembunyikan proses baca database.
    # Pemanggil cukup menerima objek Presensi, tidak perlu tahu tabel & kolomnya.
    @classmethod
    def dari_row(cls, row):
        return cls(row["id"], row["tanggal"], row["siswa_id"], row["kelas_id"], row["status"])

    @classmethod
    def muat(cls, presensi_id):
        row = database.ambil_presensi_by_id(_ke_int(presensi_id, "Presensi"))
        if row is None:
            raise ValueError("Data presensi tidak ditemukan.")
        return cls.dari_row(row)

    @classmethod
    def ambil_kelas(cls, kelas_id, tanggal):
        """Satu objek Presensi untuk SETIAP siswa di kelas pada tanggal tsb.
        Siswa yang belum dicatat otomatis berstatus 'Belum Hadir' (id=None)."""
        tersimpan = {r["siswa_id"]: r for r in database.ambil_presensi_kelas_tanggal(kelas_id, tanggal)}
        hasil = []
        for s in database.ambil_siswa_by_kelas(kelas_id):
            if s["id"] in tersimpan:
                hasil.append(cls.dari_row(tersimpan[s["id"]]))
            else:
                hasil.append(cls(None, tanggal, s["id"], kelas_id))
        return hasil

    # ---------- validasi ----------
    # ENCAPSULATION: Semua aturan validasi presensi dikunci di dalam class ini,
    # sehingga data yang masuk database pasti sudah lolos pemeriksaan yang sama.
    @staticmethod
    def normalisasi_status(status):
        kunci = (status or "").strip().lower()
        if kunci not in Presensi._ALIAS:
            raise ValueError("Status presensi harus salah satu dari: Hadir, Izin, Sakit, Alfa.")
        return Presensi._ALIAS[kunci]

    @staticmethod
    def cek_tanggal(tanggal):
        """Pastikan format YYYY-MM-DD, kembalikan string yang sudah dirapikan."""
        try:
            return datetime.strptime((tanggal or "").strip(), "%Y-%m-%d").date().isoformat()
        except ValueError:
            raise ValueError("Tanggal presensi tidak valid.")

    @staticmethod
    def format_label(tanggal):
        """'2026-10-05' -> 'Senin, 5 Oktober 2026'"""
        d = datetime.strptime(tanggal, "%Y-%m-%d").date()
        return f"{HARI[d.weekday()]}, {d.day} {BULAN[d.month - 1]} {d.year}"

    @staticmethod
    def cek_input(kelas_id, tanggal, siswa_ids):
        """Validasi satu sesi presensi. Kembalikan (kelas_id, tanggal_rapi)."""
        kelas_id = _ke_int(kelas_id, "Kelas")
        if database.ambil_kelas_by_id(kelas_id) is None:
            raise ValueError("Kelas tidak ditemukan.")

        tanggal = Presensi.cek_tanggal(tanggal)
        if tanggal not in database.ambil_tanggal_jadwal_kelas(kelas_id):
            raise ValueError("Tidak ada jadwal untuk kelas ini pada tanggal tersebut.")

        anggota = {s["id"] for s in database.ambil_siswa_by_kelas(kelas_id)}
        for sid in siswa_ids:
            if sid not in anggota:
                raise ValueError("Ada siswa yang bukan anggota kelas ini.")
        return kelas_id, tanggal

    # ---------- aksi ----------
    # ABSTRACTION: simpan_massal() = satu pintu sederhana untuk menyimpan presensi.
    # Di dalamnya ada validasi, upsert (tidak duplikat), dan transaksi database,
    # tetapi pemanggil (Pengajar / route Flask) tidak perlu mengetahuinya.
    @staticmethod
    def simpan_massal(kelas_id, tanggal, data_status):
        """Simpan presensi banyak siswa sekaligus.
        data_status: {siswa_id: 'hadir' / 'Izin' / ...}. Semua divalidasi dulu,
        kalau ada satu yang salah tidak ada yang tersimpan. Return jumlah siswa."""
        if not data_status:
            raise ValueError("Belum ada status kehadiran yang dipilih.")
        bersih = {}
        for sid, st in data_status.items():
            bersih[_ke_int(sid, "Siswa")] = Presensi.normalisasi_status(st)
        kelas_id, tanggal = Presensi.cek_input(kelas_id, tanggal, bersih.keys())
        database.simpan_presensi_massal(kelas_id, tanggal, bersih)
        return len(bersih)

    def simpan(self):
        """Simpan objek ini (insert, atau update kalau siswa+kelas+tanggal sudah ada)."""
        self.status = Presensi.normalisasi_status(self.status)
        self.kelas_id, self.tanggal = Presensi.cek_input(self.kelas_id, self.tanggal, [self.siswa_id])
        self.id = database.simpan_presensi(self.tanggal, self.siswa_id, self.kelas_id, self.status)
        return self.id

    def update_status(self, status):
        # ENCAPSULATION: Status hanya diubah lewat method ini, sehingga selalu
        # divalidasi dulu (Hadir/Izin/Sakit/Alfa) sebelum masuk ke objek & database.
        self.status = Presensi.normalisasi_status(status)
        if self.id:
            database.update_status_presensi(self.id, self.status)
        else:
            self.simpan()
        return self.status

    @staticmethod
    def tandai_semua_hadir(daftar_presensi):
        """Ubah semua Presensi di daftar jadi 'Hadir'. Return jumlah yang diubah."""
        for p in daftar_presensi:
            p.update_status("Hadir")
        return len(daftar_presensi)

    # ---------- rekap ----------
    # ABSTRACTION: rekap_siswa()/rekap_kelas() mengembalikan hasil siap pakai
    # (jumlah per status, persen hadir) tanpa membuka detail query GROUP BY ke pemanggil.
    @staticmethod
    def rekap_siswa(siswa_id):
        """{'Hadir': n, 'Izin': n, 'Sakit': n, 'Alfa': n, 'total': n, 'persen_hadir': x}"""
        hasil = {st: 0 for st in Presensi.STATUS_VALID}
        for r in database.rekap_presensi_siswa(siswa_id):
            if r["status"] in hasil:
                hasil[r["status"]] = r["jumlah"]
        total = sum(hasil.values())
        hasil["total"] = total
        hasil["persen_hadir"] = round(hasil["Hadir"] * 100 / total, 1) if total else 0
        return hasil

    @staticmethod
    def rekap_kelas(kelas_id):
        """Daftar rekap per siswa di kelas: [{'siswa_id','nama','Hadir','Izin','Sakit','Alfa'}, ...]"""
        data = {}
        for s in database.ambil_siswa_by_kelas(kelas_id):
            data[s["id"]] = {"siswa_id": s["id"], "nama": s["nama"],
                             **{st: 0 for st in Presensi.STATUS_VALID}}
        for r in database.rekap_presensi_kelas(kelas_id):
            if r["siswa_id"] in data and r["status"] in Presensi.STATUS_VALID:
                data[r["siswa_id"]][r["status"]] = r["jumlah"]
        return list(data.values())


class CatatanPengajar:
    # Catatan akhir: 1 catatan per siswa per kelas, ditulis setelah seluruh pertemuan selesai
    def __init__(self, id, siswa_id, pengajar_id, kelas_id, isi_catatan, tanggal=None):
        self.id = id
        self.siswa_id = siswa_id
        self.pengajar_id = pengajar_id
        self.kelas_id = kelas_id
        self.isi_catatan = isi_catatan
        self.tanggal = tanggal

    def simpan_catatan(self):
        # TODO (Anggota 3): simpan catatan akhir baru ke database
        pass

    def ubah_catatan(self, isi_baru):
        # TODO (Anggota 3): edit catatan akhir yang sudah ada
        pass

    def get_detail_catatan(self):
        # TODO (Anggota 3): ambil detail catatan untuk ditampilkan di Monitoring Anak
        pass