from flask import Flask, jsonify, request, render_template,Response
from models import db, Sucursal, Producto, Stock
from sqlalchemy.exc import SQLAlchemyError
import time
import json


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:@localhost/tienda'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False 
db.init_app(app)
app.debug = True

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
            # Aquí =>lógica más compleja para determinar cuándo enviar un evento
            #  solo envia un "ping" para mantener la conexión activa
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
        sse_clients.append(request)
        # respuesta generada de la coneccion 
        yield f"data: {json.dumps({'mensaje': 'Conexión SSE establecida'})}\n\n"
        try:
            yield from eventos_sse()
        finally:
            if request in sse_clients:
                sse_clients.remove(request)
            print("Cliente SSE desconectado.")
    return Response(generate(), mimetype='text/event-stream')

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
            sucursal = Sucursal.query.get(item_stock.sucursal_id)
            if sucursal:
                resultado = {
                    'producto': producto.nombre,
                    'precio': item_stock.precio,
                    'stock': item_stock.cantidad,
                    'sucursal': sucursal.nombre,
                    'sucursal_id': sucursal.id,
                    'producto_id': producto.id
                }
                resultados.append(resultado)
                if item_stock.cantidad == 0:
                    # Enviar alerta SSE si la cantidad es 0
                    for client in sse_clients:
                        try:
                            client.environ['werkzeug.server.shutdown'](f"data: {json.dumps({'mensaje': f'¡Alerta! El producto {producto.nombre} en la sucursal {sucursal.nombre} tiene stock 0'})}\n\n".encode('utf-8'))
                        except:
                            sse_clients.remove(client)
                            print("Error al enviar alerta SSE.")

    return jsonify({'resultados': resultados})



# --- CRUD para Sucursales ---

@app.route('/sucursales', methods=['GET'])
def obtener_sucursales():
    sucursales = Sucursal.query.all()
    return jsonify({'sucursales': [{'id': s.id, 'nombre': s.nombre, 'direccion': s.direccion} for s in sucursales]})

@app.route('/sucursales/<int:sucursal_id>', methods=['GET'])
def obtener_sucursal(sucursal_id):
    sucursal = Sucursal.query.get_or_404(sucursal_id)
    return jsonify({'sucursal': {'id': sucursal.id, 'nombre': sucursal.nombre, 'direccion': sucursal.direccion}})

# para ingresar lista json sucursales 

@app.route('/sucursales', methods=['POST'])
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

# --- CRUD para Productos ---

@app.route('/productos', methods=['GET'])
def obtener_productos():
    productos = Producto.query.all()
    return jsonify({'productos': [{'id': p.id, 'nombre': p.nombre} for p in productos]})

