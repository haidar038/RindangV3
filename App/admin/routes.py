from flask import Blueprint, request, render_template, flash, redirect, url_for, make_response, send_file, jsonify, current_app, send_from_directory, abort
from flask_login import login_required, current_user
from sqlalchemy import asc
from sqlalchemy.orm import make_transient
# from flask_jwt_extended.tokens import _encode_jwt, _decode_jwt
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from collections import defaultdict
from bs4 import BeautifulSoup
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, PageBreak, Paragraph, Image, Spacer, Flowable, KeepTogether
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.lib.styles import ParagraphStyle, TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import io, os, locale, json, tempfile, random, string

from App.models import User, DataPangan, Kebun, db, Forum, Artikel
# from App import admin, login_manager, socketio

admin_page = Blueprint('admin_page', __name__)

# locale.setlocale(locale.LC_ALL, 'id_ID.UTF-8')

def petani_unique_id(prefix="PR_", string_length=2, number_length=4):
    """
    Generates a unique ID in the format PR_AB1234.

    Args:
        prefix: The static identifier prefix (default: "KR_").
        string_length: The length of the random string part (default: 2).
        number_length: The length of the random number part (default: 4).

    Returns:
        A unique ID string.
    """
    random_string = ''.join(random.choices(string.ascii_uppercase, k=string_length))
    random_number = ''.join(random.choices(string.digits, k=number_length))
    unique_id = f"{prefix}{random_string}{random_number}"
    return unique_id

def ahli_unique_id(prefix="EXP_", string_length=2, number_length=4):
    """
    Generates a unique ID in the format EXP_AB1234.

    Args:
        prefix: The static identifier prefix (default: "KR_").
        string_length: The length of the random string part (default: 2).
        number_length: The length of the random number part (default: 4).

    Returns:
        A unique ID string.
    """
    random_string = ''.join(random.choices(string.ascii_uppercase, k=string_length))
    random_number = ''.join(random.choices(string.digits, k=number_length))
    unique_id = f"{prefix}{random_string}{random_number}"
    return unique_id

def save_verification_document(user, document):
    filename = secure_filename(document.filename)
    relative_path = f'verification_docs/{user.id}/{filename}'
    full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], relative_path)
    
    # Buat direktori jika belum ada
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    
    document.save(full_path)
    user.verification_document = relative_path
    db.session.commit()

@admin_page.route("/admin-dashboard", methods=['POST', 'GET'])
@login_required
def index():
    if current_user.role == 'user':
        return redirect(url_for('views.dashboard'))

    user = User.query.all()
    kelurahan = Kebun.query.all()
    produksi = DataPangan.query.all()

    # Mengakumulasi total panen berdasarkan kelurahan_id
    total_panen_per_kelurahan = defaultdict(int)
    for data in produksi:
        try:
            total_panen_per_kelurahan[data.kelurahan_id] += data.jml_panen
        except Exception as e:
            # Menangani error jika terjadi saat menambahkan data ke total_panen_per_kelurahan
            print(f"Error saat menambahkan data panen ke total_panen_per_kelurahan: {e}")

    try:
        total_kebun = sum(kel.kebun for kel in kelurahan)
    except Exception as e:
        # Menangani error jika terjadi saat menghitung total_kebun
        print(f"Error saat menghitung total kebun: {e}")
        total_kebun = 0

    try:
        total_panen = sum(prod.jml_panen for prod in produksi)
    except Exception as e:
        # Menangani error jika terjadi saat menghitung total_panen
        print(f"Error saat menghitung total panen: {e}")
        total_panen = 0

    stat_cabai = []
    stat_tomat = []
    for panenCabai in DataPangan.query.filter_by(komoditas='Cabai').all():
        totalCabai = panenCabai.jml_panen
        stat_cabai.append(totalCabai)
    for panenTomat in DataPangan.query.filter_by(komoditas='Tomat').all():
        totalTomat = panenTomat.jml_panen
        stat_tomat.append(totalTomat)

    totalPanenCabai = sum(stat_cabai)
    totalPanenTomat = sum(stat_tomat)

    if not current_user.is_authenticated:
        redirect(url_for('views.adminLogin'))
    return render_template('admin-dashboard/index.html', user=user, kelurahan=kelurahan, produksi=produksi, total_panen_per_kelurahan=total_panen_per_kelurahan, total_kebun=total_kebun, total_panen=total_panen, round_num=round, genhash=generate_password_hash, checkhash=check_password_hash, totalPanenCabai=totalPanenCabai, totalPanenTomat=totalPanenTomat)

