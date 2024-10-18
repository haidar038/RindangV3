from flask import Blueprint, request, render_template, flash, redirect, url_for, session, Response, current_app, jsonify
from flask_login import login_required, logout_user, login_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Message
from datetime import datetime, timedelta
from App.utils import confirm_token, generate_confirmation_token, send_password_reset_email
from App.models import User, Personal, Ahli, Petani
from App import app, db, login_manager, mail, limiter

import logging, string, random, smtplib, os, tempfile, json

auth = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

PICTURE_ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def picture_allowed_file(filename):
    return '.' in filename and \
            filename.rsplit('.', 1)[1].lower() in PICTURE_ALLOWED_EXTENSIONS

def save_verification_document(user, document):
    filename = secure_filename(document.filename)
    relative_path = f'verification_docs/{user.id}/{filename}'
    full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'verification_docs', str(user.id))
    os.makedirs(full_path, exist_ok=True)
    document.save(os.path.join(full_path, filename))
    return relative_path

def save_temp_data(user_id, data):
    with tempfile.NamedTemporaryFile(mode='w', delete=False, prefix=f'user_{user_id}_', suffix='.json') as temp:
        json.dump(data, temp)
        return temp.name

# Define a custom error handler for unauthorized access
@auth.errorhandler(401)
def unauthorized(error):
    return Response(response="Unauthorized", status=401)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def general_unique_id(prefix="RU_", string_length=2, number_length=4):
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

def generate_username(email):
    """Generate a username from the email address."""
    username_base = email.split('@')[0]
    random_digits = ''.join(random.choice(string.digits) for _ in range(4))
    return f"{username_base}{random_digits}"

