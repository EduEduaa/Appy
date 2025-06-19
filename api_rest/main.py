from flask import Flask, jsonify, request, render_template, Response, abort
from models import db, Sucursal, Producto, Stock, Venta, DetalleVenta
from sqlalchemy.exc import SQLAlchemyError
import time
import json
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:@localhost/tienda'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
app.debug = True

API_TOKEN = "mi_api_key_segura_abc123"

def require_api_token(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if token != f"Bearer {API_TOKEN}":
            abort(401, description="No autorizado. Token inválido o faltante.")
        return f(*args, **kwargs)
    return decorated_function

# inicio
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/pagar.html')
def pagar_page():
    return render_template('pagar.html')

@app.route('/gracias.html')
def gracias_page():
    return render_template('gracias.html')


sse_clients = []

def eventos_sse():
    while True:
        time.sleep(5)  # Intervalo para verificar
        for client in list(sse_clients):  # Iterar sobre una copia para permitir modificaciones
            # Aquí => lógica más compleja para determinar cuándo enviar un evento
            # solo envia un "ping" para mantener la conexión activa
            try:
                yield f"event: ping\ndata: {json.dumps({'time': time.time()})}\n\n"
            except GeneratorExit:
                sse_clients.remove(client)
                print("Cliente SSE desconectado.")
            except:
                sse_clients.remove(client)
                print("Error al enviar evento SSE.")

@app.route('/stream')
def sse_stream():
    def generate():
       
        response_stream = Response(eventos_sse(), mimetype='text/event-stream')
        sse_clients.append(response_stream) # Agregamos el objeto Response para luego poder eliminarlo

        try:
            yield from eventos_sse()
        finally:
            if response_stream in sse_clients:
                sse_clients.remove(response_stream)
                print("Cliente SSE desconectado.")
    return Response(generate(), mimetype='text/event-stream')

# --- BUSCAR PRODUCTO (AJUSTADO) ---
@app.route('/buscar_producto', methods=['GET'])
def buscar_producto():
    nombre_producto = request.args.get('nombre')
    if not nombre_producto:
        return jsonify({'error': 'Por favor, proporciona un nombre de producto'}), 400

    resultados = []
    # Busca productos por nombre
    productos_encontrados = Producto.query.filter(db.func.lower(Producto.nombre) == nombre_producto.lower()).all()

    for producto in productos_encontrados:
        # Busca el stock de este producto en todas las sucursales
        stock_items = Stock.query.filter_by(producto_id=producto.id).all()
        for item_stock in stock_items:
            sucursal = Sucursal.query.get(item_stock.sucursal_id)
            if sucursal:
                # El precio se obtiene directamente del producto
                resultado = {
                    'producto_id': producto.id,
                    'producto_nombre': producto.nombre,
                    'precio': producto.precio, # <--- ¡Ahora el precio viene del producto!
                    'imagen': producto.imagen, # <--- ¡La imagen viene del producto!
                    'stock_disponible': item_stock.cantidad,
                    'sucursal_id': sucursal.id,
                    'sucursal_nombre': sucursal.nombre
                }
                resultados.append(resultado)

                if item_stock.cantidad == 0:
                    # Enviar alerta SSE si la cantidad es 0
                    for client_response in sse_clients:
                        try:
                            # Para enviar un evento SSE, necesitas acceder al generador
                            # y "yield" el evento. Esto es más complejo con Response
                            # objetos directamente en una lista global.
                            # Para un ejemplo simple, simulamos una alerta aquí.
                            # En un sistema real, usarías una cola de mensajes o una librería SSE dedicada.
                            print(f"Alerta SSE: ¡El producto {producto.nombre} en la sucursal {sucursal.nombre} tiene stock 0!")
                            # Una implementación más robusta implicaría un mecanismo para "empujar"
                            # datos a los generadores de cada cliente.
                        except Exception as e:
                            print(f"Error al intentar enviar alerta SSE a un cliente: {e}")
                            # sse_clients.remove(client_response) # Quitar el cliente si falla
    return jsonify({'resultados': resultados})

# --- CRUD para Sucursales (sin cambios, ya estaban correctos) ---

@app.route('/sucursales', methods=['GET'])
def obtener_sucursales():
    sucursales = Sucursal.query.all()
    return jsonify({'sucursales': [{'id': s.id, 'nombre': s.nombre, 'direccion': s.direccion} for s in sucursales]})

@app.route('/sucursales/<int:sucursal_id>', methods=['GET'])
def obtener_sucursal(sucursal_id):
    sucursal = Sucursal.query.get_or_404(sucursal_id)
    return jsonify({'sucursal': {'id': sucursal.id, 'nombre': sucursal.nombre, 'direccion': sucursal.direccion}})

@app.route('/sucursales', methods=['POST'])
@require_api_token
def crear_sucursal():
    data = request.get_json()
    if not isinstance(data, list):
        return jsonify({'error': 'Por favor, envía una lista de sucursales'}), 400
    nuevas_sucursales = []
    for sucursal_data in data:
        if 'nombre' not in sucursal_data or 'direccion' not in sucursal_data:
            return jsonify({'error': 'Solicitud inválida. Falta nombre o dirección en una sucursal'}), 400
        nueva_sucursal = Sucursal(nombre=sucursal_data['nombre'], direccion=sucursal_data['direccion'])
        db.session.add(nueva_sucursal)
        db.session.flush() # Para obtener el ID antes del commit final
        nuevas_sucursales.append({'id': nueva_sucursal.id, 'nombre': nueva_sucursal.nombre, 'direccion': nueva_sucursal.direccion})
    db.session.commit()
    return jsonify({'sucursales_creadas': nuevas_sucursales}), 201

@app.route('/sucursales/<int:sucursal_id>', methods=['PUT'])
def actualizar_sucursal(sucursal_id):
    sucursal = Sucursal.query.get_or_404(sucursal_id)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Solicitud inválida'}), 400
    sucursal.nombre = data.get('nombre', sucursal.nombre)
    sucursal.direccion = data.get('direccion', sucursal.direccion)
    db.session.commit()
    return jsonify({'sucursal': {'id': sucursal.id, 'nombre': sucursal.nombre, 'direccion': sucursal.direccion}})

@app.route('/sucursales/<int:sucursal_id>', methods=['DELETE'])
def eliminar_sucursal(sucursal_id):
    sucursal = Sucursal.query.get_or_404(sucursal_id)
    db.session.delete(sucursal)
    db.session.commit()
    return jsonify({'resultado': True})

# --- CRUD para Productos (AJUSTADO) ---

@app.route('/productos', methods=['GET'])
def obtener_productos():
    productos = Producto.query.all()
    # Ahora incluimos precio e imagen
    return jsonify({'productos': [{'id': p.id, 'nombre': p.nombre, 'precio': p.precio, 'imagen': p.imagen} for p in productos]})

@app.route('/productos/<int:producto_id>', methods=['GET'])
def obtener_producto(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    # Ahora incluimos precio e imagen
    return jsonify({'producto': {'id': producto.id, 'nombre': producto.nombre, 'precio': producto.precio, 'imagen': producto.imagen}})

@app.route('/productos', methods=['POST'])
def crear_producto():
    data = request.get_json()
    if not isinstance(data, list):
        return jsonify({'error': 'Por favor, envía una lista de productos'}), 400
    nuevos_productos = []
    for producto_data in data:
        # Validamos que los campos requeridos estén presentes
        if not all(key in producto_data for key in ['nombre', 'precio', 'imagen']):
            return jsonify({'error': 'Solicitud inválida. Faltan nombre, precio o imagen en un producto'}), 400
        
        nuevo_producto = Producto(
            nombre=producto_data['nombre'],
            precio=producto_data['precio'],
            imagen=producto_data['imagen']
        )
        db.session.add(nuevo_producto)
        db.session.flush() # Para obtener el ID antes del commit final
        nuevos_productos.append({
            'id': nuevo_producto.id,
            'nombre': nuevo_producto.nombre,
            'precio': nuevo_producto.precio,
            'imagen': nuevo_producto.imagen
        })
    db.session.commit()
    return jsonify({'productos_creados': nuevos_productos}), 201

@app.route('/productos/<int:producto_id>', methods=['PUT'])
def actualizar_producto(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Solicitud inválida'}), 400
    
    # Actualizamos todos los campos posibles
    producto.nombre = data.get('nombre', producto.nombre)
    producto.precio = data.get('precio', producto.precio)
    producto.imagen = data.get('imagen', producto.imagen)

    db.session.commit()
    return jsonify({
        'mensaje': 'Producto actualizado exitosamente',
        'producto': {
            'id': producto.id,
            'nombre': producto.nombre,
            'precio': producto.precio,
            'imagen': producto.imagen
        }
    })

@app.route('/productos/<int:producto_id>', methods=['DELETE'])
def eliminar_producto(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    db.session.delete(producto)
    db.session.commit()
    return jsonify({'resultado': True})

# --- CRUD para Stock (AJUSTADO: Eliminado 'precio' de la creación/actualización de stock) ---

@app.route('/stock', methods=['GET'])
def obtener_stock():
    stock_items = Stock.query.all()
    # Ya no se incluye 'precio' en el stock
    return jsonify({'stock': [{'sucursal_id': s.sucursal_id, 'producto_id': s.producto_id, 'cantidad': s.cantidad} for s in stock_items]})

@app.route('/sucursales/<int:sucursal_id>/productos/<int:producto_id>/stock', methods=['GET'])
def obtener_stock_sucursal_producto(sucursal_id, producto_id):
    stock_item = Stock.query.filter_by(sucursal_id=sucursal_id, producto_id=producto_id).first_or_404()
    # Ya no se incluye 'precio' en el stock
    return jsonify({'stock': {'sucursal_id': stock_item.sucursal_id, 'producto_id': stock_item.producto_id, 'cantidad': stock_item.cantidad}})

@app.route('/sucursales/<int:sucursal_id>/productos/<int:producto_id>/stock', methods=['POST'])
def crear_stock(sucursal_id, producto_id):
    if not request.get_json() or 'cantidad' not in request.get_json():
        return jsonify({'error': 'Solicitud inválida. Falta cantidad'}), 400
    
    # Asegúrate de que el producto y la sucursal existan
    sucursal = Sucursal.query.get(sucursal_id)
    producto = Producto.query.get(producto_id)
    if not sucursal:
        return jsonify({'error': f'Sucursal con ID {sucursal_id} no encontrada'}), 404
    if not producto:
        return jsonify({'error': f'Producto con ID {producto_id} no encontrado'}), 404

    # Verifica si ya existe stock para esta sucursal y producto
    existing_stock = Stock.query.filter_by(sucursal_id=sucursal_id, producto_id=producto_id).first()
    if existing_stock:
        return jsonify({'error': 'Ya existe stock para este producto en esta sucursal. Usa PUT para actualizar.'}), 409 # Conflict

    nuevo_stock = Stock(sucursal_id=sucursal_id, producto_id=producto_id, cantidad=request.get_json()['cantidad'])
    db.session.add(nuevo_stock)
    db.session.commit()
    return jsonify({'stock': {'sucursal_id': nuevo_stock.sucursal_id, 'producto_id': nuevo_stock.producto_id, 'cantidad': nuevo_stock.cantidad}}), 201

@app.route('/stock/bulk', methods=['POST'])
def crear_stock_bulk():
    data = request.get_json()
    if not isinstance(data, list):
        return jsonify({'error': 'Por favor, envía una lista de items de stock'}), 400
    stock_creados = []
    for item_data in data:
        # 'precio' ya no es necesario aquí para el stock
        if 'sucursal_id' not in item_data or 'producto_id' not in item_data or 'cantidad' not in item_data:
            return jsonify({'error': 'Solicitud inválida. Falta información en un item de stock (sucursal_id, producto_id, cantidad)'}), 400

        sucursal_id = item_data['sucursal_id']
        producto_id = item_data['producto_id']
        cantidad = item_data['cantidad']

        sucursal = Sucursal.query.get(sucursal_id)
        producto = Producto.query.get(producto_id)
        if not sucursal or not producto:
            return jsonify({'error': f'Sucursal o producto no encontrado para sucursal_id: {sucursal_id}, producto_id: {producto_id}'}), 400

        # Verifica si ya existe stock para esta combinación
        existing_stock = Stock.query.filter_by(sucursal_id=sucursal_id, producto_id=producto_id).first()
        if existing_stock:
            # Si ya existe, puedes elegir actualizarlo o saltarlo
            existing_stock.cantidad += cantidad # O = cantidad si se quiere sobrescribir
            db.session.add(existing_stock) # Para asegurar que los cambios se rastrean
            stock_creados.append({
                'accion': 'actualizado',
                'sucursal_id': existing_stock.sucursal_id,
                'producto_id': existing_stock.producto_id,
                'cantidad': existing_stock.cantidad
            })
        else:
            nuevo_stock = Stock(sucursal_id=sucursal_id, producto_id=producto_id, cantidad=cantidad)
            db.session.add(nuevo_stock)
            stock_creados.append({
                'accion': 'creado',
                'sucursal_id': nuevo_stock.sucursal_id,
                'producto_id': nuevo_stock.producto_id,
                'cantidad': nuevo_stock.cantidad
            })
    db.session.commit()
    return jsonify({'stock_procesado': stock_creados}), 201


@app.route('/sucursales/<int:sucursal_id>/productos/<int:producto_id>/stock', methods=['PUT'])
def actualizar_stock(sucursal_id, producto_id):
    stock_item = Stock.query.filter_by(sucursal_id=sucursal_id, producto_id=producto_id).first_or_404()
    data = request.get_json()
    if not data or 'cantidad' not in data:
        return jsonify({'error': 'Solicitud inválida. Falta la cantidad a actualizar'}), 400

    cantidad_nueva = data['cantidad'] # Asumo que 'cantidad' es la cantidad final, no un cambio incremental

    try:
        stock_item.cantidad = cantidad_nueva
        db.session.commit()
        # Ya no se incluye 'precio' en la respuesta de stock
        return jsonify({'stock': {'sucursal_id': stock_item.sucursal_id, 'producto_id': stock_item.producto_id, 'cantidad': stock_item.cantidad}})
    except SQLAlchemyError as e:
        db.session.rollback() # Importante hacer rollback en caso de error
        print(f"Error al actualizar el stock: {e}")
        return jsonify({'error': 'Ocurrió un error al actualizar el stock en la base de datos'}), 500

@app.route('/sucursales/<int:sucursal_id>/productos/<int:producto_id>/stock', methods=['DELETE'])
def eliminar_stock(sucursal_id, producto_id):
    stock_item = Stock.query.filter_by(sucursal_id=sucursal_id, producto_id=producto_id).first_or_404()
    db.session.delete(stock_item)
    db.session.commit()
    return jsonify({'resultado': True})

# --- CRUD Ventas (AJUSTADO para usar el precio del Producto) ---

# --- CRUD Ventas (AJUSTADO para usar el precio del Producto) ---

@app.route('/ventas', methods=['GET'])
def listar_ventas():

    ventas_db = Venta.query.order_by(Venta.fecha.desc()).all() 

    ventas_agrupadas = {}
    for venta in ventas_db:
        venta_id = venta.id
        if venta_id not in ventas_agrupadas:
            sucursal = Sucursal.query.get(venta.sucursal_id)
            ventas_agrupadas[venta_id] = {
                'id_venta': venta.id,
                'fecha': venta.fecha.strftime('%Y-%m-%d %H:%M:%S'),
                'sucursal_nombre': sucursal.nombre if sucursal else 'Sucursal desconocida',
                'total_venta': venta.total,
                'detalles': [] 
            }
        
        for detalle in venta.detalles:
            producto = Producto.query.get(detalle.producto_id)
            ventas_agrupadas[venta_id]['detalles'].append({
                'producto_nombre': producto.nombre if producto else 'Producto desconocido',
                'producto_imagen': producto.imagen if producto else None, 
                'cantidad': detalle.cantidad,
                'precio_unitario': detalle.precio_unitario, 
                'subtotal_detalle': detalle.cantidad * detalle.precio_unitario
            })
    
    ventas_para_html = list(ventas_agrupadas.values())

    
    return render_template('listar_ventas.html', ventas=ventas_para_html)


  



@app.route('/ventas', methods=['POST'])
def registrar_venta():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Datos no proporcionados'}), 400

    sucursal_id = data.get('sucursal_id')
    productos_en_venta = data.get('productos')  

    if not sucursal_id or not productos_en_venta:
        return jsonify({'error': 'Faltan datos: sucursal_id o productos'}), 400

    total_venta = 0
    detalles_venta = []

    try:
        for item in productos_en_venta:
            producto_id = item.get('producto_id')
            cantidad_vendida = item.get('cantidad')

            if not producto_id or not cantidad_vendida:
                return jsonify({'error': 'Producto o cantidad inválida en los detalles de la venta'}), 400

            # Obtener el producto para su precio e información
            producto = Producto.query.get(producto_id)
            if not producto:
                return jsonify({'error': f'Producto con ID {producto_id} no encontrado'}), 404

            # Obtener el stock para verificar disponibilidad y actualizar
            stock_item = Stock.query.filter_by(sucursal_id=sucursal_id, producto_id=producto_id).first()
            if not stock_item or stock_item.cantidad < cantidad_vendida:
                return jsonify({'error': f'Sin stock suficiente para el producto "{producto.nombre}" (ID {producto_id}) en la sucursal {sucursal_id}. Stock disponible: {stock_item.cantidad if stock_item else 0}'}), 400

            # Usar el precio del producto para el cálculo de la venta
            precio_unitario_producto = producto.precio # <--- ¡Precio del Producto!
            subtotal_detalle = cantidad_vendida * precio_unitario_producto
            total_venta += subtotal_detalle

            # Descontar del stock
            stock_item.cantidad -= cantidad_vendida

            # Crear detalle de venta
            detalle = DetalleVenta(
                producto_id=producto_id,
                cantidad=cantidad_vendida,
                precio_unitario=precio_unitario_producto # Registrar el precio del producto al momento de la venta
            )
            detalles_venta.append(detalle)

        # Crear la venta principal
        nueva_venta = Venta(
            sucursal_id=sucursal_id,
            fecha=datetime.utcnow(),
            total=total_venta
        )
        db.session.add(nueva_venta)
        db.session.flush()  # Obtener el ID de la venta antes de añadir los detalles

        # Asociar detalles con la venta
        for detalle in detalles_venta:
            detalle.venta_id = nueva_venta.id
            db.session.add(detalle)

        db.session.commit()

        return jsonify({'mensaje': 'Venta registrada exitosamente', 'venta_id': nueva_venta.id, 'total_venta': total_venta}), 201

    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"Error de base de datos al registrar la venta: {e}")
        return jsonify({'error': f'Error de base de datos al registrar la venta: {str(e)}'}), 500
    except Exception as e:
        db.session.rollback()
        print(f"Error inesperado al registrar la venta: {e}")
        return jsonify({'error': f'Error inesperado al registrar la venta: {str(e)}'}), 500

# --- Endpoint para obtener detalles de una venta específica (Nuevo) ---
@app.route('/ventas/<int:venta_id>', methods=['GET'])
def obtener_venta(venta_id):
    venta = Venta.query.get_or_404(venta_id)
    
    detalles_formato = []
    for detalle in venta.detalles:
        producto = Producto.query.get(detalle.producto_id)
        detalles_formato.append({
            'producto_id': detalle.producto_id,
            'producto_nombre': producto.nombre if producto else 'Desconocido',
            'producto_imagen': producto.imagen if producto else None,
            'cantidad': detalle.cantidad,
            'precio_unitario': detalle.precio_unitario
        })
    
    sucursal = Sucursal.query.get(venta.sucursal_id)

    return jsonify({
        'id': venta.id,
        'sucursal_id': venta.sucursal_id,
        'sucursal_nombre': sucursal.nombre if sucursal else 'Desconocida',
        'fecha': venta.fecha.strftime('%Y-%m-%d %H:%M:%S'),
        'total': venta.total,
        'detalles': detalles_formato
    })


# --- Endpoint para eliminar una venta (Nuevo) ---
@app.route('/ventas/<int:venta_id>', methods=['DELETE'])
def eliminar_venta(venta_id):
    venta = Venta.query.get_or_404(venta_id)
    
    try:
      
        DetalleVenta.query.filter_by(venta_id=venta.id).delete()
        
        # Eliminar la venta
        db.session.delete(venta)
        db.session.commit()
        return jsonify({'mensaje': 'Venta eliminada exitosamente'}), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': f'Error al eliminar la venta: {str(e)}'}), 500


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)