@admin_page.route('/admin-dashboard/<string:username>/profil', methods=['POST', 'GET'])
@login_required
def profile(username):
    print(current_user.role)
    user = User.query.filter_by(username=username).first()
    return render_template('admin-dashboard/profile.html', user=user)

@admin_page.route('/admin-dashboard/<int:id>/profil/update-username', methods=['GET', 'POST'])
@login_required
def updateusername(id):
    user = User.query.get_or_404(id)
    password = request.form['userPass']

    if request.method == 'POST':
        if check_password_hash(current_user.password, password):
            user.username = request.form['username']
            db.session.commit()
            flash('Username berhasil diubah!', category='success')  # Assuming you have a flash message system
            return redirect((request.referrer))  # For successful update
        else:
            # Handle incorrect password scenario (e.g., flash a message or redirect)
            flash('Kata sandi salah, silakan coba lagi!', category='error')  # Assuming you have a flash message system
            return redirect(url_for('admin_page.profile', username=user.username))  # Redirect back to the form
        
@admin_page.route('/admin-dashboard/<int:id>/profil/update-password', methods=['GET', 'POST'])
@login_required
def updatepassword(id):
    user = User.query.get_or_404(id)
    oldpass = request.form['old-pass']
    newpass = request.form['new-pass']
    confnewpass = request.form['new-pass-conf']

    if request.method == 'POST':
        if check_password_hash(current_user.password, oldpass):
            if confnewpass != newpass:
                flash('Konfirmasi kata sandi tidak cocok!', 'error')
            else:
                user.password = generate_password_hash(newpass, method='pbkdf2')
                db.session.commit()
                flash('Kata sandi berhasil diperbarui!', category='success')  # Assuming you have a flash message system
                return redirect((request.referrer))  # For successful update
        else:
            # Handle incorrect password scenario (e.g., flash a message or redirect)
            flash('Kata sandi salah, silakan coba lagi!', category='error')  # Assuming you have a flash message system
            return redirect(url_for('admin_page.profile', username=user.username))  # Redirect back to the form

@admin_page.route('/admin-dashboard/user-management')
@login_required
def user_mgn():
    users = User.query.filter(User.role != 'admin').all()
    users_data = [
    {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'nama_lengkap': getattr(user, 'nama_lengkap', None),
        'role': user.role,
        'is_confirmed': user.is_confirmed,
        'petani_request': user.petani_request,
        'ahli_request': user.ahli_request,
        'verification_document': user.verification_document if hasattr(user, 'verification_document') else None
    }
        for user in users
    ]
    return render_template('admin-dashboard/user-management.html', users_data=users_data)

@admin_page.route('/verify_upgrades')
@login_required
def verify_upgrades():
    petani_requests = User.query.filter_by(petani_request=True, is_verified=False).all()
    ahli_requests = User.query.filter_by(ahli_request=True, is_verified=False).all()
    return render_template('admin/verify_upgrades.html', petani_requests=petani_requests, ahli_requests=ahli_requests)

@admin_page.route('/verification_docs/<path:filename>')
@login_required
def view_document(filename):
    # Pastikan hanya admin yang bisa mengakses
    if current_user.role != 'admin':
        abort(403)
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

@admin_page.route('/admin-dashboard/approve-upgrade/<int:user_id>', methods=['POST'])
@login_required
def approve_upgrade(user_id):
    user = User.query.get_or_404(user_id)
    additional_info = getattr(user, 'additional_info', {}) or {}

    try:
        if user.ahli_request:
            # Update user yang ada menjadi Ahli
            user.role = 'ahli'
            user.is_verified = True
            user.unique_id = ahli_unique_id()
            user.bidang_keahlian = additional_info.get('bidang_keahlian')
            user.gelar = additional_info.get('gelar')
            user.ahli_request = False
        elif user.petani_request:
            # Update user yang ada menjadi Petani
            user.role = 'petani'
            user.is_verified = True
            user.unique_id = petani_unique_id()
            user.luas_lahan = additional_info.get('luas_lahan')
            user.petani_request = False

        db.session.commit()
        return jsonify({'success': True, 'message': 'User upgrade approved'})
    except Exception as e:
        db.session.rollback()
        print(f"Error during upgrade: {str(e)}")
        return jsonify({'success': False, 'message': 'Error during upgrade'}), 500

