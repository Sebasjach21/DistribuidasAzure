import os
import smtplib
from email.mime.text import MIMEText
from flask import Flask, jsonify, request
from mssql_python import connect

app = Flask(__name__)


def enviar_correo_alerta(asunto, mensaje, destino):
    # Soporta dos convenciones de nombres en variables de entorno: SMTP_* y EMAIL_*.
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER") or os.getenv("EMAIL_USER")
    smtp_password = os.getenv("SMTP_PASSWORD") or os.getenv("EMAIL_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM") or smtp_user
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")

    if not smtp_user:
        raise ValueError("Falta SMTP_USER o EMAIL_USER")
    if not smtp_password:
        raise ValueError("Falta SMTP_PASSWORD o EMAIL_PASSWORD")
    if not smtp_from:
        raise ValueError("Falta SMTP_FROM")

    correo = MIMEText(mensaje, "plain", "utf-8")
    correo["Subject"] = asunto
    correo["From"] = smtp_from
    correo["To"] = destino

    with smtplib.SMTP(smtp_host, smtp_port) as servidor:
        servidor.ehlo()
        if use_tls:
            servidor.starttls()
            servidor.ehlo()
        servidor.login(smtp_user, smtp_password)
        servidor.sendmail(smtp_from, [destino], correo.as_string())


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
        "SMTP_HOST": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "SMTP_PORT": os.getenv("SMTP_PORT", "587"),
        "SMTP_USER_EXISTS": bool(os.getenv("SMTP_USER")),
        "SMTP_PASSWORD_EXISTS": bool(os.getenv("SMTP_PASSWORD")),
        "EMAIL_USER_EXISTS": bool(os.getenv("EMAIL_USER")),
        "EMAIL_PASSWORD_EXISTS": bool(os.getenv("EMAIL_PASSWORD")),
        "SMTP_FROM": os.getenv("SMTP_FROM") or os.getenv("SMTP_USER") or os.getenv("EMAIL_USER"),
        "SMTP_USE_TLS": os.getenv("SMTP_USE_TLS", "true"),
    })


@app.route("/test-smtp")
def test_smtp():
    """Prueba conexión SMTP sin enviar correo"""
    try:
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER") or os.getenv("EMAIL_USER")
        smtp_password = os.getenv("SMTP_PASSWORD") or os.getenv("EMAIL_PASSWORD")
        use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")

        if not smtp_user:
            return jsonify({"success": False, "error": "No hay EMAIL_USER o SMTP_USER"}), 400
        if not smtp_password:
            return jsonify({"success": False, "error": "No hay EMAIL_PASSWORD o SMTP_PASSWORD"}), 400

        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as servidor:
            servidor.ehlo()
            if use_tls:
                servidor.starttls()
                servidor.ehlo()
            servidor.login(smtp_user, smtp_password)
            return jsonify({
                "success": True,
                "message": "Conexión SMTP exitosa",
                "host": smtp_host,
                "port": smtp_port,
                "tls": use_tls
            })
    except smtplib.SMTPAuthenticationError as e:
        return jsonify({
            "success": False,
            "error": f"Credenciales inválidas: {str(e)}"
        }), 401
    except smtplib.SMTPException as e:
        return jsonify({
            "success": False,
            "error": f"Error SMTP: {str(e)}"
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Error: {str(e)}"
        }), 500


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
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({
                "success": False,
                "message": "El body debe ser un JSON objeto con: to, subject, message"
            }), 400

        destino = data.get("to")
        asunto = data.get("subject")
        mensaje = data.get("message")

        if not destino or not asunto or not mensaje:
            return jsonify({
                "success": False,
                "message": "Faltan datos: to, subject, message"
            }), 400

        enviar_correo_alerta(asunto, mensaje, destino)
        return jsonify({
            "success": True,
            "message": "Correo enviado exitosamente"
        }), 200
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
    except smtplib.SMTPAuthenticationError as e:
        return jsonify({
            "success": False,
            "error": f"Error de autenticación SMTP: {str(e)}"
        }), 401
    except smtplib.SMTPException as e:
        return jsonify({
            "success": False,
            "error": f"Error SMTP: {str(e)}"
        }), 500
    except Exception as e:
        import traceback
        return jsonify({
            "success": False,
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc() if app.debug else None
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)