import pandas as pd
import math
from datetime import datetime

EXCEL_FILE = "campana_19.xlsx"
OUTPUT_SQL = "insert_campaign_19.sql"
CAMPAIGN_ID = 19

def sql_value(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "NULL"

    if isinstance(v, pd.Timestamp):
        if pd.isna(v):
            return "NULL"
        return "'" + v.strftime("%Y-%m-%d %H:%M:%S") + "'"

    s = str(v).strip()
    if s == "" or s.lower() in ("nan", "nat", "none"):
        return "NULL"

    s = s.replace("\\", "\\\\").replace("'", "''")
    return f"'{s}'"

def sql_int(v, default="NULL"):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return default
    s = str(v).strip()
    if s == "":
        return default
    return str(int(float(s)))

df = pd.read_excel(EXCEL_FILE)

df = df[
    (df["ID Campaña"] == 19) &
    (df["Tipo origen"].fillna("").str.strip().str.lower() == "prospect")
]

# Solo campaña 19
df = df[df["ID Campaña"] == CAMPAIGN_ID]

columns = [
    "campaign_id",
    "email",
    "lead_id",
    "segment",
    "send_status",
    "sent_at",
    "delivered_at",
    "opened_at",
    "clicked_at",
    "bounced_at",
    "complained_at",
    "last_event",
    "click_count",
    "tracking_id",
    "ses_message_id",
    "entity_kind",
    "entity_id",
    "idioma",
    "pais",
    "origen",
    "tipo_lead",
    "estado"
]

with open(OUTPUT_SQL, "w", encoding="utf-8") as f:
    f.write("START TRANSACTION;\n\n")

    for _, row in df.iterrows():
        values = [
            sql_int(row.get("ID Campaña")),
            sql_value(row.get("Email")),
            sql_int(row.get("ID Lead")),
            sql_value(row.get("Segmento")),
            sql_value(row.get("Estado envío") or "pending"),
            sql_value(row.get("Fecha envío email")),
            sql_value(row.get("Fecha entrega")),
            sql_value(row.get("Fecha apertura")),
            sql_value(row.get("Fecha clic")),
            sql_value(row.get("Fecha rebote")),
            sql_value(row.get("Fecha queja")),
            sql_value(row.get("Último evento")),
            sql_int(row.get("Número de clics"), default="0"),
            sql_value(row.get("Tracking ID")),
            sql_value(row.get("ID mensaje SES")),
            sql_value(row.get("Tipo origen")),
            sql_int(row.get("ID origen")),
            sql_value(row.get("Idioma")),
            sql_value(row.get("País")),
            sql_value(row.get("Origen")),
            sql_value(row.get("Tipo lead")),
            sql_value(row.get("Estado contacto")),
        ]

        f.write(
            f"INSERT INTO campaign_recipients ({', '.join(columns)}) "
            f"VALUES ({', '.join(values)});\n"
        )

    f.write("\nCOMMIT;\n")

print(f"Generado {OUTPUT_SQL} con {len(df)} filas.")