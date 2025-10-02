

from sqlalchemy import Column, Integer, ForeignKey, SmallInteger, Date
from datetime import datetime

from app_init import db





# Tabla intermedia para relación muchos-a-muchos entre User y Project
user_project = db.Table('user_project',
    db.Column('uid', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('pid', db.Integer, db.ForeignKey('project.id'), primary_key=True)
)


# Modelo Account
class Account(db.Model):
    __tablename__ = 'account'

    uid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)

    users = db.relationship('User', backref='account', cascade='all, delete')
    projects = db.relationship('Project', backref='account', cascade='all, delete')






# Definir el modelo de usuario


class User(db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=True)
    password = db.Column(db.String(150), nullable=True)
    uid = db.Column(db.Integer, db.ForeignKey('account.uid'), nullable=True)
    uid_hytronik = db.Column(db.Integer, nullable=False)

    projects = db.relationship(
        'Project',
        secondary='user_project',
        back_populates='users'
    )




# Modelo ResetToken
class ResetToken(db.Model):
    __tablename__ = 'reset_token'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)

    user = db.relationship('User', backref='reset_tokens')

    
class Project(db.Model):
    __tablename__ = 'project'

    id = db.Column(db.Integer, primary_key=True)
    pid = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    uid = db.Column(db.Integer, db.ForeignKey('account.uid'), nullable=False)
    scheduler_name = db.Column(db.String(255), nullable=True)
    scheduler_arn = db.Column(db.String(512), nullable=True)
    ruta_login = db.Column(db.String(512), nullable=True)
    s_reservas = db.Column(db.String(60),nullable=True)


    users = db.relationship(
        'User',
        secondary='user_project',
        back_populates='projects'
    )

    

