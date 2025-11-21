# -*- coding: utf-8 -*-
"""
Módulo para importar/normalizar emails/HTML como plantillas,
rehostear imágenes en S3 y opcionalmente subir la plantilla completa al bucket.

Requisitos:
  pip install premailer beautifulsoup4 lxml jinja2 boto3 requests
"""
import html
import os
import re
import json
import uuid
import base64
import mimetypes
from urllib.parse import quote as urlquote
from email import policy
from email.parser import BytesParser
from urllib.parse import urlparse
import requests
import boto3
import botocore
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from PIL import Image
import io
from flask import Response as FlaskResponse

from pathlib import Path



# Ajusta a tu raíz real



BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_ROOT = (BASE_DIR / "emails" / "templates").resolve()
print("[BOOT] TEMPLATES_ROOT =", TEMPLATES_ROOT)






from config import (ROOT_PREFIX_S3,AWS_REGION,S3_BUCKET, USE_S3)





from premailer import transform

# =========================
# Configuración
# =========================








_MAX_IMG_BYTES = 10 * 1024 * 1024  # 10MB
_EXT_BY_CT = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/svg+xml": "svg",
    "image/bmp": "bmp",
}

_session = None
_s3 = None


def get_s3():
    """Cliente S3 singleton con región configurada."""
    global _session, _s3
    if _s3 is None:
        _session = boto3.session.Session(region_name=AWS_REGION)
        _s3 = _session.client("s3")
    return _s3


def slugify(s: str) -> str:
    """Convierte un string en un slug seguro para nombres de carpetas/archivos."""
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9\-_.]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-") or "template"





def put_public_s3(
    key: str,
    content: bytes | str,
    content_type: str | None = None,
    cache_seconds: int | None = 31536000,   # None => no tocar Cache-Control
) -> str:
    """
    Sube un objeto a S3 con ContentType y Cache-Control adecuados.
    - Para recursos versionados por query (?v=etag), usa cache_seconds alto (p.ej. 31536000) + immutable.
    - Para recursos mutables (HTML/manifest), pasa cache_seconds=0 para poner no-cache.
    Devuelve URL virtual-hosted con región.
    """
    if not USE_S3:
        raise RuntimeError("S3 no está habilitado (S3_BUCKET vacío)")

    if isinstance(content, str):
        content = content.encode("utf-8")

    # Content-Type (si no viene, intenta deducir por extensión)
    if not content_type:
        guess, _ = mimetypes.guess_type(key)
        content_type = guess or "application/octet-stream"

    # Cache-Control según Beael caso
    headers = {}
    if cache_seconds is None:
        pass  # no establecer Cache-Control/Expires
    elif cache_seconds <= 0:
        headers["CacheControl"] = "no-cache, no-store, must-revalidate"
        headers["Expires"] = "0"
    else:
        headers["CacheControl"] = f"public, max-age={cache_seconds}, immutable"
        # opcional: no pongas Expires cuando max-age está presente

    s3 = get_s3()
    args = dict(
        Bucket=S3_BUCKET,
        Key=key,
        Body=content,
        ContentType=content_type,
        **headers,
    )

    try:
        s3.put_object(ACL="public-read", **args)
    except botocore.exceptions.ClientError as e:
        code = (e.response.get("Error") or {}).get("Code", "")
        if code in ("AccessControlListNotSupported", "AccessDenied"):
            s3.put_object(**args)  # bucket con BPA/Owner Enforced
        else:
            raise

    key_enc = urlquote(key, safe="/")
    return f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{key_enc}"

# =========================
# Carga de fuente (EML/HTML)
# =========================

def load_email_source(path_or_html: str) -> str:
    """
    Acepta:
      - ruta a .eml → extrae el text/html
      - ruta a .html
      - string con HTML
    """
    if not path_or_html:
        return ""

    if path_or_html.lower().endswith(".eml") and os.path.exists(path_or_html):
        with open(path_or_html, "rb") as f:
            msg = BytesParser(policy=policy.default).parse(f)
        html_part = None
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    # Usa el payload decodificado para respetar charset
                    payload = part.get_payload(decode=True) or b""
                    charset = part.get_content_charset() or "utf-8"
                    html_part = payload.decode(charset, errors="replace")
                    break
        else:
            if msg.get_content_type() == "text/html":
                payload = msg.get_payload(decode=True) or b""
                charset = msg.get_content_charset() or "utf-8"
                html_part = payload.decode(charset, errors="replace")
        return html_part or ""

    # Ruta a archivo HTML
    if os.path.exists(path_or_html):
        with open(path_or_html, "r", encoding="utf-8") as f:
            return f.read()

    # Asumimos que ya es HTML
    return path_or_html


# =========================
# Rehost de imágenes
# =========================

from typing import Callable, Optional, Tuple, Dict, Any

_MAX_IMG_BYTES = 20 * 1024 * 1024  # tu límite
# _guess_ext(ct, hint) -> ya la tienes con 2 parámetros

def rehost_image_final(
    src: str,
    *,
    slug: str,
    alloc_id,
    cid_resolver: Callable[[str], tuple[bytes, str]] | None = None,     # ej. lambda cid: (bytes, content_type)
    _memo: dict[str, str] | None = None
) -> str:
    if not src:
        return src
    memo = _memo if _memo is not None else {}
    if src in memo:
        return memo[src]

    def _store(content: bytes, ct: str, hint: str = "") -> str:
        ext = _guess_ext(ct, hint)
        img_id = str(alloc_id())
        key = f"emails/templates/{slug}/images/{img_id}.{ext}"
        put_public_s3(key, content, ct, cache_seconds=31536000)
        url = public_url(key)
        memo[src] = url
        return url

    # cid:
    if src.startswith("cid:") and cid_resolver:
        cid = src[4:]
        content, ct = cid_resolver(cid)  # debe devolver (bytes, content_type)
        return _store(content, ct, f"cid.{ct.split('/')[-1]}")

    # data:
    if src.startswith("data:"):
        header, payload = src.split(",", 1)
        ct = header.split(";")[0].split(":")[1] if ":" in header else "application/octet-stream"
        is_b64 = ";base64" in header
        content = base64.b64decode(payload) if is_b64 else payload.encode("utf-8")
        if len(content) > _MAX_IMG_BYTES:
            raise ValueError("Imagen inline supera el límite permitido")
        return _store(content, ct, f"cid.{ct.split('/')[-1]}")

    # http(s):
    if src.startswith("http://") or src.startswith("https://"):
        try:
            r = requests.get(src, timeout=20, allow_redirects=True, stream=True)
            r.raise_for_status()
        except requests.RequestException as e:
            raise ValueError(f"No se pudo descargar la imagen: {src} • {e}") from e
        ct = r.headers.get("Content-Type", "application/octet-stream")
        content = r.content
        if len(content) > _MAX_IMG_BYTES:
            raise ValueError(f"Imagen remota demasiado grande: {len(content)} bytes")
        return _store(content, ct, src)

    # rutas relativas → devuélvelas tal cual (se resolverán más tarde si corresponde)
    return src


# =========================
# Normalización HTML
# =========================
def normalize_html(html: str, *, slug: str | None = None) -> BeautifulSoup:
    inlined = transform(html, remove_classes=False, disable_validation=True)
    soup = BeautifulSoup(inlined, "lxml")

    for tag in soup(["script", "iframe", "object", "style"]):
        tag.decompose()

    if slug:
        alloc = make_id_allocator(1)
        for img in soup.find_all("img"):
            src = (img.get("src") or "").strip()
            if not src:
                continue
            try:
                # sube DIRECTO a emails/templates/<slug>/images/<id>.<ext>
                new_src = rehost_image_final(src, slug=slug, alloc_id=alloc)
                img["src"] = new_src
                if not img.get("alt"):
                    img["alt"] = "image"
            except Exception:
                pass

    return soup



def find_ctas(soup: BeautifulSoup):
    """Heurística sencilla para detectar CTAs tipo botón."""
    ctas = []
    for a in soup.find_all("a"):
        text = (a.get_text() or "").strip()
        href = (a.get("href") or "").strip()
        style = (a.get("style") or "").lower()
        classes = a.get("class") or []
        is_button = ("padding" in style) or ("background" in style) or ("btn" in classes)
        if href and (is_button or len(text) <= 30):
            ctas.append(a)
    return ctas





def s3_list(prefix: str):
    """Debug: lista objetos en S3 bajo un prefijo."""
    s3 = get_s3()
    try:
        resp = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix, MaxKeys=50)
        return [it["Key"] for it in resp.get("Contents", [])]
    except Exception as e:
        print("[DEBUG] list_objects error:", repr(e))
        return []
    

def enumerate_images_and_tag(soup: BeautifulSoup):
    """
    Asegura data-img-id incremental en cada <img> y devuelve metadatos básicos.
    """
    images = []
    next_id = 1
    for img in soup.find_all("img"):
        img_id = img.get("data-img-id")
        if not img_id:
            img_id = str(next_id)
            img["data-img-id"] = img_id
            next_id += 1
        else:
            try:
                n = int(img_id)
                next_id = max(next_id, n + 1)
            except ValueError:
                img["data-img-id"] = str(next_id)
                img_id = str(next_id)
                next_id += 1

        src = (img.get("src") or "").strip()
        alt = (img.get("alt") or "").strip() or f"image-{img_id}"
        images.append({"id": int(img_id), "src": src, "alt": alt})
    images.sort(key=lambda x: x["id"])
    return images


def to_placeholders(soup: BeautifulSoup) -> BeautifulSoup:
    """Sustituye contenido por placeholders Jinja pensados para la plantilla."""
    # Headline
    h1 = soup.find(["h1"]) or soup.find(["h2"])
    if h1:
        h1.string = "{{ headline }}"




        # Hero: primer <img>
    images = soup.find_all("img")
    if images:
        hero = images[0]
        hero["data-img-id"] = hero.get("data-img-id") or "1"
        # NO cambiamos hero["src"] -> lo dejamos apuntando al asset subido
        # hero["src"] = "{{ hero_url }}"
        hero["alt"] = hero.get("alt") or "{{ hero_alt | default('Hero') }}"
        



    # Texto principal → colapsa <p> a un bloque de contenido editable
    paragraphs = soup.find_all("p")
    if len(paragraphs) >= 2:
        first_parent = paragraphs[0].parent
        placeholder = soup.new_tag("div")
        placeholder.string = "{{ html_content | safe }}"
        for p in list(first_parent.find_all("p")):
            p.decompose()
        first_parent.append(placeholder)

    # CTAs
    for a in find_ctas(soup):
        a.string = "{{ cta_label }}"
        a["href"] = "{{ cta_url_wrapped }}"

    # Unsubscribe
    footer = soup.find(string=re.compile("darse de baja|unsubscribe", re.I))
    if footer and getattr(footer, "parent", None) is not None and footer.parent.name == "a":
        footer.parent["href"] = "{{ unsubscribe_url }}"
    else:
        body = soup.body or soup
        unsub = soup.new_tag("a", href="{{ unsubscribe_url }}")
        unsub.string = "Darse de baja"
        p = soup.new_tag("p")
        p.append(unsub)
        body.append(p)

    # Pixel
    pixel = soup.new_tag("img", src="{{ open_pixel_url }}")
    pixel["width"] = "1"
    pixel["height"] = "1"
    pixel["style"] = "display:none;"
    (soup.body or soup).append(pixel)

    return soup


def generate_schema() -> dict:
    """Esquema de variables editable por marketing/ops."""
    return {
         "variables": {
            "subject": "Asunto del email",
            "headline": "Título principal",
            "hero_url": "https://.../banner.jpg",
            "hero_alt": "Texto alternativo",
            "html_content": "",  # <- antes: "Contenido en HTML…"
            "cta_label": "Ver más",
            "cta_url": "https://tu-sitio.com/oferta",
            "cta_url_wrapped": "...",
            "unsubscribe_url": "...",
            "open_pixel_url": "...",
            "company_address": "Dirección legal / contacto"
        }
    }


def to_mjml(_html_soup: BeautifulSoup) -> str:
    """
    Conversión mínima a MJML para tener un punto de partida.
    Mejora esto según tu diseño real.
    """
    parts = []
    parts.append('<mjml><mj-body background-color="#f6f9fc">')
    parts.append('<mj-section><mj-column>')
    parts.append('<mj-image src="{{ hero_url }}" alt="{{ hero_alt }}" />')
    parts.append('<mj-text font-size="20px" font-weight="700">{{ headline }}</mj-text>')
    parts.append('<mj-text>{{ html_content }}</mj-text>')
    parts.append('<mj-button href="{{ cta_url_wrapped }}">{{ cta_label }}</mj-button>')
    parts.append('<mj-text font-size="12px">¿No quieres recibir más emails? <a href="{{ unsubscribe_url }}">Darse de baja</a><br/>{{ company_address }}</mj-text>')
    parts.append('</mj-column></mj-section>')
    parts.append('</mj-body></mjml>')
    return "\n".join(parts)

def generate_initial_manifest(slug: str, images_meta: list[dict], lang: str = "en") -> dict:
    """
    Manifest inicial con imágenes COMPARTIDAS.
    - NO aplica reglas de tamaño aquí.
    - Si images_meta ya trae target_w/target_h/fit, se copian.
    - Si no, luego ensure_dimensions_if_missing(slug) los rellenará.
    """
    base = f"emails/templates/{slug}"
    shared_dir = f"{base}/images/"   # imágenes compartidas (sin idioma)

    def _filename(it: dict) -> str:
        # Preferimos filename si viene del extractor
        if it.get("filename"):
            return it["filename"]
        # Si no, construimos a partir de id + ext/content_type
        ext = (it.get("ext")
               or (it.get("content_type", "").split("/")[-1] if it.get("content_type") else "")
               or "jpg").lstrip(".").lower()
        return f"{it['id']}.{ext}"

    # Nodo de idioma: paths y attachments (sin images_dir aquí)
    lang_node = {
        "name": slug,
        "paths": {
            "html":     f"{base}/{lang}/template.html",
            "mjml":     f"{base}/{lang}/template.mjml",
            "schema":   f"{base}/{lang}/schema.json",
            "original": f"{base}/{lang}/original.html",
        },
        "attachments": [],
        # los parciales del mensaje se rellenan luego (upsert_partials_in_manifest)
    }

    # Construye shared.images: solo key + (copiar dims si ya vienen)
    shared_images = {}
    for it in images_meta:
        name = _filename(it)
        entry = {
            "key": f"{shared_dir}{name}",
            # url/etag/last_modified los pondrá update_manifest(slug)
        }
        # Si el uploader ya calculó tamaños, conservarlos
        for k in ("target_w", "target_h", "fit"):
            if k in it and it[k] is not None:
                entry[k] = it[k]
        # Si marcaste is_logo durante la clasificación, consérvalo
        if it.get("is_logo") is True:
            entry["is_logo"] = True

        shared_images[name] = entry

    return {
        "slug": slug,
        "display_name": slug,
        "default_lang": lang,
        "languages": { lang: lang_node },
        "shared": {
            "images_dir": shared_dir,
            "images": shared_images,
            "attachments": [],
            # los parciales de firma se añaden luego (upsert_shared_signature_in_manifest)
        },
        # espejo por compatibilidad
        "images_dir": shared_dir,
        "updated_at": None,
    }


def upload_template_dir_to_s3(local_dir: str, slug: str) -> dict:
    """
    Sube todo el directorio de salida a:
      s3://{bucket}/emails/templates/{slug}/...
    Devuelve {'base_prefix': ..., 'files': [{'key':..., 'url':...}, ...]}
    """
    if not USE_S3:
        raise RuntimeError("S3 no está habilitado (S3_BUCKET vacío)")

    results = []
    base_prefix = f"emails/templates/{slug.strip('/')}/"
    for root, _, files in os.walk(local_dir):
        for name in files:
            path = os.path.join(root, name)
            rel = os.path.relpath(path, local_dir).replace("\\", "/")
            key = base_prefix + rel
            ct, _ = mimetypes.guess_type(name)
            with open(path, "rb") as f:
                content = f.read()
            url = put_public_s3(key, content, ct or "application/octet-stream")
            results.append({"key": key, "url": url})
    return {"base_prefix": base_prefix, "files": results}


def rehost_images_under_template(soup: BeautifulSoup, slug: str):
    """
    Sube cada <img> a s3://{bucket}/emails/templates/<slug>/images/{id}.{ext}
    y reescribe el src a la URL pública.
    Requiere que previamente exista data-img-id en cada <img>.
    """
    for img in soup.find_all("img"):
        src = (img.get("src") or "").strip()
        if not src:
            continue
        img_id = img.get("data-img-id")
        if not img_id:
            # si por lo que sea no está, saltamos (o podrías asignarlo aquí)
            continue

        # 1) obtener bytes + content-type (soporta data:, http(s), relativo)
        content = None
        ct = None
        ext_hint = None

        if src.startswith("data:"):
            header, payload = src.split(",", 1)
            ct = header.split(";")[0].split(":")[1] if ":" in header else "application/octet-stream"
            is_b64 = ";base64" in header
            content = base64.b64decode(payload) if is_b64 else payload.encode("utf-8")
            ext_hint = src  # por si _guess_ext quiere usarlo
        elif src.startswith("http://") or src.startswith("https://"):
            r = requests.get(src, timeout=20, allow_redirects=True, stream=True)
            r.raise_for_status()
            ct = r.headers.get("Content-Type", "application/octet-stream")
            content = r.content
            ext_hint = src
        else:
            # ruta relativa local → intenta leer del filesystem si existe
            if os.path.exists(src):
                with open(src, "rb") as f:
                    content = f.read()
                ct, _ = mimetypes.guess_type(src)
                ext_hint = src
            else:
                # si no podemos leerla, la dejamos tal cual
                continue

        if content is None:
            continue

        # 2) decidir extensión final y clave destino
        ext = _guess_ext(ct, ext_hint)
        key = f"emails/templates/{slug}/images/{img_id}.{ext}"

        # 3) subir y reemplazar src
        url = put_public_s3(key, content, ct or "application/octet-stream")
        img["src"] = url

        # ALT mínimo
        if not img.get("alt"):
            img["alt"] = f"image-{img_id}"


