import os
import re
from flask import Flask, render_template, request
from datetime import datetime
from unicodedata import normalize

app = Flask(__name__)

UPLOAD_FOLDER = '/tmp'
ALLOWED_EXTENSIONS = {'txt'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# =========================
# CIE-10
# =========================
DICCIONARIO_ENFERMEDADES = {
    "A00": "Colera", "A01": "Fiebre tifoidea", "A02": "Salmonelosis",
    "B20": "VIH", "J00": "Rinitis aguda", "J01": "Sinusitis",
    "E10": "Diabetes tipo 1", "E11": "Diabetes tipo 2",
    "I10": "Hipertension", "U07": "COVID-19"
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
# MAPEO DE CAMPOS
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
# TOKENIZADOR (MEJORADO)
# =========================
def tokenizar_valor(campo, valor):
    tokens = []

    tipo_token = tipo_id_campo(campo)
    regex = LEXEMAS_REGEX.get(tipo_token, "")

    valido = bool(re.fullmatch(regex, valor.strip())) if regex else True

    tokens.append({
        "tipo": tipo_token,
        "valor": campo,
        "regex": regex,
        "estados": ["q0", "qf"]
    })

    tokens.append({
        "tipo": "VALOR_" + tipo_token,
        "valor": valor.strip(),
        "regex": regex,
        "estado": "OK" if valido else "ERROR",
        "estados": ["q0", "qf"] if valido else ["q0", "q_error"]
    })

    return tokens


# =========================
# PARSER TXT
# =========================
def parsear_archivo_txt(contenido):
    datos = {}
    patron = re.compile(r'^\s*([^:]+?)\s*:\s*(.*)$')

    for linea in contenido.splitlines():
        if not linea.strip():
            continue

        m = patron.match(linea)
        if not m:
            raise ValueError(f"Linea invalida: {linea}")

        campo = m.group(1).strip().lower()
        valor = m.group(2).strip()
        datos[campo] = valor

    return datos


# =========================
# RUTA PRINCIPAL
# =========================
@app.route("/", methods=["GET", "POST"])
def home():

    resultado = None
    mensaje_error_general = None
    tokens_por_campo = None
    arbol_dot = None

    catalogo = {
        "diagnosticos": DICCIONARIO_ENFERMEDADES,
        "sangre": TIPOS_SANGRE_VALIDOS,
        "salas": [
            "MI-P1-101",
            "CIR-P2-210",
            "PED-P3-305",
            "GO-P1-103"
        ]
    }

    if request.method == "POST":
        archivo = request.files.get("archivo")

        if archivo:
            try:
                contenido = archivo.read().decode("utf-8")
                datos = parsear_archivo_txt(contenido)

                tokens_por_campo = {}

                for campo, valor in datos.items():
                    tokens_por_campo[campo] = tokenizar_valor(campo, valor)

                # árbol simple (NO tocamos tu AFD/AFN original)
                arbol_dot = "digraph { PACIENTE -> DATOS }"

                resultado = {"exito": True, "datos": datos}

            except Exception as e:
                mensaje_error_general = str(e)

    return render_template(
        "index.html",
        resultado=resultado,
        mensaje_error_general=mensaje_error_general,
        tokens_por_campo=tokens_por_campo,
        arbol_dot=arbol_dot,
        catalogo=catalogo
    )


if __name__ == "__main__":
    app.run(debug=True)
