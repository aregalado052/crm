

from sqlalchemy import Column, Date, text,String, DateTime,  Index, ForeignKey
from datetime import datetime

from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import relationship

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

class LeadForm(db.Model):
    __tablename__ = "lead_forms"

    id = db.Column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
    )

    session_id = db.Column(db.String(64), nullable=True)

    fecha_actual = db.Column(db.Date, nullable=False)
    fecha_proyecto = db.Column(db.Date, nullable=False)
    fecha_proxima_accion = db.Column(db.Date, nullable=False)

    name = db.Column(db.String(200), nullable=False)

    tipo_lead = db.Column(
        MySQLEnum("Distribuidor", "Club", "Sin calificar", name="tipo_lead_enum"),
        nullable=False,
        server_default="Sin calificar",
    )

    email = db.Column(db.String(254), nullable=False)
    origen = db.Column(db.String(20), nullable=True)
    vendedor = db.Column(db.String(20), nullable=True)
    quote_number = db.Column(db.String(50), nullable=False)

    idioma = db.Column(db.String(32), nullable=True)
    pais = db.Column(db.String(100), nullable=True)

    descuento_adicional = db.Column(db.Numeric(5, 2), nullable=True)
    descuento_total = db.Column(db.Numeric(5, 2), nullable=False)
    cantidad_total = db.Column(db.Numeric(15, 2), nullable=False)

    probabilidad_exito = db.Column(TINYINT(unsigned=True), nullable=False)

    pistas_perimetrales = db.Column(TINYINT(unsigned=True), nullable=True)
    pistas_laterales = db.Column(TINYINT(unsigned=True), nullable=True)

    estado = db.Column(
        MySQLEnum("En curso", "Ganada", "Perdida", "Sin calificar", name="estado_enum"),
        nullable=False,
    )

    info_tecnica = db.Column(db.String(1000), nullable=True)
    info_general = db.Column(db.String(1000), nullable=True)
    observaciones = db.Column(db.String(200), nullable=True)

    unsubscribed = db.Column(db.Boolean, default=False, nullable=False)
    unsubscribed_at = db.Column(db.DateTime, nullable=True)
    proforma_solicitada = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default=db.text("0")
    )

    fecha_solicitud_proforma = db.Column(
        db.DateTime,
        nullable=True
    )


    # Renting
    renting_solicitado = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default=db.text("0")
    )

    fecha_solicitud_renting = db.Column(
        db.DateTime,
        nullable=True
    )

    renting_concedido = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default=db.text("0")
    )

    fecha_concedido_renting = db.Column(
        db.DateTime,
        nullable=True
    )

    renting_denegado = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default=db.text("0")
    )

    fecha_denegado_renting = db.Column(
        db.DateTime,
        nullable=True
    )
    email_suppressed = db.Column(
                db.Boolean,
                nullable=False,
                default=False
            )
    
    email_suppressed_at = db.Column(
        db.DateTime,
        nullable=True
    )

    email_suppressed_reason = db.Column(
        db.String(255),
        nullable=True
    )

   

    bounce_count = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    last_bounce_at = db.Column(
        db.DateTime,
        nullable=True
    )

    last_bounce_error = db.Column(
        db.Text,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.text("CURRENT_TIMESTAMP"),
    )


    updated_at = db.Column(
        db.DateTime,
        nullable=True,
        server_default=db.text("CURRENT_TIMESTAMP"),
        onupdate=db.text("CURRENT_TIMESTAMP"),
    )

    target_items = db.relationship(
        "LeadTargetItem",
        back_populates="lead",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        db.Index("idx_email", "email"),
        db.Index("idx_quote_number", "quote_number"),

        db.CheckConstraint(
            "descuento_adicional BETWEEN 0 AND 100",
            name="lead_forms_chk_1"
        ),
        db.CheckConstraint(
            "descuento_total BETWEEN 0 AND 100",
            name="lead_forms_chk_2"
        ),
        db.CheckConstraint(
            "cantidad_total >= 0",
            name="lead_forms_chk_3"
        ),
        db.CheckConstraint(
            "pistas_perimetrales BETWEEN 0 AND 20",
            name="lead_forms_chk_5"
        ),
        db.CheckConstraint(
            "pistas_laterales BETWEEN 0 AND 20",
            name="lead_forms_chk_6"
        ),
        
    )

