from App import db, admin, app
from flask_login import UserMixin
from sqlalchemy.orm import column_property
from datetime import datetime
from flask_admin.contrib.sqla.view import ModelView
from flask_admin.base import BaseView, expose
from itsdangerous import URLSafeTimedSerializer

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), nullable=False, unique=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now())
    is_confirmed = db.Column(db.Boolean, nullable=False, default=False)
    is_verified = db.Column(db.Boolean, nullable=False, default=False)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    verification_document = db.Column(db.String(255), nullable=True)
    petani_request = db.Column(db.Boolean, default=False)
    ahli_request = db.Column(db.Boolean, default=False)
    unique_id = db.Column(db.String(100), unique=True, nullable=True)
    additional_info = db.Column(db.JSON, nullable=True)
    
    # Atribut umum untuk semua jenis pengguna
    nama_lengkap = db.Column(db.String(255), nullable=True)
    pekerjaan = db.Column(db.String(100), nullable=True)
    kelamin = db.Column(db.String(50), nullable=True)
    kota = db.Column(db.String(255), nullable=True)
    kec = db.Column(db.String(255), nullable=True)
    kelurahan = db.Column(db.String(255), nullable=True)
    bio = db.Column(db.String(255), nullable=True)
    profile_pic = db.Column(db.String(255), nullable=True)

    # Atribut untuk Petani
    luas_lahan = db.Column(db.Float, nullable=True)

    # Atribut untuk Ahli
    bidang_keahlian = db.Column(db.String(255), nullable=True)
    gelar = db.Column(db.String(100), nullable=True)

    __mapper_args__ = {
        'polymorphic_on': role,
        'polymorphic_identity': 'user'
    }

    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return f"User('{self.username}', '{self.email}', '{self.role}')"

class Admin(User):
    __mapper_args__ = {
        'polymorphic_identity': 'admin'
    }

class Personal(User):
    __mapper_args__ = {
        'polymorphic_identity': 'personal'
    }

class Petani(User):
    __mapper_args__ = {
        'polymorphic_identity': 'petani'
    }

class Ahli(User):
    __mapper_args__ = {
        'polymorphic_identity': 'ahli'
    }

user_kebun = db.Table('user_kebun',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id')),
    db.Column('kebun_id', db.Integer, db.ForeignKey('kebun.id'))
)

class Kebun(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unique_id = db.Column(db.String(20), nullable=True)
    nama = db.Column(db.String(255), nullable=True)
    foto = db.Column(db.String(100), nullable=True)
    luas_kebun = db.Column(db.Float, nullable=True)
    koordinat = db.Column(db.String(100), nullable=True, default='')
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)
    pangan_data = db.relationship('DataPangan', backref='Kebun', lazy=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    users = db.relationship('User', secondary=user_kebun, back_populates='kebun')

User.kebun = db.relationship('Kebun', secondary=user_kebun, back_populates='users')

class Komoditas(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(255), nullable=False)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)

class DataPangan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    jml_bibit = db.Column(db.Integer, nullable=False)
    komoditas = db.Column(db.String(50), nullable=False)
    tanggal_bibit = db.Column(db.Date, nullable=False)
    jml_panen = db.Column(db.Integer, nullable=True, default=0)
    tanggal_panen = db.Column(db.Date, nullable=True)
    estimasi_panen = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(50), nullable=True, default='Penanaman')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    komoditas_id = db.Column(db.Integer, db.ForeignKey('komoditas.id', ondelete='SET NULL'), nullable=True)
    kebun_id = db.Column(db.Integer, db.ForeignKey('kebun.id', ondelete='CASCADE'), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)

class Artikel(db.Model):
    __tablename__ = 'artikel'
    id = db.Column(db.Integer, primary_key=True)
    judul = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))  # Foreign key ke tabel 'users'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_approved = db.Column(db.Boolean, default=False)
    is_drafted = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)

    # Relationship ke tabel User
    user = db.relationship('User', backref='artikel')

class Forum(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now())
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    replied_at = db.Column(db.DateTime, nullable=True)
    replied_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)