# Admin Login Route
@auth.route('/adminLogin', methods=['GET', 'POST'])
def adminLogin():
    """Handles admin login."""
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_page.index'))
        else:
            return redirect(url_for('views.dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['userPassword']

        admin_user = User.query.filter_by(username=username).first()

        if admin_user and check_password_hash(admin_user.password, password):
            session['role'] = 'admin'
            login_user(admin_user, remember=True)
            flash("Anda berhasil masuk!", category="success")
            return redirect(url_for('admin_page.index'))
        elif admin_user is None:
            flash(f"Akun dengan username {username} tidak ditemukan. Mungkin anda telah menggantinya!", category='warning')
            return redirect(url_for('auth.adminLogin'))
        else:
            flash("Kata sandi salah, coba lagi.", category='warning')
            return redirect(url_for('auth.adminLogin'))

    return render_template('admin-dashboard/login.html')

# User Login Route
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_page.index'))

    if request.method == 'POST':
        email = request.form['emailAddress']
        password = request.form['userPassword']
        remember = 'remember' in request.form

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            if not user.is_confirmed:
                flash('Harap konfirmasikan akun Anda sebelum login.', 'warning')
                return redirect(url_for('auth.login', email=email))
            
            login_user(user, remember=remember, duration=timedelta(days=30))  # Set remember me duration
            
            session['role'] = user.role  # Store user role in session
            flash("Berhasil Masuk!", category='success')
            
            if user.role == 'admin':
                return redirect(url_for('admin_page.index'))
            else:
                return redirect(url_for('views.index'))
        
        elif user is None:
            flash("Akun anda belum terdaftar, silakan daftar terlebih dahulu", category='warning')
        else:
            flash("Kata sandi salah, silakan coba lagi.", category='error')

    return render_template('auth/login.html', page='User', email=request.form.get('emailAddress', ''))

# User Registration Route
@auth.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for('views.index'))

    if request.method == 'POST':
        email = request.form['emailAddress']
        password = request.form['userPass']
        confirm_password = request.form['userPassConf']
        role = request.form.get('role', 'personal')
        unique_id = general_unique_id()
        username = generate_username(email)

        if len(password) < 8:
            flash('Kata sandi harus berisi 8 karakter atau lebih', category='error')
            return redirect(url_for('auth.register'))
        elif confirm_password != password:
            flash('Kata sandi tidak cocok.', category='error')
            return redirect(url_for('auth.register'))
        elif User.query.filter_by(email=email).first():
            flash('Email sudah digunakan, silakan buat yang lain.', category='error')
            return redirect(url_for('auth.register'))

        try:
            user = Personal(email=email, username=username, unique_id=unique_id, password=generate_password_hash(password))

            db.session.add(user)
            db.session.commit()

            try:
                send_confirmation_email(email)
                flash('Akun berhasil dibuat! Silahkan cek email Anda untuk verifikasi.', category='success')
            except Exception as email_error:
                current_app.logger.error(f"Gagal mengirim email konfirmasi: {str(email_error)}")
                flash('Akun berhasil dibuat, tetapi gagal mengirim email konfirmasi. Silakan hubungi admin.', 'warning')

            return redirect(url_for('auth.login'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error during registration: {str(e)}")
            flash('Terjadi kesalahan saat membuat akun. Silakan coba lagi.', category='error')
            return redirect(url_for('auth.register'))

    return render_template('auth/register.html', page='User')

def send_confirmation_email(user_email):
    try:
        token = generate_confirmation_token(user_email)
        confirm_url = url_for('auth.confirm_email', token=token, _external=True)
        html = render_template('auth/activate.html', confirm_url=confirm_url)
        subject = "Silakan konfirmasi email anda"
        msg = Message(subject=subject, sender=('official@rindang.net'), recipients=[user_email], html=html)
        
        current_app.logger.debug(f"Attempting to send email to {user_email}")
        current_app.logger.debug(f"Confirmation URL: {confirm_url}")
        
        with mail.connect() as conn:
            conn.send(msg)
        current_app.logger.info(f"Email sent successfully to {user_email}")
    except smtplib.SMTPAuthenticationError:
        current_app.logger.error("SMTP Authentication Error. Please check your username and password.")
        raise
    except smtplib.SMTPException as e:
        current_app.logger.error(f"SMTP error occurred: {str(e)}")
        raise
    except Exception as e:
        current_app.logger.error(f"Failed to send email: {str(e)}")
        current_app.logger.exception("Email sending error")
        raise

# @auth.route('/email_template')
# def email_template():
#     return render_template('auth/email_template.html', page='email_template')

@auth.route('/confirm/<token>')
def confirm_email(token):
    logger.info(f"Email confirmation attempt with token: {token[:10]}...")
    try:
        email = confirm_token(token)
    except:
        flash('Link konfirmasi tidak valid atau telah kedaluwarsa.', 'danger')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(email=email).first_or_404()
    if user.is_confirmed:
        flash('Akun sudah dikonfirmasi. Silakan login.', 'success')
    else:
        user.is_confirmed = True
        user.confirmed_on = datetime.now()
        db.session.add(user)
        db.session.commit()
        flash('Anda telah mengonfirmasi akun Anda. Terima kasih!', 'success')
    return redirect(url_for('auth.login'))

@auth.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    """Handles user request to reset forgotten password."""
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if user:
            send_password_reset_email(user)
            flash('Email untuk atur ulang kata sandi telah terkirim. Silahkan periksa kotak masuk anda.', 'info')
            return redirect(url_for('auth.login'))
        else:
            flash('Tidak ditemukan akun dengan email tersebut.', 'warning')
            return redirect(url_for('auth.forgot_password'))
    return render_template('auth/forgot_password.html')

@auth.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Handles password reset with the provided token."""
    user = User.verify_reset_password_token(token)
    if not user:
        flash('Token tidak valid atau sudah kadaluarsa', 'warning')
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if password != confirm_password:
            flash('Konfirmasi kata sandi tidak cocok.', 'danger')
            return redirect(url_for('auth.reset_password', token=token)) 
        
        user.password_hash=generate_password_hash(password, method='pbkdf2')

        db.session.commit()
        flash('Kata sandi anda telah diperbarui! Silahkan masuk dengan kata sandi baru.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/reset_password.html')

@auth.route('/resend')
@limiter.limit("3 per hour")
def resend_confirmation():
    if current_user.is_authenticated:
        return redirect(url_for('views.index'))

    return render_template('auth/resend_confirmation.html')

@auth.route('/resend', methods=['POST'])
def resend_confirmation_post():
    email = request.form['email']
    user = User.query.filter_by(email=email).first()

    if user:
        if user.is_confirmed:
            flash('Akun sudah dikonfirmasi. Silakan login.', 'info')
        else:
            send_confirmation_email(user.email)
            flash('Email konfirmasi baru telah dikirim.', 'success')
    else:
        flash('Tidak ditemukan akun dengan alamat email tersebut.', 'danger')

    return redirect(url_for('auth.login'))

# @auth.route('/upgrade/petani', methods=['GET', 'POST'])
# @login_required
# def upgrade_to_petani():
#     if current_user.role != 'personal':
#         flash('Anda sudah memiliki akun khusus', 'warning')
#         return redirect(url_for('dashboard'))
    
#     if request.method == 'POST':
#         # Process form data
#         document = request.files['verification_document']
#         if document and picture_allowed_file(document.filename):
#             filename = secure_filename(document.filename)
#             document.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
#             current_user.petani_request = True
#             current_user.verification_document = filename
#             db.session.commit()
            
#             flash('Permintaan upgrade ke akun Petani telah dikirim', 'success')
#             return redirect(url_for('dashboard'))
    
#     return render_template('upgrade_petani.html')

@auth.route('/upgrade_account/<int:id>', methods=['POST'])
@login_required
def upgrade_account(id):
    if current_user.id != id:
        flash('Unauthorized', 'warning')
        return redirect(request.referrer)

    account_type = request.form.get('accountType')
    verification_document = request.files.get('verificationDocument')

    if not account_type or not verification_document:
        flash('Data tidak lengkap', 'warning')
        return redirect(request.referrer)

    user = User.query.get(id)
    
    # Cek apakah user sudah memiliki role yang diminta
    if (account_type == 'petani' and user.role == 'petani') or (account_type == 'ahli' and user.role == 'ahli'):
        flash('Anda sudah memiliki role ini', 'warning')
        return redirect(request.referrer)

    filename = save_verification_document(user, verification_document)

    if account_type == 'petani':
        user.petani_request = True
        user.additional_info = {
            'luas_lahan': request.form.get('luasLahan')
        }
    elif account_type == 'ahli':
        user.ahli_request = True
        user.gelar = request.form.get('gelar')
        user.additional_info = {
            'bidang_keahlian': request.form.get('bidangKeahlian'),
            'gelar': request.form.get('gelar')
        }
    user.verification_document = filename
    db.session.commit()

    # return jsonify({'success': True, 'message': 'Permintaan upgrade akun berhasil dikirim'})
    flash('Permintaan upgrade akun berhasil dikirim', 'success')
    return redirect(request.referrer)

# Logout Route
@auth.route('/logout')
@login_required
def logout():
    try:
        # Logout the user
        logout_user()
        
        # Clear the session
        session.clear()
        
        flash('Anda telah berhasil keluar dari akun.', 'info')
        
        # Redirect to login page
        return redirect(url_for('auth.login'))
    except Exception as e:
        current_app.logger.error(f"Error during logout: {str(e)}")
        flash('Terjadi kesalahan saat mencoba keluar. Silakan coba lagi.', 'error')
        return redirect(url_for('views.dashboard'))