def build_framework(
    input_path_or_html,
    out_dir="output",
    slug: str | None = None,
    lang: str | None = None,
    upload_to_s3: bool = True,
    display_name: str | None = None,
    lang_attachments: list | None = None
) -> dict:
    """
    Flujo clave:
      1) normalize_html
      2) rewrite_images_to_final_and_upload  -> todas las <img> quedan como .../images/N.ext
      3) extract_message_and_signature_from_html sobre el HTML reescrito
      4) clasificar imágenes (message vs signature) y actualizar manifest (is_logo cuando toque)
      5) limpiar cuerpo (sin imágenes) y filtrar firma (solo logos; si no hay allow-list => sin imágenes)
      6) subir parciales (message por idioma, signature compartida)
      7) placeholders + guardar template/mjml/schema
      8) upsert manifest del idioma + actualizar sección images con ?v=<etag>
    """
    if not slug:
        raise ValueError("slug requerido")

    os.makedirs(out_dir, exist_ok=True)
    lang = (lang or "en").lower()

    # 1) Guarda original local
    raw = load_email_source(input_path_or_html)
    if not raw:
        raise RuntimeError("No se pudo leer el email/HTML de entrada.")
    original_path = os.path.join(out_dir, "original.html")
    with open(original_path, "w", encoding="utf-8") as f:
        f.write(raw)

    # 2) Normaliza HTML (inline CSS, limpieza…)
    soup_norm = normalize_html(raw)
    html_norm = str(soup_norm)













    # 3) rehost
    html_imgs_final, images_meta = rewrite_images_to_final_and_upload(html_norm, slug=slug)

    # 4) split robusto (nuevo)
    # 4) Split conservador
    msg_html, sig_html = _extract_signature_bottom_up(html_imgs_final)

    print("msg_html sample:", msg_html[:200])
    print("sig_html sample:", sig_html[:200])
    print("[DEBUG] sig AFTER extract:", sorted(_collect_basenames_from_html(sig_html)))

    msg_html_full = html_imgs_final

# Debug opcional
    #print("[DEBUG] sig sample:", BeautifulSoup(sig_html or "", "lxml").get_text(" ", strip=True)[:200])

    # nombres que realmente están en el cuerpo (antes de quitarles imágenes)
    msg_names_before_clean = _collect_basenames_from_html(msg_html)

    # --- Fallback logos: si la firma no trae <img>, rescata PNGs del final, excluyendo los del cuerpo ---
    sig_html = _sig_rescue_tail_pngs(
        full_html=html_imgs_final,
        current_sig_html=sig_html,
        body_names=msg_names_before_clean,
        max_imgs=2,   # ⬅ solo dos logos
    )
    # debug temprano
    from bs4 import BeautifulSoup
    print("[DEBUG] sig BEFORE imgs:", sorted(_collect_basenames_from_html(sig_html)))
    sig_txt_dbg = BeautifulSoup(sig_html or "", "lxml").get_text(" ", strip=True)
    print("[DEBUG] sig text sample:", sig_txt_dbg[:200])

        # === FILTRO: eliminar de la firma cualquier imagen >= 30KB ===
   

    SIGNATURE_MAX_BYTES = 30 * 1024  # 30 KB

    # construimos mapa basename -> size
    sizes_by_name: dict[str, int] = {}
    for meta in images_meta or []:
        src = (meta.get("url") or meta.get("key") or "").strip()
        if not src:
            continue
        name = os.path.basename(src.split("?", 1)[0]).lower()

        sz = meta.get("size") or meta.get("filesize") or meta.get("length") or 0
        try:
            sz = int(sz)
        except (TypeError, ValueError):
            sz = 0

        if name:
            sizes_by_name[name] = sz

    # limpiamos la firma: fuera todas las imágenes grandes
    soup_sig = BeautifulSoup(sig_html or "", "lxml")
    changed = False
    for im in list(soup_sig.find_all("img")):
        src = (im.get("src") or "").strip()
        if not src:
            continue
        base = os.path.basename(src.split("?", 1)[0]).lower()
        sz = sizes_by_name.get(base, 0)
        if sz >= SIGNATURE_MAX_BYTES:
            # imagen demasiado grande para estar en la firma
            im.decompose()
            changed = True

    if changed:
        sig_html = str(soup_sig)
        print("[DEBUG] signature cleaned by size; remaining imgs:",
              sorted(_collect_basenames_from_html(sig_html)))
    # === FIN FILTRO POR TAMAÑO EN FIRMA ===

   
    # Cuerpo: SIEMPRE sin imágenes
    msg_html = remove_all_images(msg_html)

    # === Firma: mantener solo logos y NUNCA fotos grandes ===
    sig_names = _collect_basenames_from_html(sig_html)
    print("[DEBUG] sig ALL imgs:", sorted(sig_names))

    # 1) lee manifest (si existe) y toma los is_logo explícitos
    man = _load_manifest_from_s3(slug) or {}
    shared_images = (man.get("shared") or {}).get("images") or {}
    explicit_logo = {n.lower() for n, meta in shared_images.items() if meta.get("is_logo")}

    # 2) decide allow-list
    if explicit_logo:
        # usa SOLO las imágenes que estén en firma y además marcadas como logo en manifest
        allowed = sig_names & explicit_logo
    else:
        # fallback: asumimos que los logos son PNG, las fotos (jpg) NO van en la firma
        allowed = {n for n in sig_names if n.lower().endswith(".png")}

    print("[DEBUG] sig allow-list (logos permitidos):", sorted(allowed))

    from bs4 import BeautifulSoup

    if allowed:
        # dejamos SOLO las imágenes que estén en allowed
        sig_html = keep_only_logo_images(sig_html, allowed)
    else:
        # si no tenemos ningún logo reconocido,
        # ELIMINAMOS TODAS las imágenes de la firma (pero dejamos el texto)
        sig_html = remove_all_images(sig_html)

    # (IMPORTANTE) eliminar TODO el bloque viejo:
    # if sig_names:
    #     if explicit_logo:
    #         ...
    #     else:
    #         print("[DEBUG] sig allow-list (no explicit): (no filtramos)")
    # ...

    


       
    
    # 8) Guardar parciales locales
    # justo después de calcular msg_html/sig_html y limpiarlos
    out_dir_lang = os.path.join(out_dir, lang)
    msg_dir = os.path.join(out_dir_lang, "partials")
    os.makedirs(msg_dir, exist_ok=True)

    with open(os.path.join(msg_dir, "message.html"), "w", encoding="utf-8") as f:
        f.write(msg_html or "")
    with open(os.path.join(msg_dir, "message.txt"), "w", encoding="utf-8") as f:
        f.write(BeautifulSoup(msg_html or "", "lxml").get_text(" ", strip=True))

    # Aunque la firma esté vacía, subimos un placeholder pequeño para que “exista”
    sig_html_to_save = sig_html or '<!-- empty-signature -->'
    with open(os.path.join(msg_dir, "signature.html"), "w", encoding="utf-8") as f:
        f.write(sig_html_to_save)
    with open(os.path.join(msg_dir, "signature.txt"), "w", encoding="utf-8") as f:
        f.write(BeautifulSoup(sig_html or "", "lxml").get_text(" ", strip=True))

    # (la firma compartida no hace falta guardarla local si no quieres)

    if upload_to_s3 and USE_S3:
        base_lang = f"emails/templates/{slug}/{lang}/partials/"
        print("[DEBUG] S3 put:", base_lang + "message.html")
        put_public_s3(base_lang + "message.html",
                    (msg_html or "").encode("utf-8"),
                    "text/html; charset=utf-8", cache_seconds=0)
        print("[DEBUG] S3 put:", base_lang + "message.txt")
        put_public_s3(base_lang + "message.txt",
                    BeautifulSoup(msg_html or "", "lxml").get_text(" ", strip=True).encode("utf-8"),
                    "text/plain; charset=utf-8", cache_seconds=0)

        shared_base = f"emails/templates/{slug}/partials/"
        sig_html_to_upload = sig_html or "<!-- empty-signature -->"
        print("[DEBUG] S3 put:", shared_base + "signature.html")
        put_public_s3(shared_base + "signature.html",
                    sig_html_to_upload.encode("utf-8"),
                    "text/html; charset=utf-8", cache_seconds=0)
        print("[DEBUG] S3 put:", shared_base + "signature.txt")
        put_public_s3(shared_base + "signature.txt",
                    BeautifulSoup(sig_html or "", "lxml").get_text(" ", strip=True).encode("utf-8"),
                    "text/plain; charset=utf-8", cache_seconds=0)


 

    template_no_sig = remove_signature_block_by_images(html_imgs_final, sig_html)

    
    
    # 10) Placeholders conservativos y archivos de plantilla locales
    soup_final = to_placeholders_conservative(BeautifulSoup(template_no_sig or "", "lxml"))
    html_path   = os.path.join(out_dir, "template.html")
    mjml_path   = os.path.join(out_dir, "template.mjml")
    schema_path = os.path.join(out_dir, "schema.json")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(template_no_sig)


    #with open(html_path, "w", encoding="utf-8") as f:
    #    f.write(str(soup_final))
    with open(mjml_path, "w", encoding="utf-8") as f:
        f.write(to_mjml(soup_final))
    schema = generate_schema()
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)

    # 11) (opcional) manifest local de debug
    manifest_local = generate_initial_manifest(slug, images_meta, lang=lang)
    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_local, f, indent=2, ensure_ascii=False)

    # 12) Sube archivos de plantilla (NO cache fuerte)
    s3_keys = {}
    if upload_to_s3 and USE_S3:
        base_prefix = f"emails/templates/{slug}/"
        lang_prefix = f"{base_prefix}{lang}/"
        with open(original_path, "rb") as f:
            put_public_s3(f"{lang_prefix}original.html", f.read(), "text/html; charset=utf-8", cache_seconds=0)
        with open(html_path, "rb") as f:
            put_public_s3(f"{lang_prefix}template.html", f.read(), "text/html; charset=utf-8", cache_seconds=0)
        with open(mjml_path, "rb") as f:
            put_public_s3(f"{lang_prefix}template.mjml", f.read(), "application/xml", cache_seconds=0)
        with open(schema_path, "rb") as f:
            put_public_s3(f"{lang_prefix}schema.json", f.read(), "application/json", cache_seconds=0)

        s3_keys = {
            "original_key": f"{lang_prefix}original.html",
            "html_key":     f"{lang_prefix}template.html",
            "mjml_key":     f"{lang_prefix}template.mjml",
            "schema_key":   f"{lang_prefix}schema.json",
        }

        # 13) Upsert manifest del idioma (y shared.images_dir) — PRIMERO
        shared_dir = f"{base_prefix}images/"
        upsert_manifest_lang(
            slug=slug,
            lang=lang,
            display_name=display_name or slug,
            paths={
                "html":     f"{lang_prefix}template.html",
                "mjml":     f"{lang_prefix}template.mjml",
                "schema":   f"{lang_prefix}schema.json",
                "original": f"{lang_prefix}original.html",
            },
            lang_attachments=lang_attachments or [],
            images_dir=None,                 # NO por idioma (usamos el común)
            shared_images_dir=shared_dir     # común
        )

        # 14) Apuntar parciales en el manifest (ya existe)
        upsert_shared_signature_in_manifest(slug)   # shared.partials.signature_*
        upsert_partials_in_manifest(slug, lang)     # languages[lang].partials.message_*

        # 15) Reconstruir 'images' con ?v=<etag> (conserva target_w/h/fit/is_logo)
        update_manifest(slug)
        ensure_dimensions_if_missing(slug)  # añade target_w/target_h/fit si faltan

    return {
        "html_template": html_path,
        "mjml_template": mjml_path,
        "schema": schema_path,
        "manifest": manifest_path,
        "s3": s3_keys,
    }


def bucket_exists(bucket: str) -> bool:
    s3 = get_s3()
    try:
        s3.head_bucket(Bucket=bucket)
        return True
    except botocore.exceptions.ClientError as e:
        code = (e.response.get("Error") or {}).get("Code", "")
        if code in ("404", "NoSuchBucket"):
            return False
        # Región incorrecta → tratar como inexistente
        if code in ("301", "PermanentRedirect", "AuthorizationHeaderMalformed"):
            return False
        raise





def rehost_images_under_template_from_html(html: str, slug: str):
    soup = BeautifulSoup(html, "lxml")
    uploaded, skipped = [], []
    next_id = 1

    def _clean_ct(ct: str) -> str:
        return (ct or "application/octet-stream").split(";")[0].strip().lower()

    def put_bytes(content: bytes, ct: str, hint: str = "") -> str:
        ext = _guess_ext(ct, hint)  # usa tu helper o mimetypes
        key = f"emails/templates/{slug}/images/{next_id}.{ext}"
        return put_public_s3(key, content, ct or "application/octet-stream")

    for img in soup.find_all("img"):
        src = (img.get("src") or "").strip()
        if not src:
            continue

        if src.lower().startswith("cid:"):
            skipped.append({"src": src, "reason": "cid_in_html_send_eml"})
            continue

        try:
            if src.startswith("data:"):
                header, payload = src.split(",", 1)
                ct = _clean_ct(header.split(":")[1].split(";")[0] if ":" in header else "")
                content = base64.b64decode(payload) if ";base64" in header else payload.encode("utf-8")
                url = put_bytes(content, ct)

            elif src.startswith(("http://", "https://")):
                r = requests.get(src, timeout=20)
                r.raise_for_status()
                ct = _clean_ct(r.headers.get("Content-Type", "application/octet-stream"))
                url = put_bytes(r.content, ct, hint=src)

            elif os.path.exists(src):
                with open(src, "rb") as f:
                    content = f.read()
                ct, _ = mimetypes.guess_type(src)
                url = put_bytes(content, _clean_ct(ct or "application/octet-stream"), hint=src)

            else:
                skipped.append({"src": src, "reason": "unhandled_scheme_or_missing_file"})
                continue

            img["src"] = url
            if not img.get("alt"):
                img["alt"] = f"image-{next_id}"
            img["data-img-id"] = img.get("data-img-id") or str(next_id)
            uploaded.append({"id": next_id, "url": url})
            next_id += 1

        except Exception as e:
            skipped.append({"src": src, "reason": f"exception:{repr(e)}"})

    print("[DEBUG] rehost uploaded:", len(uploaded), "skipped:", skipped[:3])
    return str(soup), {"uploaded": uploaded, "skipped": skipped}

def resolve_cid_with_attachments(html: str, slug: str, attachments: list):
    """
    attachments: [{"cid": "...", "filename":"...", "content_type":"...", "data_base64":"..."}]
    Devuelve (html_resuelto, info)
      info = {"resolved":[cid...], "unresolved":[cid...]}
    """
   
    soup = BeautifulSoup(html, "lxml")

    def norm(s): return (s or "").strip().lower()
    by_cid = { norm(a.get("cid")): a for a in attachments if a.get("cid") and a.get("data_base64") }
    resolved, unresolved = [], []

    next_id = 1 + len(soup.find_all("img"))

    for img in soup.find_all("img"):
        src = (img.get("src") or "").strip()
        if not src.lower().startswith("cid:"):
            continue
        cid = norm(src[4:])
        att = by_cid.get(cid)
        if not att:
            # intenta limpiar <> " ' espacios
            cid2 = re.sub(r"[<>\"'\s]", "", cid)
            att = by_cid.get(cid2)
        if not att:
            unresolved.append(cid)
            continue

        content = base64.b64decode(att["data_base64"])
        ct = att.get("content_type") or "application/octet-stream"
        ext = _guess_ext(ct, att.get("filename") or "")
        key = f"emails/templates/{slug}/images/{next_id}.{ext}"
        url = put_public_s3(key, content, ct)
        img["src"] = url
        img["data-img-id"] = str(next_id)
        if not img.get("alt"): img["alt"] = att.get("filename") or f"image-{next_id}"
        resolved.append(cid)
        next_id += 1

    return str(soup), {"resolved": resolved, "unresolved": unresolved}



# funciones_generar_email.py



def _manifest_key(slug: str) -> str:
    return f"emails/templates/{slug}/manifest.json"

def _empty_manifest(slug: str, display_name: str | None) -> dict:
    return {
        "slug": slug,
        "display_name": display_name or slug,
        "default_lang": "en",
        "languages": {},
        "shared": {
            "images_dir": f"emails/templates/{slug}/images/",
            "attachments": []
        },
        "images_dir": f"emails/templates/{slug}/images/",
        "updated_at": int(datetime.now(timezone.utc).timestamp()),
    }

