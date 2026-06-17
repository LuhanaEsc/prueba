import os
import re
from flask import Flask, render_template, request
from datetime import datetime
from unicodedata import normalize

app = Flask(__name__)
UPLOAD_FOLDER = '/tmp'
ALLOWED_EXTENSIONS = {'txt'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Diccionario CIE-10
DICCIONARIO_ENFERMEDADES = {
    "A00": "Cólera", "A01": "Fiebre tifoidea", "A02": "Otras salmonelosis",
    "B20": "Enfermedad por VIH", "J00": "Rinitis aguda", "J01": "Sinusitis aguda",
    "E10": "Diabetes tipo 1", "E11": "Diabetes tipo 2",
    "I10": "Hipertensión esencial", "I11": "Cardiopatía hipertensiva",
    "U07": "COVID-19", "Z00": "Examen general"
}

TIPOS_SANGRE_VALIDOS = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}

# ---------- GENERACIÓN DE DOT PARA AFDs (DETERMINISTAS Y NO DETERMINISTAS) ----------
def generar_dot_afd(tipo_token, version="DFA"):
    """Devuelve el código DOT para DFA o NFA según el tipo de token."""
    # Definimos DFA y NFA para cada token
    afds = {
        "CODIGO_MEDICO": {
            "DFA": """digraph AFD_CODIGO {
    rankdir=LR;
    node [shape=circle, fontname="Arial"];
    q0 [label="q0"];
    q1 [label="q1"];
    q2 [label="q2"];
    q3 [label="q3", shape=doublecircle, fillcolor=lightgreen, style=filled];
    error [label="q_error", fillcolor=red, style=filled, fontcolor=white];
    q0 -> q1 [label="[A-Z]"];
    q0 -> error [label="otro"];
    q1 -> q2 [label="[0-9]"];
    q1 -> error [label="otro"];
    q2 -> q3 [label="[0-9]"];
    q2 -> error [label="otro"];
    q3 -> error [label="cualquier símbolo"];
}""",
            "NFA": """digraph AFN_CODIGO {
    rankdir=LR;
    node [shape=circle, fontname="Arial"];
    q0 [label="q0"];
    q1 [label="q1"];
    q2 [label="q2"];
    q3 [label="q3", shape=doublecircle, fillcolor=lightgreen, style=filled];
    q0 -> q1 [label="[A-Z]"];
    q1 -> q2 [label="[0-9]"];
    q1 -> q2 [label="ε"];  // transición ε (no determinista)
    q2 -> q3 [label="[0-9]"];
    q2 -> q3 [label="ε"];
}"""
        },
        "FECHA": {
            "DFA": """digraph AFD_FECHA {
    rankdir=LR;
    node [shape=circle, fontname="Arial"];
    q0; q1; q2; q3; q4; q5; q6; q7; q8;
    q9 [shape=doublecircle, fillcolor=lightgreen, style=filled];
    q0->q1[label="[0-9]"]; q1->q2[label="[0-9]"]; q2->q3[label="[0-9]"]; q3->q4[label="[0-9]"];
    q4->q5[label="'-'"];   q5->q6[label="[0-9]"]; q6->q7[label="[0-9]"]; q7->q8[label="'-'"];
    q8->q9[label="[0-9]"];
}""",
            "NFA": """digraph AFN_FECHA {
    rankdir=LR;
    node [shape=circle, fontname="Arial"];
    q0; q1; q2; q3; q4; q5; q6; q7; q8;
    q9 [shape=doublecircle, fillcolor=lightgreen, style=filled];
    q0->q1[label="[0-9]"]; q1->q2[label="[0-9]"]; q2->q3[label="[0-9]"]; q3->q4[label="[0-9]"];
    q4->q5[label="'-'"];   q5->q6[label="[0-9]"]; q6->q7[label="[0-9]"]; q7->q8[label="'-'"];
    q8->q9[label="[0-9]"];
    q0->q2[label="ε"]; q4->q6[label="ε"];  // transiciones ε
}"""
        },
        "HORA": {
            "DFA": """digraph AFD_HORA {
    rankdir=LR;
    node [shape=circle, fontname="Arial"];
    q0; q1a; q1b; q2; q3; q4;
    q5 [shape=doublecircle, fillcolor=lightgreen, style=filled];
    q0->q1a[label="[0-1]"]; q0->q1b[label="'2'"];
    q1a->q2[label="[0-9]"]; q1b->q2[label="[0-3]"];
    q2->q3[label="':'"];    q3->q4[label="[0-5]"];
    q4->q5[label="[0-9]"];
}""",
            "NFA": """digraph AFN_HORA {
    rankdir=LR;
    node [shape=circle, fontname="Arial"];
    q0; q1a; q1b; q2; q3; q4;
    q5 [shape=doublecircle, fillcolor=lightgreen, style=filled];
    q0->q1a[label="[0-1]"]; q0->q1b[label="'2'"];
    q1a->q2[label="[0-9]"]; q1b->q2[label="[0-3]"];
    q2->q3[label="':'"];    q3->q4[label="[0-5]"];
    q4->q5[label="[0-9]"];
    q1a->q2[label="ε"]; q1b->q2[label="ε"];
}"""
        },
        "NUMERO": {
            "DFA": """digraph AFD_NUMERO {
    rankdir=LR;
    node [shape=circle, fontname="Arial"];
    q0;
    q1 [shape=doublecircle, fillcolor=lightgreen, style=filled];
    q0->q1[label="[0-9]"];
    q1->q1[label="[0-9]"];
}""",
            "NFA": """digraph AFN_NUMERO {
    rankdir=LR;
    node [shape=circle, fontname="Arial"];
    q0; q1; q2;
    q2 [shape=doublecircle, fillcolor=lightgreen, style=filled];
    q0->q1[label="[0-9]"];
    q0->q2[label="ε"];
    q1->q1[label="[0-9]"];
    q1->q2[label="ε"];
}"""
        },
        "TIPO_SANGRE": {
            "DFA": """digraph AFD_TIPO_SANGRE {
    rankdir=LR;
    node [shape=circle, fontname="Arial"];
    q0; q1; q2 [shape=doublecircle, fillcolor=lightgreen, style=filled];
    q0->q1[label="'A'|'B'|'O'|'AB'"];
    q1->q2[label="'+'|'-'"];
}""",
            "NFA": """digraph AFN_TIPO_SANGRE {
    rankdir=LR;
    node [shape=circle, fontname="Arial"];
    q0; q1; q2;
    q2 [shape=doublecircle, fillcolor=lightgreen, style=filled];
    q0->q1[label="'A'|'B'|'O'|'AB'"];
    q1->q2[label="'+'|'-'"];
    q0->q1[label="ε"];
    q1->q2[label="ε"];
}"""
        },
        "CADENA": {
            "DFA": """digraph AFD_CADENA {
    rankdir=LR;
    node [shape=circle, fontname="Arial"];
    q0 [shape=doublecircle, fillcolor=lightgreen, style=filled];
    q0->q0[label="[A-Za-zÁÉÍÓÚÑáéíóúñ\\\\s\\\\.,\\\\-]"];
}""",
            "NFA": """digraph AFN_CADENA {
    rankdir=LR;
    node [shape=circle, fontname="Arial"];
    q0 [shape=doublecircle, fillcolor=lightgreen, style=filled];
    q0->q0[label="[A-Za-zÁÉÍÓÚÑáéíóúñ\\\\s\\\\.,\\\\-]"];
    q0->q0[label="ε"];
}"""
        },
        "ID_CAMPO": {
            "DFA": """digraph AFD_ID_CAMPO {
    rankdir=LR;
    node [shape=circle, fontname="Arial"];
    q0 [shape=doublecircle, fillcolor=lightgreen, style=filled];
    q0->q0[label="[A-Za-zÁÉÍÓÚÑáéíóúñ/]"];
}""",
            "NFA": """digraph AFN_ID_CAMPO {
    rankdir=LR;
    node [shape=circle, fontname="Arial"];
    q0 [shape=doublecircle, fillcolor=lightgreen, style=filled];
    q0->q0[label="[A-Za-zÁÉÍÓÚÑáéíóúñ/]"];
    q0->q0[label="ε"];
}"""
        }
    }
    if tipo_token not in afds:
        return ""
    return afds[tipo_token].get(version, "")