class Newsletter(db.Model):
    __tablename__ = "newsletters"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    template_s3_path = db.Column(db.String(500), nullable=False)
    lang = db.Column(db.String(10), nullable=False)
    

    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)


from sqlalchemy.dialects.mysql import INTEGER

class Campaign(db.Model):
    __tablename__ = "campaigns"

    id = db.Column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)

    name = db.Column(db.String(150), nullable=False)
    campaign_type = db.Column(db.Enum("emailing", "newsletter"), nullable=False)

    status = db.Column(
        db.Enum("draft","ready","sending","sent","cancelled"),
        default="draft",
        nullable=False
    )

    scheduled_at = db.Column(db.DateTime)
    sent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)

    sender = db.Column(db.String(255), nullable=False)
    reply_to = db.Column(db.String(255), nullable=True)
    subject_es = db.Column(db.String(255), nullable=True)
    subject_en = db.Column(db.String(255), nullable=True)

    idioma = db.Column(db.String(10), nullable=True)

    newsletter_es_id = db.Column(INTEGER(unsigned=True), db.ForeignKey("newsletters.id"), nullable=True)
    newsletter_en_id = db.Column(INTEGER(unsigned=True), db.ForeignKey("newsletters.id"), nullable=True)

    newsletter_es = db.relationship("Newsletter", foreign_keys=[newsletter_es_id])
    newsletter_en = db.relationship("Newsletter", foreign_keys=[newsletter_en_id])

    recipients = db.relationship(
        "CampaignRecipient",
        back_populates="campaign",
        cascade="all, delete-orphan",
        passive_deletes=True
    )




class CampaignRecipient(db.Model):
    __tablename__ = "campaign_recipients"

    id = db.Column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)

    email = db.Column(db.String(255), nullable=False)
    lead_id = db.Column(INTEGER(unsigned=True), nullable=True)
    segment = db.Column(db.String(80))

    pais = db.Column(db.String(100))
    idioma = db.Column(db.String(10))
    origen = db.Column(db.String(100))

    tipo_lead = db.Column(db.String(50))
    estado = db.Column(db.String(50))

    entity_kind = db.Column(db.String(20))
    entity_id = db.Column(INTEGER(unsigned=True))

    seleccionado = db.Column(db.Boolean, nullable=False, default=True)

    send_status = db.Column(db.Enum(
        "pending",
        "sent",
        "error",
        "delivered",
        "open",
        "click",
        "bounced",
        "unsubscribe",
        "complained"
    ), default="pending", nullable=False)
    sent_at = db.Column(db.DateTime)
    opened_at = db.Column(db.DateTime)
    clicked_at = db.Column(db.DateTime)
    error_message = db.Column(db.String(500))

    ses_message_id = db.Column(db.String(255))

    delivered_at = db.Column(db.DateTime)
    bounced_at = db.Column(db.DateTime)
    bounce_type = db.Column(db.String(30))
    bounce_subtype = db.Column(db.String(80))
    bounce_diagnostic = db.Column(db.Text)

    


    complained_at = db.Column(db.DateTime)

    unsubscribe_token = db.Column(db.String(128), unique=True, index=True)
    tracking_id = db.Column(db.String(64), nullable=True, index=True)

    click_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime)


        # NUEVOS CAMPOS
    email_user = db.Column(db.String(255))
    email_password = db.Column(db.LargeBinary(512))

    url_contacto = db.Column(db.Text)
    url_ofertas = db.Column(db.Text)
    url_proformas = db.Column(db.String(512))
    url_actualizar_contacto = db.Column(db.String(512))
    url_form_contacto = db.Column(db.String(512))

    api_key = db.Column(db.LargeBinary(512))
    environment = db.Column(db.String(201))

    send_email = db.Column(db.Boolean, nullable=False, default=True)
    send_wellcome_email = db.Column(db.Boolean, nullable=False, default=True)





    campaign_id = db.Column(
        INTEGER(unsigned=True),
        db.ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False
    )

    campaign = db.relationship("Campaign", back_populates="recipients")

    __table_args__ = (
        db.UniqueConstraint("unsubscribe_token", name="uq_campaign_recipients_unsubscribe_token"),
        db.UniqueConstraint("tracking_id", name="uq_campaign_recipients_tracking_id"),
        db.UniqueConstraint("campaign_id", "email", name="uq_campaign_email"),
        db.Index('idx_campaign_entity', 'campaign_id', 'entity_kind', 'entity_id'),
    )
  

