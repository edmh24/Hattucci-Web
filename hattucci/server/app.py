# server/app.py
from flask import Flask, render_template, request, redirect, jsonify
from hattucci.server.db import get_connection
import bcrypt

# Indicar la carpeta de templates y static
app = Flask(__name__, template_folder='../web/templates', static_folder='../web/static')

# ------------------------------------------
# RUTA INICIO
# ------------------------------------------
@app.route("/")
def inicio():
    return redirect("/login")  # Primera página es login

# ------------------------------------------
# RUTA REGISTRO
# ------------------------------------------
@app.route("/registro")
def registro():
    return render_template("registro.html")

# ------------------------------------------
# VERIFICAR USUARIO/CORREO (AJAX)
# ------------------------------------------
@app.route("/verificar")
def verificar():
    usuario = request.args.get("usuario")
    correo = request.args.get("correo")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if usuario:
        cursor.execute("SELECT id FROM registro WHERE usuario=%s", (usuario,))
        existe = cursor.fetchone() is not None
        conn.close()
        return jsonify({"existe": existe})

    if correo:
        cursor.execute("SELECT id FROM registro WHERE correo=%s", (correo,))
        existe = cursor.fetchone() is not None
        conn.close()
        return jsonify({"existe": existe})

    conn.close()
    return jsonify({"error": "Parámetro inválido"})

