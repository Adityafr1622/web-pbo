import os
import re
import uuid
from datetime import datetime, timedelta
from flask import (Flask, render_template, request, redirect, url_for, session, flash,
                   send_from_directory)
from werkzeug.utils import secure_filename
import database
from models.akademik import Jadwal, HARI_VALID
from models.user import buat_objek_user
from models.presensi import Presensi

# Perubahan terbaru ditandai komentar "# BARU" / "# DIUBAH".

app = Flask(__name__)
app.secret_key = 'fluenglo_secret_key_pbo'
# path absolut, jadi upload nggak nyasar kalau app dijalankan dari folder lain
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
database.migrasi()  # bikin tabel/kolom yang belum ada (alamat/nik/email, pengumpulan, catatan_akhir, riwayat_password, deskripsi kelas, dst)

BULAN = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli',
         'Agustus', 'September', 'Oktober', 'November', 'Desember']
EKSTENSI_FOTO = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}


def simpan_file(field, ekstensi_boleh=None):
    """Simpan file upload ke folder uploads dengan nama unik (biar file orang lain nggak
    ketimpa kalau namanya sama). Balikin nama file tersimpan, atau None kalau nggak ada file."""
    file = request.files.get(field)
    if not file or not file.filename:
        return None
    nama = secure_filename(file.filename)
    if not nama:
        raise ValueError('Nama file tidak valid.')
    if ekstensi_boleh and os.path.splitext(nama)[1].lower() not in ekstensi_boleh:
        raise ValueError('Format file tidak didukung.')
    nama_unik = f"{uuid.uuid4().hex[:8]}_{nama}"
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], nama_unik))
    return nama_unik


def simpan_foto(field='foto'):
    """Simpan foto profil, kembalikan nama file (atau None). Bisa raise ValueError kalau bukan gambar."""
    return simpan_file(field, EKSTENSI_FOTO)


def hapus_file(nama):
    """Buang file upload yang sudah terlanjur disimpan tapi datanya gagal masuk database."""
    if nama:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], nama))
        except OSError:
            pass


def get_current_user():
    if 'user_id' not in session:
        return None
    row = database.ambil_user_by_id(session['user_id'])
    return buat_objek_user(row) if row else None


@app.context_processor
def info_pengguna():
    """Nama pengguna + daftar menu navbar, dipakai di semua template."""
    user = get_current_user()
    return {
        'nama_login': user.nama if user else '',
        # POLYMORPHISM: cukup panggil tampilkan_menu(), ga perlu cek role satu-satu
        'menu_user': user.tampilkan_menu() if user else [],
    }


