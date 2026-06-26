import os
import re
from flask import Flask, render_template, request
from datetime import datetime
from unicodedata import normalize, combining

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
SALAS_VALIDAS = {
    "MI-P1-101",
    "CIR-P2-210",
    "PED-P3-305",
    "GO-P1-103",
    "MI-P2-103"
}


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
def normalizar_campo(campo):
    campo = campo.lower().strip()
    campo = normalize('NFKD', campo)
    campo = ''.join(ch for ch in campo if not combining(ch))
    campo = campo.replace(' ', '_').replace('/', '_').replace('-', '_')
    return campo


def tipo_id_campo(campo):
    campo = normalizar_campo(campo)

    mapa = {
        "dni": "id_dni",
        "edad": "id_edad",
        "nombre": "id_nombre",
        "apellido": "id_apellido",
        "diagnostico": "id_diagnostico",
        "fecha": "id_fecha",
        "hora": "id_hora",
        "hospital_clinica": "id_hospital",
        "hospital_clinica": "id_hospital",
        "laboratorio": "id_laboratorio",
        "salon": "id_salon",
        "examenes": "id_examenes",
        "enfermera_medico": "id_personal",
        "tipo_sangre": "id_tipo_sangre",
        "tipo_de_sangre": "id_tipo_sangre"
    }

    return mapa.get(campo, "id_campo")


# =========================
# TOKENIZADOR (MEJORADO)
# =========================
def validar_semantica(tipo_token, valor):
    valor = valor.strip()

    if tipo_token == "id_edad":
        if not valor.isdigit():
            return False, "Edad debe ser un número entero"
        edad = int(valor)
        if 0 <= edad <= 120:
            return True, None
        return False, "Edad debe estar entre 0 y 120"

    if tipo_token == "id_diagnostico":
        if valor in DICCIONARIO_ENFERMEDADES:
            return True, None
        return False, f"Diagnóstico '{valor}' no pertenece a la lista de CIE-10 conocida"

    if tipo_token == "id_tipo_sangre":
        if valor in TIPOS_SANGRE_VALIDOS:
            return True, None
        return False, f"Tipo de sangre '{valor}' no es válido"

    if tipo_token == "id_fecha":
        try:
            datetime.strptime(valor, "%Y-%m-%d")
            return True, None
        except ValueError:
            return False, "Fecha debe tener formato YYYY-MM-DD"

    if tipo_token == "id_hora":
        try:
            datetime.strptime(valor, "%H:%M")
            return True, None
        except ValueError:
            return False, "Hora debe tener formato HH:MM"

    if tipo_token == "id_salon":
        if valor in SALAS_VALIDAS:
            return True, None
        return False, f"Sala '{valor}' no es válida"

    return True, None


def tokenizar_valor(campo, valor):
    tipo_token = tipo_id_campo(campo)
    regex = LEXEMAS_REGEX.get(tipo_token, "")
    valor_str = valor.strip()
    # Campos desconocidos deben marcarse como error
    if tipo_token == "id_campo":
        lex_valido = False
        sem_valido = False
        sem_error = "Campo desconocido"
        valido = False
    # Valores vacíos deben considerarse inválidos para campos esperados
    elif valor_str == "":
        lex_valido = False
        sem_valido = False
        sem_error = "Valor vacío"
        valido = False
    else:
        lex_valido = bool(re.fullmatch(regex, valor_str)) if regex else True
        sem_valido, sem_error = validar_semantica(tipo_token, valor_str)
        valido = lex_valido and sem_valido
    graph_label = f"{tipo_token}\n{valor_str}"

    afn_dot = generar_dot_afn_token(graph_label, valido)
    afd_dot = generar_dot_afd_token(graph_label, valido)
    sintactico_dot = generar_dot_sintactico_token(tipo_token, valor_str)

    token_data = {
        "tipo": tipo_token,
        "campo": campo,
        "valor": valor_str,
        "regex": regex,
        "estado": "OK" if valido else "ERROR",
        "estados": ["q0", "qf"] if valido else ["q0", "q_error"],
        "afn_dot": afn_dot,
        "afd_dot": afd_dot,
        "sintactico_dot": sintactico_dot,
        "semantico_error": sem_error,
        "lexico_valido": lex_valido,
        "semantico_valido": sem_valido
    }

    if not lex_valido and regex:
        token_data["error_mensaje"] = f"No cumple regex: {regex}"
    elif not sem_valido:
        token_data["error_mensaje"] = sem_error

    return token_data


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


def generar_dot_afn_token(label, valido=True):
    label = label.replace('"', '\\"')
    if valido:
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

    return "\n".join([
        "digraph G {",
        "  rankdir=LR;",
        "  node [shape=circle, style=filled, fillcolor=\"#f8f9fa\", fontname=\"Arial\"];",
        "  q0 [label=\"q0\"];",
        "  q_error [label=\"q_error\", shape=doublecircle, style=filled, fillcolor=\"#fdecea\", color=\"#c0392b\"];",
        "  qf [label=\"qf\", shape=doublecircle, fillcolor=\"#dfe6ff\"];",
        "  edge [fontname=\"Courier\"];",
        f"  q0 -> q_error [label=\"{label}\"];",
        "}"
    ])