# ------------------------------------------
# REGISTRAR USUARIO
# ------------------------------------------
@app.route("/registrar", methods=["POST"])
def registrar():
    usuario = request.form.get("usuario")
    correo = request.form.get("correo")
    nombre = request.form.get("nombre")
    apellido = request.form.get("apellido")
    telefono = request.form.get("telefono")
    contraseña = request.form.get("contraseña")  # usar el mismo name que en login.html

    # Validaciones
    if not all([usuario, correo, nombre, apellido, telefono, contraseña]):
        return "❌ Todos los campos son requeridos"
    if "@" not in correo or (".com" not in correo and ".net" not in correo):
        return "❌ Correo inválido"

    # Hashear contraseña y convertir a string para guardar en MySQL
    hashed = bcrypt.hashpw(contraseña.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM registro WHERE usuario=%s OR correo=%s", (usuario, correo))
    if cursor.fetchone():
        conn.close()
        return "❌ Usuario o correo ya existen"

    cursor.execute("""
        INSERT INTO registro (usuario, correo, nombre, apellido, telefono, contraseña)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (usuario, correo, nombre, apellido, telefono, hashed))
    conn.commit()
    conn.close()

    return redirect("/login")

# ------------------------------------------
# LOGIN
# ------------------------------------------
@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/ingresar", methods=["POST"])
def ingresar():
    usuario = request.form.get("usuario")
    contraseña = request.form.get("contraseña")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM registro WHERE usuario=%s", (usuario,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return "❌ Usuario no encontrado"

    # Verificación correcta de la contraseña
    if bcrypt.checkpw(contraseña.encode("utf-8"), user["contraseña"].encode("utf-8")):
        return redirect("/menu")
    else:
        return render_template("login.html", error="❌ Contraseña incorrecta")
    
@app.route("/validar_usuario_login")
def validar_usuario_login():
    usuario = request.args.get("usuario")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM registro WHERE usuario=%s", (usuario,))
    user = cursor.fetchone()
    conn.close()

    return {"existe": True} if user else {"existe": False}


# ------------------------------------------
# MENÚ
# ------------------------------------------
@app.route("/menu")
def menu():
    return render_template("menu.html")

# ------------------------------------------
# INVENTARIO
# ------------------------------------------
@app.route("/inventario")
def inventario():
    return render_template("inventario.html")

# ------------------------------------------
# REGISTRAR INVENTARIO (NUEVO / COMPRADO)
# ------------------------------------------
@app.route("/registrar_inventario", methods=["POST"])
def registrar_inventario():
    data = request.get_json()

    try:
        producto = data["producto"]
        fecha_venc = data["vencimiento"][:10]
        stock = int(data["stock"])
        precio_venta = float(data["precio_venta"])

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # ============================================================
        # 1️⃣ BUSCAR SI EXISTE UN PRODUCTO IGUAL (misma info excepto stock)
        # ============================================================
        sql_buscar = """
            SELECT * FROM inventario
            WHERE producto = %s
            AND precio_venta = %s
            AND fecha_vencimiento = %s
            LIMIT 1
        """

        cursor.execute(sql_buscar, (producto, precio_venta, fecha_venc))
        existente = cursor.fetchone()

        # ============================================================
        # 2️⃣ SI EXISTE → SUMAR STOCK
        # ============================================================
        if existente:
            nuevo_stock = existente["stock"] + stock

            cursor.execute("""
                UPDATE inventario
                SET stock = %s
                WHERE id = %s
            """, (nuevo_stock, existente["id"]))

            conn.commit()
            return jsonify({"ok": True, "update": True})

        # ============================================================
        # 3️⃣ SI NO EXISTE → CREAR NUEVA FILA
        # ============================================================
        sql_insertar = """
            INSERT INTO inventario (producto, fecha_vencimiento, stock, precio_venta)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(sql_insertar, (producto, fecha_venc, stock, precio_venta))
        conn.commit()

        return jsonify({"ok": True, "insert": True})

    except Exception as e:
        print("❌ ERROR REGISTRAR INVENTARIO:", e)
        return jsonify({"ok": False, "error": str(e)})

    finally:
        cursor.close()
        conn.close()


# ------------------------------------------
# OBTENER INVENTARIO
# ------------------------------------------
@app.route("/obtener_inventario", methods=["GET"])
def obtener_inventario():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT 
                id,
                producto,
                fecha_vencimiento,
                stock,
                precio_venta
            FROM inventario
            ORDER BY id DESC
        """)

        items = cursor.fetchall()
        return jsonify(items)

    except Exception as e:
        print("❌ ERROR INVENTARIO:", e)
        return jsonify([])

    finally:
        cursor.close()
        conn.close()

# ------------------------------------------
# ELIMINAR PRODUCTO DEL INVENTARIO
# ------------------------------------------
@app.route("/eliminar_inventario/<int:id>", methods=["DELETE"])
def eliminar_inventario(id):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM inventario WHERE id = %s", (id,))
        conn.commit()

        return jsonify({"ok": True})

    except Exception as e:
        print("❌ ERROR eliminando inventario:", e)
        return jsonify({"ok": False, "error": str(e)})

    finally:
        cursor.close()
        conn.close()


# ------------------------------------------
# VENTAS
# ------------------------------------------
@app.route("/ventas")
def ventas():
    return render_template("ventas.html")

from datetime import date

@app.route("/descontar_stock", methods=["POST"])
def descontar_stock():
    data = request.get_json()
    venta = data.get("venta", [])
    comprobante = data.get("comprobante", "SIN_COMPROBANTE")

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Obtener fecha actual AAAA-MM-DD
        fecha_hoy = date.today()

        # Si hay boleta, obtener correlativo
        correlativo = None
        if comprobante == "BOLETA":
            correlativo = obtener_siguiente_correlativo()  # 🔥 LLAMA A TU FUNCIÓN

        # --------------------------------------------
        # GUARDAR CADA PRODUCTO DE LA VENTA
        # --------------------------------------------
        for item in venta:

            # Descontar stock
            cursor.execute("""
                UPDATE inventario
                SET stock = stock - %s
                WHERE id = %s
            """, (item["cantidad"], item["id"]))

            # Registrar venta
            cursor.execute("""
                INSERT INTO ventas (producto, cantidad, total, fecha_venta, numero_boleta)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                item["nombre"],
                item["cantidad"],
                item["total"],
                fecha_hoy,
                correlativo
            ))

        conn.commit()

        # --------------------------------------------
        # RESPUESTA AL FRONTEND
        # --------------------------------------------
        return jsonify({
            "ok": True,
            "correlativo": str(correlativo) if correlativo else None
        })

    except Exception as e:
        print("❌ ERROR al procesar venta:", e)
        return jsonify({"ok": False, "error": str(e)})

    finally:
        cursor.close()
        conn.close()



def obtener_siguiente_correlativo():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Obtener número actual
    cursor.execute("SELECT numero FROM boletas_correlativo ORDER BY id DESC LIMIT 1")
    data = cursor.fetchone()

    if not data:
        numero = 1
        cursor.execute("INSERT INTO boletas_correlativo (numero) VALUES (1)")
    else:
        numero = data["numero"] + 1
        cursor.execute("INSERT INTO boletas_correlativo (numero) VALUES (%s)", (numero,))

    conn.commit()
    cursor.close()
    conn.close()

    return numero



# ------------------------------------------
# COMPRAS
# ------------------------------------------
@app.route("/compras")
def compras():
    return render_template("compras.html")