# ---------- SIMULACIÓN DE AFD PARA OBTENER ESTADOS ----------
def simular_afd(tipo_token, cadena):
    """Devuelve una secuencia de estados ilustrativa."""
    if tipo_token in ["CODIGO_MEDICO", "FECHA", "HORA", "NUMERO", "TIPO_SANGRE", "CADENA", "ID_CAMPO"]:
        estados = ["q0"]
        for i in range(len(cadena)):
            estados.append(f"q{i+1}")
        estados.append("qf (aceptación)")
        return estados
    else:
        return ["q0", "q_error (rechazo)"]

# ---------- TOKENIZACIÓN CON DOT ----------
def tokenizar_valor(campo, valor):
    tokens = []
    # Token ID_CAMPO
    tokens.append({
        "tipo": "ID_CAMPO",
        "valor": campo,
        "estados": ["q0", "qf (aceptación)"],
        "dot_dfa": generar_dot_afd("ID_CAMPO", "DFA"),
        "dot_nfa": generar_dot_afd("ID_CAMPO", "NFA")
    })
    # Token DOS_PUNTOS (sin AFD)
    tokens.append({
        "tipo": "DOS_PUNTOS",
        "valor": ":",
        "estados": [],
        "dot_dfa": "",
        "dot_nfa": ""
    })
    # Token del valor
    tipo_token = "CADENA"
    if campo.lower() in ["diagnostico", "diagnóstico", "código", "codigo"]:
        tipo_token = "CODIGO_MEDICO"
    elif campo.lower() in ["fecha", "date"]:
        tipo_token = "FECHA"
    elif campo.lower() in ["hora", "time"]:
        tipo_token = "HORA"
    elif campo.lower() in ["dni", "cedula", "cédula", "edad", "años", "anos"]:
        tipo_token = "NUMERO"
    elif campo.lower() in ["tipo de sangre", "tipo sangre", "rh", "sangre", "tipo_sangre"]:
        tipo_token = "TIPO_SANGRE"

    valido = False
    if tipo_token == "CODIGO_MEDICO":
        valido = bool(re.fullmatch(r'^[A-Z]\d{2}$', valor.strip().upper()))
    elif tipo_token == "FECHA":
        valido = bool(re.fullmatch(r'^\d{4}-\d{2}-\d{2}$', valor.strip()))
    elif tipo_token == "HORA":
        valido = bool(re.fullmatch(r'^([01]\d|2[0-3]):[0-5]\d$', valor.strip()))
    elif tipo_token == "NUMERO":
        valido = bool(re.fullmatch(r'^\d+$', valor.strip()))
    elif tipo_token == "TIPO_SANGRE":
        valido = bool(re.fullmatch(r'^(A|B|AB|O)[+-]$', valor.strip().upper()))
    else:
        valido = bool(re.fullmatch(r'^[A-Za-zÁÉÍÓÚÑáéíóúñ\s\.\,\-]+$', valor.strip()))

    if valido:
        estados = simular_afd(tipo_token, valor.strip())
        dot_dfa = generar_dot_afd(tipo_token, "DFA")
        dot_nfa = generar_dot_afd(tipo_token, "NFA")
    else:
        tipo_token = "ERROR_LEXICO"
        estados = ["q0", "q_error (rechazo)"]
        dot_dfa = ""
        dot_nfa = ""

    tokens.append({
        "tipo": tipo_token,
        "valor": valor.strip(),
        "estados": estados,
        "dot_dfa": dot_dfa,
        "dot_nfa": dot_nfa
    })
    return tokens