@app.route('/productos/<int:producto_id>', methods=['GET'])
def obtener_producto(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    return jsonify({'producto': {'id': producto.id, 'nombre': producto.nombre}})

# para ingresar lista json productos
@app.route('/productos', methods=['POST'])
def crear_producto():
    data = request.get_json()
    if not isinstance(data, list):
        return jsonify({'error': 'Por favor, envía una lista de productos'}), 400
    nuevos_productos = []
    for producto_data in data:
        if 'nombre' not in producto_data:
            return jsonify({'error': 'Solicitud inválida. Falta el nombre en un producto'}), 400
        nuevo_producto = Producto(nombre=producto_data['nombre'])
        db.session.add(nuevo_producto)
        nuevos_productos.append({'id': nuevo_producto.id, 'nombre': nuevo_producto.nombre})
    db.session.commit()
    return jsonify({'productos_creados': nuevos_productos}), 201

@app.route('/productos/<int:producto_id>', methods=['PUT'])
def actualizar_producto(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    data = request.get_json()
    if not data or 'nombre' not in data:
        return jsonify({'error': 'Solicitud inválida. Falta el nombre'}), 400
    producto.nombre = data['nombre']
    db.session.commit()
    return jsonify({'producto': {'id': producto.id, 'nombre': producto.nombre}})

@app.route('/productos/<int:producto_id>', methods=['DELETE'])
def eliminar_producto(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    db.session.delete(producto)
    db.session.commit()
    return jsonify({'resultado': True})

# --- CRUD para Stock ---

@app.route('/stock', methods=['GET'])
def obtener_stock():
    stock_items = Stock.query.all()
    return jsonify({'stock': [{'sucursal_id': s.sucursal_id, 'producto_id': s.producto_id, 'cantidad': s.cantidad, 'precio': s.precio} for s in stock_items]})

@app.route('/sucursales/<int:sucursal_id>/productos/<int:producto_id>/stock', methods=['GET'])
def obtener_stock_sucursal_producto(sucursal_id, producto_id):
    stock_item = Stock.query.filter_by(sucursal_id=sucursal_id, producto_id=producto_id).first_or_404()
    return jsonify({'stock': {'sucursal_id': stock_item.sucursal_id, 'producto_id': stock_item.producto_id, 'cantidad': stock_item.cantidad, 'precio': stock_item.precio}})

@app.route('/sucursales/<int:sucursal_id>/productos/<int:producto_id>/stock', methods=['POST'])
def crear_stock(sucursal_id, producto_id):
    if not request.get_json() or 'cantidad' not in request.get_json() or 'precio' not in request.get_json():
        return jsonify({'error': 'Solicitud inválida. Falta cantidad o precio'}), 400
    nuevo_stock = Stock(sucursal_id=sucursal_id, producto_id=producto_id, cantidad=request.get_json()['cantidad'], precio=request.get_json()['precio'])
    db.session.add(nuevo_stock)
    db.session.commit()
    return jsonify({'stock': {'sucursal_id': nuevo_stock.sucursal_id, 'producto_id': nuevo_stock.producto_id, 'cantidad': nuevo_stock.cantidad, 'precio': nuevo_stock.precio}}), 201


# para ingresar lista json stock
@app.route('/stock/bulk', methods=['POST'])
def crear_stock_bulk():
    data = request.get_json()
    if not isinstance(data, list):
        return jsonify({'error': 'Por favor, envía una lista de items de stock'}), 400
    stock_creados = []
    for item_data in data:
        if 'sucursal_id' not in item_data or 'producto_id' not in item_data or 'cantidad' not in item_data or 'precio' not in item_data:
            return jsonify({'error': 'Solicitud inválida. Falta información en un item de stock'}), 400

        sucursal_id = item_data['sucursal_id']
        producto_id = item_data['producto_id']
        cantidad = item_data['cantidad']
        precio = item_data['precio']

        # Verificar si la sucursal y el producto existen (opcional pero recomendado)
        sucursal = Sucursal.query.get(sucursal_id)
        producto = Producto.query.get(producto_id)
        if not sucursal or not producto:
            return jsonify({'error': f'Sucursal o producto no encontrado para sucursal_id: {sucursal_id}, producto_id: {producto_id}'}), 400

        nuevo_stock = Stock(sucursal_id=sucursal_id, producto_id=producto_id, cantidad=cantidad, precio=precio)
        db.session.add(nuevo_stock)
        stock_creados.append({
            'sucursal_id': nuevo_stock.sucursal_id,
            'producto_id': nuevo_stock.producto_id,
            'cantidad': nuevo_stock.cantidad,
            'precio': nuevo_stock.precio
        })
    db.session.commit()
    return jsonify({'stock_creado': stock_creados}), 201


@app.route('/sucursales/<int:sucursal_id>/productos/<int:producto_id>/stock', methods=['PUT'])
def actualizar_stock(sucursal_id, producto_id):
    stock_item = Stock.query.filter_by(sucursal_id=sucursal_id, producto_id=producto_id).first_or_404()
    data = request.get_json()
    if not data or 'cantidad' not in data:
        return jsonify({'error': 'Solicitud inválida. Falta la cantidad a actualizar'}), 400

    cantidad_cambio = data['cantidad']

    try:
        stock_item.cantidad += cantidad_cambio
        db.session.commit()
        return jsonify({'stock': {'sucursal_id': stock_item.sucursal_id, 'producto_id': stock_item.producto_id, 'cantidad': stock_item.cantidad, 'precio': stock_item.precio}})
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


#para importar todo Json 

# @app.route('/importar_todo', methods=['POST'])
# def importar_todo():
#     data = request.get_json()
#     if not data:
#         return jsonify({'error': 'Por favor, proporciona datos JSON'}), 400

#     sucursales_data = data.get('sucursales', [])
#     productos_data = data.get('productos', [])
#     stock_data = data.get('stock', [])

#     try:
#         # Crear sucursales
#         nuevas_sucursales = []
#         for sucursal_data in sucursales_data:
#             if 'nombre' not in sucursal_data or 'direccion' not in sucursal_data:
#                 return jsonify({'error': 'Datos de sucursal inválidos'}), 400
#             nueva_sucursal = Sucursal(nombre=sucursal_data['nombre'], direccion=sucursal_data['direccion'])
#             db.session.add(nueva_sucursal)
#             db.session.flush()  # Para obtener el ID inmediatamente
#             nuevas_sucursales.append({'id': nueva_sucursal.id, 'nombre': nueva_sucursal.nombre, 'direccion': nueva_sucursal.direccion})
#         db.session.commit()

#         # Crear productos
#         nuevos_productos = []
#         for producto_data in productos_data:
#             if 'nombre' not in producto_data:
#                 return jsonify({'error': 'Datos de producto inválidos'}), 400
#             nuevo_producto = Producto(nombre=producto_data['nombre'])
#             db.session.add(nuevo_producto)
#             db.session.flush()  # Para obtener el ID inmediatamente
#             nuevos_productos.append({'id': nuevo_producto.id, 'nombre': nuevo_producto.nombre})
#         db.session.commit()

#         # Crear stock
#         stock_creados = []
#         for item_data in stock_data:
#             sucursal_id = item_data.get('sucursal_id')
#             producto_id = item_data.get('producto_id')
#             cantidad = item_data.get('cantidad')
#             precio = item_data.get('precio')

#             if not all([sucursal_id, producto_id, cantidad, precio]):
#                 return jsonify({'error': 'Datos de stock inválidos'}), 400

#             sucursal = Sucursal.query.get(sucursal_id)
#             producto = Producto.query.get(producto_id)

#             if not sucursal or not producto:
#                 return jsonify({'error': f'Sucursal o producto no encontrado para sucursal_id: {sucursal_id}, producto_id: {producto_id}'}), 400

#             nuevo_stock = Stock(sucursal_id=sucursal_id, producto_id=producto_id, cantidad=cantidad, precio=precio)
#             db.session.add(nuevo_stock)
#             stock_creados.append({
#                 'sucursal_id': nuevo_stock.sucursal_id,
#                 'producto_id': nuevo_stock.producto_id,
#                 'cantidad': nuevo_stock.cantidad,
#                 'precio': nuevo_stock.precio
#             })
#         db.session.commit()

#         return jsonify({
#             'mensaje': 'Importación completa',
#             'sucursales_creadas': nuevas_sucursales,
#             'productos_creados': nuevos_productos,
#             'stock_creado': stock_creados
#         }), 201

#     except Exception as e:
#         db.session.rollback()
#         return jsonify({'error': f'Error durante la importación: {str(e)}'}), 500



if __name__ == '__main__':
    with app.app_context():
        db.create_all() 
        app.run(debug=True)