def _load_manifest_from_s3(slug: str) -> dict | None:
    s3 = get_s3()
    mk = _manifest_key(slug)
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=mk)
        return json.loads(obj["Body"].read())
    except s3.exceptions.NoSuchKey:
        return None

def _save_manifest_to_s3(slug: str, manifest: dict) -> None:
    s3 = get_s3()
    mk = _manifest_key(slug)
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=mk,
        Body=json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
        CacheControl="no-cache, no-store, must-revalidate",
        Expires=0,
    )

def _migrate_legacy_manifest(manifest: dict) -> dict:
    # Hook opcional por si vienes de formatos antiguos
    return manifest

def upsert_manifest_lang(
    slug: str,
    lang: str,
    display_name: str | None = None,
    paths: dict | None = None,
    lang_attachments: list | None = None,
    images_dir: str | None = None,      # si lo pasas, se guarda a nivel de idioma
    shared_images_dir: str | None = None # opcional: para fijar/actualizar el común
) -> dict:
    """
    Crea/actualiza el manifest de la plantilla `slug` para el idioma `lang`.
    - `paths`: dict con claves html/mjml/schema/original (las que tengas).
    - `lang_attachments`: lista de adjuntos para el idioma.
    - `images_dir`: carpeta de imágenes para este idioma (si usas por-idioma).
    - `shared_images_dir`: si pasas uno común, se guarda en manifest['shared']['images_dir'].
    """
    lang = (lang or "en").lower()

    manifest = _load_manifest_from_s3(slug)
    if manifest is None:
        manifest = _empty_manifest(slug, display_name)
    else:
        manifest = _migrate_legacy_manifest(manifest)

    # display_name a nivel plantilla (si lo pasas, lo actualiza)
    if display_name:
        manifest["display_name"] = display_name

    # shared images_dir (común) si te interesa fijarlo/actualizarlo
    if shared_images_dir:
        manifest.setdefault("shared", {}).setdefault("attachments", [])
        manifest["shared"]["images_dir"] = shared_images_dir
        manifest["images_dir"] = shared_images_dir  # espejo por compatibilidad

    # nodo del idioma
    manifest.setdefault("languages", {})
    node = manifest["languages"].setdefault(lang, {})
    node.setdefault("attachments", [])
    node.setdefault("paths", {})

    if shared_images_dir:
        node["images_dir"] = shared_images_dir
    elif images_dir:
        # Si explícitamente te pasan un images_dir por idioma, úsalo.
        node["images_dir"] = images_dir
    else:
        # Hereda el común si no hay otro
        node.setdefault("images_dir", manifest.get("images_dir"))

    # nombre para el idioma (opcional: si quieres mostrarlo distinto)
    if display_name and not node.get("name"):
        node["name"] = display_name

    # paths (solo sobreescribe los que pases)
    if paths:
        node["paths"].update(paths)

    # images_dir por idioma (si lo pasas, lo fija aquí)
    if images_dir:
        node["images_dir"] = images_dir
    else:
        # si no lo pasas y no existe uno previo, hereda el común por comodidad
        node.setdefault("images_dir", manifest.get("images_dir"))

    # adjuntos del idioma
    if lang_attachments is not None:
        node["attachments"] = lang_attachments

    # marca de actualización
    manifest["updated_at"] = int(datetime.now(timezone.utc).timestamp())

    # guardar
    _save_manifest_to_s3(slug, manifest)
    return manifest



def insert_extra_files_into_html(html: str, slug: str, lang: str, attachments: list):
    # ...
    key = f"emails/templates/{slug}/attachments/{lang}/{fname}"  # 👈 POR IDIOMA
    url = put_public_s3(key, content, ct)
    uploaded.append({"filename": fname, "content_type": ct, "key": key, "url": url, "lang": lang})
    # ...
    return str(soup), uploaded




def extract_default_context_from_html(raw_html: str) -> dict:
    soup = BeautifulSoup(raw_html, "lxml")

    # Headline: primer h1/h2
    h = soup.find(["h1", "h2"])
    headline = (h.get_text(strip=True) if h else "Demo Headline")

    # Hero: primer <img>
    img = soup.find("img")
    hero_url = (img.get("src") or "").strip() if img else ""
    hero_alt = (img.get("alt") or "Imagen") if img else "Imagen"

    # Cuerpo: primeros bloques de texto
    blocks = []
    for node in soup.find_all(["p", "ul", "ol", "table", "blockquote"], limit=8):
        blocks.append(str(node))
        if len(blocks) >= 6:
            break
    html_content = "".join(blocks) or "<p>Contenido de demostración…</p>"

    return {
        "subject": "Vista previa • Demo",
        "headline": headline,
        "hero_url": hero_url,
        "hero_alt": hero_alt,
        "html_content": html_content,
        "cta_label": "Ver más",
        "cta_url": "https://example.com",
        "cta_url_wrapped": "https://example.com/click?u=demo",
        "unsubscribe_url": "https://example.com/unsubscribe",
        "open_pixel_url": "data:image/gif;base64,R0lGODlhAQABAAAAACw=",
        "company_address": "Compañía • Dirección"
    }






def _guess_ext(ct: str, hint: str = "") -> str:
    """
    Devuelve la extensión de archivo sin punto (jpg, png, gif...) a partir
    del Content-Type o del nombre/hint de la URL.
    """
    ct = (ct or "").lower().strip()
    hint = (hint or "").split("?", 1)[0].split("#", 1)[0]  # limpia query/fragment
    hint_lower = hint.lower()

    # 1) Si viene content-type, intenta mapear con mimetypes
    if ct:
        ext = mimetypes.guess_extension(ct)
        if ext:
            return ext.lstrip(".")
        # fallback para algunos cts no mapeados
        if "jpeg" in ct: return "jpg"
        if "pjpeg" in ct: return "jpg"
        if "png" in ct: return "png"
        if "gif" in ct: return "gif"
        if "webp" in ct: return "webp"
        if "svg" in ct: return "svg"
        if "icon" in ct: return "ico"

    # 2) Si no, deduce por el hint (path del URL)
    path = urlparse(hint_lower).path or hint_lower
    if path.endswith(".jpeg"): return "jpg"
    if path.endswith(".jpg"):  return "jpg"
    if path.endswith(".png"):  return "png"
    if path.endswith(".gif"):  return "gif"
    if path.endswith(".webp"): return "webp"
    if path.endswith(".svg"):  return "svg"
    if path.endswith(".ico"):  return "ico"

    # 3) Último recurso: usa la parte después del último punto (si existe)
    if "." in path:
        return path.rsplit(".", 1)[-1]

    # 4) Sin información → "bin"
    return "bin"


def _norm_cid(c: str | None) -> tuple[str | None, str | None]:
    """Devuelve (cid_con_brackets, cid_sin_brackets) o (None, None)."""
    if not c:
        return None, None
    c = c.strip()
    if c.startswith("<") and c.endswith(">"):
        return c, c[1:-1]
    return f"<{c}>", c



def extract_html_inline_and_attachments_from_eml_bytes(
    eml_bytes: bytes,
    slug: str,
    lang: str,
    append_unreferenced_images: bool = True,
) -> dict:
    """
    - Extrae HTML (o convierte text/plain a HTML básico)
    - Sube imágenes inline (cid:) a S3 y reescribe <img src="cid:...">
    - Convierte data: URIs a S3 y reescribe
    - Sube adjuntos NO inline (pdf, vídeo, etc.) a S3
    Devuelve siempre un dict con "html", "images", "attachments", "debug"
    """
    msg = BytesParser(policy=policy.default).parsebytes(eml_bytes)

    # 1) HTML (o text/plain → HTML)
    html = None
    for part in msg.walk():
        if part.get_content_type() == "text/html" and "attachment" not in (part.get("Content-Disposition") or "").lower():
            payload = part.get_payload(decode=True) or b""
            cs = part.get_content_charset() or "utf-8"
            try:
                html = payload.decode(cs, errors="replace")
            except Exception:
                html = payload.decode("utf-8", errors="replace")
            break
    if not html:
        # fallback: text/plain
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in (part.get("Content-Disposition") or "").lower():
                payload = part.get_payload(decode=True) or b""
                cs = part.get_content_charset() or "utf-8"
                try:
                    txt = payload.decode(cs, errors="replace")
                except Exception:
                    txt = payload.decode("utf-8", errors="replace")
                html = "<!doctype html><html><body><pre>" + (
                    txt.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
                ) + "</pre></body></html>"
                break
    if not html:
        # Devuelve dict (no None) para que el caller pueda responder 400 legible
        return {"html": "", "images": [], "attachments": [], "debug": {"reason": "no_html"}}

    soup = BeautifulSoup(html, "lxml")

    # 2) Indexar imágenes por CID y recopilar adjuntos
    def norm_cid_key(s: str) -> str:
        s = (s or "").strip()
        if s.startswith("<") and s.endswith(">"):
            s = s[1:-1]
        return s.strip().lower()

    cid_parts: dict[str, dict] = {}     # cid (sin <>) → {content, content_type, filename, cid_with, cid_nb}
    attachments_no_cid = []             # imágenes adjuntas sin cid
    other_attachments = []              # pdf, vídeo, etc.

    for part in msg.walk():
        ct = (part.get_content_type() or "")
        disp = (part.get("Content-Disposition") or "").lower()
        filename = part.get_filename() or ""
        content = part.get_payload(decode=True) or b""
        if not content:
            continue

        if ct.startswith("image/"):
            cid_hdr = part.get("Content-ID") or ""
            cid_with = cid_hdr.strip()
            cid_nb   = norm_cid_key(cid_hdr)  # sin <>
            if cid_nb:
                cid_parts[cid_nb] = {
                    "content": content,
                    "content_type": ct,
                    "filename": filename,
                    "cid_with": cid_with,
                    "cid_nb": cid_nb,
                }
            else:
                attachments_no_cid.append({"content": content, "content_type": ct, "filename": filename})
        else:
            if "attachment" in disp or part.is_attachment():
                other_attachments.append({"content": content, "content_type": ct, "filename": filename})

    # 3) Subir imágenes y reescribir HTML
    uploaded_images = []
    next_id = 1

    def _put_bytes(content: bytes, ct: str, hint: str = "", id_for_name: int | None = None) -> tuple[str, str, int]:
        nonlocal next_id
        ext = _guess_ext(ct, hint)              # asegúrate: def _guess_ext(ct, hint="")
        img_id = (id_for_name if id_for_name is not None else next_id)
        key = f"emails/templates/{slug}/images/{img_id}.{ext}"  # imágenes comunes (sin idioma)
        url = put_public_s3(key, content, ct or "application/octet-stream", cache_seconds=31536000)
        # avanza next_id si lo asignamos aquí
        if id_for_name is None:
            next_id += 1
        return url, key, img_id

    # 3.1) Reescribir <img src="cid:...">
    img_tags = list(soup.find_all("img"))
    for img in img_tags:
        src = (img.get("src") or "").strip()
        if not src.lower().startswith("cid:"):
            continue
        raw = src[4:].strip().lower()
        data = cid_parts.get(raw)
        if not data:
            raw2 = re.sub(r"[<>\"'\s]", "", raw)
            data = cid_parts.get(raw2)
        if not data:
            continue
        
        content = data["content"]
        content_size = len(content)

        url, key, img_id = _put_bytes(content, data["content_type"], data.get("filename") or "", id_for_name=next_id)
        img["src"] = url
        img["data-img-id"] = str(img_id)
        if not img.get("alt"):
            img["alt"] = f"image-{img_id}"

        uploaded_images.append({
            "id": img_id,
            "url": url,
            "key": key,
            "cid": data.get("cid_with"),
            "cid_nb": data.get("cid_nb"),
            "content_type": data.get("content_type"),
            "source": "cid",
            "size": content_size,
        })
        next_id = img_id + 1

    # 3.2) Reescribir data: URIs
    for img in soup.find_all("img"):
        src = (img.get("src") or "").strip()
        if not src.startswith("data:"):
            continue
        header, payload = src.split(",", 1)
        ct2 = header.split(";")[0].split(":")[1] if ":" in header else "application/octet-stream"
        content = base64.b64decode(payload) if ";base64" in header else payload.encode("utf-8")
        content_size = len(content)

        url, key, img_id = _put_bytes(content, ct2, id_for_name=next_id)
        img["src"] = url
        img["data-img-id"] = str(img_id)
        if not img.get("alt"):
            img["alt"] = f"image-{img_id}"

        uploaded_images.append({
            "id": img_id,
            "url": url,
            "key": key,
            "content_type": ct2,
            "source": "data-uri",
            "size": content_size,
        })
        next_id = img_id + 1

    # 3.3) Imágenes adjuntas sin cid → opcionalmente insertarlas al final
    inserted_urls = []
    for att in attachments_no_cid:
        content = att["content"]
        content_size = len(content)

        url, key, img_id = _put_bytes(content, att["content_type"], att.get("filename") or "", id_for_name=next_id)
        uploaded_images.append({
            "id": img_id,
            "url": url,
            "key": key,
            "content_type": att["content_type"],
            "source": "attachment",
            "size": content_size,
        })

        inserted_urls.append((img_id, url, att.get("filename") or ""))
        next_id = img_id + 1

    if append_unreferenced_images and inserted_urls:
        body = soup.body or soup
        wrap = soup.new_tag("div")
        wrap["data-inserted"] = "unreferenced-attachments"
        for (img_id, url, fname) in inserted_urls:
            itag = soup.new_tag("img", src=url)
            itag["alt"] = fname or f"image-{img_id}"
            itag["data-img-id"] = str(img_id)
            wrap.append(itag)
        body.append(wrap)

    # 4) Otros adjuntos (PDF, vídeo, etc.)
    uploaded_attachments = []
    for att in other_attachments:
        fname = (att.get("filename") or "attachment").replace("\\", "_").replace("/", "_")
        ct3 = att.get("content_type") or "application/octet-stream"
        key = f"emails/templates/{slug}/{lang}/attachments/{fname}"  # adjuntos por idioma
        url = put_public_s3(key, att["content"], ct3, cache_seconds=0)  # mutable
        uploaded_attachments.append({
            "filename": fname,
            "content_type": ct3,
            "key": key,
            "url": url,
            "lang": lang,
        })

    # 5) Subir cid-map.json (ambas variantes)
    cid_map = {}
    for img in uploaded_images:
        if img.get("cid"):
            cid_map[img["cid"]] = img["url"]                 # "<cid...>" -> url
        if img.get("cid_nb"):
            cid_map[f"cid:{img['cid_nb']}"] = img["url"]     # "cid:..."  -> url

    cid_map_key = None
    if cid_map:
        cid_map_key = f"emails/templates/{slug}/{lang}/cid-map.json"
        put_public_s3(
            cid_map_key,
            json.dumps(cid_map, indent=2, ensure_ascii=False).encode("utf-8"),
            "application/json",
            cache_seconds=0,
        )

    # 6) Return (¡fuera de _put_bytes!)
    return {
        "html": str(soup),
        "images": uploaded_images,
        "attachments": uploaded_attachments,
        "cid_map_key": cid_map_key,
        "debug": {
            "html_img_count": len(soup.find_all("img")),
            "uploaded_images": len(uploaded_images),
            "uploaded_attachments": len(uploaded_attachments),
            "has_cid_map": bool(cid_map),
        }
    }

def rehost_relative_imgs_to_s3(html: str, slug: str, lang: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    changed = False
    for img in soup.find_all("img"):
        src = (img.get("src") or "").strip()
        if not src or src.startswith(("http://", "https://", "cid:", "data:")):
            continue
        # es relativa → sube a S3 (si tienes el archivo local, o ignórala)
        # Aquí no tenemos bytes del archivo relativo, así que solo la marcamos (debug)
        print("[WARN] Img relativa en preview (no hay bytes que subir):", src)
    return str(soup)


def replace_cid_srcs_with_urls(html: str, cid_map: dict) -> str:
    if not cid_map or "cid:" not in html:
        return html
    soup = BeautifulSoup(html, "lxml")
    for img in soup.find_all("img"):
        src = (img.get("src") or "").strip()
        if not src.startswith("cid:"):
            continue
        url = cid_map.get(src)
        if not url:
            token = src[4:]
            if token and not token.startswith("<"):
                url = cid_map.get(f"<{token}>")
        if url:
            img["src"] = url
    return str(soup)

def find_first_image_url(slug: str) -> str | None:
    s3 = get_s3()
    prefix = f"emails/templates/{slug}/images/"
    page = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)
    for obj in page.get("Contents", []):
        key = obj["Key"]
        if key.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
            return f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{key}"
    return None

def fix_relative_imgs(html: str, slug: str) -> str:
    """Reemplaza src relativos (o '...') por una imagen válida en S3 (fallback)."""
    soup = BeautifulSoup(html, "lxml")
    fallback = None
    changed = False
    for img in soup.find_all("img"):
        src = (img.get("src") or "").strip()
        if not src or src == "..." or src.startswith(("/", "./", "../")) or not src.startswith(("http://","https://","data:","cid:")):
            if fallback is None:
                fallback = find_first_image_url(slug)
                if not fallback:
                    print("[WARN] No hay imágenes en S3 para usar como fallback.")
                    break
            img["src"] = fallback
            # si no tiene alt, añade uno
            if not img.get("alt"):
                img["alt"] = "image"
            changed = True
    if changed:
        print("[DEBUG] Se reemplazaron imágenes relativas por fallback")
    return str(soup)



