"""Aturan dashboard: 8 pertemuan per kelas dan hanya data tahun yang ada."""
import unittest
import tempfile
from unittest.mock import patch
from datetime import date, timedelta
import database


class Dashboard8PertemuanTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.patch=patch.object(database,'DB_NAME',self.tmp.name+'/test.sqlite')
        self.patch.start()
        database.migrasi()
        self.guru=database.tambah_user('Pengajar Uji','guru8','tes','pengajar')
        self.kelas=database.tambah_kelas('Basic 8',self.guru)
        self.siswa=database.tambah_user('Siswa Uji','siswa8','tes','siswa',kelas_id=self.kelas)
        self.siswa2=database.tambah_user('Siswa Lain','siswa9','tes','siswa',kelas_id=self.kelas)

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def jadwal(self, tanggal):
        con=database.get_connection()
        con.execute('INSERT INTO jadwal (hari,jam,kelas_id,pengajar_id,tanggal) VALUES (?,?,?,?,?)',
                    ('Senin','08.00 - 09.00',self.kelas,self.guru,tanggal))
        con.commit();con.close()

    def tugas(self, judul):
        con=database.get_connection()
        cur=con.execute('INSERT INTO tugas(judul,deskripsi,kelas_id,pengajar_id,tanggal_dibuat) VALUES(?,?,?,?,?)',
                 (judul,'Tes',self.kelas,self.guru,'2026-10-02 10:00:00'))
        val=cur.lastrowid
        con.commit();con.close()
        return val

    def test_total_8_dan_sisa_berdasarkan_presensi(self):
        lama=(date.today()-timedelta(days=20)).isoformat()
        depan=(date.today()+timedelta(days=20)).isoformat()
        self.jadwal(lama)
        self.jadwal(depan)
        siswa=database.data_dashboard_siswa(self.siswa,self.kelas)['stat']
        self.assertEqual((siswa['total'],siswa['sisa'],siswa['selesai']), (8,8,0))
        # Dua siswa pada tanggal yang sama dihitung satu pertemuan.
        database.simpan_presensi(lama,self.siswa,self.kelas,'Hadir')
        database.simpan_presensi(lama,self.siswa2,self.kelas,'Izin')
        self.assertEqual(database.data_dashboard_siswa(self.siswa,self.kelas)['stat']['sisa'],7)
        self.assertEqual(database.data_dashboard_pengajar(self.guru,self.kelas)['stat']['sisa'],7)
        admin=database.data_dashboard_admin(date.today().year)
        self.assertEqual(admin['progress'][0]['selesai'],1)
        self.assertEqual(admin['progress'][0]['total'],8)
        # Terjadwal besok, tapi sudah terpresensi = telah dilaksanakan (sesuai aturan).
        database.simpan_presensi(depan,self.siswa,self.kelas,'Alfa')
        self.assertEqual(database.data_dashboard_siswa(self.siswa,self.kelas)['stat']['sisa'],6)
        database.hapus_presensi(self.kelas,lama,self.siswa)
        database.hapus_presensi(self.kelas,lama,self.siswa2)
        self.assertEqual(database.data_dashboard_siswa(self.siswa,self.kelas)['stat']['sisa'],7)

    def test_presensi_belum_hadir_tidak_mengurangi_sisa(self):
        d=date.today().isoformat();self.jadwal(d)
        con=database.get_connection()
        con.execute('INSERT INTO presensi(tanggal,siswa_id,kelas_id,status) VALUES (?,?,?,?)',
                    (d,self.siswa,self.kelas,'Belum Hadir'))
        con.commit();con.close()
        self.assertEqual(database.data_dashboard_siswa(self.siswa,self.kelas)['stat']['sisa'],8)

    def test_progress_tidak_lebih_dari_8(self):
        con=database.get_connection()
        for i in range(10):
            d=f'2026-10-{i+1:02d}'
            con.execute('INSERT INTO presensi(tanggal,siswa_id,kelas_id,status) VALUES(?,?,?,?)',
                        (d,self.siswa,self.kelas,'Hadir'))
        con.execute('INSERT INTO jadwal(hari,jam,kelas_id,pengajar_id,tanggal) VALUES(?,?,?,?,?)',
                    ('Senin','8.00',self.kelas,self.guru,'2026-10-01'))
        con.commit();con.close()
        self.assertEqual(database.data_dashboard_siswa(self.siswa,self.kelas)['stat']['sisa'],0)
        self.assertEqual(database.data_dashboard_admin(2026)['progress'][0]['selesai'],8)
        self.assertEqual(database.data_dashboard_pengajar(self.guru,self.kelas)['stat']['sisa'],0)

    def test_dropdown_dan_perbandingan_hanya_tahun_berdata(self):
        self.jadwal('2026-10-08')
        data=database.data_dashboard_admin(2026)
        self.assertEqual(data['tahun_opsi'],[2026])
        self.assertEqual([r[0] for r in data['rekap']],[2026])
        self.assertEqual(data['tahun'],2026)
        self.assertEqual(database.data_dashboard_admin(2024)['tahun'],2026)
        self.jadwal('2022-03-10')
        self.jadwal('2023-03-10')
        data=database.data_dashboard_admin(2026)
        self.assertEqual(data['tahun_opsi'],[2026,2023,2022])
        self.assertEqual([r[0] for r in data['rekap']],[2026,2023,2022])

    def test_panel_tugas_siswa_dan_data_privat(self):
        a=self.tugas('Tugas yang sudah dinilai')
        b=self.tugas('Tugas menunggu nilai')
        c=self.tugas('Tugas belum dikerjakan')
        con=database.get_connection()
        con.execute('INSERT INTO pengumpulan(tugas_id,siswa_id,file_jawaban,nilai) VALUES(?,?,?,?)',
                    (a,self.siswa,'a.pdf',93))
        con.execute('INSERT INTO pengumpulan(tugas_id,siswa_id,file_jawaban,nilai) VALUES(?,?,?,?)',
                    (b,self.siswa,'b.pdf',None))
        con.execute('INSERT INTO pengumpulan(tugas_id,siswa_id,file_jawaban,nilai) VALUES(?,?,?,?)',
                    (c,self.siswa2,'c.pdf',91))
        con.commit();con.close()
        result=database.data_dashboard_siswa(self.siswa,self.kelas)
        self.assertEqual((result['stat']['dikerjakan'],result['stat']['belum_tugas'],
                          result['stat']['dinilai'],result['stat']['belum_nilai']), (2,1,1,1))
        for panel, expected in [('dikerjakan',{a,b}),('belum_tugas',{c}),
                               ('dinilai',{a}),('belum_nilai',{b})]:
            self.assertEqual({v['id'] for v in database.data_dashboard_siswa(self.siswa,self.kelas,panel)['daftar']},expected)
        self.assertEqual({v['id'] for v in database.data_dashboard_siswa(self.siswa2,self.kelas,'dikerjakan')['daftar']},{c})
        other=database.tambah_kelas('Kelas Lain',self.guru)
        with self.assertRaisesRegex(ValueError,'bukan milik siswa'):
            database.data_dashboard_siswa(self.siswa,other,'dikerjakan')

if __name__ == '__main__':unittest.main()