def generar_dot_afd_token(label, valido=True):
    label = label.replace('"', '\\"')
    if valido:
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

    return "\n".join([
        "digraph G {",
        "  rankdir=LR;",
        "  node [shape=circle, style=filled, fillcolor=\"#f8f9fa\", fontname=\"Arial\"];",
        "  q0 [label=\"q0\"];",
        "  q_error [label=\"q_error\", shape=doublecircle, style=filled, fillcolor=\"#fdecea\", color=\"#c0392b\"];",
        "  edge [fontname=\"Courier\"];",
        f"  q0 -> q_error [label=\"{label}\"];",
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


def generar_dot_sintactico_general(tokens_por_campo):
    lineas = [
        "digraph G {",
        "  rankdir=TB;",
        "  node [shape=box, style=filled, fillcolor=\"#ffffff\", fontname=\"Arial\"];",
        "  root [label=\"SINTAXIS GENERAL\"];"
    ]
    idx = 1
    for campo, token in tokens_por_campo.items():
        # Excluir campos desconocidos del árbol sintáctico general
        if token.get("tipo") == "id_campo":
            continue
        token_label = token["tipo"].replace('_', ' ').upper()
        valor = token["valor"].replace('"', '\\"')
        lineas.append(f"  n{idx} [label=\"{token_label}: {valor}\"];" )
        lineas.append(f"  root -> n{idx};")
        idx += 1
    lineas.append("}")
    return "\n".join(lineas)


def generar_dot_semantico_general(tokens_por_campo):
    lineas = [
        "digraph G {",
        "  rankdir=TB;",
        "  node [shape=box, style=filled, fillcolor=\"#ffffff\", fontname=\"Arial\"];",
        "  root [label=\"SEMANTICA GENERAL\"];"
    ]
    idx = 1
    for campo, token in tokens_por_campo.items():
        # Excluir campos desconocidos del árbol semántico general
        if token.get("tipo") == "id_campo":
            continue
        estado = token.get("estado", "OK")
        token_label = token["tipo"].replace('_', ' ').upper()
        lineas.append(f"  n{idx} [label=\"{token_label}: {estado}\"];" )
        lineas.append(f"  root -> n{idx};")
        idx += 1
    lineas.append("}")
    return "\n".join(lineas)


def generar_dot_afd_nfa(tokens_por_campo):
    lineas = [
        "digraph G {",
        "  rankdir=LR;",
        "  node [shape=circle, style=filled, fillcolor=\"#f8f9fa\", fontname=\"Arial\"];",
        "  q0 [label=\"q0\"];",
        "  qf [label=\"qf\", shape=doublecircle, fillcolor=\"#dfe6ff\"];",
        "  edge [fontname=\"Courier\"];"
    ]

    for index, (campo, token) in enumerate(tokens_por_campo.items(), start=1):
        token_label = token["tipo"]
        valor = token["valor"].replace('"', '\\"')
        label = f"{token_label}\\n{valor}"
        lineas.append(f"  q0 -> q{index} [label=\"{label}\"];" )
        lineas.append(f"  q{index} -> qf [label=\"ε\"];" )

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
    for index, (campo, token) in enumerate(tokens_por_campo.items(), start=1):
        token_label = token["tipo"]
        valor = token["valor"].replace('"', '\\"')
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
    tokens_usados = None
    arbol_sintactico_general = None
    arbol_semantico_general = None

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
                tokens_usados = []

                validacion_lines = []
                valido_completo = True
                validacion_campos = []

                for campo, valor in datos.items():
                    token_data = tokenizar_valor(campo, valor)
                    tokens_por_campo[campo] = token_data
                    tokens_usados.append(token_data)

                    if token_data.get("estado") == "ERROR":
                        valido_completo = False
                        # Mensaje específico para campos desconocidos
                        if token_data.get("tipo") == "id_campo":
                            validacion_lines.append(f"Campo no esperado: '{campo}'")
                        elif token_data.get("error_mensaje"):
                            validacion_lines.append(
                                f"Campo '{campo}' con valor '{valor}': {token_data.get('error_mensaje')}"
                            )
                        else:
                            validacion_lines.append(
                                f"Campo '{campo}' con valor '{valor}' no es válido"
                            )

                    validacion_campos.append({
                        "campo": campo,
                        "valor": valor,
                        "valido": token_data.get("estado") == "OK",
                        "estado": token_data.get("estado"),
                        "label": campo.replace('_', ' ').title(),
                        "desconocido": token_data.get("tipo") == "id_campo",
                        "error_mensaje": token_data.get("error_mensaje")
                    })

                if valido_completo and datos:
                    validacion_resumen = {
                        "valido": True,
                        "mensaje": "El archivo .txt es válido y todos los campos se reconocen correctamente.",
                        "detalles": [],
                        "campos": validacion_campos
                    }
                else:
                    validacion_resumen = {
                        "valido": False,
                        "mensaje": "El archivo .txt contiene uno o varios valores inválidos.",
                        "detalles": validacion_lines or ["No se encontraron datos válidos."],
                        "campos": validacion_campos
                    }

                arbol_sintactico_general = generar_dot_sintactico_general(tokens_por_campo)
                arbol_semantico_general = generar_dot_semantico_general(tokens_por_campo)
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
        tokens_usados=tokens_usados,
        validacion_resumen=validacion_resumen if 'validacion_resumen' in locals() else None,
        arbol_sintactico_general=arbol_sintactico_general,
        arbol_semantico_general=arbol_semantico_general,
        mostrar_tabla_general=mostrar_tabla_general,
        catalogo=catalogo,
        tokens_generales=TOKENS_GENERALES
    )

if __name__ == "__main__":
    app.run(debug=True)