CID_URL_RE = re.compile(r'url\((["\']?)(cid:[^)]+)\1\)', re.I)



def replace_cid_everywhere(html: str, cid_map: dict) -> str:
    if not cid_map:
        return html
    soup = BeautifulSoup(html, "lxml")
    # <img src="cid:...">
    for img in soup.find_all("img"):
        src = (img.get("src") or "").strip()
        if src.startswith("cid:"):
            url = cid_map.get(src) or cid_map.get(f"<{src[4:]}>")
            if url:
                img["src"] = url
    # style="...url(cid:...)..."
    for tag in soup.find_all(True):
        style = tag.get("style")
        if not style or "cid:" not in style:
            continue
        def _sub(m):
            cid = m.group(2)
            url = cid_map.get(cid) or cid_map.get(f"<{cid[4:]}>")
            return f'url("{url}")' if url else m.group(0)
        new_style = CID_URL_RE.sub(_sub, style)
        if new_style != style:
            tag["style"] = new_style
    # background="cid:..."
    for tag in soup.find_all(True):
        bg = tag.get("background")
        if bg and bg.startswith("cid:"):
            url = cid_map.get(bg) or cid_map.get(f"<{bg[4:]}>")
            if url:
                tag["background"] = url
    # VML genérico con src="cid:..."
    for tag in soup.find_all(lambda t: t.has_attr("src") and isinstance(t.get("src"), str) and t.get("src").startswith("cid:")):
        src = tag.get("src")
        url = cid_map.get(src) or cid_map.get(f"<{src[4:]}>")
        if url:
            tag["src"] = url
    return str(soup)

def inject_preview_css(html: str) -> str:
    INJECT = """
    <style>
      img { max-width: 100% !important; height: auto !important; display: block !important; opacity: 1 !important; visibility: visible !important; }
      *[style*="display:none"], *[style*="height:0"], *[style*="max-height:0"], *[style*="opacity:0"] {
        display: block !important; height: auto !important; max-height: none !important; opacity: 1 !important; visibility: visible !important;
      }
      table[background], td[background], th[background],
      *[style*="background:"], *[style*="background-image"] {
        background-size: cover !important;
        background-repeat: no-repeat !important;
        min-height: 200px !important;
      }
    </style>
    """
    return html.replace("</head>", INJECT + "</head>", 1) if "</head>" in html else INJECT + html


# funciones_generar_email.py
def to_placeholders_conservative(soup):
   
    # Headline → placeholder si existe
    h1 = soup.find(["h1"]) or soup.find(["h2"])
    if h1 and "{{ headline }}" not in (h1.get_text() or ""):
        h1.string = "{{ headline }}"

    # NO toques los src de <img>; sólo asegura id/alt
    next_id = 1
    for img in soup.find_all("img"):
        if not img.get("data-img-id"):
            img["data-img-id"] = str(next_id)
            next_id += 1
        if not img.get("alt"):
            img["alt"] = f"image-{img['data-img-id']}"

    # NO borres los <p> originales; añade un hueco editable
    marker = soup.new_tag("div")
    marker.string = "{{ html_content | safe }}"
    (soup.body or soup).append(marker)

    # CTAs: conviértelos en placeholders sin eliminar otros enlaces/imágenes
    for a in find_ctas(soup):
        a.string = "{{ cta_label }}"
        a["href"] = "{{ cta_url_wrapped }}"

    # Unsubscribe
    footer = soup.find(text=re.compile("darse de baja|unsubscribe", re.I))
    if footer and getattr(footer, "parent", None) and footer.parent.name == "a":
        footer.parent["href"] = "{{ unsubscribe_url }}"
    else:
        unsub = soup.new_tag("a", href="{{ unsubscribe_url }}")
        unsub.string = "Darse de baja"
        p = soup.new_tag("p"); p.append(unsub)
        (soup.body or soup).append(p)

    # Pixel
    pixel = soup.new_tag("img", src="{{ open_pixel_url }}")
    pixel["width"] = "1"; pixel["height"] = "1"; pixel["style"] = "display:none;"
    (soup.body or soup).append(pixel)

    return soup


def public_url(key):
    # URL pública si el bucket es público; si no, usa presigned_url
    return f"https://{S3_BUCKET}.s3.amazonaws.com/{(key)}"



def parent_of(prefix: str) -> str | None:
    if not prefix or prefix == ROOT_PREFIX_S3:
        return None
    p = prefix.rstrip("/")
    up = p[:p.rfind("/")+1]  # incluye la última barra
    return up if up.startswith(ROOT_PREFIX_S3) else ROOT_PREFIX_S3

def build_images_map(images_dir: str, manifest: dict | None = None) -> dict:
    """
    Devuelve: { "1.jpg": {key, etag, last_modified, url, is_logo} , ... }
    - Marca automáticamente is_logo=True si el nombre acaba en .png
    - Si el manifest ya tenía is_logo para ese nombre, se respeta
    """
    s3 = get_s3()
    if not images_dir:
        return {}

    # índice previo para preservar is_logo si ya existía
    prev = {}
    if manifest:
        prev = (manifest.get("shared", {}) or {}).get("images", {}) or {}
        # si también manejas imágenes por idioma, puedes fusionar aquí prev.update(...)

    out = {}
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=images_dir):
        for obj in (page.get("Contents") or []):
            key = obj["Key"]
            if key.endswith("/"):
                continue
            name = key.rsplit("/", 1)[-1]
            head = s3.head_object(Bucket=S3_BUCKET, Key=key)
            etag = head["ETag"].strip('"')
            lm   = head["LastModified"].isoformat()
            size_bytes = obj.get("Size") or head.get("ContentLength") or 0

            # regla automática
            auto_is_logo = name.lower().endswith(".png")

            # preserva si ya estaba definido en el manifest previo
            prev_is_logo = (prev.get(name) or {}).get("is_logo")
            is_logo = prev_is_logo if isinstance(prev_is_logo, bool) else auto_is_logo
            if size_bytes > 40 * 1024:
                is_logo = False

            out[name] = {
                "key": key,
                "etag": etag,
                "last_modified": lm,
                "url": f"{public_url(key)}?v={etag}",
                "is_logo": is_logo,
            }
    return out


def update_manifest(slug: str) -> dict:
    s3 = get_s3()
    mk = f"emails/templates/{slug}/manifest.json"
    man = json.loads(s3.get_object(Bucket=S3_BUCKET, Key=mk)["Body"].read())

    # shared
    shared_dir = (man.get("shared") or {}).get("images_dir")
    if shared_dir:
        man.setdefault("shared", {})
        prev = (man["shared"].get("images") or {}).copy()
        fresh = build_images_map(shared_dir)  # <-- SOLO key/etag/last_modified/url
        # fusiona conservando target_*/fit/is_logo previos
        merged = {}
        for name, core in fresh.items():
            merged[name] = _merge_image_meta(prev.get(name), core)
        man["shared"]["images"] = merged

    # por idioma (si lo usas)
    for lc, ld in (man.get("languages") or {}).items():
        images_dir = ld.get("images_dir") or man.get("images_dir")
        if images_dir:
            prev = (ld.get("images") or {}).copy()
            fresh = build_images_map(images_dir)
            merged = {}
            for name, core in fresh.items():
                merged[name] = _merge_image_meta(prev.get(name), core)
            man["languages"][lc]["images"] = merged

    man["updated_at"] = int(datetime.now(timezone.utc).timestamp())

    s3.put_object(
        Bucket=S3_BUCKET, Key=mk,
        Body=json.dumps(man, indent=2, ensure_ascii=False).encode(),
        ContentType="application/json",
        CacheControl="no-cache, no-store, must-revalidate",
        Expires=0,
    )
    return man
def update_manifest_for_key(slug: str, key: str) -> dict:
    s3 = get_s3()
    mk = f"emails/templates/{slug}/manifest.json"
    man = json.loads(s3.get_object(Bucket=S3_BUCKET, Key=mk)["Body"].read())

    head = s3.head_object(Bucket=S3_BUCKET, Key=key)
    etag = head["ETag"].strip('"')
    lm   = head["LastModified"].isoformat()
    name = key.rsplit("/", 1)[-1]
    core = {"key": key, "etag": etag, "last_modified": lm, "url": f"{public_url(key)}?v={etag}"}

    # Política: imágenes SOLO en shared (sin variantes por idioma)
    man.setdefault("shared", {}).setdefault("images", {})
    imgs_shared = man["shared"]["images"]
    imgs_shared[name] = _merge_image_meta(imgs_shared.get(name), core)

    # Limpieza: elimina cualquier entrada duplicada en languages.*.images
    for lc, ld in (man.get("languages") or {}).items():
        imgs_lang = ld.get("images") or {}
        if name in imgs_lang:
            imgs_lang.pop(name, None)
            ld["images"] = imgs_lang
    man["updated_at"] = int(datetime.now(timezone.utc).timestamp())

    s3.put_object(
        Bucket=S3_BUCKET, Key=mk,
        Body=json.dumps(man, indent=2, ensure_ascii=False).encode(),
        ContentType="application/json",
        CacheControl="no-cache, no-store, must-revalidate",
        Expires=0,
    )
    return man


def manifest_lookup(manifest: dict, lang: str, name: str) -> str | None:
    lang_node = (manifest.get("languages") or {}).get(lang) or {}
    imgs_lang = (lang_node.get("images") or {})
    imgs_shared = (manifest.get("shared") or {}).get("images") or {}
    # preferencia: por idioma, luego shared
    if name in imgs_lang:   return imgs_lang[name]["url"]
    if name in imgs_shared: return imgs_shared[name]["url"]
    # normaliza .jpeg→.jpg
    key2 = name.lower().replace(".jpeg",".jpg")
    for m in (imgs_lang, imgs_shared):
        for k, v in m.items():
            if k.lower().replace(".jpeg",".jpg") == key2:
                return v["url"]
    return None



IMG_SRC_RE   = re.compile(r'(<img[^>]+(?:\s|^)(?:src)=["\'])([^"\']+)(["\'])', re.IGNORECASE)
DATA_SRC_RE  = re.compile(r'(<img[^>]+(?:\s|^)(?:data-src|data-original)=["\'])([^"\']+)(["\'])', re.IGNORECASE)
SRCSET_RE    = re.compile(r'(<(?:img|source)[^>]+srcset=["\'])([^"\']+)(["\'])', re.IGNORECASE)
URL_FUNC_RE  = re.compile(r'url\((["\']?)([^)"\']+)\1\)', re.IGNORECASE)  # en style/background
DEBUG_REWRITE = False  # pon True temporalmente para ver qué se cambia

def _build_by_name(manifest: dict, lang: str) -> dict:
    ln = (manifest.get("languages") or {}).get(lang) or {}
    imgs_lang   = (ln.get("images") or {})
    imgs_shared = (manifest.get("shared") or {}).get("images") or {}
    by_name = { n.lower().replace(".jpeg",".jpg"): v["url"] for n, v in imgs_shared.items() }
    by_name.update({ n.lower().replace(".jpeg",".jpg"): v["url"] for n, v in imgs_lang.items() })
    return by_name

def _map_name(url: str, by_name: dict) -> str | None:
    base = url.split("?", 1)[0]
    path = urlparse(base).path or base
    name = path.rsplit("/", 1)[-1].lower().replace(".jpeg",".jpg")
    return by_name.get(name)

def apply_manifest_images_all(html: str, manifest: dict, lang: str = "en") -> str:
    by_name = _build_by_name(manifest, lang)
    if not by_name:
        if DEBUG_REWRITE: print("[REWRITE] manifest has no images")
        return html

    # 1) <img src="...">
    def _rw_src(m):
        pre, src, suf = m.groups()
        new = _map_name(src, by_name)
        if new and DEBUG_REWRITE: print(f"[REWRITE src] {src} => {new}")
        return f"{pre}{new}{suf}" if new else m.group(0)
    html = IMG_SRC_RE.sub(_rw_src, html)

    # 2) <img data-src="..."> / data-original
    def _rw_data_src(m):
        pre, src, suf = m.groups()
        new = _map_name(src, by_name)
        if new and DEBUG_REWRITE: print(f"[REWRITE data-src] {src} => {new}")
        return f"{pre}{new}{suf}" if new else m.group(0)
    html = DATA_SRC_RE.sub(_rw_data_src, html)

    # 3) srcset="a.jpg 1x, b.jpg 2x"
    def _rw_srcset(m):
        pre, srcset, suf = m.groups()
        parts = [p.strip() for p in srcset.split(",")]
        out = []
        for p in parts:
            seg = p.split()
            if not seg:
                continue
            url = seg[0]
            new = _map_name(url, by_name)
            if new:
                if DEBUG_REWRITE: print(f"[REWRITE srcset] {url} => {new}")
                seg[0] = new
            out.append(" ".join(seg))
        return f"{pre}{', '.join(out)}{suf}"
    html = SRCSET_RE.sub(_rw_srcset, html)

    # 4) style="background-image:url(...)" / CSS inline
    def _rw_url(m):
        q, u = m.groups()
        new = _map_name(u, by_name)
        if new and DEBUG_REWRITE: print(f"[REWRITE url()] {u} => {new}")
        return f"url({q}{new}{q})" if new else m.group(0)
    html = URL_FUNC_RE.sub(_rw_url, html)

    return html


def _download_bytes(url: str) -> tuple[bytes, str]:
    # Descarga y devuelve (bytes, content_type)
    # Usa requests (o tu cliente) y mapea content-type a ext si hace falta
    import requests
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    ct = r.headers.get("Content-Type","application/octet-stream")
    return r.content, ct

def _cid_bytes(cid: str, cid_attachments: dict[str, dict]) -> tuple[bytes, str]:
    # cid_attachments: { "<cid>": { "content": b"...", "content_type": "image/jpeg" }, ... }
    obj = cid_attachments.get(cid)
    if not obj: raise KeyError(cid)
    return obj["content"], obj.get("content_type","application/octet-stream")

IMG_SRC_RE   = re.compile(r'(<img[^>]*?\s(?:src)=["\'])([^"\']+)(["\'])', re.I)
DATA_SRC_RE  = re.compile(r'(<img[^>]*?\s(?:data-src|data-original)=["\'])([^"\']+)(["\'])', re.I)
SRCSET_RE    = re.compile(r'(<(?:img|source)[^>]*?\s(?:srcset)=["\'])([^"\']+)(["\'])', re.I)
URL_FUNC_RE  = re.compile(r'url\((["\']?)([^)"\']+)\1\)', re.I)
BG_ATTR_RE   = re.compile(r'(<[^>]+?\sbackground=)["\']([^"\']+)["\']', re.I)
VML_FILL_RE  = re.compile(r'(<v:fill[^>]*?\ssrc=)["\']([^"\']+)["\']', re.I)
VML_IMGDATA_RE = re.compile(r'(<v:imagedata[^>]*?\ssrc=)["\']([^"\']+)["\']', re.I)

def build_final_images_and_rewrite(
    html: str, slug: str, lang: str,
    cid_attachments: dict[str,dict] | None = None
) -> tuple[str, list[dict]]:
    """
    Sube cada imagen a `emails/templates/<slug>/images/<id>.<ext>` y reescribe el HTML
    a la URL pública final (SIN ?v=). Devuelve (html_reescrito, images_meta).
    images_meta: [{id:"1", alt:"...", ext:"jpg"}...]
    """
    soup = BeautifulSoup(html, "lxml")
    base = f"emails/templates/{slug}/images/"
    next_id = 1
    images_meta = []

    def _store_and_url(src: str) -> tuple[str, str]:
        nonlocal next_id
        # src puede ser http(s), cid:..., data:... (puedes ampliar)
        if src.startswith("cid:"):
            cid = src[4:]
            data, ct = _cid_bytes(cid, cid_attachments or {})
            # pasa CONTENT-TYPE como primer arg y un hint como segundo
            ext = _guess_ext(ct, f"cid.{ct.split('/')[-1]}")
        else:
            data, ct = _download_bytes(src)  # asegúrate de que retorna (bytes, content_type)
            ext = _guess_ext(ct, src)        # CONTENT-TYPE primero, URL como hint

        img_id = str(next_id); next_id += 1
        filename = f"{img_id}.{ext}"
        key = f"{base}{filename}"
        # imágenes: cache fuerte; luego versionas con ?v=<etag> desde el manifest
        put_public_s3(key, data, ct, cache_seconds=31536000)
        images_meta.append({"id": img_id, "alt": "", "ext": ext})
        return public_url(key), filename  # url_final_sin_version, filename


    # <img src>
    for img in soup.find_all("img"):
        src = img.get("src")
        if not src: continue
        final_url, filename = _store_and_url(src)
        img["src"] = final_url
        img["data-img-id"] = filename.split(".")[0]  # solo el id
        # alt
        if "alt" in img.attrs:
            images_meta[-1]["alt"] = img["alt"]

        # data-src / data-original
        for a in ("data-src","data-original"):
            if img.get(a):
                img[a] = final_url

        # srcset
        if img.get("srcset"):
            parts = [p.strip() for p in img["srcset"].split(",")]
            out=[]
            for p in parts:
                seg=p.split()
                if not seg: continue
                seg[0]=final_url
                out.append(" ".join(seg))
            img["srcset"]=", ".join(out)

    # background=""
    def _rewrite_attr(regex, setter):
        html_text = str(soup)
        def repl(m):
            pre,url = m.groups()
            final_url, _ = _store_and_url(url)
            return f'{pre}"{final_url}"'
        return regex.sub(repl, html_text)

    html1 = BG_ATTR_RE.sub(lambda m: f'{m.group(1)}"{_store_and_url(m.group(2))[0]}"', str(soup))
    html1 = VML_FILL_RE.sub(lambda m: f'{m.group(1)}"{_store_and_url(m.group(2))[0]}"', html1)
    html1 = VML_IMGDATA_RE.sub(lambda m: f'{m.group(1)}"{_store_and_url(m.group(2))[0]}"', html1)
    html1 = URL_FUNC_RE.sub(lambda m: f'url({m.group(1)}{_store_and_url(m.group(2))[0]}{m.group(1)})', html1)

    return html1, images_meta



