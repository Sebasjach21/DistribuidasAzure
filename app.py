import os
from flask import Flask, jsonify, request
from mssql_python import connect
import resend
import threading

app = Flask(__name__)


def get_connection():
    server = os.getenv("DB_SERVER")
    database = os.getenv("DB_DATABASE")
    username = os.getenv("DB_USERNAME")
    password = os.getenv("DB_PASSWORD")
    port = os.getenv("DB_PORT", "1433")

    if not server:
        raise ValueError("Falta DB_SERVER")
    if not database:
        raise ValueError("Falta DB_DATABASE")
    if not username:
        raise ValueError("Falta DB_USERNAME")
    if not password:
        raise ValueError("Falta DB_PASSWORD")

    connection_string = (
        f"Server=tcp:{server},{port};"
        f"Database={database};"
        f"Uid={username};"
        f"Pwd={password};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
        f"Authentication=SqlPassword;"
    )

    return connect(connection_string)


@app.route("/")
def home():
    return jsonify({
        "success": True,
        "message": "API Flask funcionando correctamente en Render"
    })


@app.route("/debug-env")
def debug_env():
    return jsonify({
        "DB_SERVER": os.getenv("DB_SERVER"),
        "DB_DATABASE": os.getenv("DB_DATABASE"),
        "DB_USERNAME": os.getenv("DB_USERNAME"),
        "DB_PASSWORD_EXISTS": bool(os.getenv("DB_PASSWORD")),
        "DB_PORT": os.getenv("DB_PORT"),
    })


@app.route("/test-db")
def test_db():
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT GETDATE() AS fecha_servidor")
        row = cursor.fetchone()

        return jsonify({
            "success": True,
            "message": "Conexión a SQL Server exitosa",
            "server_date": str(row[0])
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": "Error al conectar con SQL Server",
            "error": str(e)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route("/productos")
def listar_productos():
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT TOP 20 id, nombre, precio, imagen_url
            FROM productos
            ORDER BY id DESC
        """)
        rows = cursor.fetchall()

        data = []
        for row in rows:
            data.append({
                "id": row[0],
                "nombre": row[1],
                "precio": float(row[2]) if row[2] is not None else None,
                "imagen_url": row[3],
            })

        return jsonify({
            "success": True,
            "data": data
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": "Error al consultar productos",
            "error": str(e)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

#?============== RESEND
# Configurar API Key
resend.api_key = os.environ["RESEND_API_KEY"]
FROM_EMAIL = os.environ.get("MAIL_RESEND", "onboarding@resend.dev")

# Función de envío
def enviar_correo_resend(destino, asunto, mensaje):
    resend.Emails.send({
        "from": FROM_EMAIL,
        "to": [destino],
        "subject": asunto,
        "html": f"<p>{mensaje}</p>"
    })

# Endpoint
@app.route("/enviar-alerta-resend", methods=["POST"])
def enviar_alerta_resend():
    data = request.json

    correo = data.get("email")
    asunto = data.get("subject", "Notificación")
    mensaje = data.get("message", "Mensaje desde Render")

    if not correo:
        return jsonify({"error": "Falta el email"}), 400

    try:
        # Evita WORKER TIMEOUT
        threading.Thread(target=enviar_correo_resend, args=(correo, asunto, mensaje)).start()

        return jsonify({
            "status": "ok",
            "msg": "Correo enviado (async)"
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "msg": str(e)
        }), 500