# ---------- GENERACIÓN DE DOT DEL ÁRBOL SINTÁCTICO ----------
def generar_dot_arbol(datos):
    dot = "digraph ArbolSintactico {\n"
    dot += "    node [shape=box, style=filled, fillcolor=lightblue, fontname=\"Arial\"];\n"
    dot += "    PACIENTE [label=\"PACIENTE\", fillcolor=lightgreen, style=filled];\n"
    for i, (campo, valor) in enumerate(datos.items()):
        campo_id = f"campo{i}"
        valor_id = f"valor{i}"
        # Escapar caracteres especiales para DOT
        campo_clean = campo.replace('"', '\\"').replace('\n', ' ').replace('\\', '\\\\')
        valor_clean = str(valor).replace('"', '\\"').replace('\n', ' ').replace('\\', '\\\\')
        # Determinar tipo de token para el valor
        tipo = "CADENA"
        if campo.lower() in ["diagnostico", "diagnóstico", "código", "codigo"]:
            tipo = "CODIGO_MEDICO"
        elif campo.lower() in ["fecha", "date"]:
            tipo = "FECHA"
        elif campo.lower() in ["hora", "time"]:
            tipo = "HORA"
        elif campo.lower() in ["dni", "cedula", "cédula", "edad", "años", "anos"]:
            tipo = "NUMERO"
        elif campo.lower() in ["tipo de sangre", "tipo sangre", "rh", "sangre", "tipo_sangre"]:
            tipo = "TIPO_SANGRE"
        dot += f'    {campo_id} [label="CAMPO: {campo_clean}"];\n'
        dot += f'    {valor_id} [label="{tipo}: {valor_clean}"];\n'
        dot += f"    PACIENTE -> {campo_id};\n"
        dot += f"    {campo_id} -> {valor_id};\n"
    dot += "}\n"
    return dot