# Si no los tienes ya:
# from urllib.parse import urlparse
# import mimetypes

# Helpers que ya usas:
# - put_public_s3(key, content, content_type, cache_seconds=...)
# - public_url(key)
# - _guess_ext(ct: str, hint: str = "") -> str
# - make_id_allocator(start=1)

def make_id_allocator(start=1):
    """
    Devuelve un callable que asigna IDs consecutivos.
    Ejemplo:
        alloc = make_id_allocator(1)
        print(alloc())  # 1
        print(alloc())  # 2
    """
    i = start
    def _next():
        nonlocal i
        v = i
        i += 1
        return v
    return _next

def _download_bytes(url: str) -> tuple[bytes, str]:
    r = requests.get(url, timeout=20, allow_redirects=True, stream=True)
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "application/octet-stream")

def rewrite_images_to_final_and_upload(html: str, *, slug: str, cid_map: dict | None = None):
    """
    Reescribe todas las imágenes a su ruta final estable:
      s3://emails/templates/<slug>/images/<id>.<ext>
    y devuelve (html_reescrito, images_meta).

    - Soporta: <img src>, data-src, data-original, srcset, background=, style="url(...)", VML (v:fill, v:imagedata).
    - http(s) y data: URIs. Si se pasa cid_map, también 'cid:...'.
    - Imágenes con caché fuerte (1 año) — luego se versionan con ?v=<etag> vía manifest.
    """
   
    base_key_prefix = f"emails/templates/{slug}/images/"

    soup = BeautifulSoup(html or "", "lxml")
    alloc = make_id_allocator(1)
    memo: dict[str, str] = {}     # src original -> url final
    url2id: dict[str, str] = {}   # url final -> id (para poder añadir alt luego)
    images_meta: list[dict] = []

    def _store(content: bytes, ct: str, hint: str = "") -> tuple[str, str, str]:
        ext = _guess_ext(ct, hint)
        img_id = str(alloc())
        key = f"{base_key_prefix}{img_id}.{ext}"
        url = put_public_s3(key, content, ct or "application/octet-stream", cache_seconds=31536000)

        # índice estable = orden de subida
        idx = len(images_meta)
        filename = key.rsplit("/", 1)[-1]

        meta = {
            "id": img_id,
            "filename": filename,
            "key": key,
            "url": url,
            "content_type": ct,
            # ⬇️ inyecta tamaños aquí
            **_dimensions_for_image(idx, img_id)
        }
        images_meta.append(meta)
        url2id[url] = img_id
        return url, key, img_id
    

    def _from_cid(cid: str) -> tuple[bytes, str]:
        if not cid_map:
            raise ValueError(f"CID no disponible: {cid}")
        entry = cid_map.get(cid) or cid_map.get(cid.strip("<>").lower())
        if not entry:
            raise ValueError(f"CID no encontrado: {cid}")
        return entry["content"], entry.get("content_type", "application/octet-stream")

    # ---- Reescritura de <img ...> ----
    def _rewrite_img_like_url(src: str) -> str:
        if not src:
            return src

        # memo evita subidas repetidas
        if src in memo:
            return memo[src]

        try:
            if src.startswith("cid:"):
                b, ct = _from_cid(src[4:])
                url, _, _ = _store(b, ct, f"cid.{ct.split('/')[-1]}")
                memo[src] = url
                return url

            if src.startswith("data:"):
                header, payload = src.split(",", 1)
                ct = header.split(";")[0].split(":")[1] if ":" in header else "application/octet-stream"
                content = base64.b64decode(payload) if ";base64" in header else payload.encode("utf-8")
                url, _, _ = _store(content, ct, f"cid.{ct.split('/')[-1]}")
                memo[src] = url
                return url

            if src.startswith("http://") or src.startswith("https://"):
                content, ct = _download_bytes(src)
                url, _, _ = _store(content, ct, src)
                memo[src] = url
                return url

            # rutas relativas u otras → no tocar
            return src
        except Exception:
            # si falla, conserva src original para no romper
            return src

    # <img ...>
    for img in soup.find_all("img"):
        # prioridades habituales
        cand = img.get("src") or img.get("data-src") or img.get("data-original")
        if cand:
            new_src = _rewrite_img_like_url(cand.strip())
            if img.get("src"):
                img["src"] = new_src
            if img.get("data-src"):
                img["data-src"] = new_src
            if img.get("data-original"):
                img["data-original"] = new_src

        # srcset: reescribe el primer recurso (simple; puedes expandir si necesitas múltiples)
        if img.get("srcset"):
            parts = [p.strip() for p in img["srcset"].split(",")]
            if parts:
                first = parts[0].split()[0]
                new_first = _rewrite_img_like_url(first)
                # reconstruye manteniendo descriptores (1x, 2x, etc.)
                new_srcset = []
                for p in parts:
                    seg = p.split()
                    if not seg:
                        continue
                    seg[0] = new_first if seg[0] == first else _rewrite_img_like_url(seg[0])
                    new_srcset.append(" ".join(seg))
                img["srcset"] = ", ".join(new_srcset)

    # background="..."
    BG_ATTR_RE = re.compile(r'(<[^>]+?\sbackground=)(["\'])([^"\']+)\2', re.I)
    def _repl_bg(m):
        pre, q, u = m.groups()
        return f'{pre}{q}{_rewrite_img_like_url(u)}{q}'
    html_str = BG_ATTR_RE.sub(_repl_bg, str(soup))

    # VML (Outlook)
    VML_FILL_RE    = re.compile(r'(<v:fill[^>]*?\ssrc=)(["\'])([^"\']+)\2', re.I)
    VML_IMGDATA_RE = re.compile(r'(<v:imagedata[^>]*?\ssrc=)(["\'])([^"\']+)\2', re.I)
    def _repl_vml(m):
        pre, q, u = m.groups()
        return f'{pre}{q}{_rewrite_img_like_url(u)}{q}'
    html_str = VML_FILL_RE.sub(_repl_vml, html_str)
    html_str = VML_IMGDATA_RE.sub(_repl_vml, html_str)

    # style="background: url(...)"
    URL_FUNC_RE = re.compile(r'url\((["\']?)([^)\'"]+)\1\)', re.I)
    def _repl_url(m):
        q, u = m.groups()
        return f'url({q}{_rewrite_img_like_url(u)}{q})'
    html_str = URL_FUNC_RE.sub(_repl_url, html_str)

    # Devuelve HTML final y metadatos de subidas
    return html_str, images_meta


def _attachments_html(att_list: list[dict]) -> str:
    if not att_list:
        return ""
    lis = []
    for a in att_list:
        name = a.get("filename") or a.get("key") or "archivo"
        url  = a.get("url") or ""
        lis.append(f'<li><a href="{url}" target="_blank" rel="noopener">{name}</a></li>')
    return (
        '<div style="margin-top:20px;font-family:Arial,Helvetica,sans-serif;font-size:14px">'
        '<p style="font-weight:bold;margin:0 0 8px">Archivos adjuntos:</p>'
        f"<ul>{''.join(lis)}</ul>"
        "</div>"
    )





def enforce_dimensions_from_manifest(html: str, manifest: dict) -> str:
    shared = (manifest.get("shared") or {})
    images = (shared.get("images") or {})
    if not images:
        return html

    # Construimos índice por nombre de archivo → (w,h,fit)
    dims_by_name = {}
    for name, meta in images.items():
        w = meta.get("target_w")
        h = meta.get("target_h")
        fit = (meta.get("fit") or "").lower()
        if w or h:
            dims_by_name[name.lower()] = (w, h, fit)

    if not dims_by_name:
        return html

    soup = BeautifulSoup(html, "lxml")
    for img in soup.find_all("img"):
        src = (img.get("src") or "").strip()
        if not src:
            continue
        # nombre de archivo sin querystring
        path = urlparse(src).path
        filename = (path.split("/")[-1] if path else "").lower()
        if filename not in dims_by_name:
            continue

        w, h, fit = dims_by_name[filename]

        # Reglas sencillas y compatibles con email:
        # - Para "contain": fija ancho y deja altura auto para no deformar
        # - Para "cover": en email no hay verdadero cover fiable; o recortas servidor (ver Opción B),
        #   o fuerzas width/height (posible deformación en algunos clientes).
        styles = []
        if w:
            img["width"] = str(int(w))          # atributo HTML (más compatible)
            styles.append(f"width:{int(w)}px")
        if h:
            # solo forzamos height si el fit es cover (contiene puede deformar)
            if fit == "cover":
                img["height"] = str(int(h))
                styles.append(f"height:{int(h)}px")
            else:
                # contain → intentamos mantener proporción
                styles.append("height:auto")

        # intenta object-fit donde se soporte (Gmail web, Apple Mail), no en todos
        if fit in ("cover", "contain"):
            styles.append(f"object-fit:{fit}")
            styles.append("display:block")  # evitar gaps en algunos clientes

        # fusiona con style existente
        old = (img.get("style") or "").strip().rstrip(";")
        if old:
            styles.insert(0, old)
        img["style"] = ";".join(styles) + ";"

    return str(soup)


def load_template_html(slug: str, lang: str, prefer_template=True) -> str:
    """
    Devuelve el HTML de template.html (si existe) o original.html como fallback.
    """
    s3 = get_s3()
    base = f"emails/templates/{slug}/{lang}"
    tpl_key = f"{base}/template.html"
    raw_key = f"{base}/original.html"

    def _exists(k):
        try:
            s3.head_object(Bucket=S3_BUCKET, Key=k)
            return True
        except botocore.exceptions.ClientError:
            return False

    chosen = tpl_key if (prefer_template and _exists(tpl_key)) else raw_key
    obj = s3.get_object(Bucket=S3_BUCKET, Key=chosen)
    return obj["Body"].read().decode("utf-8", "replace")



_SIGNATURE_HINTS = re.compile(
    r"(footer|firma|signature|sig|unsubscribe|contact|address)",
    re.IGNORECASE
)

def _clean_soup(soup: BeautifulSoup) -> None:
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

def _find_signature_block(soup: BeautifulSoup):
    # 1) Por clase/ID con hints
    for el in soup.find_all(True):
        cid = (el.get("id") or "") + " " + " ".join(el.get("class") or [])
        if _SIGNATURE_HINTS.search(cid):
            return el

    # 2) Por etiqueta semántica footer
    foot = soup.find("footer")
    if foot: 
        return foot

    # 3) Última tabla o div “compacto” del body
    candidates = []
    for tagname in ("table", "div", "section"):
        candidates += soup.body.find_all(tagname, recursive=False) if soup.body else []
    if not candidates:
        candidates = soup.find_all(["table","div","section"])
    if candidates:
        # último bloque con poquito contenido (heurística)
        for el in reversed(candidates):
            txt = el.get_text(" ", strip=True)
            if txt and len(txt) <= 400:  # ajustable
                return el
        return candidates[-1]

    return None

def extract_message_and_signature_from_html(html: str) -> dict:
    """
    Devuelve:
    {
      "message_text": "...",
      "signature_text": "...",
      "message_html": "<...>",
      "signature_html": "<...>"
    }
    """
    soup = BeautifulSoup(html, "lxml")
    _clean_soup(soup)

    body = soup.body or soup
    sig_block = _find_signature_block(soup)

    # Clonar para separar
    message_html, signature_html = "", ""
    if sig_block:
        # separa firma
        signature_html = str(sig_block)
        sig_block.extract()

    message_html = str(body)

    # Texto plano legible
    signature_text = BeautifulSoup(signature_html, "lxml").get_text("\n", strip=True) if signature_html else ""
    message_text   = BeautifulSoup(message_html,   "lxml").get_text("\n", strip=True)

    # Limpieza suave de saltos múltiples
    message_text   = re.sub(r"\n{3,}", "\n\n", message_text).strip()
    signature_text = re.sub(r"\n{3,}", "\n\n", signature_text).strip()

    return {
        "message_text": message_text,
        "signature_text": signature_text,
        "message_html": message_html,
        "signature_html": signature_html,
    }

def upload_shared_signature(slug: str, html: str, txt: str):
    base_shared = f"emails/templates/{slug}/partials/"
    put_public_s3(base_shared + "signature.html", html.encode("utf-8"), "text/html; charset=utf-8", cache_seconds=0)
    put_public_s3(base_shared + "signature.txt",  txt.encode("utf-8"),  "text/plain; charset=utf-8", cache_seconds=0)




def _empty_manifest(slug: str, display_name: str | None = None) -> dict:
    return {
        "slug": slug,
        "display_name": display_name or slug,
        "default_lang": "en",
        "languages": {},
        "shared": {"attachments": [], "images_dir": f"emails/templates/{slug}/images/"},
        "images_dir": f"emails/templates/{slug}/images/",
        "updated_at": int(datetime.now(timezone.utc).timestamp()),
    }

