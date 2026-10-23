"""Uji tambahan untuk revisi dashboard; membutuhkan dependency dari requirements.txt."""
import unittest
from datetime import date, timedelta

import database


class RevisiDashboardTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from unittest.mock import patch
        self.tmp = tempfile.TemporaryDirectory()
        self.mock_db = patch.object(database, 'DB_NAME', self.tmp.name + '/revisi.sqlite')
        self.mock_db.start()
        database.migrasi()
        self.teacher = database.tambah_user('Guru Test', 'guru_revisi', 'Password', 'pengajar')
        self.kelas = database.tambah_kelas('Kelas Revisi', self.teacher)
        self.siswa = database.tambah_user('Siswa Revisi', 'siswa_revisi', 'Password', 'siswa', kelas_id=self.kelas)

    def tearDown(self):
        self.mock_db.stop()
        self.tmp.cleanup()

    def test_sisa_presensi_tidak_tergantung_tanggal(self):
        d_lama = (date.today() - timedelta(days=20)).isoformat()
        d_depan = (date.today() + timedelta(days=20)).isoformat()
        conn = database.get_connection()
        try:
            for d in (d_lama, d_depan):
                conn.execute('INSERT INTO jadwal (hari,jam,kelas_id,pengajar_id,tanggal) VALUES(?,?,?,?,?)',
                             ('Senin','08.00 - 09.00',self.kelas,self.teacher,d))
            conn.commit()
        finally: conn.close()
        info = database.data_dashboard_pengajar(self.teacher, self.kelas)
        self.assertEqual(info['stat']['sisa'], 8)  # target 8, belum ada presensi
        self.assertEqual(info['progress'][0]['selesai'], 0)
        database.simpan_presensi(d_lama,self.siswa,self.kelas,'hadir',pengajar_id=self.teacher)
        info = database.data_dashboard_pengajar(self.teacher,self.kelas)
        self.assertEqual(info['stat']['sisa'], 7)
        self.assertEqual(info['progress'][0]['selesai'], 1)
        database.hapus_presensi(self.kelas,d_lama,self.siswa)
        self.assertEqual(database.data_dashboard_pengajar(self.teacher,self.kelas)['stat']['sisa'],8)
        database.simpan_presensi(d_depan,self.siswa,self.kelas,'izin',pengajar_id=self.teacher)
        self.assertEqual(database.data_dashboard_pengajar(self.teacher,self.kelas)['stat']['sisa'],7)

    def test_rekap_warna_6_kategori_berdasarkan_data(self):
        d = date.today().isoformat()
        conn = database.get_connection()
        try:
            conn.execute('INSERT INTO jadwal (hari,jam,kelas_id,pengajar_id,tanggal) VALUES(?,?,?,?,?)',
                         ('Senin','08.00 - 09.00',self.kelas,self.teacher,d))
            conn.commit()
        finally: conn.close()
        rekap = database.data_dashboard_admin(date.today().year)
        self.assertEqual(len(rekap['diagram_rekap']['irisan']),6)
        self.assertEqual(rekap['diagram_rekap']['total'],sum(rekap['stat'].values()))
        warna = [k['warna'] for k in rekap['diagram_rekap']['irisan']]
        self.assertEqual(len(set(warna)),6)
        self.assertIn('conic-gradient',rekap['diagram_rekap']['gradien'])
        self.assertIn(warna[0],rekap['diagram_rekap']['gradien'])


if __name__ == '__main__':
    unittest.main()