@admin_page.route('/admin-dashboard/reject-upgrade/<int:user_id>', methods=['POST'])
@login_required
def reject_upgrade(user_id):
    user = User.query.get_or_404(user_id)
    user.petani_request = False
    user.ahli_request = False
    db.session.commit()
    return jsonify({'success': True, 'message': 'User upgrade rejected'})

def get_chart_data():
    kelurahan_data = {}
    kelurahan_list = Kebun.query.all()

    for kelurahan in kelurahan_list:
        panen_data = (
            db.session.query(DataPangan.jml_panen, DataPangan.tanggal_panen, DataPangan.komoditas)
            .filter_by(kelurahan_id=kelurahan.id)  # Hapus filter user_id
            .order_by(asc(DataPangan.tanggal_panen))
            .all()
        )

        if kelurahan.nama not in kelurahan_data:
            kelurahan_data[kelurahan.nama] = {}

        for data in panen_data:
            jml_panen, tgl_panen, komoditas = data
            if komoditas not in kelurahan_data[kelurahan.nama]:
                kelurahan_data[kelurahan.nama][komoditas] = {
                    'jml_panen': [],
                    'tgl_panen': [],
                    'komoditas': []
                }
            kelurahan_data[kelurahan.nama][komoditas]['jml_panen'].append(jml_panen)
            kelurahan_data[kelurahan.nama][komoditas]['tgl_panen'].append(tgl_panen)
            kelurahan_data[kelurahan.nama][komoditas]['komoditas'].append(komoditas)

    return kelurahan_data


@admin_page.route('/admin-dashboard/articles-management')
@login_required
def articles_mgn():
    datas = Artikel.query.all()
    
    all_data = [
        {
            'id': data.id,
            'judul': data.judul,
            'created_by': data.user.nama_lengkap if data.user else 'Unknown',  # Mengambil nama lengkap dari relasi user
            'created_at': data.created_at,
            'content': data.content,
            'is_approved': data.is_approved,
            'is_drafted': data.is_drafted,
            'is_deleted': data.is_deleted,
        }
        for data in datas
    ]
    return render_template('admin-dashboard/articles-management.html', all_data=all_data)

@admin_page.route('/admin-dashboard/articles-management/approve/<int:id>', methods=['GET', 'POST'])
@login_required
def approve_article(id):
    try:
        data = Artikel.query.get_or_404(id)
        if data.is_drafted:
            flash('Tidak dapat menyetujui karena artikel masih tersimpan sebagai draft!', 'warning')
            return redirect(request.referrer)
        else:
            data.is_approved = True
            db.session.commit()
            flash('Artikel berhasil disetujui', 'success')
            return redirect(request.referrer)
    except:
        flash('Terjadi kesalahan saat menyetujui artikel, silakan coba lagi', 'danger')
        return redirect(request.referrer)


@admin_page.route('/admin-dashboard/data-produksi', methods=['POST', 'GET'])
@login_required
def dataproduksi():
    if current_user.role == 'user':
        return redirect(url_for('views.dashboard'))

    kelurahan_list = Kebun.query.all()
    chart_data = get_chart_data()

    allDataCabai = DataPangan.query.filter_by(komoditas='Cabai').order_by(asc(DataPangan.tanggal_panen)).all()
    allDataTomat = DataPangan.query.filter_by(komoditas='Tomat').order_by(asc(DataPangan.tanggal_panen)).all()

    stat_cabai = []
    stat_tomat = []

    tgl_panen_cabai = []
    tgl_panen_tomat = []

    for panenCabai in allDataCabai:
        totalCabai = panenCabai.jml_panen
        tglPanenCabai = panenCabai.tanggal_panen
        stat_cabai.append(totalCabai)
        tgl_panen_cabai.append(tglPanenCabai)
    for panenTomat in allDataTomat:
        totalTomat = panenTomat.jml_panen
        tglPanenTomat = panenTomat.tanggal_panen
        stat_tomat.append(totalTomat)
        tgl_panen_tomat.append(tglPanenTomat)

    return render_template('admin-dashboard/data-produksi.html', chart_data=chart_data, kel=kelurahan_list, tgl_panen_cabai=tgl_panen_cabai, tgl_panen_tomat=tgl_panen_tomat, stat_cabai=json.dumps(stat_cabai), stat_tomat=json.dumps(stat_tomat))