def upsert_shared_signature_in_manifest(slug: str, display_name: str | None = None) -> dict:
    s3 = get_s3()
    mk = f"emails/templates/{slug}/manifest.json"

    # 1) cargar o crear base
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=mk)
        man = json.loads(obj["Body"].read())
    except botocore.exceptions.ClientError as e:
        if e.response.get("Error", {}).get("Code") == "NoSuchKey":
            man = _empty_manifest(slug, display_name)
        else:
            raise

    # 2) asegurar shared.partials
    man.setdefault("shared", {}).setdefault("partials", {})
    man["shared"]["partials"].update({
        "signature_html": f"emails/templates/{slug}/partials/signature.html",
        "signature_text": f"emails/templates/{slug}/partials/signature.txt",
    })

    # 3) timestamp y guardar
    man["updated_at"] = int(datetime.now(timezone.utc).timestamp())
    s3.put_object(
        Bucket=S3_BUCKET, Key=mk,
        Body=json.dumps(man, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
        CacheControl="no-cache, no-store, must-revalidate",
        Expires=0,
    )
    return man

def upsert_partials_in_manifest(slug: str, lang: str) -> dict:
    s3 = get_s3()
    mk = f"emails/templates/{slug}/manifest.json"
    man = json.loads(s3.get_object(Bucket=S3_BUCKET, Key=mk)["Body"].read())
    man.setdefault("languages", {}).setdefault(lang, {})
    man["languages"][lang].setdefault("partials", {})
    man["languages"][lang]["partials"].update({
        "message_html":   f"emails/templates/{slug}/{lang}/partials/message.html",
        "message_text":   f"emails/templates/{slug}/{lang}/partials/message.txt",
        
    })
    man["updated_at"] = int(datetime.now(timezone.utc).timestamp())
    s3.put_object(
        Bucket=S3_BUCKET, Key=mk,
        Body=json.dumps(man, indent=2, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
        CacheControl="no-cache, no-store, must-revalidate",
        Expires=0,
    )
    return man



def _basename_from_src(src: str) -> str:
    if not src: return ""
    # quita querystring ?v=...
    path = urlparse(src).path or src
    return os.path.basename(path).lower()



def remove_all_images(html: str) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    for img in soup.find_all("img"):
        img.decompose()
    return str(soup)


def get_allowed_logo_filenames(slug: str, sig_html: str) -> set[str]:
    """Intenta leer logos del manifest (is_logo=True); si falla, usa los .png presentes en la firma."""
    allowed = set()
    try:
        s3 = get_s3()
        mk = f"emails/templates/{slug}/manifest.json"
        man = json.loads(s3.get_object(Bucket=S3_BUCKET, Key=mk)["Body"].read())
        for name, meta in (man.get("shared", {}).get("images", {}) or {}).items():
            if meta.get("is_logo"):
                allowed.add(name.lower())
    except Exception:
        pass
    if not allowed:
        # Fallback: cualquier .png presente en la firma
        soup = BeautifulSoup(sig_html or "", "lxml")
        for img in soup.find_all("img"):
            name = _basename_from_src(img.get("src", ""))
            if name.endswith(".png"):
                allowed.add(name)
    return allowed




def upsert_image_classification_in_manifest(slug: str, classification: dict) -> dict:
    """
    Lee manifest, inserta/actualiza in_message, in_signature, is_logo en shared.images[*].
    Preserva marcas previas si ya existían (prioriza clasificación nueva si hay conflicto).
    """
    s3 = get_s3()
    mk = f"emails/templates/{slug}/manifest.json"
    try:
        man = json.loads(s3.get_object(Bucket=S3_BUCKET, Key=mk)["Body"].read())
    except Exception:
        man = {}

    shared = man.setdefault("shared", {})
    imgs = shared.setdefault("images", {})

    for name, cls in classification.items():
        meta = imgs.setdefault(name, {})
        # conserva key/url/etag/last_modified si ya están; añade flags
        meta["in_message"] = cls["in_message"]
        meta["in_signature"] = cls["in_signature"]
        # si ya había is_logo definido manualmente, respétalo; si no, usa el calculado
        if not isinstance(meta.get("is_logo"), bool):
            meta["is_logo"] = cls["is_logo"]

    man["updated_at"] = int(__import__("datetime").datetime.now(__import__("datetime").timezone.utc).timestamp())
    s3.put_object(
        Bucket=S3_BUCKET, Key=mk,
        Body=json.dumps(man, indent=2, ensure_ascii=False).encode(),
        ContentType="application/json",
        CacheControl="no-cache, no-store, must-revalidate",
        Expires=0,
    )
    return man

_ICON_RE = re.compile(r"(logo|icon|facebook|instagram|linkedin|youtube|whatsapp|twitter|x|tiktok|brand)", re.I)

def _is_small_or_icon(name: str, meta: dict) -> bool:
    n = (name or "").lower()
    if meta.get("is_logo"):           # marcado explícito
        return True
    if _ICON_RE.search(n):            # nombre sugiere icono/logo
        return True
    # si guardas dimensiones en el manifest:
    w = meta.get("target_w") or meta.get("w") or 0
    h = meta.get("target_h") or meta.get("h") or 0
    if (w and w <= 200) or (h and h <= 120):
        return True
    # si guardas tamaño de archivo (puedes añadirlo en update_manifest):
    size = meta.get("size") or meta.get("bytes") or 0
    if size and size <= 80_000:       # <= ~80KB suele ser icono
        return True
    return False


_SIGNATURE_MARKERS = [
    # Español
    r"\b(un\s+saludo|saludos|atentamente|cordial(?:mente)?|gracias)\b",
    # Inglés
    r"\b(kind\s+regards|best\s+regards|regards|sincerely|thanks|thank you)\b",
    # Francés
    r"\b(cordialement|bien\s+à\s+vous|salutations)\b",
]

# Listas de cierres/saludos por idioma
LANG_HINTS = {
    "es": {
        "closings": [
            r"un\s+saludo[s]?", r"saludos", r"atentamente", r"cordialmente",
            r"gracias", r"muchas\s+gracias", r"recibe[n]?\s+un\s+cordial\s+saludo"
        ]
    },
    "en": {
        "closings": [
            r"kind\s+regards", r"best\s+regards", r"regards", r"sincerely",
            r"thanks(?!giving)", r"many\s+thanks", r"thank\s+you"
        ]
    },
    "fr": {
        "closings": [
            r"cordialement", r"bien\s+à\s+vous", r"salutations\s+distinguées",
            r"merci", r"avec\s+mes\s+remerciements"
        ]
    }
}

# Separadores típicos de firmas
SIG_SEPARATORS = [
    r"^--\s*$",                          # -- (plaintext)
    r"^_{2,}\s*$",                       # __________
    r"^–{2,}\s*$",                       # ––
    r"^envoyé\s+depuis\s+mon\s+iphone",  # FR móviles
    r"^sent\s+from\s+my",                # EN móviles
]


def _looks_like_signature_block(tag) -> bool:
    """
    Heurística visual/estructural:
    - tablas pequeñas al final
    - muchos <br>, textos cortos, muchos links y/o imgs pequeñas
    """
    if not tag: return False
    text = _norm_text(tag.get_text(" ", strip=True))
    if not text: return False
    # muy corto => sospechoso de firma
    if len(text) < 40:
        return True
    # tiene varios <br> y muchos enlaces/imágenes
    links = len(tag.find_all("a"))
    imgs  = len(tag.find_all("img"))
    brs   = len(tag.find_all("br"))
    if (links + imgs) >= 2 and brs >= 2:
        return True
    # tablas pequeñas
    if tag.name == "table":
        # ancho por estilo/attrs (muy simple)
        style = (tag.get("style") or "").lower()
        if "width" in style and ("200" in style or "250" in style or "300" in style):
            return True
    return False
def try_with_lang(lc: str, html: str) -> BeautifulSoup | None:
        
        soup = BeautifulSoup(html or "", "lxml")
        body = soup.body or soup
        closings = LANG_HINTS.get(lc, {}).get("closings", [])
        if not closings: return None
        pattern = re.compile(r"(" + r"|".join(closings) + r")\b", re.I)
        # recorre párrafos desde abajo y corta en el primero que parezca cierre
        ps = body.find_all(["p", "div", "table"])
        for node in reversed(ps):
            txt = _norm_text(node.get_text(" ", strip=True))
            if not txt: 
                continue
            if pattern.search(txt):
                return node
        return None



USE_NEW_SPLITTER = True  # ponlo a False si quieres volver al comportamiento anterior

_SIGNATURE_RE = re.compile("|".join(_SIGNATURE_MARKERS), re.IGNORECASE)

def get_message_and_signature(html: str, lang: str = "en") -> tuple[str, str]:
    soup = BeautifulSoup(html or "", "lxml")
    body = soup.body or soup

    # 1) si existe contenedor típico de firma (Thunderbird/Outlook)
    sig_container = body.find(class_=lambda c: c and "moz-signature" in c.lower())
    if not sig_container:
        sig_container = body.find("div", attrs={"data-signature": True})
    if sig_container:
        # Firma = ese contenedor; Mensaje = todo menos ese contenedor
        sig_html = str(sig_container)
        sig_container.decompose()
        msg_html = str(body)
        return msg_html, sig_html

    # 2) busca frase de despedida y toma el “resto” como firma
    #    nos quedamos con el último match para evitar saludos intermedios
    text_nodes = body.find_all(text=True)
    last_pos = -1
    for t in text_nodes:
        m = _SIGNATURE_RE.search(t)
        if m:
            # subimos al bloque visible (p/div/td/tr/table) más cercano que tenga contenido
            node = t.parent
            while node and node.name not in ("p", "div", "td", "tr", "table", "section"):
                node = node.parent
            if node:
                # recuerda el último candidato
                last_pos = max(last_pos, node.sourceline or -1)

    if last_pos != -1:
        # corta por la última posición
        # estrategia simple: recorre los hijos y cuando pasemos la línea, todo pasa a firma
        msg_frag = []
        sig_frag = []
        for child in list(body.children):
            # algunos parsers no tienen sourceline: fallback por orden
            line = getattr(child, "sourceline", None)
            if line and line >= last_pos:
                sig_frag.append(child)
            else:
                msg_frag.append(child)

        sig_html = "".join(str(x) for x in sig_frag) or ""
        msg_html = "".join(str(x) for x in msg_frag) or ""
        if sig_html.strip():
            return msg_html, sig_html

    # 3) fallback: si hay una tabla final (muy típico de firma), úsala como firma
    tables = body.find_all("table")
    if tables:
        last_table = tables[-1]
        sig_html = str(last_table)
        last_table.decompose()
        msg_html = str(body)
        return msg_html, sig_html

    # 4) último recurso: sin firma detectable
    return str(body), ""




def _count_text_chars(el):
    return len((el.get_text(" ", strip=True) or ""))

def _count_imgs(el):
    return len(el.find_all("img"))


def _find_last_cue_node(body: BeautifulSoup):
    last = None
    for el in body.find_all(True, recursive=True):
        txt = (el.get_text(" ", strip=True) or "").lower()
        if any(p in txt for p in CUE_PHRASES):
            last = el
    return last



def looks_like_signature_block(tag) -> bool:
    """Heurística simple para detectar un bloque de firma."""
    if not getattr(tag, "name", None):
        return False
    txt = " ".join((tag.get_text(" ", strip=True) or "").split())
    if not txt:
        return False
    # corto = sospechoso
    if len(txt) < 40:
        return True
    links = len(tag.find_all("a"))
    imgs  = len(tag.find_all("img"))
    brs   = len(tag.find_all("br"))
    if (links + imgs) >= 2 and brs >= 2:
        return True
    if tag.name == "table":
        style = (tag.get("style") or "").lower()
        if "width" in style and any(w in style for w in ("200", "250", "300")):
            return True
    return False

def _has_cue(text_html_lower: str) -> bool:
    return any(c in text_html_lower for c in CUE_PHRASES)

def _is_probably_body(html: str) -> bool:
    # heurística simple: listas/títulos largos -> cuerpo
    low = (html or "").lower()
    return any(t in low for t in ("<ul", "<ol", "<li", "<h1", "<h2", "<h3"))

def guard_signature_false_positive(sig_html: str, msg_html: str) -> tuple[str, str]:
 
    sig_html = sig_html or ""
    msg_html = msg_html or ""

    soup_sig = BeautifulSoup(sig_html, "lxml")
    sig_text = soup_sig.get_text(" ", strip=True)
    sig_len  = len(sig_text)
    sig_imgs = len(soup_sig.find_all("img"))
    has_cue  = _has_cue(sig_html.lower())

    # --- GUARD RAIL ---
    if (sig_imgs == 0) and (not has_cue) and (sig_len >= 140 or _is_probably_body(sig_html)):
        # falso positivo: la “firma” es texto de cuerpo
        # => devuélvelo al cuerpo y deja firma vacía
        new_msg_html = msg_html + "\n" + sig_html
        return "", new_msg_html
    return sig_html, msg_html



CONTACT_TOKENS = [
    "tel", "t.", "m.", "mobile", "email", "e.", "web", "www", "@", "http", "https",
    "planetpower", "ledpadel", "moduloled", ".es", ".com", ".fr", ".it", ".de"
]

EXPLICIT_SIGNATURE_CLASSES = {
    "moz-signature", "gmail_signature", "signature", "firma", "__signature__", "email-signature"
}

re_email = re.compile(r"\b[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}\b", re.I)
re_phone = re.compile(r"\+?\d[\d\s().\-]{6,}")
re_forward_header = re.compile(r"^(de:|from:|enviado el:|sent:|para:|to:|asunto:|subject:)\b", re.I)

def _txt(node):
    return (node.get_text(" ", strip=True) if hasattr(node, "get_text") else "").strip()

def _basename_from_src(src: str) -> str:
    from urllib.parse import urlparse
    import os
    if not src: return ""
    path = urlparse(src).path or src
    return os.path.basename(path).lower()



def _is_explicit_signature_container(node) -> bool:
    cls = (node.get("class") or [])
    idv = (node.get("id") or "").lower()
    if any(c.lower() in EXPLICIT_SIGNATURE_CLASSES for c in cls): return True
    if idv in EXPLICIT_SIGNATURE_CLASSES: return True
    return False

def _node_score(node) -> int:
    """Suma señales de 'bloque de firma'."""
    if not node: return 0
    score = 0
    txt = _txt(node)
    tl  = txt.lower()
    links = len(node.find_all("a"))
    imgs  = node.find_all("img")
    brs   = len(node.find_all("br"))

    # cues textuales
    if any(cue in tl for cue in CUE_PHRASES): score += 4

    # datos de contacto
    if re_email.search(txt): score += 2
    if re_phone.search(txt): score += 2
    if sum(t in tl for t in CONTACT_TOKENS) >= 2: score += 2

    # estructura "firma"
    if links >= 2: score += 1
    if brs >= 2:   score += 1
    if node.name == "table":
        # muchas firmas vienen en tabla pequeña
        style = (node.get("style") or "").lower()
        if "width" in style:
            if any(w in style for w in ("200", "250", "300", "320", "354", "400")):
                score += 2
        tds = node.find_all("td")
        if 1 <= len(tds) <= 8:
            score += 1

    # imágenes "logo-ish": png/svg, nombres tipo logo, o tamaño pequeño si hay attrs
    logos = 0
    for img in imgs:
        name = _basename_from_src(img.get("src", ""))
        if name.endswith((".png", ".svg")): logos += 1
        if any(k in name for k in ("logo", "firma", "signature", "brand", "marca")): logos += 1
        try:
            w = int((img.get("width") or "0").split("px")[0])
            h = int((img.get("height") or "0").split("px")[0])
            if 0 < w <= 400 and 0 < h <= 200:
                logos += 1
        except Exception:
            pass
    if logos >= 1: score += 2
    if logos >= 2: score += 1

    # longitud moderada (firmas suelen ser cortas/medias)
    if len(txt) <= 800: score += 1
    if len(txt) <= 300: score += 1

    return score

def split_message_signature(html: str) -> tuple[str, str]:
    """
    1) Limpia cabeceras de forward/reply.
    2) Si hay contenedor explícito de firma → corta ahí.
    3) Si no, puntúa nodos de primer nivel de abajo arriba y corta en el primero que supere umbral.
    4) Agrupa desde ese nodo hasta el final como firma (uniendo bloques contiguos con score>0).
    """
    soup = BeautifulSoup(html or "", "lxml")
    body = soup.body or soup

    _strip_forward_headers(body)

    # candidatos de primer nivel
    blocks = [n for n in body.find_all(recursive=False) if n.name in ("p","div","table","ul","ol") and _txt(n)]

    if not blocks:
        return str(body), ""

    # 2) contenedor explícito
    for i in range(len(blocks)-1, -1, -1):
        if _is_explicit_signature_container(blocks[i]):
            msg = blocks[:i]
            sig = blocks[i:]
            msg_wrap = BeautifulSoup("<div></div>", "lxml")
            sig_wrap = BeautifulSoup("<div></div>", "lxml")
            for n in msg: msg_wrap.div.append(n.extract())
            for n in sig: sig_wrap.div.append(n.extract())
            return str(msg_wrap.div), str(sig_wrap.div)

    # 3) scoring bottom-up
    scores = [(_node_score(n)) for n in blocks]
    # umbral: 4 funciona bien; si nada supera, baja a 3
    cut_idx = None
    for thresh in (4, 3):
        for i in range(len(blocks)-1, -1, -1):
            if scores[i] >= thresh:
                cut_idx = i
                break
        if cut_idx is not None:
            break

    if cut_idx is None:
        # sin señales → no separamos
        return str(body), ""

    # 4) agrupa firma desde cut_idx y arrastra nodos siguientes que tengan alguna señal (score>0)
    j = cut_idx + 1
    while j < len(blocks) and _node_score(blocks[j]) > 0:
        j += 1

    msg_nodes = blocks[:cut_idx]
    sig_nodes = blocks[cut_idx:j]
    # si todo quedó como firma, exige tener cue/email/phone; si no, no separe
    if not msg_nodes:
        strong = any(_has_strong_signature_signal(n) for n in sig_nodes)
        if not strong:
            return str(body), ""

    msg_wrap = BeautifulSoup("<div></div>", "lxml")
    sig_wrap = BeautifulSoup("<div></div>", "lxml")
    for n in msg_nodes: msg_wrap.div.append(n.extract())
    for n in sig_nodes: sig_wrap.div.append(n.extract())
    return str(msg_wrap.div), str(sig_wrap.div)

def _has_strong_signature_signal(node) -> bool:
    t = _txt(node)
    tl = t.lower()
    if any(c in tl for c in CUE_PHRASES): return True
    if re_email.search(t): return True
    if re_phone.search(t): return True
    if any(c.lower() in (node.get("class") or []) for c in EXPLICIT_SIGNATURE_CLASSES): return True
    return False


FORWARD_LABELS = ("de:", "from:", "enviado el:", "sent:", "para:", "to:", "asunto:", "subject:", "cc:")

def remove_forward_headers_aggressive(html: str) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    body = soup.body or soup
    # busca bloques candidatos con varias etiquetas de cabecera
    candidates = []
    for node in body.find_all(["div","p","table"], recursive=True):
        txt = (node.get_text(" ", strip=True) or "").lower()
        hits = sum(lbl in txt for lbl in FORWARD_LABELS)
        if hits >= 2:
            # sube al contenedor “bonito”
            top = node
            for _ in range(3):
                if not top.parent or top.parent == body: break
                # si el padre solo contiene ese nodo, sube
                if len([c for c in top.parent.find_all(recursive=False) if getattr(c, "name", None)]) <= 2:
                    top = top.parent
            candidates.append(top)
    # dedup por id
    seen = set()
    for n in candidates:
        if id(n) in seen: continue
        seen.add(id(n))
        n.decompose()
    return str(body)

def _looks_like_body(txt: str) -> bool:
    t = (txt or "").strip()
    # mucho texto o listas → probablemente cuerpo
    return (len(t) > 600) or ("<ul" in t.lower()) or ("<ol" in t.lower())

def _is_logo_by_heuristic(name: str, meta: dict | None) -> bool:
    n = (name or "").lower()
    if not (n.endswith(".png") or n.endswith(".svg")):
        return False
    # nombre típico de logo
    if any(k in n for k in ("logo", "firma", "signature", "brand", "mark", "isologo")):
        return True
    # tamaños “pequeños” si tienes meta (puedes leer de manifest target_w/target_h o exif):
    w = (meta or {}).get("target_w") or 0
    h = (meta or {}).get("target_h") or 0
    if w and h and (w <= 400 and h <= 200):
        return True
    return False


def _looks_like_body(html: str) -> bool:
    # mucho texto, varias listas/párrafos → pinta de cuerpo
    soup = BeautifulSoup(html or "", "lxml")
    txt = (soup.get_text(" ", strip=True) or "")
    paras = len(soup.find_all("p")) + len(soup.find_all("li"))
    return len(txt) > 1200 or paras >= 8

def keep_only_logo_images(html: str, allowed_filenames: set[str]) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    for img in soup.find_all("img"):
        name = _basename_from_src(img.get("src", ""))
        if name not in allowed_filenames:
            img.decompose()
    return str(soup)


def fallback_tail_signature(full_html: str) -> tuple[str, str]:
    soup = BeautifulSoup(full_html or "", "lxml")
    text = soup.get_text(" ", strip=True).lower()
    CUE = ("kind regards","best regards","regards,","saludos","un saludo","cordialmente","atentamente")
    hit = None
    for cue in CUE:
        idx = text.rfind(cue)
        if idx != -1:
            hit = cue; break
    if not hit:
        return full_html, ""  # nada que hacer

    # parte visual: toma el último <table> o <div> pequeño al final
    blocks = soup.find_all(["table","div","p"])
    tail = []
    for tag in reversed(blocks):
        t = (tag.get_text(" ", strip=True) or "").lower()
        if len(t) <= 1200 or len(tag.find_all("img")) <= 6:
            tail.append(tag)
            if len(tail) >= 2:  # 1-2 bloques finales
                break

    sig_soup = BeautifulSoup("<div></div>", "lxml")
    wrap = sig_soup.new_tag("div")
    for tag in reversed(tail):
        wrap.append(tag.extract())
    sig_soup.body.append(wrap) if sig_soup.body else sig_soup.append(wrap)

    # cuerpo = original menos lo extraído
    body_html = str(soup)
    sig_html  = str(sig_soup)
    return body_html, sig_html



CUE_PHRASES = (
    # ES
    "saludos", "un saludo", "saludos cordiales", "atentamente", "cordialmente",
    "reciba un cordial saludo", "gracias y saludos", "gracias, saludos",
    # EN
    "kind regards", "best regards", "regards,", "regards", "sincerely", "thanks,", "thank you",
    # FR
    "cordialement", "bien cordialement", "sincèrement", "salutations distinguées"
)

def _is_small_block(tag: BeautifulSoup) -> bool:
    """Bloque típico de firma: poco texto o varias <br>, enlaces e imágenes, o tabla estrecha."""
    if not tag: return False
    text = (tag.get_text(" ", strip=True) or "")
    if len(text) <= 40:  # muy corta
        return True
    brs   = len(tag.find_all("br"))
    links = len(tag.find_all("a"))
    imgs  = len(tag.find_all("img"))
    if (links + imgs) >= 2 and brs >= 2:
        return True
    if tag.name == "table":
        style = (tag.get("style") or "").lower()
        w = ""
        # detecta width fijo típico Word/Outlook
        for tok in ("width:", "width="):
            if tok in style:
                w = style.split(tok,1)[1][:12]
                break
        if any(x in style for x in ("200", "220", "240", "250", "260", "280", "300")):
            return True
    return False

def _tail_blocks(soup: BeautifulSoup, max_pick: int = 3):
    """Devuelve hasta 3 bloques del final que 'huelan' a firma."""
    blocks = [t for t in soup.find_all(["table","div","p"]) if t.get_text(strip=True)]
    picked = []
    for tag in reversed(blocks):
        if _is_small_block(tag):
            picked.append(tag)
        if len(picked) >= max_pick:
            break
    return list(reversed(picked))


EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"\+?\d[\d \-\(\)]{6,}")
URL_RE   = re.compile(r"https?://|www\.", re.I)


def _node_has_contact_tokens(tag) -> bool:
    t = tag.get_text(" ", strip=True)
    return bool(EMAIL_RE.search(t) or PHONE_RE.search(t) or URL_RE.search(t))

def _many_breaks_links_imgs(tag) -> bool:
    return (len(tag.find_all("br")) >= 2 and
            (len(tag.find_all("a")) + len(tag.find_all("img"))) >= 2)

def _is_small_table(tag) -> bool:
    if tag.name != "table":
        return False
    style = (tag.get("style") or "").lower()
    width_hit = any(w in style for w in ["200", "250", "300", "265.15pt", "354px"])
    # también si hay pocas celdas y bastante <br>
    tds = tag.find_all("td")
    return width_hit or (len(tds) <= 6 and len(tag.find_all("br")) >= 2)

def _strip_forward_headers(soup: BeautifulSoup):
    # quita bloques típicos de “De: … Enviado el: … Para: …”
    for t in soup.find_all(text=True):
        txt = (t or "").strip().lower()
        if txt.startswith("de: ") or txt.startswith("from: "):
            # sube a contenedor superior con borde/estilo o párrafo
            block = t
            for _ in range(4):
                if hasattr(block, "parent") and block.parent:
                    block = block.parent
            try:
                block.decompose()
            except Exception:
                pass

def _blocks_bottom_up(soup: BeautifulSoup):
    # devuelve tags “bloque” desde el final: p, div, table, ul/ol
    blocks = []
    for tag in soup.find_all(True, recursive=False):
        blocks.append(tag)
    # si todo está anidado, cae a aplanado simple
    if not blocks:
        blocks = soup.find_all(["p","div","table","ul","ol"])
    return list(reversed(blocks or []))

def _inner_html(tag) -> str:
    return "".join(str(c) for c in (tag.contents or []))

def _collect_basenames_from_html(html: str) -> set[str]:
    from urllib.parse import urlparse
    import os
    names = set()
    s = BeautifulSoup(html or "", "lxml")
    for img in s.find_all("img"):
        src = (img.get("src") or "").strip()
        if not src:
            continue
        path = urlparse(src).path or src
        names.add(os.path.basename(path).lower())
    return names


_CUE_PHRASES = [
    # EN
    "kind regards", "best regards", "regards,", "sincerely", "cheers", "thank you", "thanks and regards",
    # ES
    "saludos", "saludos cordiales", "un saludo", "atentamente", "gracias", "cordialmente",
    # FR
    "cordialement", "bien à vous", "sincèrement", "merci", "salutations",
]

_HDR_QUOTED = [
    # cabecera citada de Outlook/Thunderbird/Gmail
    "from:", "de:", "sent:", "enviado el:", "to:", "para:", "cc:", "subject:", "asunto:"
]

_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_PHONE_RE = re.compile(r"(\+\d{1,3}\s*)?(\(?\d{2,4}\)?[\s\-]?)?\d{3,}((\s|-)d{2,})*", re.I)

def _norm(s: str) -> str:
    return (s or "").strip().lower()

def _looks_quoted_header(txt: str) -> bool:
    t = _norm(txt)
    hits = sum(1 for h in _HDR_QUOTED if h in t)
    # si contiene varios campos de cabecera, trátalo como “header citado” (no firma)
    return hits >= 2

def _has_contact_clues(tag) -> bool:
    # enlaces con mailto/tel o dominios, teléfonos, emails
    if any((a.get("href") or "").startswith(("mailto:", "tel:")) for a in tag.find_all("a")):
        return True
    t = tag.get_text(" ", strip=True)
    if _EMAIL_RE.search(t): return True
    if _PHONE_RE.search(t): return True
    # enlaces a dominios propios
    if any("." in (a.get_text() or a.get("href") or "") for a in tag.find_all("a")):
        return True
    return False

def _is_small_visual_block(tag) -> bool:
    # firmas suelen ir en tablas o divs estrechos
    style = _norm(tag.get("style") or "")
    if "width" in style:
        for w in ["180", "200", "220", "240", "260", "300", "320", "350", "400"]:
            if w in style:
                return True
    # tablas pequeñas con pocas celdas
    if tag.name == "table":
        cells = tag.find_all(["td","th"])
        if len(cells) and len(cells) <= 8:
            return True
    # muchas <br> o varias imágenes pequeñas
    brs = len(tag.find_all("br"))
    imgs = tag.find_all("img")
    small_imgs = 0
    for i in imgs:
        w = i.get("width"); h = i.get("height")
        if w and h:
            try:
                w = int(str(w).replace("px",""))
                h = int(str(h).replace("px",""))
                if w <= 400 and h <= 180: small_imgs += 1
            except: pass
    if brs >= 2 or small_imgs >= 1:
        return True
    return False

def _has_cue_phrase(tag) -> bool:
    t = _norm(tag.get_text(" ", strip=True))
    return any(c in t for c in _CUE_PHRASES)

def _is_signature_candidate(tag) -> bool:
    if not tag: return False
    # ignora headers citados (“De:… Enviado el:…”)
    if _looks_quoted_header(tag.get_text(" ", strip=True)):
        return False
    # Señales combinadas
    score = 0
    if _has_cue_phrase(tag):      score += 2
    if _has_contact_clues(tag):   score += 2
    if _is_small_visual_block(tag): score += 1
    # texto corto suma
    if len(tag.get_text(" ", strip=True)) <= 600: score += 1
    return score >= 3  # umbral



def _looks_like_logo_img(bs_img) -> bool:
        """Heurística simple por tamaño/nombre para logos."""
        name = _basename_from_src(bs_img.get("src", ""))
        t = (bs_img.get("style") or "").lower()
        # lee width/height explícitos si existen
        def _to_int(v):
            try:
                return int(v)
            except:
                return None

        w = _to_int(bs_img.get("width") or "")
        h = _to_int(bs_img.get("height") or "")
        # intenta extraer de style: width:120px;height:40px;
        import re
        if w is None:
            m = re.search(r"width\s*:\s*(\d+)", t)
            if m: w = _to_int(m.group(1))
        if h is None:
            m = re.search(r"height\s*:\s*(\d+)", t)
            if m: h = _to_int(m.group(1))

        # límites típicos de logo/icono (ajustables)
        small_w = (w is not None and w <= 220)
        small_h = (h is not None and h <= 120)

        name_hint = any(k in name for k in ("logo", "icon", "brand", "isologo", "mark"))
        png_hint  = name.endswith(".png")

        # criterios: PNG + (pequeño o indica logo en nombre)
        return (png_hint and (small_w or small_h or name_hint))



def _norm_text(s): 
    return (s or "").strip()

def _block_level(tag):
    return tag and tag.name in {
        "table","tbody","tr","td","div","section","article","p","ul","ol","li"
    }

def _has_contacts(txt):
    t = txt.lower()
    return (
        any(c in t for c in CUE_PHRASES) or
        _EMAIL_RE.search(txt) is not None or
        _PHONE_RE.search(txt) is not None or
        "http://" in t or "https://" in t or ".com" in t or ".es" in t or ".fr" in t
    )

def _img_count(tag):
    return len(tag.find_all("img")) if tag else 0

def _table_is_small(tab):
    if not tab or tab.name != "table": return False
    sty = (tab.get("style") or "").lower()
    if "width" in sty:
        # heurística simple de ancho “pequeño” de firma
        return any(w in sty for w in ["200", "220", "240", "250", "280", "300", "320", "340", "360"])
    # si no hay width, usa número de celdas e imágenes
    tds = tab.find_all("td")
    return len(tds) <= 10 and _img_count(tab) <= 6


def bs(html: str):
    # helper para evitar repetir import y minimizar fallos
    return BeautifulSoup(html or "", "lxml")



DISCLAIMER_CUES = [
    "la información contenida",  # ES
    "confidential", "privileged", "este e-mail", "this email contains"
]

def safe_split_message_signature(html: str) -> tuple[str, str]:
    s = bs(html)
    body = s.body or s

    # 1) texto plano del documento completo
    full_txt = body.get_text(" ", strip=True)
    low = full_txt.lower()

    # 2) busca la ÚLTIMA ocurrencia de una frase de firma (“Kind Regards”, “Saludos”, etc.)
    cut_idx = -1
    cue_found = None
    for cue in CUE_PHRASES:
        idx = low.rfind(cue)
        if idx > cut_idx:
            cut_idx = idx
            cue_found = cue

    # 3) si no hay frase de cortesía, intenta con disclaimers (suelen ir en la firma)
    if cut_idx < 0:
        for cue in DISCLAIMER_CUES:
            idx = low.rfind(cue)
            if idx > cut_idx:
                cut_idx = idx
                cue_found = cue

    # 4) si seguimos sin nada, heurística: último bloque con muchos links/imagenes o una tablita
    if cut_idx < 0:
        # baja desde el final buscando un bloque candidato
        cand = None
        for node in reversed(list(body.descendants)):
            if getattr(node, "name", None) in ("p","div","table"):
                txt = (node.get_text(" ", strip=True) or "")
                links = len(node.find_all("a")) if hasattr(node, "find_all") else 0
                imgs  = len(node.find_all("img")) if hasattr(node, "find_all") else 0
                if (links + imgs) >= 2 or node.name == "table":
                    cand = node
                    break
        if cand:
            # corta a partir del nodo candidato
            sig_frag = str(cand)
            # borra el candidato del body para formar el mensaje
            cand.extract()
            return (str(s), sig_frag)
        else:
            # no hay firma detectable
            return (html, "")

    # 5) tenemos un índice en el TEXTO; ahora hay que “mapearlo” a un nodo HTML
    # recorre párrafos desde el final hasta encontrar el que contiene la cue
    sig_container = None
    for node in reversed(list(body.find_all(["p","div","table"]))):
        txt = (node.get_text(" ", strip=True) or "").lower()
        if cue_found and cue_found in txt:
            sig_container = node
            break

    if not sig_container:
        # fallback tosco: parte el texto a lo bruto
        # (mejor que nada, pero normalmente encontraremos el nodo arriba)
        msg_part, sig_part = full_txt[:cut_idx], full_txt[cut_idx:]
        # envuelve para mantener HTML mínimamente válido
        return (f"<div>{msg_part}</div>", f"<div>{sig_part}</div>")

    # 6) construye firma = desde 'sig_container' hasta el final (hermanos siguientes)
    sig_wrapper = s.new_tag("div")
    cur = sig_container
    while cur:
        nxt = cur.next_sibling
        sig_wrapper.append(cur.extract())
        cur = nxt

    # lo restante en <body> es el mensaje
    return (str(s), str(sig_wrapper))




def _collect_img_names_in_order(html: str):
    """Devuelve [(basename, outer_html_img)] en orden de aparición."""
    soup = BeautifulSoup(html or "", "lxml")
    out = []
    for img in soup.find_all("img"):
        src = (img.get("src") or "").strip()
        if not src:
            continue
        name = _basename_from_src(src)  # ya la tienes
        if name:
            out.append((name, str(img)))
    return out



def _sig_rescue_tail_pngs(
    full_html: str,
    current_sig_html: str,
    body_names: set[str] | None = None,
    max_imgs: int = 2,
    images_map: dict | None = None,   # <- NUEVO, pero opcional
) -> str:
    """
    Si la firma quedó sin <img>, añade PNGs del final del documento
    (típicos logos), excluyendo los que también están en el cuerpo.

    - Si `images_map` viene con metadatos, usamos `_is_signature_image`
      para filtrar (tamaño < 30KB, is_logo, etc.).
    - Si `images_map` es None o vacío, se comporta como la versión vieja
      (acepta todos los PNG del final que no estén en el cuerpo).
    """
    from bs4 import BeautifulSoup

    # si ya hay imágenes en la firma, no tocar
    if BeautifulSoup(current_sig_html or "", "lxml").find("img"):
        return current_sig_html

    body_names = body_names or set()
    ordered = _collect_img_names_in_order(full_html)  # [(name, <img ...>)]
    if not ordered:
        return current_sig_html

    use_filter = bool(images_map)   # solo filtramos por tamaño/logo si tenemos meta
    images_map = images_map or {}

    tail_html = []
    started = False

    for name, tag_html in reversed(ordered):
        nlow = name.lower()

        # solo PNGs y que no estén en el cuerpo
        if not nlow.endswith(".png") or nlow in body_names:
            if started:
                break
            else:
                continue

        # si tenemos metadatos, aplicamos el filtro “de firma”
        if use_filter:
            meta = images_map.get(name, {})
            if not _is_signature_image(meta):
                if started:
                    break
                else:
                    continue

        tail_html.append(tag_html)
        started = True

        if len(tail_html) >= max_imgs:
            break

    if not tail_html:
        return current_sig_html

    tail_html.reverse()  # mantener orden visual

    return (current_sig_html or "") + '<div class="sig-logos">' + "".join(tail_html) + "</div>"


# --- PONER AL INICIO DEL MÓDULO ---
from bs4 import BeautifulSoup
import re

PHONE_RE   = re.compile(r'\b(?:\+?\d{1,3}[\s.-]?)?(?:\d[\s.-]?){6,}\b')
EMAIL_RE   = re.compile(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}', re.I)
DOMAIN_RE  = re.compile(r'\b(?:planetpower\.es|moduloled\.es|ledpadel\.com)\b', re.I)

BLOCK_TAGS = {"table", "div", "section", "footer", "p"}

def _has_signature_cues(tag: "bs4.element.Tag") -> bool:
    if not tag: return False
    txt = tag.get_text(" ", strip=True) if tag else ""
    if not txt:
        # si no hay texto, quizás hay logos
        if tag.find("img"):
            return True
        return False
    cues = (
        PHONE_RE.search(txt) or
        EMAIL_RE.search(txt) or
        DOMAIN_RE.search(txt)
    )
    imgs = bool(tag.find("img"))
    return bool(cues or imgs)

def _extract_signature_bottom_up(html: str) -> tuple[str, str]:
    """
    Busca desde el final el último bloque que 'huela' a firma.
    Devuelve (message_html, signature_html) preservando orden.
    Si no encuentra firma, signature_html = "".
    """
    soup = BeautifulSoup(html or "", "lxml")
    body = soup.body or soup

    # candidatos: elementos de primer nivel en <body>
    children = [c for c in body.children if getattr(c, "name", None)]
    if not children:
        return html, ""

    # busca el último bloque con señales de firma
    sig_start_idx = None
    for idx in range(len(children) - 1, -1, -1):
        el = children[idx]
        if el.name not in BLOCK_TAGS:
            continue
        if _has_signature_cues(el):
            sig_start_idx = idx
            break

    if sig_start_idx is None:
        # sin firma identificable
        return html, ""

    # firma = desde ese bloque hasta el final (preservando orden)
    sig_nodes = children[sig_start_idx:]
    msg_nodes = children[:sig_start_idx]

    # serializa preservando exactamente los nodos
    sig_html = "".join(str(n) for n in sig_nodes).strip()
    msg_html = "".join(str(n) for n in msg_nodes).strip()

    print(f"[INFO] Firma detectada en bloque {sig_start_idx} de {len(children)} (bottom-up)")
    print(f"[DEBUG] Firma HTML: {sig_html[:120]}...")

    return msg_html, sig_html




def _dimensions_for_image(idx: int, img_id: str, content: bytes) -> dict:
    """
    Calcula dimensiones manteniendo la proporción original,
    pero normalizando el ancho a 600 px.
    """
    try:
        img = Image.open(io.BytesIO(content))
        w, h = img.size
        ratio = h / w
        target_w = 900
        target_h = int(target_w * ratio)
        fit = "contain"  # no recortar, solo escalar
        return {"target_w": target_w, "target_h": target_h, "fit": fit}
    except Exception as e:
        # si algo falla, devolvemos solo ancho fijo
        return {"target_w": 900, "fit": "contain"}




def _default_dims_for_index(idx: int, content: bytes) -> dict:
    """
    Calcula dimensiones manteniendo proporción.
    idx = posición en la secuencia (0 = hero)
    content = bytes de la imagen (ya descargados o recibidos)
    """
    target_w = 900
    try:
        img = Image.open(io.BytesIO(content))
        w, h = img.size
        ratio = h / w
        target_h = int(target_w * ratio)

        # Solo la primera imagen puede forzarse a "cover"
        fit = "cover" if idx == 0 else "contain"

        return {"target_w": target_w, "target_h": target_h, "fit": fit}
    except Exception:
        # fallback si no podemos leer la imagen
        return {"target_w": target_w, "fit": "contain"}





def _merge_image_meta(old_meta: dict | None, new_core: dict) -> dict:
    """
    Funde metadatos de imagen preservando campos “persistentes” si ya existían
    en el manifest anterior, y tomando del core lo nuevo (key/url/etag/last_modified…).
    """
    old_meta = old_meta or {}
    merged = dict(new_core)  # base = lo nuevo (key, url, etag, last_modified, filename, etc.)
    for k in ("target_w", "target_h", "fit", "is_logo"):
        if k in old_meta and old_meta[k] is not None:
            merged[k] = old_meta[k]
    return merged






def ensure_dimensions_if_missing(slug: str) -> None:
    man = _load_manifest_from_s3(slug) or {}
    shared = man.setdefault("shared", {})
    imgs = shared.setdefault("images", {})
    s3 = get_s3()

    for idx, name in enumerate(sorted(imgs.keys())):
        meta = imgs.get(name) or {}
        has_any = any(k in meta for k in ("target_w", "target_h", "fit"))
        if has_any:
            continue  # ya tiene dimensiones, no recalcular

        key = meta.get("key")
        if not key:
            # Si no hay key, no podemos descargar nada, saltamos
            continue

        try:
            obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
            content = obj["Body"].read()
        except Exception as e:
            print(f"[WARN] No se pudo descargar {key} para calcular dimensiones: {e}")
            continue

        meta.update(_default_dims_for_index(idx, content))
        imgs[name] = meta

    _save_manifest_to_s3(slug, man)

#


def _basename_no_qs(u: str) -> str:
    p = urlparse(u or "").path
    return os.path.basename(p).split("?")[0].lower()

def _collect_img_names(node) -> set[str]:
    names = set()
    for i in node.find_all("img"):
        names.add(_basename_no_qs(i.get("src","")))
    return {n for n in names if n}

def remove_signature_block_by_images(full_html: str, sig_html: str) -> str:
    """
    Quita SOLO el bloque más bajo cuyo conjunto de imágenes sea subconjunto
    de las imágenes que aparecen en la firma. Si la firma no tiene imágenes,
    no elimina nada (conservador).
    """
    if not (full_html and sig_html):
        return full_html or ""

    fsoup = BeautifulSoup(full_html, "lxml")
    ssoup = BeautifulSoup(sig_html,   "lxml")

    sig_imgs = _collect_img_names(ssoup)
    if not sig_imgs:
        return full_html  # no sabemos qué borrar: no toques nada

    candidates = list(fsoup.find_all(["table","div","section","footer","p"]))
    for node in reversed(candidates):  # de abajo hacia arriba
        node_imgs = _collect_img_names(node)
        if node_imgs and node_imgs.issubset(sig_imgs):
            node.decompose()
            return str(fsoup)

    return full_html


import json
from flask import Response as FlaskResponse

def _coerce_items(obj):
    """Devuelve SIEMPRE una lista/dict serializable a JSON."""
    # --- Desempaquetar tupla (Response, status) ---
    if isinstance(obj, tuple) and len(obj) == 2 and isinstance(obj[1], int):
        obj = obj[0]  # nos quedamos con el Response

    if obj is None:
        return []

    # Si ya es lista/dict
    if isinstance(obj, (list, dict)):
        if isinstance(obj, dict) and "items" in obj and isinstance(obj["items"], list):
            return obj["items"]
        return obj

    # Flask Response
    if isinstance(obj, FlaskResponse):
        data = obj.get_json(silent=True)
        if data is None:
            # Intento extra: parsear el body a mano
            try:
                data = json.loads(obj.get_data(as_text=True) or "null")
            except Exception:
                data = None
        if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
            return data["items"]
        return data or []

    # requests.Response
    try:
        import requests
        if isinstance(obj, requests.Response):
            try:
                data = obj.json()
            except Exception:
                try:
                    data = json.loads(obj.text or "null")
                except Exception:
                    data = None
            if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
                return data["items"]
            return data or []
    except Exception:
        pass

    # Cadenas/bytes con JSON
    if isinstance(obj, (str, bytes, bytearray)):
        try:
            data = json.loads(obj if isinstance(obj, str) else obj.decode("utf-8", "ignore"))
            if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
                return data["items"]
            return data or []
        except Exception:
            return []

    # Cualquier otro tipo no serializable
    return []

def pjoin(*parts): return (TEMPLATES_ROOT.joinpath(*parts)).resolve()

def paths(slug, lang):
    base = pjoin(slug)           # …/emails/templates/<slug>
    langdir = base / lang        # …/emails/templates/<slug>/<lang>
    return {
        "message": langdir / "partials" / "message.html",
        "original": langdir / "original.html",
        "template": langdir / "template.html",
        "signature": base / "partials" / "signature.html",
    }

def s3_join(*parts: str) -> str:
    # Une partes sin duplicar barras y colapsa // por /
    key = "/".join(p.strip("/") for p in parts if p is not None and p != "")
    return re.sub(r"/{2,}", "/", key)

def key_message(slug, lang):  return s3_join(ROOT_PREFIX_S3, slug, lang, "partials", "message.html")
def key_original(slug, lang): return s3_join(ROOT_PREFIX_S3, slug, lang, "original.html")
def key_template(slug, lang): return s3_join(ROOT_PREFIX_S3, slug, lang, "template.html")
def key_signature(slug):      return s3_join(ROOT_PREFIX_S3, slug, "partials", "signature.html")

def s3_get_text(key: str) -> str | None:
    s3=get_s3()
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
        return obj["Body"].read().decode("utf-8", errors="replace")
    except botocore.exceptions.ClientError as e:   # 👈 nombre completo
        code = e.response.get("Error", {}).get("Code")
        if code in ("NoSuchKey", "404", "NotFound"):
            return None
        raise

   
def s3_put_text(key: str, text: str) -> dict:
    s3=get_s3()
    return s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=text.encode("utf-8"),
        ContentType="text/html; charset=utf-8",
        CacheControl="no-cache",
    )