class LeadTarget(db.Model):
    __tablename__ = "lead_targets"

    id = db.Column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
    )

    nombre_target = db.Column(db.String(150), nullable=False)

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.text("CURRENT_TIMESTAMP"),
    )

    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.text("CURRENT_TIMESTAMP"),
        onupdate=db.text("CURRENT_TIMESTAMP"),
    )

    items = db.relationship(
        "LeadTargetItem",
        back_populates="target",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class LeadTargetItem(db.Model):
    __tablename__ = "lead_target_items"

    target_id = db.Column(
        BIGINT(unsigned=True),
        db.ForeignKey("lead_targets.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    lead_id = db.Column(
        BIGINT(unsigned=True),
        db.ForeignKey("lead_forms.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.text("CURRENT_TIMESTAMP"),
    )

    target = db.relationship("LeadTarget", back_populates="items")
    lead = db.relationship("LeadForm", back_populates="target_items")

    __table_args__ = (
        db.Index("idx_lead_target_items_lead_id", "lead_id"),
    )



class LeadCampaignHistory(db.Model):
    __tablename__ = "lead_campaign_history"

    id = db.Column(db.BigInteger, primary_key=True)

    lead_id = db.Column(db.BigInteger, nullable=True)
    campaign_id = db.Column(db.Integer, nullable=False)
    recipient_id = db.Column(db.Integer, nullable=True)

    email = db.Column(db.String(255), nullable=False)

    campaign_name = db.Column(db.String(150), nullable=False)
    campaign_type = db.Column(db.String(50), nullable=False)

    sent_at = db.Column(db.DateTime, nullable=False)

    send_status = db.Column(db.String(50), nullable=False)

    entity_kind = db.Column(db.String(20), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)

    

    idioma = db.Column(db.String(10))
    pais = db.Column(db.String(100))
    origen = db.Column(db.String(100))
    tipo_lead = db.Column(db.String(50))
    estado = db.Column(db.String(50))

    created_at = db.Column(db.DateTime, server_default=db.text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        db.Index("idx_campaign_entity", "campaign_id", "entity_kind", "entity_id"),
        db.UniqueConstraint("campaign_id", "entity_kind", "entity_id", name="uq_campaign_target"),
    )
class ProspectsIA(db.Model):
    __tablename__ = "prospects_IA"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    fecha = db.Column(db.Date, nullable=False)
    idioma = db.Column(db.String(100), nullable=False)
    pais = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), nullable=False, unique=True)

    club = db.Column(db.String(100))

    estado = db.Column(
        db.Enum('operativo', 'renovacion', 'concepto', 'proyecto', name='estado_enum'),
        nullable=False
    )

    tipo = db.Column(
        db.Enum('Sin Calificar', 'Distribuidor', 'Club', name='prospect_tipo_enum'),
        nullable=False,
        default='Sin Calificar',
        server_default='Sin Calificar'
    )

    propietario = db.Column(db.String(100))
    num_pistas = db.Column(db.Integer)

    web = db.Column(db.String(255))
    youtube = db.Column(db.String(100))
    instagram = db.Column(db.String(100))
    linkedin_club = db.Column(db.String(100))
    linkedin_propietario = db.Column(db.String(100))
    booking_app = db.Column(db.String(100))
    proveedor_pistas = db.Column(db.String(100))

    unsubscribed = db.Column(db.Boolean, default=False)
    unsubscribed_at = db.Column(db.DateTime)
    email_suppressed = db.Column(
    db.Boolean,
    nullable=False,
    default=False
)

    email_suppressed_at = db.Column(db.DateTime)

    email_suppressed_reason = db.Column(
        db.String(255)
    )

    bounce_count = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    last_bounce_at = db.Column(db.DateTime)

    last_bounce_error = db.Column(db.Text)


    lead_status = db.Column(
        db.Enum('prospect', 'lead'),
        nullable=False,
        default='prospect'
    )

    lead_converted_at = db.Column(db.DateTime, nullable=True)

    lead_converted_campaign_id = db.Column(
        db.Integer,
        db.ForeignKey("campaigns.id"),
        nullable=True
    )

    lead_converted_tracking_id = db.Column(db.String(64), nullable=True)

    source_id = db.Column(db.Integer, db.ForeignKey("prospect_sources.id"))
    source = db.relationship("ProspectSource", back_populates="prospects")

    target_items = db.relationship(
        "ProspectTargetItem",
        back_populates="prospect",
        cascade="all, delete-orphan"
    )



    

   



from sqlalchemy.dialects.mysql import BIGINT

class ProspectTarget(db.Model):
    __tablename__ = "prospect_targets"

    id = db.Column(BIGINT(unsigned=False), primary_key=True, autoincrement=True)

    name = db.Column(db.String(150), nullable=False)

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.text("CURRENT_TIMESTAMP")
    )

    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.text("CURRENT_TIMESTAMP"),
        onupdate=db.text("CURRENT_TIMESTAMP")
    )

    # Relación con items
    items = db.relationship(
        "ProspectTargetItem",
        back_populates="target",
        cascade="all, delete-orphan"
    )

