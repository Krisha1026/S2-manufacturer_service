from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import pymysql
from datetime import datetime

app = Flask(__name__, template_folder='templates')
CORS(app)

# MySQL Configuration (WAMP)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/cozy_manufacturer'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_POOL_RECYCLE'] = 299
app.config['SQLALCHEMY_POOL_SIZE'] = 20

db = SQLAlchemy(app)

class BlanketModel(db.Model):
    __tablename__ = 'blankets'
    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(100), nullable=False, unique=True)
    material = db.Column(db.String(100), nullable=False)
    current_stock = db.Column(db.Integer, default=0)
    production_capacity = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text)
    unit_cost = db.Column(db.Float, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'model_name': self.model_name,
            'material': self.material,
            'current_stock': self.current_stock,
            'production_capacity': self.production_capacity,
            'description': self.description,
            'unit_cost': self.unit_cost
        }

class DistributorOrder(db.Model):
    __tablename__ = 'distributor_orders'
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, nullable=False)
    blanket_model_id = db.Column(db.Integer, nullable=False)
    blanket_model_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='pending')
    order_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    fulfillment_date = db.Column(db.DateTime)
    
    def to_dict(self):
        return {
            'id': self.id,
            'seller_id': self.seller_id,
            'blanket_model_id': self.blanket_model_id,
            'blanket_model_name': self.blanket_model_name,
            'quantity': self.quantity,
            'status': self.status,
            'order_date': self.order_date.strftime('%Y-%m-%d %H:%M:%S'),
            'fulfillment_date': self.fulfillment_date.strftime('%Y-%m-%d %H:%M:%S') if self.fulfillment_date else None
        }

# Initialize Database
with app.app_context():
    db.create_all()

def validate_blanket_data(data, is_update=False):
    required_fields = ['model_name', 'material', 'production_capacity', 'unit_cost']
    if not is_update:
        return all(field in data for field in required_fields)
    return True

@app.route('/')
def index():
    return render_template('manufacturer.html')

@app.route('/api/blankets', methods=['GET'])
def get_blankets():
    try:
        blankets = BlanketModel.query.all()
        return jsonify([blanket.to_dict() for blanket in blankets])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/blankets/<int:id>', methods=['GET'])
def get_blanket(id):
    try:
        blanket = BlanketModel.query.get_or_404(id)
        return jsonify(blanket.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/api/blankets', methods=['POST'])
def add_blanket():
    try:
        data = request.json
        if not validate_blanket_data(data):
            return jsonify({'error': 'Missing required fields'}), 400

        blanket = BlanketModel(
            model_name=data['model_name'],
            material=data['material'],
            current_stock=data.get('current_stock', 0),
            production_capacity=data['production_capacity'],
            description=data.get('description', ''),
            unit_cost=data['unit_cost']
        )
        db.session.add(blanket)
        db.session.commit()
        return jsonify({'message': 'Blanket model added successfully', 'data': blanket.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/blankets/<int:id>', methods=['PUT'])
def update_blanket(id):
    try:
        blanket = BlanketModel.query.get_or_404(id)
        data = request.json
        
        if 'model_name' in data:
            blanket.model_name = data['model_name']
        if 'material' in data:
            blanket.material = data['material']
        if 'current_stock' in data:
            blanket.current_stock = data['current_stock']
        if 'production_capacity' in data:
            blanket.production_capacity = data['production_capacity']
        if 'description' in data:
            blanket.description = data['description']
        if 'unit_cost' in data:
            blanket.unit_cost = data['unit_cost']
            
        db.session.commit()
        return jsonify({'message': 'Blanket model updated successfully', 'data': blanket.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/blankets/<int:id>', methods=['DELETE'])
def delete_blanket(id):
    try:
        blanket = BlanketModel.query.get_or_404(id)
        db.session.delete(blanket)
        db.session.commit()
        return jsonify({'message': 'Blanket model deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/inventory', methods=['POST'])
def update_inventory():
    try:
        data = request.json
        required_fields = ['blanket_id', 'action', 'quantity']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400

        blanket = BlanketModel.query.get(data['blanket_id'])
        if not blanket:
            return jsonify({'error': 'Blanket model not found'}), 404
        
        if data['action'] == 'add':
            blanket.current_stock += data['quantity']
        elif data['action'] == 'remove':
            if blanket.current_stock < data['quantity']:
                return jsonify({'error': 'Insufficient stock'}), 400
            blanket.current_stock -= data['quantity']
        else:
            return jsonify({'error': 'Invalid action'}), 400
        
        db.session.commit()
        return jsonify({'message': 'Inventory updated successfully', 'current_stock': blanket.current_stock})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/orders', methods=['POST'])
def create_distributor_order():
    try:
        data = request.json
        required_fields = ['seller_id', 'blanket_model_id', 'quantity']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400

        blanket = BlanketModel.query.get(data['blanket_model_id'])
        if not blanket:
            return jsonify({'error': 'Blanket model not found'}), 404

        # Create the order
        order = DistributorOrder(
            seller_id=data['seller_id'],
            blanket_model_id=data['blanket_model_id'],
            blanket_model_name=blanket.model_name,
            quantity=data['quantity'],
            status='pending'
        )
        
        # Check if we can fulfill immediately
        if blanket.current_stock >= data['quantity']:
            blanket.current_stock -= data['quantity']
            order.status = 'fulfilled'
            order.fulfillment_date = datetime.utcnow()
        
        db.session.add(order)
        db.session.commit()
        
        return jsonify({
            'message': 'Order created successfully',
            'order': order.to_dict(),
            'fulfilled': order.status == 'fulfilled'
        }), 201
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/orders', methods=['GET'])
def get_distributor_orders():
    try:
        status_filter = request.args.get('status')
        query = DistributorOrder.query
        
        if status_filter:
            query = query.filter(DistributorOrder.status == status_filter)
            
        orders = query.order_by(DistributorOrder.order_date.desc()).all()
        return jsonify([order.to_dict() for order in orders])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/orders/<int:id>/fulfill', methods=['POST'])
def fulfill_order(id):
    try:
        order = DistributorOrder.query.get_or_404(id)
        if order.status != 'pending':
            return jsonify({'error': 'Order is not pending'}), 400
            
        blanket = BlanketModel.query.get(order.blanket_model_id)
        if not blanket:
            return jsonify({'error': 'Blanket model not found'}), 404
            
        if blanket.current_stock < order.quantity:
            return jsonify({'error': 'Not enough stock to fulfill order'}), 400
            
        blanket.current_stock -= order.quantity
        order.status = 'fulfilled'
        order.fulfillment_date = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Order fulfilled successfully',
            'order': order.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/orders/<int:id>/cancel', methods=['POST'])
def cancel_order(id):
    try:
        order = DistributorOrder.query.get_or_404(id)
        if order.status != 'pending':
            return jsonify({'error': 'Only pending orders can be cancelled'}), 400
            
        order.status = 'cancelled'
        db.session.commit()
        
        return jsonify({
            'message': 'Order cancelled successfully',
            'order': order.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True, use_reloader=False)