@admin_page.route('admin-dashboard/data-produksi/<int:id>', methods=['POST', 'GET'])
@login_required
def dataproduksikel(id):
    if current_user.role == 'user':
        return redirect(url_for('views.dashboard'))
    
    kelurahan = Kebun.query.get_or_404(id)
    kelurahan_data = {}

    pangan = (
        db.session.query(DataPangan.jml_panen, DataPangan.tanggal_panen, DataPangan.komoditas)
        .filter_by(kelurahan_id=kelurahan.id)  # Hapus filter user_id
        .order_by(asc(DataPangan.tanggal_panen))
        .all()
    )

    if kelurahan.nama not in kelurahan_data:
        kelurahan_data[kelurahan.nama] = {}

    for data in pangan:
        jml_panen, tgl_panen, komoditas = data
        if komoditas not in kelurahan_data[kelurahan.nama]:
            kelurahan_data[kelurahan.nama][komoditas] = {
                'jml_panen': [],
                'tgl_panen': [],
                'komoditas': []
            }
        kelurahan_data[kelurahan.nama][komoditas]['jml_panen'].append(jml_panen)
        kelurahan_data[kelurahan.nama][komoditas]['tgl_panen'].append(tgl_panen)
        kelurahan_data[kelurahan.nama][komoditas]['komoditas'].append(komoditas)

    allDataCabai = DataPangan.query.filter_by(komoditas='Cabai').order_by(asc(DataPangan.tanggal_panen)).all()
    allDataTomat = DataPangan.query.filter_by(komoditas='Tomat').order_by(asc(DataPangan.tanggal_panen)).all()

    stat_cabai = []
    stat_tomat = []

    tgl_panen_cabai = []
    tgl_panen_tomat = []

    for panenCabai in allDataCabai:
        totalCabai = panenCabai.jml_panen
        tglPanenCabai = panenCabai.tanggal_panen
        stat_cabai.append(totalCabai)
        tgl_panen_cabai.append(tglPanenCabai)
    for panenTomat in allDataTomat:
        totalTomat = panenTomat.jml_panen
        tglPanenTomat = panenTomat.tanggal_panen
        stat_tomat.append(totalTomat)
        tgl_panen_tomat.append(tglPanenTomat)

    return render_template('/admin-dashboard/data-kelurahan.html', chart_data=kelurahan_data, kelurahan=kelurahan, stat_cabai=json.dumps(stat_cabai), stat_tomat=json.dumps(stat_tomat))

