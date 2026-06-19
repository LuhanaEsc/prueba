<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Minicompilador Médico</title>

<style>
body {
    font-family: Arial;
    background: #f4f6f9;
    margin: 30px;
}

.card {
    background: white;
    padding: 15px;
    border-radius: 10px;
    margin-bottom: 20px;
}

.token {
    background: #eef;
    padding: 8px;
    margin: 5px 0;
    border-radius: 5px;
}

.ok { color: green; }
.error { color: red; }

.catalogo {
    background: #fff;
    padding: 15px;
    border-left: 5px solid #3498db;
    margin-top: 20px;
}
</style>
</head>

<body>

<h1>🧠 Minicompilador Médico</h1>

<!-- ================= FORM ================= -->
<div class="card">
<form method="POST" enctype="multipart/form-data">
    <input type="file" name="archivo">
    <button>Compilar</button>
</form>
</div>

<!-- ================= TOKENS ================= -->
{% if tokens_por_campo %}
<div class="card">
<h2>📌 Tokens</h2>

{% for campo, tokens in tokens_por_campo.items() %}
    <h3>Campo: {{ campo }}</h3>

    {% for t in tokens %}
        <div class="token">
            <b>Tipo:</b> {{ t.tipo }} <br>
            <b>Valor:</b> {{ t.valor }} <br>
            <b>Regex:</b> {{ t.regex }} <br>
            <b class="{{ 'ok' if t.estado == 'OK' else 'error' }}">
                Estado: {{ t.estado }}
            </b>
        </div>
    {% endfor %}

{% endfor %}
</div>
{% endif %}

<!-- ================= CATÁLOGO ================= -->
<div class="catalogo">
<h2>📚 Catálogo de referencia</h2>

<h3>🧪 Diagnósticos</h3>
<ul>
{% for k,v in catalogo.diagnosticos.items() %}
<li>{{ k }} - {{ v }}</li>
{% endfor %}
</ul>

<h3>🩸 Sangre</h3>
<ul>
{% for s in catalogo.sangre %}
<li>{{ s }}</li>
{% endfor %}
</ul>

<h3>🏥 Salas</h3>
<ul>
{% for s in catalogo.salas %}
<li>{{ s }}</li>
{% endfor %}
</ul>

</div>

</body>
</html>
