import os
import threading
from flask import Flask, jsonify, request
from mssql_python import connect
import resend
import threading

try:
    from resend import Resend
    HAS_RESEND = True
except ImportError:
    HAS_RESEND = False
    Resend = None

app = Flask(__name__)


def enviar_correo_alerta(asunto, mensaje, destino):
    """Envía correo usando Resend (recomendado para Render)"""
    resend_key = os.getenv("RESEND_API_KEY")
    
    if not resend_key:
        raise ValueError("Falta RESEND_API_KEY")
    
    if not HAS_RESEND:
        raise ValueError("Resend no instalado")
    
    client = Resend(api_key=resend_key)
    
    response = client.emails.send({
        "from": "onboarding@resend.dev",
        "to": destino,
        "subject": asunto,
        "html": f"<p>{mensaje}</p>"
    })
    
    if not response.get("id"):
        raise ValueError(f"Error Resend: {response}")


def enviar_correo_resend(destino, asunto, mensaje):
    """Envía correo usando Resend (sincrónico)."""
    resend_key = os.getenv("RESEND_API_KEY")
    from_email = os.getenv("MAIL_RESEND", "onboarding@resend.dev")

    if not resend_key:
        raise ValueError("Falta RESEND_API_KEY")
    if not HAS_RESEND:
        raise ValueError("Resend no instalado")

    client = Resend(api_key=resend_key)
    client.emails.send({
        "from": from_email,
        "to": destino,
        "subject": asunto,
        "html": f"<p>{mensaje}</p>"
    })


@app.route("/enviar-alerta-resend", methods=["POST"])
def enviar_alerta_resend():
    data = request.get_json(silent=True) or {}

    correo = data.get("email") or data.get("to")
    asunto = data.get("subject", "Notificación")
    mensaje = data.get("message", "Mensaje desde Render")

    if not correo:
        return jsonify({"error": "Falta el email"}), 400

    try:
        thread = threading.Thread(target=enviar_correo_resend, args=(correo, asunto, mensaje), daemon=True)
        thread.start()

        return jsonify({
            "status": "ok",
            "msg": "Correo en proceso de envío (async)"
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "msg": str(e)
        }), 500


@app.route("/test-resend")
def test_resend():
    """Devuelve estado de instalación y presencia de RESEND_API_KEY (no envía correo)."""
    return jsonify({
        "has_resend_library": HAS_RESEND,
        "resend_api_key_exists": bool(os.getenv("RESEND_API_KEY")),
        "recommended_from": "onboarding@resend.dev"
    })


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


@app.route("/enviar-alerta", methods=["POST"])
def enviar_alerta():
    try:
        data = request.get_json(silent=True) or {}
        destino = data.get("to") or data.get("email")
        asunto = data.get("subject")
        mensaje = data.get("message")

        if not destino or not asunto or not mensaje:
            return jsonify({
                "success": False,
                "message": "Faltan datos"
            }), 400

        enviar_correo_alerta(asunto, mensaje, destino)
        return jsonify({
            "success": True,
            "message": "Correo enviado"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)