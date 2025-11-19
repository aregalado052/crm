

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

    
from sqlalchemy import (
    Column,
    String,
    Date,
    Numeric,
    DateTime,
    CheckConstraint,
    Index,
    func,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.mysql import (
    BIGINT,
    TINYINT,
    ENUM as MySQLEnum,
)

Base = declarative_base()


class LeadForm(Base):
    __tablename__ = "lead_forms"

    id = Column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
    )

    session_id = Column(String(64), nullable=True)

    fecha_actual = Column(Date, nullable=False)
    fecha_proyecto = Column(Date, nullable=False)
    fecha_proxima_accion = Column(Date, nullable=False)

    name = Column(String(200), nullable=False)

    tipo_lead = Column(
        MySQLEnum("Distribuidor", "Club", "Sin calificar", name="tipo_lead_enum"),
        nullable=False,
        server_default="Sin calificar",
    )

    email = Column(String(254), nullable=False)
    origen = Column(String(20), nullable=True)
    vendedor = Column(String(20), nullable=True)
    quote_number = Column(String(50), nullable=False)

    idioma = Column(String(32), nullable=True)
    pais = Column(String(100), nullable=True)

    descuento_adicional = Column(Numeric(5, 2), nullable=True)
    descuento_total = Column(Numeric(5, 2), nullable=False)
    cantidad_total = Column(Numeric(15, 2), nullable=False)

    probabilidad_exito = Column(TINYINT(unsigned=True), nullable=False)

    pistas_perimetrales = Column(TINYINT(unsigned=True), nullable=True)
    pistas_laterales = Column(TINYINT(unsigned=True), nullable=True)

    estado = Column(
        MySQLEnum("En curso", "Ganada", "Perdida", "Sin calificar", name="estado_enum"),
        nullable=False,
    )

    info_tecnica = Column(String(1000), nullable=True)
    info_general = Column(String(1000), nullable=True)
    observaciones = Column(String(200), nullable=True)

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),  # CURRENT_TIMESTAMP
    )

    updated_at = Column(
        DateTime,
        nullable=True,
        server_default=func.now(),  # CURRENT_TIMESTAMP
        onupdate=func.now(),        # ON UPDATE CURRENT_TIMESTAMP
    )

    __table_args__ = (
        # Índices
        Index("idx_email", "email"),
        Index("idx_quote_number", "quote_number"),

        # CHECK constraints
        CheckConstraint("descuento_adicional BETWEEN 0 AND 100", name="lead_forms_chk_1"),
        CheckConstraint("descuento_total BETWEEN 0 AND 100", name="lead_forms_chk_2"),
        CheckConstraint("cantidad_total >= 0", name="lead_forms_chk_3"),
        CheckConstraint(
            "pistas_perimetrales BETWEEN 0 AND 20",
            name="lead_forms_chk_5",
        ),
        CheckConstraint(
            "pistas_laterales BETWEEN 0 AND 20",
            name="lead_forms_chk_6",
        ),
    )

