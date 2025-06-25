from flask import Flask, jsonify, request, render_template, Response, abort
from models import db, Sucursal, Producto, Stock, Venta, DetalleVenta
from sqlalchemy.exc import SQLAlchemyError
import time
import json
from datetime import datetime
from functools import wraps
import grpc
from concurrent import futures
import os
import shutil 

# Importar stubs gRPC generados
from grpc_stubs import mantenedor_productos_pb2,mantenedor_productos_pb2_grpc


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:@localhost/tienda'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
app.debug = True

API_TOKEN = "mi_api_key_segura_abc123"

UPLOAD_FOLDER = 'static/uploads/product_images'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- Autenticación y Decorador ---
def require_api_token(f):
    """Decorador para requerir un token de API en los headers de la solicitud."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
       
        if not token or not token.startswith("Bearer "):
            abort(401, description="No autorizado. Formato de token inválido o faltante.")
        
        # Extrae el token real después de "Bearer "
        actual_token = token.split("Bearer ")[1]
        
        if actual_token != API_TOKEN:
            abort(401, description="No autorizado. Token inválido.")
        return f(*args, **kwargs)
    return decorated_function

# --- Rutas de Flask ---

@app.route('/')
def home_page(): 
    return render_template('index.html')

@app.route('/mantenedor')
def product_maintainer():
    return render_template('mantenedor_productos.html')

@app.route('/mantenedor/agregar')
def add_product_page():
    return render_template('agregar_producto.html')

@app.route('/mantenedor/editar/<int:product_id>')
def edit_product_page(product_id):
    return render_template('editar_producto.html', product_id=product_id)

@app.route('/pagar.html')
def pagar_page():
    return render_template('pagar.html')

@app.route('/gracias.html')
def gracias_page():
    return render_template('gracias.html')



@app.route('/api/products', methods=['GET'])
def get_products_api():
    with grpc.insecure_channel('localhost:50051') as channel:
        stub = mantenedor_productos_pb2_grpc.ProductMaintainerStub(channel)
        try:
            response = stub.GetAllProducts(mantenedor_productos_pb2.GetAllProductsRequest())
            products_data = []
            for product in response.products:
                products_data.append({
                    'id': product.id,
                    'nombre': product.nombre,
                    'precio': product.precio,
                    'imagen': product.imagen
                })
            return jsonify(products_data)
        except grpc.RpcError as e:
            abort(e.code().value[0], description=e.details())



@app.route('/api/grpc/product/<int:product_id>', methods=['GET'])
def grpc_get_product(product_id):
    with grpc.insecure_channel('localhost:50051') as channel:
        stub = mantenedor_productos_pb2_grpc.ProductMaintainerStub(channel)
        try:
            response = stub.GetProduct(mantenedor_productos_pb2.GetProductRequest(product_id=product_id))
            return jsonify({
                'id': response.id,
                'nombre': response.nombre,
                'precio': response.precio,
                'imagen': response.imagen
            })
        except grpc.RpcError as e:
            abort(e.code().value[0], description=e.details())

@app.route('/api/grpc/product', methods=['POST'])
def grpc_create_product():
    data = request.json
    with grpc.insecure_channel('localhost:50051') as channel:
        stub = mantenedor_productos_pb2_grpc.ProductMaintainerStub(channel)
        try:
            response = stub.CreateProduct(mantenedor_productos_pb2.CreateProductRequest(
                nombre=data['nombre'],
                precio=float(data['precio']),
                imagen=data.get('imagen', '')
            ))
            return jsonify({
                'id': response.id,
                'nombre': response.nombre,
                'precio': response.precio,
                'imagen': response.imagen
            }), 201
        except grpc.RpcError as e:
            abort(e.code().value[0], description=e.details())

@app.route('/api/grpc/product/<int:product_id>', methods=['PUT'])
def grpc_update_product(product_id):
    data = request.json
    with grpc.insecure_channel('localhost:50051') as channel:
        stub = mantenedor_productos_pb2_grpc.ProductMaintainerStub(channel)
        try:
            response = stub.UpdateProduct(mantenedor_productos_pb2.UpdateProductRequest(
                id=product_id,
                nombre=data['nombre'],
                precio=float(data['precio']),
                imagen=data.get('imagen', '')
            ))
            return jsonify({
                'id': response.id,
                'nombre': response.nombre,
                'precio': response.precio,
                'imagen': response.imagen
            })
        except grpc.RpcError as e:
            abort(e.code().value[0], description=e.details())

@app.route('/api/grpc/product/<int:product_id>', methods=['DELETE'])
def grpc_delete_product(product_id):
    with grpc.insecure_channel('localhost:50051') as channel:
        stub = mantenedor_productos_pb2_grpc.ProductMaintainerStub(channel)
        try:
            response = stub.DeleteProduct(mantenedor_productos_pb2.DeleteProductRequest(product_id=product_id))
            if response.success:
                return jsonify({'message': response.message}), 200
            else:
                abort(400, description=response.message)
        except grpc.RpcError as e:
            abort(e.code().value[0], description=e.details())

@app.route('/api/grpc/upload_image/<int:product_id>', methods=['POST'])
def grpc_upload_image(product_id):
    if 'image' not in request.files:
        abort(400, "No se proporcionó archivo de imagen.")

    file = request.files['image']
    if file.filename == '':
        abort(400, "No se seleccionó ningún archivo.")

    if file:
        def generate_chunks():
            # Enviar el chunk inicial con product_id y filename
            yield mantenedor_productos_pb2.UploadProductImageRequest(
                product_id=product_id,
                filename=file.filename
            )
            while True:
                chunk = file.read(4096)  # Leer en chunks de 4KB
                if not chunk:
                    break
                yield mantenedor_productos_pb2.UploadProductImageRequest(chunk_data=chunk)

        with grpc.insecure_channel('localhost:50051') as channel:
            stub = mantenedor_productos_pb2_grpc.ProductMaintainerStub(channel)
            try:
                response = stub.UploadProductImage(generate_chunks())
                if response.success:
                    return jsonify({'message': response.message, 'image_url': response.image_url}), 200
                else:
                    abort(400, description=response.message)
            except grpc.RpcError as e:
                abort(e.code().value[0], description=e.details())

# --- Server-Sent Events (SSE) ---
sse_clients = []

def sse_event_generator():
    """Generador que envía 'ping' a los clientes SSE para mantener la conexión."""
    while True:
            # o una librería SSE más robusta (como Flask-SSE) para empujar mensajes a los clientes conectados.
        time.sleep(10) # Intervalo para enviar pings
        yield f"event: ping\ndata: {json.dumps({'time': datetime.now().isoformat()})}\n\n"

@app.route('/stream')
def sse_stream():
    """Endpoint para la conexión SSE."""
    response = Response(sse_event_generator(), mimetype='text/event-stream')
    return response

# --- BUSCAR PRODUCTO (AJUSTADO) ---
@app.route('/buscar_producto', methods=['GET'])
def buscar_producto():
    nombre_producto = request.args.get('nombre')
    if not nombre_producto:
        return jsonify({'error': 'Por favor, proporciona un nombre de producto'}), 400

    resultados = []
    
    productos_encontrados = Producto.query.filter(db.func.lower(Producto.nombre) == nombre_producto.lower()).all()

    for producto in productos_encontrados:
     
        stock_items = Stock.query.filter_by(producto_id=producto.id).all()
        for item_stock in stock_items:
            # Usar db.session.get() para la API de SQLAlchemy 2.0
            sucursal = db.session.get(Sucursal, item_stock.sucursal_id)
            if sucursal:
                resultado = {
                    'producto_id': producto.id,
                    'producto_nombre': producto.nombre,
                    'precio': producto.precio,
                    'imagen': producto.imagen,
                    'stock_disponible': item_stock.cantidad,
                    'sucursal_id': sucursal.id,
                    'sucursal_nombre': sucursal.nombre
                }
                resultados.append(resultado)
    
                if item_stock.cantidad == 0:
                    print(f"ALERTA STOCK 0: ¡El producto {producto.nombre} en la sucursal {sucursal.nombre} tiene stock 0!")
    return jsonify({'resultados': resultados})

# --- CRUD para Sucursales ---

@app.route('/sucursales', methods=['GET'])
def obtener_sucursales():
    sucursales = Sucursal.query.all()
    return jsonify({'sucursales': [{'id': s.id, 'nombre': s.nombre, 'direccion': s.direccion} for s in sucursales]})

@app.route('/sucursales/<int:sucursal_id>', methods=['GET'])
def obtener_sucursal(sucursal_id):
  
    sucursal = db.session.get(Sucursal, sucursal_id)
    if not sucursal:
        abort(404, description="Sucursal no encontrada")
    return jsonify({'sucursal': {'id': sucursal.id, 'nombre': sucursal.nombre, 'direccion': sucursal.direccion}})

@app.route('/sucursales', methods=['POST'])
@require_api_token
def crear_sucursal():
    data = request.get_json()
    if not isinstance(data, list):
        return jsonify({'error': 'Por favor, envía una lista de sucursales'}), 400
    nuevas_sucursales = []
    try:
        for sucursal_data in data:
            if 'nombre' not in sucursal_data or 'direccion' not in sucursal_data:
                return jsonify({'error': 'Solicitud inválida. Falta nombre o dirección en una sucursal'}), 400
            nueva_sucursal = Sucursal(nombre=sucursal_data['nombre'], direccion=sucursal_data['direccion'])
            db.session.add(nueva_sucursal)
            db.session.flush() # Para obtener el ID antes del commit final
            nuevas_sucursales.append({'id': nueva_sucursal.id, 'nombre': nueva_sucursal.nombre, 'direccion': nueva_sucursal.direccion})
        db.session.commit()
        return jsonify({'sucursales_creadas': nuevas_sucursales}), 201
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': f'Error al crear sucursales: {str(e)}'}), 500


@app.route('/sucursales/<int:sucursal_id>', methods=['PUT'])
def actualizar_sucursal(sucursal_id):
   
    sucursal = db.session.get(Sucursal, sucursal_id)
    if not sucursal:
        abort(404, description="Sucursal no encontrada")
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Solicitud inválida'}), 400
    sucursal.nombre = data.get('nombre', sucursal.nombre)
    sucursal.direccion = data.get('direccion', sucursal.direccion)
    try:
        db.session.commit()
        return jsonify({'sucursal': {'id': sucursal.id, 'nombre': sucursal.nombre, 'direccion': sucursal.direccion}})
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': f'Error al actualizar sucursal: {str(e)}'}), 500


@app.route('/sucursales/<int:sucursal_id>', methods=['DELETE'])
def eliminar_sucursal(sucursal_id):
    
    sucursal = db.session.get(Sucursal, sucursal_id)
    if not sucursal:
        abort(404, description="Sucursal no encontrada")
    try:
        db.session.delete(sucursal)
        db.session.commit()
        return jsonify({'resultado': True, 'message': 'Sucursal eliminada exitosamente'})
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': f'Error al eliminar sucursal: {str(e)}'}), 500

# --- CRUD para Productos (AJUSTADO) ---


@app.route('/productos/<int:producto_id>', methods=['DELETE'])
def eliminar_producto(producto_id):
    # Usar db.session.get() para la API de SQLAlchemy 2.0
    producto = db.session.get(Producto, producto_id)
    if not producto:
        abort(404, description="Producto no encontrado")
    try:
        db.session.delete(producto)
        db.session.commit()
        return jsonify({'resultado': True, 'message': 'Producto eliminado exitosamente'})
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': f'Error al eliminar producto: {str(e)}'}), 500


# --- CRUD para Stock ---

@app.route('/stock', methods=['GET'])
def obtener_stock():
    stock_items = Stock.query.all()
    return jsonify({'stock': [{'sucursal_id': s.sucursal_id, 'producto_id': s.producto_id, 'cantidad': s.cantidad} for s in stock_items]})

@app.route('/sucursales/<int:sucursal_id>/productos/<int:producto_id>/stock', methods=['GET'])
def obtener_stock_sucursal_producto(sucursal_id, producto_id):
    stock_item = Stock.query.filter_by(sucursal_id=sucursal_id, producto_id=producto_id).first()
    if not stock_item:
        abort(404, description="Stock no encontrado para esta sucursal y producto")
    return jsonify({'stock': {'sucursal_id': stock_item.sucursal_id, 'producto_id': stock_item.producto_id, 'cantidad': stock_item.cantidad}})

@app.route('/sucursales/<int:sucursal_id>/productos/<int:producto_id>/stock', methods=['POST'])
def crear_stock(sucursal_id, producto_id):
    if not request.get_json() or 'cantidad' not in request.get_json():
        return jsonify({'error': 'Solicitud inválida. Falta cantidad'}), 400
    
   
    sucursal = db.session.get(Sucursal, sucursal_id)
    producto = db.session.get(Producto, producto_id)
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
    try:
        db.session.commit()
        return jsonify({'stock': {'sucursal_id': nuevo_stock.sucursal_id, 'producto_id': nuevo_stock.producto_id, 'cantidad': nuevo_stock.cantidad}}), 201
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': f'Error al crear stock: {str(e)}'}), 500


@app.route('/stock/bulk', methods=['POST'])
def crear_stock_bulk():
    data = request.get_json()
    if not isinstance(data, list):
        return jsonify({'error': 'Por favor, envía una lista de items de stock'}), 400
    stock_procesados = []
    try:
        for item_data in data:
            if 'sucursal_id' not in item_data or 'producto_id' not in item_data or 'cantidad' not in item_data:
                return jsonify({'error': 'Solicitud inválida. Falta información en un item de stock (sucursal_id, producto_id, cantidad)'}), 400

            sucursal_id = item_data['sucursal_id']
            producto_id = item_data['producto_id']
            cantidad = item_data['cantidad']

         
            sucursal = db.session.get(Sucursal, sucursal_id)
            producto = db.session.get(Producto, producto_id)
            if not sucursal or not producto:
                return jsonify({'error': f'Sucursal o producto no encontrado para sucursal_id: {sucursal_id}, producto_id: {producto_id}'}), 400

            existing_stock = Stock.query.filter_by(sucursal_id=sucursal_id, producto_id=producto_id).first()
            if existing_stock:
                existing_stock.cantidad += cantidad # O = cantidad si se quiere sobrescribir
                db.session.add(existing_stock) # Para asegurar que los cambios se rastrean
                stock_procesados.append({
                    'accion': 'actualizado',
                    'sucursal_id': existing_stock.sucursal_id,
                    'producto_id': existing_stock.producto_id,
                    'cantidad': existing_stock.cantidad
                })
            else:
                nuevo_stock = Stock(sucursal_id=sucursal_id, producto_id=producto_id, cantidad=cantidad)
                db.session.add(nuevo_stock)
                stock_procesados.append({
                    'accion': 'creado',
                    'sucursal_id': nuevo_stock.sucursal_id,
                    'producto_id': nuevo_stock.producto_id,
                    'cantidad': nuevo_stock.cantidad
                })
        db.session.commit()
        return jsonify({'stock_procesado': stock_procesados}), 201
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': f'Error al procesar stock en masa: {str(e)}'}), 500


@app.route('/sucursales/<int:sucursal_id>/productos/<int:producto_id>/stock', methods=['PUT'])
def actualizar_stock(sucursal_id, producto_id):
    stock_item = Stock.query.filter_by(sucursal_id=sucursal_id, producto_id=producto_id).first()
    if not stock_item:
        abort(404, description="Stock no encontrado para esta sucursal y producto")

    data = request.get_json()
    if not data or 'cantidad' not in data:
        return jsonify({'error': 'Solicitud inválida. Falta la cantidad a actualizar'}), 400

    cantidad_nueva = data['cantidad'] 

    try:
        stock_item.cantidad = cantidad_nueva
        db.session.commit()
        return jsonify({'stock': {'sucursal_id': stock_item.sucursal_id, 'producto_id': stock_item.producto_id, 'cantidad': stock_item.cantidad}})
    except SQLAlchemyError as e:
        db.session.rollback()
        print(f"Error al actualizar el stock: {e}")
        return jsonify({'error': 'Ocurrió un error al actualizar el stock en la base de datos'}), 500

@app.route('/sucursales/<int:sucursal_id>/productos/<int:producto_id>/stock', methods=['DELETE'])
def eliminar_stock(sucursal_id, producto_id):
    stock_item = Stock.query.filter_by(sucursal_id=sucursal_id, producto_id=producto_id).first()
    if not stock_item:
        abort(404, description="Stock no encontrado para esta sucursal y producto")
    try:
        db.session.delete(stock_item)
        db.session.commit()
        return jsonify({'resultado': True, 'message': 'Stock eliminado exitosamente'})
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': f'Error al eliminar stock: {str(e)}'}), 500


# --- CRUD Ventas ---
@app.route('/ventas', methods=['GET'])
def listar_ventas():
    ventas_db = Venta.query.order_by(Venta.fecha.desc()).all() 

    ventas_agrupadas = {}
    for venta in ventas_db:
        venta_id = venta.id
        if venta_id not in ventas_agrupadas:
            
            sucursal = db.session.get(Sucursal, venta.sucursal_id)
            ventas_agrupadas[venta_id] = {
                'id_venta': venta.id,
                'fecha': venta.fecha.strftime('%Y-%m-%d'),
                'sucursal_nombre': sucursal.nombre if sucursal else 'Sucursal desconocida',
                'total_venta': venta.total,
                'detalles': [] 
            }
        
        for detalle in venta.detalles:
            
            producto = db.session.get(Producto, detalle.producto_id)
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
        
        sucursal_existente = db.session.get(Sucursal, sucursal_id)
        if not sucursal_existente:
            return jsonify({'error': f'Sucursal con ID {sucursal_id} no encontrada'}), 404

        for item in productos_en_venta:
            producto_id = item.get('producto_id')
            cantidad_vendida = item.get('cantidad')

            if not producto_id or not cantidad_vendida or not isinstance(cantidad_vendida, int) or cantidad_vendida <= 0:
                return jsonify({'error': 'Producto, cantidad o formato de cantidad inválida en los detalles de la venta'}), 400

            # Obtener el producto para su precio e información
         
            producto = db.session.get(Producto, producto_id)
            if not producto:
                return jsonify({'error': f'Producto con ID {producto_id} no encontrado'}), 404

            # Obtener el stock para verificar disponibilidad y actualizar
            stock_item = Stock.query.filter_by(sucursal_id=sucursal_id, producto_id=producto_id).first()
            if not stock_item or stock_item.cantidad < cantidad_vendida:
                return jsonify({'error': f'Sin stock suficiente para el producto "{producto.nombre}" (ID {producto_id}) en la sucursal {sucursal_existente.nombre}. Stock disponible: {stock_item.cantidad if stock_item else 0}'}), 400
            
            # Actualizar stock
            stock_item.cantidad -= cantidad_vendida
            db.session.add(stock_item) # Marcar para actualización

            # Calcular subtotal y acumular total
            precio_unitario_producto = producto.precio
            subtotal_item = precio_unitario_producto * cantidad_vendida
            total_venta += subtotal_item

            detalles_venta.append(DetalleVenta(
                producto_id=producto_id,
                cantidad=cantidad_vendida,
                precio_unitario=precio_unitario_producto
            ))
        
        # Crear la venta principal
        nueva_venta = Venta(
            sucursal_id=sucursal_id,
            fecha=datetime.now(),
            total=total_venta,
            detalles=detalles_venta # Asigna la lista de DetalleVenta
        )
        db.session.add(nueva_venta)
        db.session.commit()

        return jsonify({
            'mensaje': 'Venta registrada exitosamente',
            'venta_id': nueva_venta.id,
            'total_venta': nueva_venta.total,
            'fecha': nueva_venta.fecha.strftime('%Y-%m-%d %H:%M:%S')
        }), 201

    except SQLAlchemyError as e:
        db.session.rollback() 
        return jsonify({'error': f'Error en la base de datos al registrar la venta: {str(e)}'}), 500
    except Exception as e:
        db.session.rollback() 
        return jsonify({'error': f'Error inesperado al registrar la venta: {str(e)}'}), 500


if __name__ == '__main__':

    with app.app_context():
        db.create_all() 

    app.run(debug=True, port=5000)