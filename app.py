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
    "id_dni": r"^\d{8}$",
    "id_edad": r"^\d{1,3}$",
    "id_diagnostico": r"^[A-Z]\d{2}$",
    "id_fecha": r"^\d{4}-\d{2}-\d{2}$",
    "id_hora": r"^([01]\d|2[0-3]):[0-5]\d$",
    "id_tipo_sangre": r"^(A|B|AB|O)[+-]$",
    "id_nombre": r"^[A-Za-záéíóúÁÉÍÓÚüÜñÑ\s]+$",
    "id_apellido": r"^[A-Za-záéíóúÁÉÍÓÚüÜñÑ\s]+$",
    "id_hospital": r"^[A-Za-záéíóúÁÉÍÓÚüÜñÑ\s\.\-]+$",
    "id_laboratorio": r"^[A-Za-z0-9\s\-]+$",
    "id_salon": r"^(MI|CIR|PED|GO)-P\d{1,2}-\d{1,3}$",
    "id_examenes": r"^.+$",
    "id_personal": r"^[A-Za-záéíóúÁÉÍÓÚüÜñÑ\s\.]+$"
}


# =========================
# TABLA DE TOKENS GENERAL
# =========================
TOKENS_GENERALES = [
    {"token": "id_nombre",      "descripcion": "Nombre del paciente",          "ejemplo": "Juan",          "regex": r"^[A-Za-záéíóúÁÉÍÓÚüÜñÑ\s]+$"},
    {"token": "id_apellido",    "descripcion": "Apellido del paciente",         "ejemplo": "Perez",         "regex": r"^[A-Za-záéíóúÁÉÍÓÚüÜñÑ\s]+$"},
    {"token": "id_dni",         "descripcion": "Documento de identidad (8 dígitos)", "ejemplo": "12345678", "regex": r"^\d{8}$"},
    {"token": "id_edad",        "descripcion": "Edad del paciente (1-3 dígitos)", "ejemplo": "30",          "regex": r"^\d{1,3}$"},
    {"token": "id_diagnostico", "descripcion": "Código CIE-10",                 "ejemplo": "J00",           "regex": r"^[A-Z]\d{2}$"},
    {"token": "id_fecha",       "descripcion": "Fecha en formato YYYY-MM-DD",   "ejemplo": "2025-06-10",    "regex": r"^\d{4}-\d{2}-\d{2}$"},
    {"token": "id_hora",        "descripcion": "Hora en formato HH:MM",         "ejemplo": "09:15",         "regex": r"^([01]\d|2[0-3]):[0-5]\d$"},
    {"token": "id_hospital",    "descripcion": "Nombre de hospital o clínica",  "ejemplo": "Clinica Central","regex": r"^[A-Za-záéíóúÁÉÍÓÚüÜñÑ\s\.\-]+$"},
    {"token": "id_laboratorio", "descripcion": "Nombre del laboratorio",        "ejemplo": "Lab Uno",       "regex": r"^[A-Za-z0-9\s\-]+$"},
    {"token": "id_salon",       "descripcion": "Código de sala (AREA-PX-NUM)",  "ejemplo": "MI-P2-103",     "regex": r"^(MI|CIR|PED|GO)-P\d{1,2}-\d{1,3}$"},
    {"token": "id_examenes",    "descripcion": "Nombre del examen médico",      "ejemplo": "Hemograma",     "regex": r"^.+$"},
    {"token": "id_personal",    "descripcion": "Nombre del médico o enfermera", "ejemplo": "Dra Lopez",     "regex": r"^[A-Za-záéíóúÁÉÍÓÚüÜñÑ\s\.]+$"},
    {"token": "id_tipo_sangre", "descripcion": "Tipo de sangre ABO/Rh",        "ejemplo": "A+",            "regex": r"^(A|B|AB|O)[+-]$"},
]


# =========================
# MAPEO DE CAMPOS
# =========================
def tipo_id_campo(campo):
    campo = campo.lower().strip()
    campo = campo.replace(' ', '_').replace('/', '_').replace('-', '_')

    mapa = {
        "dni": "id_dni",
        "edad": "id_edad",
        "nombre": "id_nombre",
        "apellido": "id_apellido",
        "diagnostico": "id_diagnostico",
        "fecha": "id_fecha",
        "hora": "id_hora",
        "hospital_clinica": "id_hospital",
        "hospital_clínica": "id_hospital",
        "laboratorio": "id_laboratorio",
        "salon": "id_salon",
        "examenes": "id_examenes",
        "enfermera_medico": "id_personal",
        "tipo_sangre": "id_tipo_sangre"
    }

    return mapa.get(campo, "id_campo")


