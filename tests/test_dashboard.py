"""Uji regresi dashboard / riwayat kelas; jalankan: python -m unittest discover -s tests."""
import os
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch

import database


class DashboardDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, 'test_fluenglo.db')
        self.mock_db = patch.object(database, 'DB_NAME', self.db)
        self.mock_db.start()
        database.migrasi()
        self.teacher = database.tambah_user('Pengajar Test', 'pengajar_test', 'Test12345', 'pengajar')
        self.first = database.tambah_kelas('Kelas Test Satu', self.teacher)
        self.second = database.tambah_kelas('Kelas Test Dua', self.teacher)
        self.siswa = database.tambah_user('Siswa Test', 'siswa_test', 'Test12345', 'siswa', kelas_id=self.first)

    def tearDown(self):
        self.mock_db.stop()
        self.tmp.cleanup()

    def kelulusan(self):
        database.tambah_catatan_akhir(self.siswa, self.first, self.teacher, 'Selesai', lulus=1)

    def test_tidak_boleh_pindah_tanpa_lulus(self):
        with self.assertRaisesRegex(ValueError, 'belum dinyatakan lulus'):
            database.edit_user(self.siswa, kelas_id=self.second)
        self.assertEqual(database.ambil_user_by_id(self.siswa)['kelas_id'], self.first)

    def test_riwayat_tersimpan_dan_perkelas(self):
        self.kelulusan()
        database.edit_user(self.siswa, kelas_id=self.second)
        self.assertEqual({r['id'] for r in database.ambil_riwayat_kelas_siswa(self.siswa)},
                         {self.first, self.second})
        self.assertTrue(database.siswa_anggota_kelas(self.siswa, self.first))
        self.assertIsNone(database.rekap_nilai_siswa(self.siswa, self.second)['rata_rata'])
        # Tidak boleh menghapus kelas historis beserta data lama.
        with self.assertRaisesRegex(ValueError, 'riwayat'):
            database.hapus_kelas(self.first)

    def test_grafik_presensi_kumulatif(self):
        dates = [date.today()-timedelta(days=i) for i in (5,4,3,2)]
        c = database.get_connection()
        for d in dates:
            c.execute('INSERT INTO jadwal(hari,jam,kelas_id,pengajar_id,tanggal) VALUES(?,?,?,?,?)',
                      ('Senin', '08.00 - 09.00', self.first, self.teacher, d.isoformat()))
        for d,status in zip(dates,['Hadir','Alfa','Hadir']):
            c.execute('INSERT INTO presensi(tanggal,siswa_id,kelas_id,status) VALUES(?,?,?,?)',
                      (d.isoformat(),self.siswa,self.first,status))
        c.commit();c.close()
        points=database.grafik_presensi_siswa(self.siswa,self.first)
        self.assertEqual([p['nilai'] for p in points],[100,50,66.67])
        self.assertEqual([p['arah'] for p in points],[None,'turun','naik'])

    def test_kelas_tahun_berbeda_akun_sama(self):
        now = date.today()
        next_year = date(now.year+1,3,5)
        c=database.get_connection()
        for d,k in [(now,self.first),(next_year,self.second)]:
            c.execute('INSERT INTO jadwal(hari,jam,kelas_id,pengajar_id,tanggal) VALUES(?,?,?,?,?)',
                      ('Senin','08.00 - 09.00',k,self.teacher,d.isoformat()))
        c.commit();c.close()
        self.kelulusan()
        database.edit_user(self.siswa,kelas_id=self.second)
        self.assertEqual(database.data_dashboard_admin(now.year)['stat']['siswa'],1)
        self.assertEqual(database.data_dashboard_admin(next_year.year)['stat']['siswa'],1)


if __name__ == '__main__':
    unittest.main()
