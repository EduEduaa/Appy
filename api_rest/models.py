from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Sucursal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False)
    direccion = db.Column(db.String(120), nullable=False)
    stock = db.relationship('Stock', backref='sucursal', lazy=True)

    def __repr__(self):
        return f"<Sucursal {self.nombre}>"

class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False)
    stock = db.relationship('Stock', backref='producto', lazy=True)

    def __repr__(self):
        return f"<Producto {self.nombre}>"

class Stock(db.Model):
    sucursal_id = db.Column(db.Integer, db.ForeignKey('sucursal.id'), primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'), primary_key=True)
    cantidad = db.Column(db.Integer, nullable=False)
    precio = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f"<Stock sucursal_id={self.sucursal_id}, producto_id={self.producto_id}>"