def s3_key_exists(key: str) -> bool:
    s3=get_s3()
    try:
        s3.head_object(Bucket=S3_BUCKET, Key=key)
        return True
    except botocore.exceptions.ClientError:
        return False
def rebuild_template(slug: str, lang: str) -> dict:
    # 1) Leer piezas vigentes
    msg_key = k(ROOT_PREFIX_S3, slug, lang, "partials", "message.html")
    sig_key = k(ROOT_PREFIX_S3, slug, "partials", "signature.html")
    tpl_key = k(ROOT_PREFIX_S3, slug, lang, "template.html")

    message   = s3_get_text(msg_key) or ""  # no inventamos fallback aquí: la pieza manda
    signature = s3_get_text(sig_key) or ""

    # 2) Cargar template actual o sembrar uno nuevo si no existe
    tpl_html = s3_get_text(tpl_key)
    if not tpl_html or ("BEGIN:MESSAGE" not in tpl_html and "END:MESSAGE" not in tpl_html):
        tpl_html = seed_template(slug, lang, message, signature)

    # 3) Sustituir bloques por anclas
    new_html, n_msg = replace_block(tpl_html, "MESSAGE", "MESSAGE", message)
    new_html, n_sig = replace_block(new_html, "SIGNATURE", "SIGNATURE", signature)

    # 4) Persistir como "última versión"
    s3_put_text(tpl_key, new_html)

    return {"template_key": tpl_key, "replacements": {"message": n_msg, "signature": n_sig}}

