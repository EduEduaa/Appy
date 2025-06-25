from concurrent import futures
import grpc
import os
import time

from flask import Flask 
from models import db, Producto 


from grpc_stubs import mantenedor_productos_pb2, mantenedor_productos_pb2_grpc
from sqlalchemy.exc import SQLAlchemyError


grpc_app = Flask(__name__)
grpc_app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:@localhost/tienda'
grpc_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(grpc_app)

# Configuración para la subida de imágenes (necesaria para el servicer)
UPLOAD_FOLDER = 'static/uploads/product_images'
grpc_app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- Implementación del Servidor gRPC ---
class ProductMaintainerServicer(mantenedor_productos_pb2_grpc.ProductMaintainerServicer):
    def GetProduct(self, request, context):
        with grpc_app.app_context(): # Usa el contexto de la aplicación para acceder a la DB
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
        with grpc_app.app_context():
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
        with grpc_app.app_context():
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
        with grpc_app.app_context():
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
        with grpc_app.app_context():
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
        with grpc_app.app_context():
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

            product = db.session.get(Producto, product_id)
            if not product:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Producto no encontrado para la carga de imagen.")
                return mantenedor_productos_pb2.UploadProductImageResponse(success=False, message="Producto no encontrado")
            
            base, ext = os.path.splitext(filename)
            unique_filename = f"{product_id}_{int(time.time())}{ext}"
            # Usa grpc_app.config['UPLOAD_FOLDER'] para la ruta de carga
            file_path = os.path.join(grpc_app.config['UPLOAD_FOLDER'], unique_filename)

            try:
                with open(file_path, 'wb') as f:
                    f.write(file_data)

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

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    mantenedor_productos_pb2_grpc.add_ProductMaintainerServicer_to_server(
        ProductMaintainerServicer(), server
    )
    server.add_insecure_port('[::]:50051') 
    server.start()
    print("Servidor gRPC iniciado en el puerto 50051")
    server.wait_for_termination()

if __name__ == '__main__':
    
    with grpc_app.app_context():
        db.create_all()
    serve()