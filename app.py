import os
import re
from flask import Flask, render_template, request
from datetime import datetime
from unicodedata import normalize

app = Flask(__name__)

ALLOWED_EXTENSIONS = {'txt'}

# =========================
# CATALOGO CIE-10
# =========================
DICCIONARIO_ENFERMEDADES = {
    "A00": "Colera", "A01": "Fiebre tifoidea", "B20": "VIH",
    "E10": "Diabetes tipo 1", "E11": "Diabetes tipo 2",
    "J00": "Rinitis aguda", "U07": "COVID-19"
}

TIPOS_SANGRE_VALIDOS = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}

# =========================
# REGEX POR LEXEMA
# =========================
LEXEMAS_REGEX = {
    "ID_DNI": r"^\d{8}$",
    "ID_EDAD": r"^\d{1,3}$",
    "ID_DIAGNOSTICO": r"^[A-Z]\d{2}$",
    "ID_FECHA": r"^\d{4}-\d{2}-\d{2}$",
    "ID_HORA": r"^([01]\d|2[0-3]):[0-5]\d$",
    "ID_TIPO_SANGRE": r"^(A|B|AB|O)[+-]$",
    "ID_NOMBRE": r"^[A-Za-záéíóúÁÉÍÓÚüÜñÑ\s]+$",
    "ID_APELLIDO": r"^[A-Za-záéíóúÁÉÍÓÚüÜñÑ\s]+$",
    "ID_HOSPITAL": r"^[A-Za-záéíóúÁÉÍÓÚüÜñÑ\s\.\-]+$",
    "ID_LABORATORIO": r"^[A-Za-z0-9\s\-]+$",
    "ID_SALON": r"^(MI|CIR|PED|GO)-P\d{1,2}-\d{1,3}$",
    "ID_EXAMENES": r"^.+$",
    "ID_PERSONAL": r"^[A-Za-záéíóúÁÉÍÓÚüÜñÑ\s\.]+$"
}

# =========================
# TIPOS DE CAMPOS
# =========================
def tipo_id_campo(campo):
    campo = campo.lower()

    mapa = {
        "dni": "ID_DNI",
        "edad": "ID_EDAD",
        "nombre": "ID_NOMBRE",
        "apellido": "ID_APELLIDO",
        "diagnostico": "ID_DIAGNOSTICO",
        "fecha": "ID_FECHA",
        "hora": "ID_HORA",
        "hospital_clinica": "ID_HOSPITAL",
        "laboratorio": "ID_LABORATORIO",
        "salon": "ID_SALON",
        "examenes": "ID_EXAMENES",
        "enfermera_medico": "ID_PERSONAL",
        "tipo_sangre": "ID_TIPO_SANGRE"
    }

    return mapa.get(campo, "ID_CAMPO")

# =========================
# TOKENIZACION
# =========================
def tokenizar_valor(campo, valor):
    tipo_token = tipo_id_campo(campo)
    regex = LEXEMAS_REGEX.get(tipo_token, r".*")

    valido = bool(re.fullmatch(regex, valor.strip()))

    tokens = []

    # token campo
    tokens.append({
        "tipo": tipo_token,
        "valor": campo,
        "regex": regex,
        "estado": "OK"
    })

    # token valor
    tokens.append({
        "tipo": "VALOR_" + tipo_token,
        "valor": valor.strip(),
        "regex": regex,
        "estado": "OK" if valido else "ERROR"
    })

    return tokens

# =========================
# PARSER TXT
# =========================
def parsear_archivo_txt(contenido):
    datos = {}
    for linea in contenido.splitlines():
        if ":" not in linea:
            continue
        k, v = linea.split(":", 1)
        datos[k.strip().lower()] = v.strip()
    return datos

# =========================
# RUTA
# =========================
@app.route("/", methods=["GET", "POST"])
def home():
    tokens_por_campo = None
    resultado = None
    mensaje_error_general = None
    catalogo = {
        "diagnosticos": DICCIONARIO_ENFERMEDADES,
        "sangre": list(TIPOS_SANGRE_VALIDOS),
        "salas": [
            "MI-P1-101", "CIR-P2-210",
            "PED-P3-305", "GO-P1-103"
        ]
    }

    if request.method == "POST":
        archivo = request.files.get("archivo")

        if not archivo:
            mensaje_error_general = "Archivo no enviado"
        else:
            contenido = archivo.read().decode("utf-8")
            datos = parsear_archivo_txt(contenido)

            tokens_por_campo = {}
            for k, v in datos.items():
                tokens_por_campo[k] = tokenizar_valor(k, v)

            resultado = {
                "exito": True,
                "datos": datos
            }

    return render_template(
        "index.html",
        tokens_por_campo=tokens_por_campo,
        resultado=resultado,
        mensaje_error_general=mensaje_error_general,
        catalogo=catalogo
    )

if __name__ == "__main__":
    app.run(debug=True)