@admin_page.route("/admin-dashboard/laporan/userid=<int:id>", methods=['GET'])
@login_required
def report(id):
    locale.setlocale(locale.LC_ALL, 'id_ID')
    if current_user.role == 'user':
        return redirect(url_for('views.dashboard'))

    kel = Kebun.query.get_or_404(id)
    today = datetime.today()
    kmd = DataPangan.query.filter_by(kelurahan_id=kel.id).all()

    # Register Font    
    from App.run import app
    font_dir = os.path.join(app.root_path, 'static', 'fonts', 'plusjakarta')
    for font_file in os.listdir(font_dir):
        if font_file.endswith('.ttf'):
            font_path = os.path.join(font_dir, font_file)
            with open(font_path, 'rb') as f:  # Buka file font dalam mode biner
                font_name = font_file[:-4]
                pdfmetrics.registerFont(TTFont(font_name, f))

    # Render template HTML dengan data
    html = render_template('admin-dashboard/laporan.html', today=today, kel=kel, kmd=kmd, round_numb=round)

    # Buat buffer file
    buffer = io.BytesIO()

    # Parsing HTML dan ekstrak data tabel
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table')

    # print(table)
    
    # Periksa apakah tabel ditemukan
    if table is None:
        raise ValueError("Tabel dengan id 'report' tidak ditemukan dalam HTML")

    # Buat dokumen PDF
    BASE_MARGIN = 2 * cm
    page_width, page_height = A4
    total_margin_width = 2 * BASE_MARGIN
    available_table_width = page_width - total_margin_width
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=BASE_MARGIN,  # Increased top margin
        leftMargin=BASE_MARGIN,
        rightMargin=BASE_MARGIN,
        bottomMargin=BASE_MARGIN
    )

    # Ekstrak data tabel
    data = []
    for row in table.find_all('tr'):
        cells = row.find_all('td')
        if not cells:  # Jika tidak ada sel data, gunakan sel header
            cells = row.find_all('th')
        data.append([cell.text.strip() for cell in cells])
    
    h1_style = ParagraphStyle(name='Heading1', fontName='PlusJakartaSans-Bold', fontSize=22, alignment=TA_CENTER)
    normal_style = ParagraphStyle(name='Normal', fontName='PlusJakartaSans-Regular', fontSize=12)
    date_style = ParagraphStyle(name='Date', fontName='PlusJakartaSans-Italic', fontSize=10, alignment=TA_RIGHT, textColor=colors.gray)
    
    col_widths = [available_table_width / len(data[0])] * len(data[0])
    table_width = page_width - 2 * BASE_MARGIN
    table_style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.Color(0.533, 0.788, 0.482)),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'PlusJakartaSans-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        # ('BOX', (0, 0), (-1, -1), 1, colors.gray),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.Color(0,0,0,0.25)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Align text to the top
        # ('ALIGN', (1, 0), (-1, -1), 'CENTER'),  # Center align text in columns 1 and onwards
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),  # Center align text in columns 1 and onwards
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),  # Center align text in columns 1 and onwards
    ])

    # for i in range(len(data)):
    #     table_style.add('LINEABOVE', (0,i), (-1,i), 1, colors.gray)
    #     table_style.add('LINEBELOW', (0,i), (-1,i), 1, colors.gray)

    # Buat tabel
    table = Table(data, style=table_style, rowHeights=1*cm, colWidths=[1.25*cm, 3.85*cm],
              repeatRows=1, splitByRow=True, hAlign='CENTER')
    title = Paragraph("Laporan Produksi", h1_style )

    # Buat elemen-elemen untuk dokumen
    # elements.append(table)

    # Logo
    logo_path = os.path.join(app.root_path, 'static', 'logo', 'rindang-logo-y.png')
    
    # Dapatkan ukuran gambar asli
    image_reader = ImageReader(logo_path)
    img_width, img_height = image_reader.getSize()
    aspect_ratio = img_width / img_height

    # Tentukan tinggi gambar yang diinginkan
    desired_height = 12*mm
    # Hitung lebar gambar berdasarkan rasio aspek
    desired_width = desired_height * aspect_ratio

    # Buat objek Image dengan ukuran yang dihitung
    today = Paragraph(today.strftime('%A, %d %B %Y'), date_style)

    logo = Image(logo_path, width=desired_width, height=desired_height, hAlign='LEFT')
    logo_and_time = Table([[logo, today]], colWidths=[desired_width, table_width - desired_width])
    logo_and_time.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Vertically align logo and title in the middle
    ]))

    elements = [
        logo_and_time,
        Spacer(0, 15),
        title,
        Spacer(0, 32),
        Paragraph(f"Kebun: {kel.nama}", normal_style),
        Spacer(0, 4),
        Paragraph(f"Jumlah Kebun: {kel.kebun} Kebun", normal_style),
        Spacer(0, 15),
        table
    ]

    # doc.build([layout_table], canvasmaker=canvas.Canvas)
    doc.build(elements, canvasmaker=canvas.Canvas)

    # Reset posisi buffer ke awal
    buffer.seek(0)

    response = make_response(buffer.getvalue())
    # response.headers['Content-Disposition'] = f'attachment; filename=Report_of_{kel.nama}.pdf'
    response.headers['Content-Disposition'] = f'inline; filename=Report_of_{kel.nama}.pdf'
    response.mimetype = 'application/pdf'

    response.set_cookie('pdf-filename', f'Report_of_{kel.nama}.pdf')
    response.direct_passthrough = True  # Prevent automatic download

    pdf_value = buffer.getvalue()
    # buffer.close()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
        temp_pdf.write(buffer.getvalue())
        temp_pdf_path = temp_pdf.name

    # Kirimkan file sementara menggunakan send_file
    return send_file(
        temp_pdf_path,
        as_attachment=True,
        download_name=f'Report_of_{kel.nama}.pdf',
        mimetype='application/pdf'
    )
    return render_template('admin-dashboard/laporan.html', today=today, kel=kel, kmd=kmd, round_numb=round, pdf_value=pdf_value)