# ------------------------------------------
# REGISTRAR COMPRA
# ------------------------------------------
@app.route("/registrar_compra", methods=["POST"])
def registrar_compra():

    data = request.get_json()

    # Normalizar fechas → asegurar solo formato YYYY-MM-DD
    fecha_registro = str(data["fecha_registro"])[:10]
    fecha_vencimiento = str(data["fecha_vencimiento"])[:10]

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # -----------------------------------------------
        # 1️⃣ Buscar coincidencia EXACTA (solo día, sin hora)
        # -----------------------------------------------
        sql_buscar = """
        SELECT 
            id,
            nombre_proveedor,
            contacto_proveedor,
            producto,
            cantidad,
            precio_unitario,
            fecha_registro,
            fecha_vencimiento
        FROM compras
        WHERE nombre_proveedor = %s
          AND contacto_proveedor = %s
          AND producto = %s
          AND precio_unitario = %s
          AND DATE(fecha_vencimiento) = %s
          AND DATE(fecha_registro) = %s
        LIMIT 1
        """

        cursor.execute(sql_buscar, (
            data["proveedor_nombre"],
            data["proveedor_contacto"],
            data["producto"],
            data["precio_unitario"],
            fecha_vencimiento,
            fecha_registro
        ))

        compra_existente = cursor.fetchone()

        # -----------------------------------------------
        # 2️⃣ Si coincide → sumar cantidad
        # -----------------------------------------------
        if compra_existente:
            nueva_cantidad = compra_existente["cantidad"] + int(data["cantidad"])

            cursor.execute("""
                UPDATE compras
                SET cantidad = %s
                WHERE id = %s
            """, (nueva_cantidad, compra_existente["id"]))

            conn.commit()

            return jsonify({"ok": True, "update": True})

        # -----------------------------------------------
        # 3️⃣ Si NO coincide → insertar nueva compra
        # -----------------------------------------------
        cursor.execute("""
            INSERT INTO compras (
                nombre_proveedor,
                contacto_proveedor,
                producto,
                cantidad,
                precio_unitario,
                fecha_registro,
                fecha_vencimiento
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            data["proveedor_nombre"],
            data["proveedor_contacto"],
            data["producto"],
            data["cantidad"],
            data["precio_unitario"],
            fecha_registro,
            fecha_vencimiento
        ))

        conn.commit()
        return jsonify({"ok": True, "insert": True})

    except Exception as e:
        print("❌ ERROR REGISTRO COMPRA:", e)
        return jsonify({"ok": False, "error": str(e)})

    finally:
        cursor.close()
        conn.close()

# ------------------------------------------
# OBTENER TODAS LAS COMPRAS (FORMATO SOLO FECHA)
# ------------------------------------------
@app.route("/obtener_compras", methods=["GET"])
def obtener_compras():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT 
                id,
                nombre_proveedor,
                contacto_proveedor,
                producto,
                cantidad,
                precio_unitario,
                DATE(fecha_registro) AS fecha_registro,
                DATE(fecha_vencimiento) AS fecha_vencimiento
            FROM compras
            ORDER BY fecha_registro DESC, id DESC
        """)

        compras = cursor.fetchall()

        return jsonify(compras)

    except Exception as e:
        print("❌ ERROR OBTENER COMPRAS:", e)
        return jsonify([])

    finally:
        cursor.close()
        conn.close()




@app.route("/filtrar_compras_dia", methods=["POST"])
def filtrar_compras_dia():
    data = request.get_json()
    dia = str(data.get("dia"))[:10]

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        sql = """
        SELECT
            id,
            nombre_proveedor,
            contacto_proveedor,
            producto,
            cantidad,
            precio_unitario,
            DATE_FORMAT(fecha_vencimiento, '%Y-%m-%d') AS fecha_vencimiento,
            DATE_FORMAT(fecha_registro, '%Y-%m-%d') AS fecha_registro
        FROM compras
        WHERE DATE(fecha_registro) = %s
        ORDER BY id DESC
        """

        cursor.execute(sql, (dia,))
        compras = cursor.fetchall()

        return jsonify(compras)

    except Exception as e:
        print("❌ Error filtrando día:", e)
        return jsonify([])

    finally:
        cursor.close()
        conn.close()




