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
# Asegúrate de que tu carpeta grpc_stubs contiene un archivo __init__.py vacío
# Y que las importaciones dentro de mantenedor_productos_pb2_grpc.py sean relativas (from . import mantenedor_productos_pb2)
from grpc_stubs import mantenedor_productos_pb2
from grpc_stubs import mantenedor_productos_pb2_grpc

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
        # Espera un formato "Bearer mi_api_key_segura_abc123"
        if not token or not token.startswith("Bearer "):
            abort(401, description="No autorizado. Formato de token inválido o faltante.")
        
        # Extrae el token real después de "Bearer "
        actual_token = token.split("Bearer ")[1]
        
        if actual_token != API_TOKEN:
            abort(401, description="No autorizado. Token inválido.")
        return f(*args, **kwargs)
    return decorated_function

# --- Implementación del Servidor gRPC ---
class ProductMaintainerServicer(mantenedor_productos_pb2_grpc.ProductMaintainerServicer):
    def GetProduct(self, request, context):
        with app.app_context():
            # Usar db.session.get() para la API de SQLAlchemy 2.0
            product = db.session.get(Producto, request.product_id)
            if not product:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Producto no encontrado")
                return mantenedor_productos_pb2.Product()
            return mantenedor_productos_pb2.Product(
                id=product.id,
                nombre=product.nombre,
                precio=product.precio,
                imagen=product.imagen if product.imagen else ""
            )

    def GetAllProducts(self, request, context):
        with app.app_context():
            products = Producto.query.all()
            product_list = []
            for product in products:
                product_list.append(mantenedor_productos_pb2.Product(
                    id=product.id,
                    nombre=product.nombre,
                    precio=product.precio,
                    imagen=product.imagen if product.imagen else ""
                ))
            return mantenedor_productos_pb2.ProductList(products=product_list)

    def CreateProduct(self, request, context):
        with app.app_context():
            new_product = Producto(
                nombre=request.nombre,
                precio=request.precio,
                imagen=request.imagen if request.imagen else None
            )
            db.session.add(new_product)
            try:
                db.session.commit()
                return mantenedor_productos_pb2.Product(
                    id=new_product.id,
                    nombre=new_product.nombre,
                    precio=new_product.precio,
                    imagen=new_product.imagen if new_product.imagen else ""
                )
            except SQLAlchemyError as e:
                db.session.rollback()
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(f"Error de base de datos: {str(e)}")
                return mantenedor_productos_pb2.Product()

    def UpdateProduct(self, request, context):
        with app.app_context():
            # Usar db.session.get() para la API de SQLAlchemy 2.0
            product = db.session.get(Producto, request.id)
            if not product:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Producto no encontrado")
                return mantenedor_productos_pb2.Product()

            product.nombre = request.nombre
            product.precio = request.precio
            product.imagen = request.imagen if request.imagen else None

            try:
                db.session.commit()
                return mantenedor_productos_pb2.Product(
                    id=product.id,
                    nombre=product.nombre,
                    precio=product.precio,
                    imagen=product.imagen if product.imagen else ""
                )
            except SQLAlchemyError as e:
                db.session.rollback()
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(f"Error de base de datos: {str(e)}")
                return mantenedor_productos_pb2.Product()

    def DeleteProduct(self, request, context):
        with app.app_context():
            # Usar db.session.get() para la API de SQLAlchemy 2.0
            product = db.session.get(Producto, request.product_id)
            if not product:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Producto no encontrado")
                return mantenedor_productos_pb2.DeleteProductResponse(success=False, message="Producto no encontrado")

            try:
                db.session.delete(product)
                db.session.commit()
                return mantenedor_productos_pb2.DeleteProductResponse(success=True, message="Producto eliminado exitosamente")
            except SQLAlchemyError as e:
                db.session.rollback()
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(f"Error de base de datos: {str(e)}")
                return mantenedor_productos_pb2.DeleteProductResponse(success=False, message=f"Error de base de datos: {str(e)}")

    def UploadProductImage(self, request_iterator, context):
        with app.app_context():
            file_data = b''
            product_id = None
            filename = None
            first_chunk = True

            for request_chunk in request_iterator:
                if first_chunk:
                    product_id = request_chunk.product_id
                    filename = request_chunk.filename
                    first_chunk = False
                file_data += request_chunk.chunk_data

            if product_id is None or filename is None:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("Se requiere ID de producto y nombre de archivo.")
                return mantenedor_productos_pb2.UploadProductImageResponse(success=False, message="Falta ID de producto o nombre de archivo")

            # Usar db.session.get() para la API de SQLAlchemy 2.0
            product = db.session.get(Producto, product_id)
            if not product:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Producto no encontrado para la carga de imagen.")
                return mantenedor_productos_pb2.UploadProductImageResponse(success=False, message="Producto no encontrado")

            # Generar un nombre de archivo único para evitar colisiones
            base, ext = os.path.splitext(filename)
            unique_filename = f"{product_id}_{int(time.time())}{ext}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

            try:
                with open(file_path, 'wb') as f:
                    f.write(file_data)

                # Actualizar la ruta de la imagen del producto en la base de datos
                relative_image_url = f"/static/uploads/product_images/{unique_filename}"
                product.imagen = relative_image_url
                db.session.commit()

                return mantenedor_productos_pb2.UploadProductImageResponse(
                    success=True,
                    image_url=relative_image_url,
                    message="Imagen subida exitosamente"
                )
            except IOError as e:
                db.session.rollback()
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(f"Error del sistema de archivos: {str(e)}")
                return mantenedor_productos_pb2.UploadProductImageResponse(success=False, message=f"Error del sistema de archivos: {str(e)}")
            except SQLAlchemyError as e:
                db.session.rollback()
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(f"Error de base de datos al actualizar la ruta de la imagen: {str(e)}")
                return mantenedor_productos_pb2.UploadProductImageResponse(success=False, message=f"Error de base de datos: {str(e)}")