# =========================
# TOKENIZADOR (MEJORADO)
# =========================
def tokenizar_valor(campo, valor):
    tokens = []

    tipo_token = tipo_id_campo(campo)
    regex = LEXEMAS_REGEX.get(tipo_token, "")
    valido = bool(re.fullmatch(regex, valor.strip())) if regex else True
    label = regex.strip('^$') if regex else valor.strip()
    label = label if label else valor.strip()
    graph_label = f"{tipo_token}\n{label}"

    afn_dot = generar_dot_afn_token(graph_label)
    afd_dot = generar_dot_afd_token(graph_label)
    sintactico_dot = generar_dot_sintactico_token(tipo_token, valor.strip())

    tokens.append({
        "tipo": tipo_token,
        "valor": campo,
        "regex": regex,
        "estados": ["q0", "qf"],
        "afn_dot": afn_dot,
        "afd_dot": afd_dot,
        "sintactico_dot": sintactico_dot
    })

    tokens.append({
        "tipo": "valor_" + tipo_token,
        "valor": valor.strip(),
        "regex": regex,
        "estado": "OK" if valido else "ERROR",
        "estados": ["q0", "qf"] if valido else ["q0", "q_error"],
        "afn_dot": afn_dot,
        "afd_dot": afd_dot,
        "sintactico_dot": sintactico_dot
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


def generar_dot_afn_token(label):
    label = label.replace('"', '\\"')
    return "\n".join([
        "digraph G {",
        "  rankdir=LR;",
        "  node [shape=circle, style=filled, fillcolor=\"#f8f9fa\", fontname=\"Arial\"];",
        "  q0 [label=\"q0\"];",
        "  q1 [label=\"q1\"];",
        "  qf [label=\"qf\", shape=doublecircle, fillcolor=\"#dfe6ff\"];",
        "  edge [fontname=\"Courier\"];",
        f"  q0 -> q1 [label=\"{label}\"];",
        "  q0 -> qf [label=\"ε\"];",
        "  q1 -> qf [label=\"ε\"];",
        "}"
    ])


def generar_dot_afd_token(label):
    label = label.replace('"', '\\"')
    return "\n".join([
        "digraph G {",
        "  rankdir=LR;",
        "  node [shape=circle, style=filled, fillcolor=\"#f8f9fa\", fontname=\"Arial\"];",
        "  q0 [label=\"q0\"];",
        "  q1 [label=\"q1\"];",
        "  qf [label=\"qf\", shape=doublecircle, fillcolor=\"#dfe6ff\"];",
        "  edge [fontname=\"Courier\"];",
        f"  q0 -> q1 [label=\"{label}\"];",
        "  q1 -> qf [label=\"ε\"];",
        "}"
    ])


def generar_dot_sintactico_token(tipo_token, valor):
    tipo_label = tipo_token.replace('_', ' ').upper()
    valor_label = valor.replace('"', '\\"')
    return "\n".join([
        "digraph G {",
        "  rankdir=TB;",
        "  node [shape=box, style=filled, fillcolor=\"#ffffff\", fontname=\"Arial\"];",
        "  root [label=\"SENTENCIA\"];",
        f"  token [label=\"{tipo_label}\"];",
        f"  valor [label=\"{valor_label}\"];",
        "  root -> token;",
        "  root -> valor;",
        "}"
    ])


def generar_dot_afd_nfa(tokens_por_campo):
    lineas = [
        "digraph G {",
        "  rankdir=LR;",
        "  node [shape=circle, style=filled, fillcolor=\"#f8f9fa\", fontname=\"Arial\"];",
        "  q0 [label=\"q0\"];",
        "  qf [label=\"qf\", shape=doublecircle, fillcolor=\"#dfe6ff\"];",
        "  edge [fontname=\"Courier\"];"
    ]

    for index, (campo, tokens) in enumerate(tokens_por_campo.items(), start=1):
        token_label = tokens[0]["tipo"]
        valor = tokens[1]["valor"].replace('"', '\\"')
        label = f"{token_label}\\n{valor}"
        lineas.append(f"  q0 -> q{index} [label=\"{label}\"];")
        lineas.append(f"  q{index} -> qf [label=\"ε\"];")

    lineas.append("}")
    return "\n".join(lineas)


def generar_dot_afd(tokens_por_campo):
    lineas = [
        "digraph G {",
        "  rankdir=LR;",
        "  node [shape=circle, style=filled, fillcolor=\"#f8f9fa\", fontname=\"Arial\"];",
        "  q0 [label=\"q0\"];",
        "  qf [label=\"qf\", shape=doublecircle, fillcolor=\"#dfe6ff\"];",
        "  edge [fontname=\"Courier\"];"
    ]

    acumulado = []
    for index, (campo, tokens) in enumerate(tokens_por_campo.items(), start=1):
        token_label = tokens[0]["tipo"]
        valor = tokens[1]["valor"].replace('"', '\\"')
        label = f"{token_label}\\n{valor}"
        lineas.append(f"  q{index-1} -> q{index} [label=\"{label}\"];")
        acumulado.append(label)

    lineas.append("}")
    return "\n".join(lineas)


# =========================
# RUTA PRINCIPAL
# =========================
@app.route("/", methods=["GET", "POST"])
def home():

    resultado = None
    mensaje_error_general = None
    tokens_por_campo = None
    arbol_dot = None
    afd_dot = None

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

        try:
            if archivo and archivo.filename:
                contenido = archivo.read().decode("utf-8")
                datos = parsear_archivo_txt(contenido)
                tokens_por_campo = {}

                for campo, valor in datos.items():
                    tokens_por_campo[campo] = tokenizar_valor(campo, valor)

                resultado = {"exito": True, "datos": datos, "modo": "archivo"}
            else:
                mensaje_error_general = "Debes cargar un archivo .txt para procesar los datos."

        except Exception as e:
            mensaje_error_general = str(e)

    mostrar_tabla_general = tokens_por_campo is None

    return render_template(
        "index.html",
        resultado=resultado,
        mensaje_error_general=mensaje_error_general,
        tokens_por_campo=tokens_por_campo,
        arbol_dot=arbol_dot,
        afd_dot=afd_dot,
        mostrar_tabla_general=mostrar_tabla_general,
        catalogo=catalogo,
        tokens_generales=TOKENS_GENERALES
    )


if __name__ == "__main__":
    app.run(debug=True)
