import io, os
from flask import Flask, send_from_directory, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_admin import Admin
from flask_socketio import SocketIO
from flask_migrate import Migrate
from flask_cors import CORS
# from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
from werkzeug.security import generate_password_hash
from flask_toastr import Toastr
from mailersend import emails
from sqlalchemy import create_engine
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from flask_sitemap import Sitemap
from flask_ckeditor import CKEditor, upload_fail, upload_success
from flask_flatpages import FlatPages
from datetime import timedelta

app = Flask(__name__)

load_dotenv()
socketio = SocketIO(cors_allowed_origins="*")
db = SQLAlchemy()
login_manager = LoginManager()
toastr = Toastr()
admin = Admin(name='admin')
ckeditor = CKEditor()
buffer = io.BytesIO()
migrate = Migrate(app, db)
ext = Sitemap(app=app)
mail = Mail()
flatpages = FlatPages()
mailer = emails.NewEmail(os.getenv('MAILERSEND_API_KEY'))

UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
# if not os.path.exists(UPLOAD_FOLDER):
#     os.makedirs(UPLOAD_FOLDER)

mysql_port = os.environ.get("MYSQLPORT", "3306")

mysql_uri = (f'mysql+pymysql://{os.environ.get("MYSQLUSER")}:'
        f'{os.environ.get("MYSQLPASSWORD")}@'
        f'{os.environ.get("MYSQLHOST")}:'
        f'{mysql_port}/'
        f'{os.environ.get("MYSQLDATABASE")}')

# Create engine only if all necessary environment variables are set
if all([os.environ.get("MYSQLUSER"), os.environ.get("MYSQLPASSWORD"),
        os.environ.get("MYSQLHOST"), os.environ.get("MYSQLDATABASE")]):
    engine = create_engine(mysql_uri)
    limiter = Limiter(
        key_func=get_remote_address,
        storage_uri=f"mysql://{mysql_uri}",
        storage_options={"engine": engine}
    )
else:
    print("Warning: MySQL environment variables are not fully set. Limiter will use in-memory storage.")
    limiter = Limiter(key_func=get_remote_address)

def create_app():
    app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", 'rindang_digifarm') # Gunakan variabel environment atau nilai default
    app.config['SQLALCHEMY_DATABASE_URI'] = mysql_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "pool_timeout": 20,
        "max_overflow": 5
    }
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Batasi ukuran file (misal: 16MB)
    app.config['SESSION_COOKIE_SECURE'] = True  # Untuk HTTPS
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_PROTECTION'] = 'strong'
    app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)  # atau durasi yang Anda inginkan
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=365)  # Maksimum lifetime
    app.config['REMEMBER_COOKIE_NAME'] = 'remember_token'

    # MAIL CONFIG
    app.config['MAIL_SERVER'] = str(os.environ.get('MAIL_SERVER', 'srv175.niagahoster.com'))
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 465))
    app.config['MAIL_USE_TLS'] = False
    app.config['MAIL_USE_SSL'] = True
    app.config['MAIL_USERNAME'] = str(os.environ.get('MAIL_USERNAME'))
    app.config['MAIL_PASSWORD'] = str(os.environ.get('MAIL_PASSWORD'))
    app.config['MAIL_DEFAULT_SENDER'] = str(os.environ.get('MAIL_DEFAULT_SENDER', 'official@rindang.net'))

    # CKEDITOR
    app.config['CKEDITOR_PKG_TYPE'] = 'standard'
    app.config['CKEDITOR_ENABLE_CSRF'] = True
    app.config['CKEDITOR_SERVE_LOCAL'] = True
    app.config['CKEDITOR_FILE_UPLOADER'] = 'upload'

    # Tambahkan ini untuk memastikan autentikasi SMTP
    app.config['MAIL_USE_CREDENTIALS'] = True
    app.config['MAIL_ASCII_ATTACHMENTS'] = False

    db.init_app(app)
    socketio.init_app(app)
    login_manager.init_app(app)
    toastr.init_app(app)
    ckeditor.init_app(app)
    flatpages.init_app(app)
    mail.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    from .auth.routes import auth
    from .views.routes import views
    from .admin.routes import admin_page

    app.register_blueprint(auth, url_prefix='/')
    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(admin_page, url_prefix='/')

    login_manager.login_view = 'auth.login'

    @app.route('/uploads/<path:filename>')
    def uploaded_files(filename):
        path = app.config['UPLOADED_PATH']
        return send_from_directory(path, filename)

    @app.route('/upload', methods=['POST'])
    def upload():
        f = request.files.get('upload')
        extension = f.filename.split('.')[-1].lower()
        if extension not in ['jpg', 'gif', 'png', 'jpeg']:  # Validate allowed extensions
            return upload_fail(message='Image only!')  # Customize error message
        f.save(os.path.join(app.config['UPLOADED_PATH'], f.filename))
        url = url_for('uploaded_files', filename=f.filename)
        return upload_success(url=url)

    with app.app_context():
        db.create_all()

        from App.models import User  # Ganti import Admin menjadi User

        # Cek apakah admin sudah ada
        admin = User.query.filter_by(role='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='official@rindang.net',
                password=generate_password_hash('admrindang123'),
                role='admin'
            )
            admin.is_confirmed = True
            db.session.add(admin)
            db.session.commit()

    return app

app = create_app()