# ---------- ANÁLISIS SINTÁCTICO ----------
def analizar_sintaxis(datos):
    campos_requeridos = [
        'nombre', 'apellido', 'dni', 'edad', 'diagnostico',
        'fecha', 'hora', 'hospital_clinica', 'laboratorio',
        'salon', 'examenes', 'enfermera_medico', 'tipo_sangre'
    ]
    errores = []
    for campo in campos_requeridos:
        if campo not in datos or not datos[campo] or len(datos[campo].strip()) == 0:
            errores.append(("SINTÁCTICO", f"Falta el campo '{campo}' en el archivo"))
    return errores

# ---------- ANÁLISIS SEMÁNTICO ----------
def validar_semantica(datos, token_diagnostico):
    errores = []
    nombre = datos.get('nombre', '')
    apellido = datos.get('apellido', '')
    dni = datos.get('dni', '')
    edad = datos.get('edad', '')
    fecha = datos.get('fecha', '')
    hora = datos.get('hora', '')
    hospital = datos.get('hospital_clinica', '')
    laboratorio = datos.get('laboratorio', '')
    salon = datos.get('salon', '')
    examenes = datos.get('examenes', '')
    enfermera = datos.get('enfermera_medico', '')
    tipo_sangre = datos.get('tipo_sangre', '').upper()
    if tipo_sangre == '0+':
        tipo_sangre = 'O+'

    # Validar nombre y apellido
    if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', nombre.strip()):
        errores.append(("SEMÁNTICO", "El nombre solo debe contener letras"))
    if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', apellido.strip()):
        errores.append(("SEMÁNTICO", "El apellido solo debe contener letras"))
    # Edad
    try:
        edad_num = int(edad)
        if edad_num < 0 or edad_num > 120:
            errores.append(("SEMÁNTICO", "Edad fuera de rango (0-120)"))
    except ValueError:
        errores.append(("SEMÁNTICO", "La edad debe ser un número entero"))
    # DNI
    if len(dni.strip()) != 8 or not dni.isdigit():
        errores.append(("SEMÁNTICO", "El DNI debe tener exactamente 8 dígitos numéricos"))
    # Diagnóstico
    if token_diagnostico["tipo"] == "ERROR_LEXICO":
        errores.append(("LÉXICO", f"Código inválido: {token_diagnostico['valor']}"))
    elif token_diagnostico["tipo"] == "CODIGO_MEDICO":
        if token_diagnostico["valor"] not in DICCIONARIO_ENFERMEDADES:
            errores.append(("SEMÁNTICO", f"Código {token_diagnostico['valor']} no existe en el diccionario"))
    # Fecha
    try:
        datetime.strptime(fecha, "%Y-%m-%d")
    except ValueError:
        errores.append(("SEMÁNTICO", "Fecha inválida. Use YYYY-MM-DD"))
    # Hora
    if not re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', hora):
        errores.append(("SEMÁNTICO", "Hora inválida. Use HH:MM (24h)"))
    # Hospital
    if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s\.\-]+$', hospital):
        errores.append(("SEMÁNTICO", "Hospital/Clínica solo letras, espacios, puntos y guiones"))
    # Laboratorio
    if not re.match(r'^[a-zA-Z0-9\s\-_]+$', laboratorio):
        errores.append(("SEMÁNTICO", "Laboratorio solo letras, números, espacios, guiones"))
    # Salón
    patron_salon = r'^(MI|CIR|PED|GO)-P(\d+)-(\d+)$'
    match_salon = re.match(patron_salon, salon.strip().upper())
    if not match_salon:
        errores.append(("SEMÁNTICO", "Salón inválido. Ej: MI-P2-103"))
    else:
        piso = int(match_salon.group(2))
        numero = int(match_salon.group(3))
        if piso < 1 or piso > 10:
            errores.append(("SEMÁNTICO", "Piso entre 1 y 10"))
        if numero < 1 or numero > 999:
            errores.append(("SEMÁNTICO", "Número de salón entre 1 y 999"))
    # Exámenes
    if len(examenes.strip()) == 0:
        errores.append(("SEMÁNTICO", "Exámenes no puede estar vacío"))
    # Enfermera/Médico
    if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s\.]+$', enfermera):
        errores.append(("SEMÁNTICO", "Enfermera/Médico solo letras, espacios y puntos"))
    # Tipo sangre
    if tipo_sangre not in TIPOS_SANGRE_VALIDOS:
        errores.append(("SEMÁNTICO", f"Tipo de sangre inválido. Válidos: {', '.join(TIPOS_SANGRE_VALIDOS)}"))
    return errores