class ProspectTargetItem(db.Model):
    __tablename__ = "prospect_target_items"

    target_id = db.Column(
        BIGINT(unsigned=False),
        db.ForeignKey("prospect_targets.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    prospect_id = db.Column(
        db.Integer,
        db.ForeignKey("prospects_IA.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.text("CURRENT_TIMESTAMP"),
    )

    # Relaciones
    target = db.relationship("ProspectTarget", back_populates="items")

    prospect = db.relationship("ProspectsIA", back_populates="target_items")

    __table_args__ = (
        db.Index("idx_prospect_target_items_prospect_id", "prospect_id"),
    )


    class ProspectSource(db.Model):
        __tablename__ = "prospect_sources"

        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        file_name = db.Column(db.String(255), nullable=False)
        description = db.Column(db.Text)
        created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

        prospects = db.relationship(
            "ProspectsIA",
            back_populates="source"
        )

class Pais(db.Model):
    __tablename__ = "pais"

    codigo = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True
    )

    codigo_pais = db.Column(
        db.CHAR(2),
        nullable=False
    )

    pais_es = db.Column(
        db.String(100),
        nullable=False
    )

    pais_en = db.Column(
        db.String(100),
        nullable=True
    )

    pais_fr = db.Column(
        db.String(100),
        nullable=True
    )

    pais_it = db.Column(
        db.String(100),
        nullable=True
    )

    zona = db.Column(
        db.String(100),
        nullable=False
    )

    mercado = db.Column(
        db.String(20),
        nullable=False,
        server_default="General"
    )

    __table_args__ = (
        db.UniqueConstraint(
            "codigo_pais",
            name="unique_codigo_pais"
        ),
        db.CheckConstraint(
            "REGEXP_LIKE(codigo_pais, '^[A-Z]{2}$')",
            name="pais_chk_1"
        ),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci"
        }
    )

    def __repr__(self):
        return (
            f"<Pais codigo={self.codigo} "
            f"codigo_pais='{self.codigo_pais}' "
            f"pais_es='{self.pais_es}'>"
        )


class EmailGenericoCategoria(db.Model):
    __tablename__ = "email_generico_categoria"

    codigo = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True
    )

    nombre = db.Column(
        db.String(100),
        nullable=False,
        unique=True
    )

    terminos = db.relationship(
        "EmailGenericoTermino",
        back_populates="categoria",
        cascade="all, delete-orphan",
        lazy="select"
    )

    def __repr__(self):
        return (
            f"<EmailGenericoCategoria "
            f"codigo={self.codigo} "
            f"nombre='{self.nombre}'>"
        )

class EmailGenericoTermino(db.Model):
    __tablename__ = "email_generico_termino"

    codigo = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True
    )

    categoria_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "email_generico_categoria.codigo",
            ondelete="CASCADE",
            onupdate="CASCADE"
        ),
        nullable=False,
        index=True
    )

    termino = db.Column(
        db.String(100),
        nullable=False
    )

    categoria = db.relationship(
        "EmailGenericoCategoria",
        back_populates="terminos"
    )

    __table_args__ = (
        db.UniqueConstraint(
            "categoria_id",
            "termino",
            name="unique_categoria_termino"
        ),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci"
        }
    )

    def __repr__(self):
        return (
            f"<EmailGenericoTermino "
            f"categoria_id={self.categoria_id} "
            f"termino='{self.termino}'>"
        )