def serve_grpc():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    mantenedor_productos_pb2_grpc.add_ProductMaintainerServicer_to_server(
        ProductMaintainerServicer(), server
    )
    # **CORRECCIÓN CLAVE: Cambiar '[::]' a '0.0.0.0' para evitar problemas de binding IPv6**
    server.add_insecure_port('0.0.0.0:50051') 
    server.start()
    print("Servidor gRPC iniciado en el puerto 50051")
    server.wait_for_termination()

# --- Rutas de Flask ---

# **CORRECCIÓN CLAVE: Renombrar la función 'index' duplicada a 'home_page'**
@app.route('/')
def home_page(): # Renombrada de 'index' para evitar conflicto
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


# Endpoint de la API de Flask para obtener todos los productos (usado por el frontend)
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


# API de Flask para manejar llamadas gRPC desde el frontend (actuando como pasarela)
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
        # Esto solo envía un 'ping' periódico.
        # Para eventos dinámicos (e.g., stock bajo), necesitarías un mecanismo de cola de mensajes
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
    # Busca productos por nombre
    productos_encontrados = Producto.query.filter(db.func.lower(Producto.nombre) == nombre_producto.lower()).all()

    for producto in productos_encontrados:
        # Busca el stock de este producto en todas las sucursales
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

            
                # Para un sistema de notificación en tiempo real, deberías usar:
                # 1. Una librería como Flask-SSE (que se integra con Redis u otra cola de mensajes).
                # 2. Un sistema de cola de mensajes (RabbitMQ, Kafka) con un microservicio de Websockets/SSE.
       
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
    # Usar db.session.get() para la API de SQLAlchemy 2.0
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
    # Usar db.session.get() para la API de SQLAlchemy 2.0
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
    # Usar db.session.get() para la API de SQLAlchemy 2.0
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