def replace_block(html_text: str, begin: str, end: str, new_html: str) -> tuple[str, int]:
    if not new_html:
        return html_text, 0
    pat = re.compile(
        rf"(<!--\s*BEGIN:{begin}\s*-->)(.*?)(<!--\s*END:{end}\s*-->)",
        re.IGNORECASE | re.DOTALL
    )
    def _repl(m): return m.group(1) + new_html + m.group(3)
    new_text, n = pat.subn(_repl, html_text, count=1)
    return new_text, n

def seed_template(slug: str, lang: str, message: str, signature: str) -> str:
    # Intenta conservar <head> del original si existe
    orig_key = k(ROOT_PREFIX_S3, slug, lang, "original.html")
    original = s3_get_text(orig_key) or "<!doctype html><html><head></head><body></body></html>"
    orig_soup = BeautifulSoup(original, "lxml")

    base = BeautifulSoup("<!doctype html><html><head></head><body></body></html>", "lxml")
    if orig_soup.head:
        base.head.replace_with(orig_soup.head)

    body = base.body or base
    holder = base.new_tag("div")
    holder.append(Comment(" BEGIN:MESSAGE "))
    holder.append(BeautifulSoup(message or "", "lxml"))
    holder.append(Comment(" END:MESSAGE "))
    if signature:
        holder.append(Comment(" BEGIN:SIGNATURE "))
        holder.append(BeautifulSoup(signature, "lxml"))
        holder.append(Comment(" END:SIGNATURE "))
    body.clear()
    body.append(holder)
    return str(base)

import re
from bs4 import BeautifulSoup
from jinja2 import Template

ANCHOR_MSG = (r"<!--\s*BEGIN:MESSAGE\s*-->", r"<!--\s*END:MESSAGE\s*-->")
ANCHOR_SIG = (r"<!--\s*BEGIN:SIGNATURE\s*-->", r"<!--\s*END:SIGNATURE\s*-->")

def _strip_previous_injections(html: str) -> str:
    """
    Elimina cualquier inyección previa del propio preview para evitar duplicados:
    - data-injected="message|signature"
    - repeticiones accidentales entre anclas (quitar lo de dentro y dejar las anclas)
    """
    soup = BeautifulSoup(html, "lxml")

    # 1) quita wrappers de inyección previa
    for node in soup.select('[data-injected="message"], [data-injected="signature"]'):
        node.decompose()

    out = str(soup)

    # 2) normaliza bloques entre anclas: deja vacío dentro (ya lo rellenaremos después)
    def clear_anchor_block(text: str, begin_pat: str, end_pat: str) -> str:
        pat = re.compile(rf"({begin_pat})(.*?)({end_pat})", re.I | re.S)
        return pat.sub(lambda m: m.group(1) + m.group(3), text)

    out = clear_anchor_block(out, *ANCHOR_MSG)
    out = clear_anchor_block(out, *ANCHOR_SIG)
    return out




def _norm_src(s: str) -> str:
    if not s: return ""
    s = s.strip().strip('"').strip("'")

    # srcset: quédate con la primera URL
    if "," in s or " " in s:
        first = s.split(",")[0].strip().split()[0]
        if first: s = first

    if s.startswith("data:"):
        return "data-uri"
    if s.lower().startswith("cid:"):
        s = s[4:]

    try:
        u = urlparse(s); path = u.path or s
    except Exception:
        path = s

    base = os.path.basename(path).split("?")[0].split("#")[0]
    return base.lower()

def _collect_image_keys(soup: BeautifulSoup) -> set:
    keys = set()
    for im in soup.find_all("img"):
        keys.add(_norm_src(im.get("src", "")))
        if im.get("srcset"):
            keys.add(_norm_src(im.get("srcset")))
    for src in soup.find_all("source"):
        if src.get("srcset"):
            keys.add(_norm_src(src.get("srcset")))
    for node in soup.select("[style]"):
        for url in re.findall(r"url\\((.*?)\\)", node.get("style") or "", flags=re.I):
            keys.add(_norm_src(url.strip('"\'')))
    keys.discard("")
    return keys



def normalize_incoming_content(raw: str) -> str:
    raw = raw or ""
    looks_html = "<" in raw and ">" in raw
    if not looks_html:
        # tu helper ya existente
        return text_to_html_preserving_lf(raw)

    soup = BeautifulSoup(raw, "lxml")
    node = soup.body or soup  # solo contenido, sin <html>/<body>

    # limpia restos de Outlook/Thunderbird
    for t in list(node.find_all(True)):
        # elimina tags con namespace de Office/Word: o:, v:, w:
        if ":" in t.name and t.name.split(":", 1)[0].lower() in {"o", "v", "w"}:
            t.decompose()
            continue

        # quita clases Mso*/moz-*
        if t.has_attr("class"):
            t["class"] = [c for c in t.get("class", []) if not c.lower().startswith(("mso", "moz-"))]
            if not t["class"]:
                t.attrs.pop("class", None)

        # borra estilos con propiedades mso-
        if t.has_attr("style") and "mso-" in t["style"].lower():
            t.attrs.pop("style", None)

        # borra atributos moz-*
        for a in list(t.attrs.keys()):
            if a.lower().startswith("moz"):
                t.attrs.pop(a, None)

    # desenvuelve wrappers típicos de Thunderbird
    for sel in ["div.moz-signature", "div.moz-quote-pre", 'blockquote[type="cite"]']:
        for e in node.select(sel):
            e.unwrap()

    # devuelve solo hijos del body (sin <body>)
    return "".join(str(c) for c in node.children)




def text_to_html_preserving_lf(txt: str) -> str:
    """
    Convierte texto plano a HTML simple:
    - Normaliza saltos de línea (CRLF/CR -> LF)
    - Escapa caracteres HTML (&, <, >, ", ')
    - Sustituye cada LF por <br>
    """
    if not txt:
        return ""
    s = txt.replace("\r\n", "\n").replace("\r", "\n")
    s = html.escape(s, quote=True)
    return s.replace("\n", "<br>")


def split_body_and_signature(html: str):
    """
    Separación muy simple:
    - Si encuentra class="moz-signature", corta el HTML ahí.
    - Devuelve (body_html, signature_html).
    - Si no encuentra nada, devuelve (html, "").
    """
    marker = 'class="moz-signature"'
    idx = html.find(marker)
    if idx == -1:
        return html, ""

    # buscamos el <div ...> que contiene esa clase
    start_div = html.rfind("<div", 0, idx)
    if start_div == -1:
        start_div = idx

    body = html[:start_div].strip()
    signature = html[start_div:].strip()
    return body, signature

SIGNATURE_MAX_BYTES = 30 * 1024  # 30 KB

def _is_signature_image(meta: dict) -> bool:
    """
    Devuelve True si la imagen es candidata a ir en la firma.
    Criterios:
      - Si tiene tamaño (< 30 KB) => se acepta.
      - Si no hay tamaño, se permite solo si meta["is_logo"] == True.
    """
    if not isinstance(meta, dict):
        return False

    size = meta.get("size") or meta.get("filesize") or meta.get("length") or 0
    try:
        size = int(size)
    except (TypeError, ValueError):
        size = 0

    if size and size < SIGNATURE_MAX_BYTES:
        return True

    # fallback: si no tenemos tamaño, acepta solo si está marcado como logo
    return bool(meta.get("is_logo"))

def clean_signature_images(signature_html: str) -> str:
    """
    Deja solo las imágenes “de firma” dentro del HTML de la firma.
    Versión simple:
      - Borra todas las <img> que NO sean .png
      (en tu caso los logos son 1.png, 2.png, y las fotos son .jpg)
    """
    if not signature_html:
        return signature_html

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(signature_html, "lxml")

    for img in soup.find_all("img"):
        src = (img.get("src") or "").lower()
        # aquí puedes ser más estricto si quieres,
        # de momento: sólo dejamos .png en la firma
        if not src.endswith(".png"):
            img.decompose()   # eliminar la imagen

    return str(soup)