# ---------- PARSEAR ARCHIVO ----------
def parsear_archivo_txt(contenido):
    mapeo = {
        'nombre': ['nombre', 'nombres'],
        'apellido': ['apellido', 'apellidos'],
        'dni': ['dni', 'cedula', 'cédula'],
        'edad': ['edad', 'años', 'anos'],
        'diagnostico': ['diagnostico', 'diagnóstico', 'código', 'codigo', 'codigo diagnostico', 'código diagnóstico'],
        'fecha': ['fecha', 'date'],
        'hora': ['hora', 'time'],
        'hospital_clinica': ['hospital/clínica', 'hospital/clinica', 'hospital', 'clinica', 'clínica', 'hospital_clinica'],
        'laboratorio': ['laboratorio', 'lab'],
        'salon': ['salón', 'salon', 'sala', 'habitación'],
        'examenes': ['exámenes', 'examenes', 'pruebas', 'estudios'],
        'enfermera_medico': ['enfermera/médico', 'enfermera/medico', 'enfermera', 'medico', 'médico', 'enfermera_medico'],
        'tipo_sangre': ['tipo de sangre', 'tipo sangre', 'rh', 'sangre', 'tipo_sangre']
    }
    sinonimos = {}
    for clave, lista in mapeo.items():
        for sin in lista:
            sinonimos[sin.lower()] = clave

    datos = {}
    lineas = contenido.splitlines()
    patron = re.compile(r'^\s*([^:]+?)\s*:\s*(.*)$')
    for linea in lineas:
        if linea.strip() == '':
            continue
        m = patron.match(linea)
        if not m:
            raise ValueError(f"Línea inválida: {linea}")
        campo_raw = m.group(1).strip().lower()
        valor = m.group(2).strip()
        clave = sinonimos.get(campo_raw)
        if not clave:
            normalizado = re.sub(r'[^\w]', '', campo_raw)
            normalizado = normalize('NFKD', normalizado).encode('ASCII', 'ignore').decode('ASCII')
            clave = sinonimos.get(normalizado)
        if clave:
            datos[clave] = valor
    required = {'nombre', 'apellido', 'dni', 'edad', 'diagnostico', 'fecha', 'hora',
                'hospital_clinica', 'laboratorio', 'salon', 'examenes', 'enfermera_medico', 'tipo_sangre'}
    faltantes = required - set(datos.keys())
    if faltantes:
        encontrados = list(datos.keys())
        raise ValueError(f"Faltan los campos: {', '.join(faltantes)}. Detectados: {encontrados}")
    return datos

