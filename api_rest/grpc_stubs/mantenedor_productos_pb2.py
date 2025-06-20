
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC,
    6,
    31,
    0,
    '',
    'mantenedor_productos.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1amantenedor_productos.proto\x12\x14mantenedor_productos\"E\n\x07Product\x12\n\n\x02id\x18\x01 \x01(\x05\x12\x0e\n\x06nombre\x18\x02 \x01(\t\x12\x0e\n\x06precio\x18\x03 \x01(\x02\x12\x0e\n\x06imagen\x18\x04 \x01(\t\"\'\n\x11GetProductRequest\x12\x12\n\nproduct_id\x18\x01 \x01(\x05\"F\n\x14\x43reateProductRequest\x12\x0e\n\x06nombre\x18\x01 \x01(\t\x12\x0e\n\x06precio\x18\x02 \x01(\x02\x12\x0e\n\x06imagen\x18\x03 \x01(\t\"R\n\x14UpdateProductRequest\x12\n\n\x02id\x18\x01 \x01(\x05\x12\x0e\n\x06nombre\x18\x02 \x01(\t\x12\x0e\n\x06precio\x18\x03 \x01(\x02\x12\x0e\n\x06imagen\x18\x04 \x01(\t\"*\n\x14\x44\x65leteProductRequest\x12\x12\n\nproduct_id\x18\x01 \x01(\x05\"9\n\x15\x44\x65leteProductResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0f\n\x07message\x18\x02 \x01(\t\"U\n\x19UploadProductImageRequest\x12\x12\n\nproduct_id\x18\x01 \x01(\x05\x12\x12\n\nchunk_data\x18\x02 \x01(\x0c\x12\x10\n\x08\x66ilename\x18\x03 \x01(\t\"Q\n\x1aUploadProductImageResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x11\n\timage_url\x18\x02 \x01(\t\x12\x0f\n\x07message\x18\x03 \x01(\t\"\x17\n\x15GetAllProductsRequest\">\n\x0bProductList\x12/\n\x08products\x18\x01 \x03(\x0b\x32\x1d.mantenedor_productos.Product2\xe8\x04\n\x11ProductMaintainer\x12T\n\nGetProduct\x12\'.mantenedor_productos.GetProductRequest\x1a\x1d.mantenedor_productos.Product\x12Z\n\rCreateProduct\x12*.mantenedor_productos.CreateProductRequest\x1a\x1d.mantenedor_productos.Product\x12Z\n\rUpdateProduct\x12*.mantenedor_productos.UpdateProductRequest\x1a\x1d.mantenedor_productos.Product\x12h\n\rDeleteProduct\x12*.mantenedor_productos.DeleteProductRequest\x1a+.mantenedor_productos.DeleteProductResponse\x12y\n\x12UploadProductImage\x12/.mantenedor_productos.UploadProductImageRequest\x1a\x30.mantenedor_productos.UploadProductImageResponse(\x01\x12`\n\x0eGetAllProducts\x12+.mantenedor_productos.GetAllProductsRequest\x1a!.mantenedor_productos.ProductListb\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'mantenedor_productos_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  DESCRIPTOR._loaded_options = None
  _globals['_PRODUCT']._serialized_start=52
  _globals['_PRODUCT']._serialized_end=121
  _globals['_GETPRODUCTREQUEST']._serialized_start=123
  _globals['_GETPRODUCTREQUEST']._serialized_end=162
  _globals['_CREATEPRODUCTREQUEST']._serialized_start=164
  _globals['_CREATEPRODUCTREQUEST']._serialized_end=234
  _globals['_UPDATEPRODUCTREQUEST']._serialized_start=236
  _globals['_UPDATEPRODUCTREQUEST']._serialized_end=318
  _globals['_DELETEPRODUCTREQUEST']._serialized_start=320
  _globals['_DELETEPRODUCTREQUEST']._serialized_end=362
  _globals['_DELETEPRODUCTRESPONSE']._serialized_start=364
  _globals['_DELETEPRODUCTRESPONSE']._serialized_end=421
  _globals['_UPLOADPRODUCTIMAGEREQUEST']._serialized_start=423
  _globals['_UPLOADPRODUCTIMAGEREQUEST']._serialized_end=508
  _globals['_UPLOADPRODUCTIMAGERESPONSE']._serialized_start=510
  _globals['_UPLOADPRODUCTIMAGERESPONSE']._serialized_end=591
  _globals['_GETALLPRODUCTSREQUEST']._serialized_start=593
  _globals['_GETALLPRODUCTSREQUEST']._serialized_end=616
  _globals['_PRODUCTLIST']._serialized_start=618
  _globals['_PRODUCTLIST']._serialized_end=680
  _globals['_PRODUCTMAINTAINER']._serialized_start=683
  _globals['_PRODUCTMAINTAINER']._serialized_end=1299
# @@protoc_insertion_point(module_scope)
