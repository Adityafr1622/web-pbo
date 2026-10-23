"""Regresi revisi Monitoring + status Jadwal berdasarkan presensi."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database


class StatusJadwalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patcher = patch.object(database, 'DB_NAME', os.path.join(self.tmp.name, 'uji.db'))
        self.patcher.start()
        database.migrasi()
        self.guru = database.tambah_user('Guru Tes', 'guru_status', 'tes', 'pengajar')
        self.kelas = database.tambah_kelas('Basic Status', self.guru)
        self.lain = database.tambah_kelas('Kelas Lain', self.guru)
        self.siswa = database.tambah_user('Siswa Tes', 'siswa_status', 'tes', 'siswa', kelas_id=self.kelas)
        self.siswa_lain = database.tambah_user('Siswa Lain', 'siswa_status2', 'tes', 'siswa', kelas_id=self.lain)

    def tearDown(self):
        self.patcher.stop()
        self.tmp.cleanup()

    def jadwal(self, kelas, tanggal):
        conn = database.get_connection()
        try:
            cur = conn.execute('''INSERT INTO jadwal(hari,jam,kelas_id,pengajar_id,tanggal)
                                  VALUES(?,?,?,?,?)''', ('Jumat','08.00 - 09.00',kelas,self.guru,tanggal))
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def test_status_per_jadwal_bukan_berdasarkan_tanggal_saja(self):
        lampau = self.jadwal(self.kelas, '2025-05-02')
        depan = self.jadwal(self.kelas, '2028-08-04')
        lain = self.jadwal(self.lain, '2025-05-02')
        self.assertEqual(database.ambil_jadwal_terpresensi([lampau,depan,lain]),set())
        self.assertEqual(database.ambil_jadwal_terpresensi([]),set())
        database.simpan_presensi('2025-05-02',self.siswa_lain,self.lain,'Hadir')
        self.assertEqual(database.ambil_jadwal_terpresensi([lampau,depan,lain]),{lain})
        database.simpan_presensi('2028-08-04',self.siswa,self.kelas,'Izin')
        self.assertEqual(database.ambil_jadwal_terpresensi([lampau,depan,lain]),{lain,depan})
        database.simpan_presensi('2025-05-02',self.siswa,self.kelas,'Alfa')
        self.assertEqual(database.ambil_jadwal_terpresensi([lampau,depan,lain]),{lain,depan,lampau})
        database.hapus_presensi(self.kelas,'2028-08-04',self.siswa)
        self.assertEqual(database.ambil_jadwal_terpresensi([lampau,depan,lain]),{lain,lampau})

    def test_tidak_selesai_jika_presensi_belum_diisi_valid(self):
        j = self.jadwal(self.kelas,'2026-01-02')
        db = database.get_connection()
        db.execute('INSERT INTO presensi(tanggal,siswa_id,kelas_id,status) VALUES(?,?,?,?)',
                   ('2026-01-02',self.siswa,self.kelas,'Belum Hadir'))
        db.commit()
        db.close()
        self.assertEqual(database.ambil_jadwal_terpresensi([j]),set())
        database.simpan_presensi('2026-01-02',self.siswa,self.kelas,'Sakit')
        self.assertEqual(database.ambil_jadwal_terpresensi([j,j]),{j})

    def test_monitoring_no_duplicate_summary_and_jadwal_status_after_actions(self):
        root = Path(__file__).resolve().parents[1] / 'templates'
        monitoring = (root / 'monitoring.html').read_text(encoding='utf-8')
        jadwal = (root / 'kelola_jadwal.html').read_text(encoding='utf-8')
        self.assertNotIn('ringkasan.total_siswa',monitoring)
        self.assertNotIn('<div class="stat-grid">',monitoring)
        self.assertIn('<th>Status</th>',jadwal)
        self.assertIn("'Selesai' if j.selesai else 'Belum Selesai'",jadwal)
        self.assertLess(jadwal.index('<th>Aksi</th>'),jadwal.index('<th>Status</th>'))


if __name__ == '__main__':
    unittest.main()