# ---------- RUTA PRINCIPAL ----------
@app.route("/", methods=["GET", "POST"])
def home():
    resultado = None
    mensaje_error_general = None
    tokens_por_campo = None
    arbol_dot = None

    if request.method == "POST":
        if 'archivo' not in request.files:
            mensaje_error_general = "No se seleccionó ningún archivo"
        else:
            archivo = request.files['archivo']
            if archivo.filename == '':
                mensaje_error_general = "Nombre de archivo vacío"
            elif not allowed_file(archivo.filename):
                mensaje_error_general = "Formato no permitido. Use archivos .txt"
            else:
                try:
                    contenido = archivo.read().decode('utf-8')
                    datos = parsear_archivo_txt(contenido)

                    # Análisis léxico con tokens y DOTs
                    tokens_por_campo = {}
                    for campo, valor in datos.items():
                        tokens_por_campo[campo] = tokenizar_valor(campo, valor)

                    # Árbol sintáctico en DOT
                    arbol_dot = generar_dot_arbol(datos)

                    # Análisis sintáctico y semántico
                    token_diag = tokens_por_campo["diagnostico"][-1]  # el token del valor
                    errores_sintaxis = analizar_sintaxis(datos)
                    errores_semantica = validar_semantica(datos, token_diag)

                    errores_por_fase = {"LÉXICO": [], "SINTÁCTICO": [], "SEMÁNTICO": []}
                    for fase, msg in errores_sintaxis:
                        errores_por_fase[fase].append(msg)
                    for fase, msg in errores_semantica:
                        errores_por_fase[fase].append(msg)

                    total_errores = sum(len(errores_por_fase[f]) for f in errores_por_fase)

                    if total_errores == 0:
                        codigo = token_diag["valor"]
                        enfermedad = DICCIONARIO_ENFERMEDADES.get(codigo, "Desconocida")
                        resultado = {
                            "exito": True,
                            "nombre": datos['nombre'],
                            "apellido": datos['apellido'],
                            "dni": datos['dni'],
                            "edad": datos['edad'],
                            "diagnostico_nombre": enfermedad,
                            "codigo": codigo,
                            "token": token_diag,
                            "fecha": datos['fecha'],
                            "hora": datos['hora'],
                            "hospital_clinica": datos['hospital_clinica'],
                            "laboratorio": datos['laboratorio'],
                            "salon": datos['salon'].upper(),
                            "examenes": datos['examenes'],
                            "enfermera_medico": datos['enfermera_medico'],
                            "tipo_sangre": datos['tipo_sangre'].upper()
                        }
                    else:
                        resultado = {"exito": False, "errores": errores_por_fase}
                except Exception as e:
                    mensaje_error_general = f"Error al procesar el archivo: {str(e)}"

    return render_template("index.html",
                           resultado=resultado,
                           mensaje_error_general=mensaje_error_general,
                           tokens_por_campo=tokens_por_campo,
                           arbol_dot=arbol_dot)

if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