# ------------------------------------------
# ELIMINAR COMPRA
# ------------------------------------------
@app.route("/eliminar_compra/<int:id>", methods=["DELETE"])
def eliminar_compra(id):
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # 1️⃣ Obtener datos de la compra antes de borrar
        cursor.execute("""
            SELECT producto, cantidad, fecha_vencimiento, precio_unitario
            FROM compras
            WHERE id = %s
        """, (id,))
        compra = cursor.fetchone()

        if not compra:
            return jsonify({"ok": False, "error": "Compra no encontrada"})

        producto = compra["producto"]
        cantidad = compra["cantidad"]
        fecha_venc = str(compra["fecha_vencimiento"])[:10]

        # 2️⃣ Restar cantidad en inventario
        cursor.execute("""
            SELECT id, stock
            FROM inventario
            WHERE producto = %s
              AND fecha_vencimiento = %s
        """, (producto, fecha_venc))

        inv = cursor.fetchone()

        if inv:
            nuevo_stock = inv["stock"] - cantidad

            if nuevo_stock <= 0:
                # Eliminar del inventario si queda ≤ 0
                cursor.execute("DELETE FROM inventario WHERE id = %s", (inv["id"],))
            else:
                # Actualizar stock normal
                cursor.execute("""
                    UPDATE inventario
                    SET stock = %s
                    WHERE id = %s
                """, (nuevo_stock, inv["id"]))

        # 3️⃣ Eliminar la compra
        cursor.execute("DELETE FROM compras WHERE id = %s", (id,))
        conn.commit()

        return jsonify({"ok": True})

    except Exception as e:
        print("❌ ERROR eliminando compra:", e)
        return jsonify({"ok": False, "error": str(e)})

    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

@app.route("/inventario_por_producto", methods=["GET"])
def inventario_por_producto():
    producto = request.args.get("producto")
    fecha = request.args.get("fecha")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT SUM(stock) AS total
        FROM inventario
        WHERE producto = %s AND fecha_vencimiento = %s
    """, (producto, fecha))

    data = cursor.fetchone()
    total = data["total"] if data["total"] else 0

    cursor.close()
    conn.close()

    return jsonify({"total": total})




# ------------------------------------------
# REPORTES
# ------------------------------------------
@app.route("/reportes")
def reportes():
    return render_template("reportes.html")

@app.route("/logout")
def logout():
    # Aquí puedes limpiar la sesión si usas session
    return redirect("/login")

@app.route("/obtener_reportes_dia", methods=["POST"])
def obtener_reportes_dia():
    data = request.get_json()
    fecha = data["fecha"]

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # =============================
    #      RESUMEN DE VENTAS
    # =============================
    cursor.execute("""
        SELECT 
            SUM(total) AS total_ventas,
            SUM(cantidad) AS productos_vendidos,
            COUNT(*) AS num_ventas
        FROM ventas
        WHERE DATE(fecha_venta) = %s
    """, (fecha,))
    resumen_ventas = cursor.fetchone()

    if resumen_ventas["total_ventas"] is None:
        resumen_ventas = {
            "total_ventas": 0,
            "productos_vendidos": 0,
            "num_ventas": 0
        }

    # =============================
    #      RESUMEN DE COMPRAS
    # =============================
    cursor.execute("""
        SELECT 
            SUM(cantidad * precio_unitario) AS total_compras,
            COUNT(*) AS num_compras
        FROM compras
        WHERE DATE(fecha_registro) = %s
    """, (fecha,))
    resumen_compras = cursor.fetchone()

    if resumen_compras["total_compras"] is None:
        resumen_compras = {
            "total_compras": 0,
            "num_compras": 0
        }

    conn.close()

    return jsonify({
        "ventas": resumen_ventas,
        "compras": resumen_compras
    })


@app.route("/obtener_movimientos_dia", methods=["POST"])
def obtener_movimientos_dia():
    data = request.get_json()
    fecha = data["fecha"]

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # =============================
    #   VENTAS DEL DÍA
    # =============================
    cursor.execute("""
        SELECT 
            'VENTA' AS tipo,
            producto,
            cantidad,
            total,
            fecha_venta AS fecha
        FROM ventas
        WHERE DATE(fecha_venta) = %s
    """, (fecha,))
    ventas = cursor.fetchall()

    # =============================
    #   COMPRAS DEL DÍA
    # =============================
    cursor.execute("""
        SELECT 
            'COMPRA' AS tipo,
            producto,
            cantidad,
            (cantidad * precio_unitario) AS total,
            fecha_registro AS fecha
        FROM compras
        WHERE DATE(fecha_registro) = %s
    """, (fecha,))
    compras = cursor.fetchall()

    # =============================
    #    UNIR TODO EN UNA LISTA
    # =============================
    movimientos = ventas + compras

    # =============================
    #    GANANCIA O PÉRDIDA
    # =============================
    totalVentas = sum(float(v["total"]) for v in ventas)
    totalCompras = sum(float(c["total"]) for c in compras)
    ganancia = totalVentas - totalCompras


    conn.close()

    return jsonify({
        "movimientos": movimientos,
        "totalVentas": totalVentas,
        "totalCompras": totalCompras,
        "ganancia": ganancia
    })


# ------------------------------------------
# SERVIDOR
# ------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)