@app.route('/productos', methods=['GET'])
def obtener_productos():
    productos = Producto.query.all()
    return jsonify({'productos': [{'id': p.id, 'nombre': p.nombre, 'precio': p.precio, 'imagen': p.imagen} for p in productos]})

@app.route('/productos/<int:producto_id>', methods=['GET'])
def obtener_producto(producto_id):
    # Usar db.session.get() para la API de SQLAlchemy 2.0
    producto = db.session.get(Producto, producto_id)
    if not producto:
        abort(404, description="Producto no encontrado")
    return jsonify({'producto': {'id': producto.id, 'nombre': producto.nombre, 'precio': producto.precio, 'imagen': producto.imagen}})

@app.route('/productos', methods=['POST'])
def crear_producto():
    data = request.get_json()
    if not isinstance(data, list):
        return jsonify({'error': 'Por favor, envía una lista de productos'}), 400
    nuevos_productos = []
    try:
        for producto_data in data:
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
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': f'Error al crear productos: {str(e)}'}), 500


@app.route('/productos/<int:producto_id>', methods=['PUT'])
def actualizar_producto(producto_id):
    # Usar db.session.get() para la API de SQLAlchemy 2.0
    producto = db.session.get(Producto, producto_id)
    if not producto:
        abort(404, description="Producto no encontrado")
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Solicitud inválida'}), 400
    
    producto.nombre = data.get('nombre', producto.nombre)
    producto.precio = data.get('precio', producto.precio)
    producto.imagen = data.get('imagen', producto.imagen)

    try:
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
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'error': f'Error al actualizar producto: {str(e)}'}), 500


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
    
    # Asegúrate de que el producto y la sucursal existan
    # Usar db.session.get() para la API de SQLAlchemy 2.0
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

            # Usar db.session.get() para la API de SQLAlchemy 2.0
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
            # Usar db.session.get() para la API de SQLAlchemy 2.0
            sucursal = db.session.get(Sucursal, venta.sucursal_id)
            ventas_agrupadas[venta_id] = {
                'id_venta': venta.id,
                'fecha': venta.fecha.strftime('%Y-%m-%d'),
                'sucursal_nombre': sucursal.nombre if sucursal else 'Sucursal desconocida',
                'total_venta': venta.total,
                'detalles': [] 
            }
        
        for detalle in venta.detalles:
            # Usar db.session.get() para la API de SQLAlchemy 2.0
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
        # Usar db.session.get() para la API de SQLAlchemy 2.0
        sucursal_existente = db.session.get(Sucursal, sucursal_id)
        if not sucursal_existente:
            return jsonify({'error': f'Sucursal con ID {sucursal_id} no encontrada'}), 404

        for item in productos_en_venta:
            producto_id = item.get('producto_id')
            cantidad_vendida = item.get('cantidad')

            if not producto_id or not cantidad_vendida or not isinstance(cantidad_vendida, int) or cantidad_vendida <= 0:
                return jsonify({'error': 'Producto, cantidad o formato de cantidad inválida en los detalles de la venta'}), 400

            # Obtener el producto para su precio e información
            # Usar db.session.get() para la API de SQLAlchemy 2.0
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
        db.session.rollback() # Revertir cambios en caso de cualquier error
        return jsonify({'error': f'Error en la base de datos al registrar la venta: {str(e)}'}), 500
    except Exception as e:
        db.session.rollback() # Revertir cambios por otros errores no específicos de DB
        return jsonify({'error': f'Error inesperado al registrar la venta: {str(e)}'}), 500


if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Crear tablas si no existen

    # Ejecutar el servidor gRPC en un hilo separado
    import threading
    grpc_thread = threading.Thread(target=serve_grpc)
    grpc_thread.daemon = True # Permite que el programa principal se cierre incluso si el hilo gRPC está ejecutándose
    grpc_thread.start()

    # Ejecutar la aplicación Flask
    app.run(debug=True, port=5000)