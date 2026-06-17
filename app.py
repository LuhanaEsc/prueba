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

# ---------- GENERACIÓN DE DOT PARA AFDs ----------
def generar_dot_afd(tipo_token):
    """Devuelve el código DOT estándar para un tipo de token."""
    if tipo_token == "CODIGO_MEDICO":
        return """digraph AFD_CODIGO {
    rankdir=LR;
    node [shape=circle];
    q0 [label="q0"];
    q1 [label="q1"];
    q2 [label="q2"];
    q3 [label="q3", shape=doublecircle];
    error [label="q_error", color=red];
    q0 -> q1 [label="[A-Z]"];
    q0 -> error [label="otro"];
    q1 -> q2 [label="[0-9]"];
    q1 -> error [label="otro"];
    q2 -> q3 [label="[0-9]"];
    q2 -> error [label="otro"];
    q3 -> error [label="cualquier símbolo"];
}"""
    elif tipo_token == "FECHA":
        return """digraph AFD_FECHA {
    rankdir=LR;
    node [shape=circle];
    q0; q1; q2; q3; q4; q5; q6; q7; q8;
    q9 [shape=doublecircle];
    q0->q1[label="[0-9]"]; q1->q2[label="[0-9]"]; q2->q3[label="[0-9]"]; q3->q4[label="[0-9]"];
    q4->q5[label="'-'"];   q5->q6[label="[0-9]"]; q6->q7[label="[0-9]"]; q7->q8[label="'-'"];
    q8->q9[label="[0-9]"];
}"""
    elif tipo_token == "HORA":
        return """digraph AFD_HORA {
    rankdir=LR;
    node [shape=circle];
    q0; q1a; q1b; q2; q3; q4;
    q5 [shape=doublecircle];
    q0->q1a[label="[0-1]"]; q0->q1b[label="'2'"];
    q1a->q2[label="[0-9]"]; q1b->q2[label="[0-3]"];
    q2->q3[label="':'"];    q3->q4[label="[0-5]"];
    q4->q5[label="[0-9]"];
}"""
    elif tipo_token == "NUMERO":
        return """digraph AFD_NUMERO {
    rankdir=LR;
    q0[shape=circle];
    q1[shape=doublecircle];
    q0->q1[label="[0-9]"];
    q1->q1[label="[0-9]"];
}"""
    elif tipo_token == "TIPO_SANGRE":
        return """digraph AFD_TIPO_SANGRE {
    rankdir=LR;
    node [shape=circle];
    q0; q1; q2 [shape=doublecircle];
    q0->q1[label="'A'|'B'|'O'|'AB'"];
    q1->q2[label="'+'|'-'"];
}"""
    elif tipo_token == "CADENA":
        return """digraph AFD_CADENA {
    rankdir=LR;
    q0 [shape=doublecircle];
    q0->q0[label="[A-Za-zÁÉÍÓÚÑáéíóúñ\\s\\.,\\-]"];
}"""
    elif tipo_token == "ID_CAMPO":
        return """digraph AFD_ID_CAMPO {
    rankdir=LR;
    q0 [shape=doublecircle];
    q0->q0[label="[A-Za-zÁÉÍÓÚÑáéíóúñ/]"];
}"""
    else:
        return ""

# ---------- SIMULACIÓN DE AFD PARA OBTENER ESTADOS ----------
def simular_afd(tipo_token, cadena):
    """
    Simula el AFD para el tipo de token dado y devuelve la secuencia de estados.
    Solo para fines ilustrativos, no es una simulación real, sino una generación
    de estados basada en la longitud de la cadena.
    """
    # Para simplificar, generamos una secuencia de estados según la longitud
    # y el tipo de token.
    if tipo_token in ["CODIGO_MEDICO", "FECHA", "HORA", "NUMERO", "TIPO_SANGRE", "CADENA", "ID_CAMPO"]:
        # Para tokens que aceptan una longitud variable, generamos q0, q1, ..., qn, qf
        estados = ["q0"]
        for i in range(len(cadena)):
            estados.append(f"q{i+1}")
        estados.append("qf (aceptación)")
        return estados
    else:
        return ["q0", "q_error"]

# ---------- TOKENIZACIÓN CON DOT ----------
def tokenizar_valor(campo, valor):
    tokens = []
    # Token ID_CAMPO
    tokens.append({
        "tipo": "ID_CAMPO",
        "valor": campo,
        "estados": ["q0", "qf (aceptación)"],
        "dot": generar_dot_afd("ID_CAMPO")
    })
    # Token DOS_PUNTOS
    tokens.append({
        "tipo": "DOS_PUNTOS",
        "valor": ":",
        "estados": ["q0", "qf (aceptación)"],
        "dot": ""  # no hay AFD para dos puntos
    })
    # Token del valor
    # Determinar tipo
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

    # Validar con expresión regular
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
    else:  # CADENA
        valido = bool(re.fullmatch(r'^[A-Za-zÁÉÍÓÚÑáéíóúñ\s\.\,\-]+$', valor.strip()))

    if not valido:
        tipo_token = "ERROR_LEXICO"

    # Simular estados (si es válido, mostramos una secuencia, si no, error)
    if valido:
        estados = simular_afd(tipo_token, valor.strip())
    else:
        estados = ["q0", "q_error (rechazo)"]

    tokens.append({
        "tipo": tipo_token,
        "valor": valor.strip(),
        "estados": estados,
        "dot": generar_dot_afd(tipo_token) if valido else ""
    })
    return tokens

# ---------- GENERACIÓN DE DOT DEL ÁRBOL SINTÁCTICO ----------
def generar_dot_arbol(datos):
    dot = "digraph ArbolSintactico {\n"
    dot += "    node [shape=box, style=filled, fillcolor=lightblue];\n"
    dot += "    PACIENTE [label=\"PACIENTE\"];\n"
    for i, (campo, valor) in enumerate(datos.items()):
        campo_id = f"campo{i}"
        valor_id = f"valor{i}"
        dot += f'    {campo_id} [label="CAMPO: {campo}"];\n'
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
        dot += f'    {valor_id} [label="{tipo}: {valor}"];\n'
        dot += f"    PACIENTE -> {campo_id};\n"
        dot += f"    {campo_id} -> {valor_id};\n"
    dot += "}\n"
    return dot

# ---------- FUNCIONES DE ANÁLISIS SINTÁCTICO Y SEMÁNTICO ----------
# (Mantén las que ya tenías)
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

def validar_semantica(datos, token_diagnostico):
    errores = []
    # Aquí copia tus validaciones originales (edad, dni, etc.)
    # ...
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

                    # Análisis léxico con tokens y DOT
                    tokens_por_campo = {}
                    for campo, valor in datos.items():
                        tokens_por_campo[campo] = tokenizar_valor(campo, valor)

                    # Árbol sintáctico en DOT
                    arbol_dot = generar_dot_arbol(datos)

                    # Análisis sintáctico y semántico (como antes)
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