@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user_row = database.ambil_user_by_username(username)
        if user_row:
            user_obj = buat_objek_user(user_row)
            if user_obj and user_obj.cek_password(password):
                session.clear()
                session['user_id'] = user_obj.id
                session['nama'] = user_obj.nama
                session['role'] = user_obj.role
                return redirect(url_for('dashboard'))
            else:
                flash('Password salah!', 'danger')
        else:
            flash('Username tidak ditemukan!', 'danger')

    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    if user.role == 'admin':
        return redirect(url_for('kelola_akun'))
    return redirect(url_for('profil'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# --- ROUTE PROFIL (SISWA & PENGAJAR) ---
@app.route('/profil')
def profil():
    user = get_current_user()
    if not user or user.role == 'admin':
        return redirect(url_for('login'))

    # POLYMORPHISM: lihat_profil() dipanggil sama, hasilnya beda tiap role
    data = user.lihat_profil()
    if user.role == 'pengajar':
        return render_template('profil_pengajar.html', data=data, lengkap=True, bisa_ubah=True)
    return render_template('profil_siswa.html', data=data, lengkap=True, bisa_ubah=True)


@app.route('/profil/password', methods=['POST'])
def ganti_password():
    user = get_current_user()
    if not user or user.role == 'admin':
        return redirect(url_for('login'))

    password_lama = request.form.get('password_lama', '')
    password_baru = request.form.get('password_baru', '')

    try:
        # kolom konfirmasi dicek hanya kalau memang ada di form
        if 'konfirmasi_password' in request.form and password_baru != request.form['konfirmasi_password']:
            raise ValueError('Konfirmasi password tidak cocok.')
        user.ganti_password(password_lama, password_baru)  # sekaligus tercatat di riwayat_password
        flash('Password berhasil diganti!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('profil'))


@app.route('/profil/ubah', methods=['POST'])
def ubah_profil():
    """Ubah Profil siswa & pengajar: foto, no WA (wajib valid), email (opsional), alamat."""
    user = get_current_user()
    if not user or user.role not in ('siswa', 'pengajar'):
        return redirect(url_for('login'))

    foto = None
    try:
        foto = simpan_foto()
        # POLYMORPHISM: edit_profil() dipanggil sama, aturan tiap role ada di class-nya masing-masing
        user.edit_profil(whatsapp=request.form.get('whatsapp', ''),
                         email=request.form.get('email', ''),
                         foto=foto,
                         alamat=request.form.get('alamat'))  # None = field alamat nggak ada di form
        flash('Profil berhasil diperbarui!', 'success')
    except ValueError as e:
        hapus_file(foto)
        flash(str(e), 'danger')
    return redirect(url_for('profil'))


@app.route('/pengajar/<int:pengajar_id>')
def profil_pengajar(pengajar_id):
    """Profil pengajar. Admin & pengajar ybs lihat lengkap (ada NIK), siswa lihat versi publik (tanpa NIK)."""
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    row = database.ambil_user_by_id(pengajar_id)
    if not row or row['role'] != 'pengajar':
        flash('Pengajar tidak ditemukan.', 'danger')
        return redirect(url_for('dashboard'))

    # POLYMORPHISM: siapa boleh lihat siapa diputuskan tiap role sendiri
    if not user.boleh_lihat_pengajar(pengajar_id):
        flash('Kamu hanya bisa melihat profil pengajar kelasmu.', 'danger')
        return redirect(url_for('profil'))

    target = buat_objek_user(row)
    lengkap = user.role == 'admin' or user.id == target.id
    data = target.lihat_profil() if lengkap else target.profil_publik()
    return render_template('profil_pengajar.html', data=data, lengkap=lengkap,
                           bisa_ubah=(user.id == target.id))


@app.route('/siswa/<int:siswa_id>')
def profil_siswa(siswa_id):
    """Profil siswa. Admin, pengajar kelas siswa tsb (dibuka dari presensi / tugas), dan siswa ybs."""
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    row = database.ambil_user_by_id(siswa_id)
    if not row or row['role'] != 'siswa':
        flash('Siswa tidak ditemukan.', 'danger')
        return redirect(url_for('dashboard'))

    if not user.boleh_lihat_siswa(row):
        flash('Kamu tidak punya akses ke profil siswa ini.', 'danger')
        return redirect(url_for('dashboard'))

    target = buat_objek_user(row)
    return render_template('profil_siswa.html', data=target.lihat_profil(), lengkap=True,
                           bisa_ubah=(user.id == target.id),
                           kelas_id=row['kelas_id'],
                           catatan_akhir=database.ambil_catatan_akhir_by_siswa(siswa_id),
                           bisa_beri_catatan=(user.role == 'pengajar'))


# --- ROUTE KELOLA AKUN ---
@app.route('/admin/users', methods=['GET', 'POST'])
def kelola_akun():
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        nama = request.form.get('nama', '')
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        role = request.form.get('role', '')
        whatsapp = request.form.get('whatsapp', '')
        alamat = request.form.get('alamat', '')
        nik = request.form.get('nik', '')
        kelas_id = request.form.get('kelas_id', '')

        foto_filename = 'default_avatar.png'
        try:
            if role == 'pengajar':
                foto_filename = simpan_foto() or foto_filename
            user.kelola_akun('tambah', nama=nama, username=username, password=password,
                             role=role, whatsapp=whatsapp, alamat=alamat, nik=nik,
                             foto=foto_filename, kelas_id=kelas_id)
            flash('Akun berhasil dibuat!', 'success')
        except ValueError as e:
            if foto_filename != 'default_avatar.png':
                hapus_file(foto_filename)
            flash(str(e), 'danger')

        return redirect(url_for('kelola_akun'))

    users = database.ambil_semua_user()
    # DIUBAH: + riwayat_password (kartu Riwayat Perubahan Password) dan terakhir_ubah (kolom Password Diubah)
    return render_template('kelola_akun.html', users=users, kelas_list=database.ambil_semua_kelas(),
                           riwayat_password=database.ambil_riwayat_password(),
                           terakhir_ubah=database.ambil_terakhir_ubah_password())


@app.route('/admin/users/edit/<int:user_id>', methods=['POST'])
def edit_akun(user_id):
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('login'))

    target = database.ambil_user_by_id(user_id)
    if not target or target['role'] == 'admin':
        flash('Akun tidak ditemukan.', 'danger')
        return redirect(url_for('kelola_akun'))

    foto = None
    try:
        foto = simpan_foto() if target['role'] == 'pengajar' else None
        user.kelola_akun('edit', user_id=user_id,
                         nama=request.form.get('nama', ''),
                         username=request.form.get('username', ''),
                         password=request.form.get('password', ''),
                         whatsapp=request.form.get('whatsapp', ''),
                         alamat=request.form.get('alamat', ''),
                         nik=request.form.get('nik', ''),
                         kelas_id=request.form.get('kelas_id', ''),  # BARU: admin bisa pindah kelas siswa
                         foto=foto)
        flash('Akun berhasil diperbarui!', 'success')
    except ValueError as e:
        hapus_file(foto)
        flash(str(e), 'danger')
    return redirect(url_for('kelola_akun'))


@app.route('/admin/users/delete/<int:user_id>')
def hapus_akun(user_id):
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('login'))
    try:
        user.kelola_akun('hapus', user_id=user_id)
        flash('Akun berhasil dihapus!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('kelola_akun'))


@app.route('/admin/users/<int:user_id>/biodata')
def biodata_akun(user_id):
    """Tombol 'Biodata Lengkap' di tabel Kelola Akun (pengajar maupun siswa)."""
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('login'))

    row = database.ambil_user_by_id(user_id)
    if not row or row['role'] == 'admin':
        flash('Akun tidak ditemukan.', 'danger')
        return redirect(url_for('kelola_akun'))

    target = buat_objek_user(row)
    data = target.lihat_profil()  # POLYMORPHISM: Siswa & Pengajar punya lihat_profil() sendiri-sendiri
    if target.role == 'pengajar':
        return render_template('profil_pengajar.html', data=data, lengkap=True, bisa_ubah=False)
    return render_template('profil_siswa.html', data=data, lengkap=True, bisa_ubah=False,
                           kelas_id=row['kelas_id'],
                           catatan_akhir=database.ambil_catatan_akhir_by_siswa(user_id),
                           bisa_beri_catatan=False)


# --- ROUTE KELAS ---
@app.route('/kelas')
def lihat_kelas():
    """Lihat Kelas untuk siswa (kelas yang diikuti) dan pengajar (kelas yang diajar)."""
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    if user.role == 'admin':
        return redirect(url_for('kelola_kelas'))

    if user.role == 'siswa':
        kelas = user.lihat_kelas()
        kelas_list = [kelas] if kelas else []
    else:
        kelas_list = user.lihat_kelas_diajar()
    # bisa_kelola=False: template sembunyikan tombol tambah & edit kalau False
    return render_template('kelola_kelas.html', kelas_list=kelas_list, pengajar_list=[],
                           bisa_kelola=False)


@app.route('/admin/kelas', methods=['GET', 'POST'])
def kelola_kelas():
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        nama_kelas = request.form.get('nama_kelas', '')
        pengajar_id = request.form.get('pengajar_id', '')
        pengajar_id2 = request.form.get('pengajar_id2', '')
        deskripsi = request.form.get('deskripsi', '')  # BARU

        try:
            user.kelola_kelas('tambah', nama_kelas=nama_kelas, pengajar_id=pengajar_id,
                              pengajar_id2=pengajar_id2, deskripsi=deskripsi)
            flash('Kelas berhasil dibuat!', 'success')
        except ValueError as e:
            flash(str(e), 'danger')

        return redirect(url_for('kelola_kelas'))

    kelas_list = database.ambil_semua_kelas()
    pengajar_list = database.ambil_semua_pengajar()
    return render_template('kelola_kelas.html', kelas_list=kelas_list, pengajar_list=pengajar_list,
                           bisa_kelola=True)


@app.route('/admin/kelas/edit/<int:kelas_id>', methods=['POST'])  # BARU: route edit kelas (tombol pensil)
def edit_kelas(kelas_id):
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('login'))
    try:
        user.kelola_kelas('edit', kelas_id=kelas_id,
                          nama_kelas=request.form.get('nama_kelas', ''),
                          pengajar_id=request.form.get('pengajar_id', ''),
                          pengajar_id2=request.form.get('pengajar_id2', ''),
                          deskripsi=request.form.get('deskripsi', ''))
        flash('Kelas berhasil diperbarui!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('kelola_kelas'))


@app.route('/admin/kelas/delete/<int:kelas_id>')
def hapus_kelas(kelas_id):
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('login'))
    try:
        user.kelola_kelas('hapus', kelas_id=kelas_id)
        flash('Kelas berhasil dihapus!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('kelola_kelas'))


@app.route('/admin/kelas/<int:kelas_id>')
def detail_kelas(kelas_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    kelas_row = database.ambil_kelas_by_id(kelas_id)
    if not kelas_row:
        flash('Kelas tidak ditemukan.', 'danger')
        return redirect(url_for('dashboard'))

    # POLYMORPHISM: siswa cuma kelasnya sendiri, pengajar cuma kelas yang diajar, admin semuanya
    if not user.boleh_akses_kelas(kelas_id):
        flash('Kamu tidak punya akses ke kelas ini.', 'danger')
        return redirect(url_for('dashboard'))

    pengajar_list = database.ambil_pengajar_kelas(kelas_row)
    siswa_list = database.ambil_siswa_by_kelas(kelas_id)

    return render_template('detail_kelas.html', kelas=kelas_row, pengajar_list=pengajar_list,
                           siswa_list=siswa_list,
                           presensi_list=siapkan_presensi_list(kelas_id))


# --- ROUTE JADWAL ---
def siapkan_jadwal_list(rows):
    """Ubah baris tabel jadwal jadi data siap tampil di tabel:
    kelas_id, hari, tanggal, pengajar_id, nama_pengajar, jam_mulai, jam_selesai, materi, minggu.
    Minggu ke-1 = minggu (Senin-Minggu) tempat jadwal paling awal kelas tersebut."""
    def ke_tanggal(teks):
        try:
            return datetime.strptime(teks, '%Y-%m-%d').date() if teks else None
        except ValueError:
            return None

    awal = {}  # kelas_id -> Senin pada minggu jadwal paling awal
    for r in rows:
        d = ke_tanggal(r['tanggal'])
        if d:
            senin = d - timedelta(days=d.weekday())
            if r['kelas_id'] not in awal or senin < awal[r['kelas_id']]:
                awal[r['kelas_id']] = senin

    hasil = []
    for r in rows:
        d = ke_tanggal(r['tanggal'])
        try:
            jam_mulai, jam_selesai = Jadwal.pecah_jam(r['jam'])
        except ValueError:
            jam_mulai, jam_selesai = r['jam'], ''
        minggu = 1
        if d:
            minggu = ((d - timedelta(days=d.weekday())) - awal[r['kelas_id']]).days // 7 + 1
        hasil.append({
            'id': r['id'],
            'kelas_id': r['kelas_id'],
            'hari': r['hari'],
            'tanggal': f"{d.day} {BULAN[d.month - 1]} {d.year}" if d else '-',
            'pengajar_id': r['pengajar_id'],  # buat link ke profil pengajar
            'nama_pengajar': r['pengajar_nama'],
            'jam_mulai': jam_mulai,
            'jam_selesai': jam_selesai,
            'materi': r['materi'] or '-',
            'minggu': minggu,
            '_urut': (minggu, r['tanggal'] or '', HARI_VALID.index(r['hari']) if r['hari'] in HARI_VALID else 9, jam_mulai),
        })
    hasil.sort(key=lambda x: x['_urut'])
    return hasil


@app.route('/jadwal')
def lihat_jadwal():
    """Lihat Jadwal: siswa (jadwal kelasnya) dan pengajar (jadwal yang dia ajar). Cuma lihat, nggak bisa ubah."""
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    if user.role == 'admin':
        return redirect(url_for('kelola_jadwal'))

    if user.role == 'siswa':
        kelas = user.lihat_kelas()
        kelas_list = [kelas] if kelas else []
        rows = user.lihat_jadwal()
    else:
        kelas_list = user.lihat_kelas_diajar()
        rows = user.lihat_jadwal_mengajar()

    return render_template('kelola_jadwal.html', jadwal_list=siapkan_jadwal_list(rows),
                           kelas_list=kelas_list, pengajar_list=[], bisa_kelola=False)


@app.route('/admin/jadwal', methods=['GET', 'POST'])
def kelola_jadwal():
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        hari = request.form.get('hari', '')
        jam_mulai = request.form.get('jam_mulai', '')
        jam_selesai = request.form.get('jam_selesai', '')
        kelas_id = request.form.get('kelas_id', '')
        pengajar_id = request.form.get('pengajar_id', '')
        tanggal = request.form.get('tanggal', '')
        materi = request.form.get('materi', '')

        try:
            user.kelola_jadwal('tambah', hari=hari, jam_mulai=jam_mulai, jam_selesai=jam_selesai,
                               kelas_id=kelas_id, pengajar_id=pengajar_id,
                               tanggal=tanggal, materi=materi)
            flash('Jadwal berhasil ditambahkan!', 'success')
        except ValueError as e:
            flash(str(e), 'danger')

        return redirect(url_for('kelola_jadwal'))

    jadwal_list = siapkan_jadwal_list(database.ambil_semua_jadwal())
    kelas_list = database.ambil_semua_kelas()
    pengajar_list = database.ambil_semua_pengajar()

    return render_template('kelola_jadwal.html', jadwal_list=jadwal_list, kelas_list=kelas_list,
                           pengajar_list=pengajar_list, bisa_kelola=True)


@app.route('/admin/jadwal/edit/<int:jadwal_id>', methods=['POST'])  # BARU: route edit jadwal
def edit_jadwal(jadwal_id):
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('login'))
    try:
        user.kelola_jadwal('edit', jadwal_id=jadwal_id,
                           hari=request.form.get('hari', ''),
                           jam_mulai=request.form.get('jam_mulai', ''),
                           jam_selesai=request.form.get('jam_selesai', ''),
                           kelas_id=request.form.get('kelas_id', ''),
                           pengajar_id=request.form.get('pengajar_id', ''),
                           tanggal=request.form.get('tanggal', ''),
                           materi=request.form.get('materi', ''))
        flash('Jadwal berhasil diperbarui!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('kelola_jadwal'))


@app.route('/admin/jadwal/delete/<int:jadwal_id>')  # BARU: route hapus jadwal
def hapus_jadwal(jadwal_id):
    user = get_current_user()
    if not user or user.role != 'admin':
        return redirect(url_for('login'))
    try:
        user.kelola_jadwal('hapus', jadwal_id=jadwal_id)
        flash('Jadwal berhasil dihapus!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('kelola_jadwal'))


# --- ROUTE MATERI (UPLOAD, EDIT, DOWNLOAD, HAPUS) ---

@app.route('/kelas/<int:kelas_id>/materi', methods=['GET', 'POST'])
def kelola_materi(kelas_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    kelas = database.ambil_kelas_by_id(kelas_id)
    if not kelas:
        flash('Kelas tidak ditemukan.', 'danger')
        return redirect(url_for('dashboard'))

    if not user.boleh_akses_kelas(kelas_id):
        flash('Kamu tidak punya akses ke kelas ini.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        if user.role != 'pengajar':
            flash('Hanya pengajar yang dapat mengunggah materi.', 'danger')
            return redirect(url_for('kelola_materi', kelas_id=kelas_id))

        filename = None
        try:
            filename = simpan_file('file_materi')
            user.upload_materi(kelas_id, request.form.get('judul', ''),
                               request.form.get('kategori', ''), filename)
            flash('Materi berhasil diunggah!', 'success')
        except ValueError as e:
            hapus_file(filename)
            flash(str(e), 'danger')
        return redirect(url_for('kelola_materi', kelas_id=kelas_id))

    materi_list = database.ambil_materi_by_kelas(kelas_id)
    return render_template('materi.html', kelas=kelas, materi_list=materi_list, user=user)


@app.route('/materi/edit/<int:materi_id>', methods=['POST'])
def edit_materi(materi_id):
    user = get_current_user()
    if not user or user.role != 'pengajar':
        return redirect(url_for('login'))

    materi = database.ambil_materi_by_id(materi_id)
    if not materi:
        flash('Materi tidak ditemukan.', 'danger')
        return redirect(url_for('dashboard'))

    filename = None
    try:
        filename = simpan_file('file_materi')  # opsional, kosong = pakai file lama
        user.edit_materi(materi_id, request.form.get('judul', ''),
                         request.form.get('kategori', ''), filename)
        flash('Materi berhasil diperbarui!', 'success')
    except ValueError as e:
        hapus_file(filename)
        flash(str(e), 'danger')
    return redirect(url_for('kelola_materi', kelas_id=materi['kelas_id']))


@app.route('/materi/download/<int:materi_id>')
def download_materi(materi_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    materi = database.ambil_materi_by_id(materi_id)
    if not materi or not materi['file_path']:
        flash('Materi tidak ditemukan.', 'danger')
        return redirect(url_for('dashboard'))
    if not user.boleh_akses_kelas(materi['kelas_id']):
        flash('Kamu tidak punya akses ke materi ini.', 'danger')
        return redirect(url_for('dashboard'))

    nama_asli = re.sub(r'^[0-9a-f]{8}_', '', materi['file_path'])  # buang awalan unik
    return send_from_directory(app.config['UPLOAD_FOLDER'], materi['file_path'],
                               as_attachment=True, download_name=nama_asli)


@app.route('/materi/hapus/<int:materi_id>')
def hapus_materi(materi_id):
    user = get_current_user()
    if not user or user.role != 'pengajar':
        return redirect(url_for('login'))

    try:
        kelas_id = user.hapus_materi(materi_id)
        flash('Materi berhasil dihapus!', 'success')
        return redirect(url_for('kelola_materi', kelas_id=kelas_id))
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('dashboard'))


# --- ROUTE TUGAS (BUAT, KUMPUL, KOMENTAR, NILAI) ---

@app.route('/kelas/<int:kelas_id>/tugas')
def daftar_tugas(kelas_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    kelas = database.ambil_kelas_by_id(kelas_id)
    if not kelas:
        flash('Kelas tidak ditemukan.', 'danger')
        return redirect(url_for('dashboard'))
    if not user.boleh_akses_kelas(kelas_id):
        flash('Kamu tidak punya akses ke kelas ini.', 'danger')
        return redirect(url_for('dashboard'))

    tugas_list = database.ambil_tugas_by_kelas(kelas_id)
    return render_template('tugas.html', kelas=kelas, tugas_list=tugas_list, user=user)


@app.route('/tugas/tambah/<int:kelas_id>', methods=['POST'])
def buat_tugas(kelas_id):
    user = get_current_user()
    if not user or user.role != 'pengajar':
        return redirect(url_for('login'))

    try:
        user.buat_tugas(kelas_id, request.form.get('judul', ''),
                        request.form.get('deskripsi', ''), request.form.get('deadline', ''))
        flash('Tugas berhasil dibuat!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('daftar_tugas', kelas_id=kelas_id))


@app.route('/tugas/<int:tugas_id>', methods=['GET'])
def detail_tugas(tugas_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    tugas = database.ambil_tugas_by_id(tugas_id)
    if not tugas:
        flash('Tugas tidak ditemukan.', 'danger')
        return redirect(url_for('dashboard'))
    if not user.boleh_akses_kelas(tugas['kelas_id']):
        flash('Kamu tidak punya akses ke tugas ini.', 'danger')
        return redirect(url_for('dashboard'))

    if user.role == 'siswa':
        pengumpulan = database.ambil_pengumpulan_by_tugas_siswa(tugas_id, user.id)
    else:
        pengumpulan = database.ambil_pengumpulan_by_tugas(tugas_id)
    komentar_list = database.ambil_komentar_tugas(tugas_id)

    return render_template('detail_tugas.html', tugas=tugas, pengumpulan=pengumpulan,
                           komentar_list=komentar_list, user=user)


@app.route('/tugas/<int:tugas_id>/kumpul', methods=['POST'])
def kumpul_tugas(tugas_id):
    user = get_current_user()
    if not user or user.role != 'siswa':
        return redirect(url_for('login'))

    filename = None
    try:
        filename = simpan_file('file_jawaban')
        if not filename:
            raise ValueError('Pilih file jawaban terlebih dahulu!')
        user.kumpul_tugas(tugas_id, filename)
        flash('Tugas berhasil dikumpulkan!', 'success')
    except ValueError as e:
        hapus_file(filename)
        flash(str(e), 'danger')
    return redirect(url_for('detail_tugas', tugas_id=tugas_id))


@app.route('/tugas/<int:tugas_id>/komentar', methods=['POST'])
def tambah_komentar_tugas(tugas_id):
    user = get_current_user()
    if not user or user.role not in ('siswa', 'pengajar'):
        return redirect(url_for('login'))

    try:
        user.komentar_tugas(tugas_id, request.form.get('isi_komentar', ''))
        flash('Komentar berhasil dikirim.', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('detail_tugas', tugas_id=tugas_id))


@app.route('/pengumpulan/<int:pengumpulan_id>/nilai', methods=['POST'])
def beri_nilai_tugas(pengumpulan_id):
    user = get_current_user()
    if not user or user.role != 'pengajar':
        return redirect(url_for('login'))

    data = database.ambil_pengumpulan_by_id(pengumpulan_id)
    if not data:
        flash('Pengumpulan tugas tidak ditemukan.', 'danger')
        return redirect(url_for('dashboard'))

    try:
        user.beri_nilai(pengumpulan_id, request.form.get('nilai', ''))
        flash('Nilai berhasil disimpan!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('detail_tugas', tugas_id=data['tugas_id']))


# --- ROUTE CATATAN AKHIR (dari profil siswa, oleh pengajar) ---
@app.route('/kelas/<int:kelas_id>/catatan/<int:siswa_id>', methods=['POST'])
def simpan_catatan_akhir(kelas_id, siswa_id):
    user = get_current_user()
    if not user or user.role != 'pengajar':
        return redirect(url_for('login'))

    try:
        user.beri_catatan_akhir(kelas_id, siswa_id, request.form.get('catatan', ''))
        flash('Catatan akhir berhasil disimpan!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('profil_siswa', siswa_id=siswa_id))


# --- ROUTE MONITORING ---
# TODO (Anggota 3): route Monitoring (tampilan rekap nilai, rekap presensi, catatan akhir).
# Datanya sudah siap dari model:
#   siswa    -> user.lihat_monitoring()
#   pengajar -> user.lihat_monitoring_siswa(siswa_id)   (dibuka dari tombol di profil siswa)
#   admin    -> user.monitoring_sistem()  /  user.lihat_monitoring_siswa(siswa_id)

# --- ROUTE PRESENSI (Anggota 4) ---
def siapkan_presensi_list(kelas_id):
    """Daftar pertemuan kelas (dari jadwal + presensi yang sudah ada), terbaru di atas.
    Tiap item: tanggal (YYYY-MM-DD), label ('Senin, 5 Oktober 2026'),
    status = {siswa_id: 'hadir'|'izin'|'sakit'|'alfa'} untuk mengisi radio button."""
    semua_tanggal = set(database.ambil_tanggal_jadwal_kelas(kelas_id)) | \
                    set(database.ambil_tanggal_presensi_kelas(kelas_id))
    hasil = []
    for tgl in sorted(semua_tanggal, reverse=True):
        try:
            label = Presensi.format_label(tgl)
        except ValueError:
            continue
        status = {p.siswa_id: p.status.lower() for p in Presensi.ambil_kelas(kelas_id, tgl)
                  if p.status in Presensi.STATUS_VALID}
        hasil.append({'tanggal': tgl, 'label': label, 'status': status})
    return hasil


@app.route('/kelas/<int:kelas_id>/presensi', methods=['POST'])
def simpan_presensi(kelas_id):
    user = get_current_user()
    if not user or user.role != 'pengajar':
        return redirect(url_for('login'))

    data_status = {}
    for s in database.ambil_siswa_by_kelas(kelas_id):
        st = request.form.get(f"st_{s['id']}")
        if st:
            data_status[s['id']] = st

    try:
        jumlah = user.catat_presensi_kelas(kelas_id, request.form.get('tanggal', ''), data_status)
        flash(f'Presensi {jumlah} siswa berhasil disimpan!', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    return redirect(url_for('detail_kelas', kelas_id=kelas_id) + '#p-presensi')


if __name__ == '__main__':
    app.run(debug=True)