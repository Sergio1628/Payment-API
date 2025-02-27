from flask import Flask, jsonify, request, send_file, render_template
from repository.database import db
from db_models.payments import Payment
from datetime import datetime, timedelta
from payments.pix import Pix
from flask_socketio import SocketIO


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'SECRET_KEY_WEBSOCKET'

db.init_app(app)
sokcetio = SocketIO(app)

@app.route('/payments/pix', methods=['POST'])
def create_payment_pix():
    data = request.get_json()

    # Validações
    if 'amount' not in data:
        return jsonify({"message": "Invalid Amount"}), 400

    expiration_date = datetime.now() + timedelta(minutes=30)

    new_payment = Payment(amount=data['amount'], 
                          expiration_date=expiration_date)
    pix_obj = Pix()
    data_payment_pix = pix_obj.create_payment()
    new_payment.bank_payment_id = data_payment_pix["bank_payment_id"]
    new_payment.qr_code = data_payment_pix["qr_code_path"]

    db.session.add(new_payment)
    db.session.commit()

    return jsonify({"message": "The payment has been created",
                    "payment": new_payment.to_dict()})



@app.route('/payments/pix/qr_code/<file_name>',  methods=['GET'])
def get_image(file_name):
    return send_file(f"static/img/{file_name}.png", mimetype='image/png')



@app.route('/payments/pix/confirmation', methods=['POST'])
def pix_confirmation():
    data = request.get_json()

    # Valida se o bank_payment_id foi enviado
    if "bank_payment_id" not in data and "amount" not in data:
        return jsonify({"message": "Invalid payment data"}), 400
     
    payment = Payment.query.filter_by(bank_payment_id=data.get("bank_payment_id")).first()
    
    # Valida se o bank_payment_id (agora payment) é válido e não está pago
    if not payment or payment.paid:
        return jsonify({"message": " Payment not found"}), 404
        
    
    # Valida se o valor está EXATO
    if data.get("amount") != payment.amount:
        return jsonify({"message": "Invalid payment data"}), 400
    
    payment.paid = True
    db.session.commit()
    sokcetio.emit(f'payment-confirmed-{payment.id}')

    return jsonify({"message": "The Payment has been confirmed"})


@app.route('/payments/pix/<int:payment_id>', methods=['GET'])
def payment_pix_page(payment_id):
    payment = Payment.query.get(payment_id)

    if not payment:
        return render_template('404.html')

    if payment.paid:
        return render_template('confirmed_payment.html', payment_id=payment.id, amount=payment.amount,)
    return render_template('payment.html', payment_id=payment.id, amount=payment.amount, host="http://127.0.0.1:5000", qr_code=payment.qr_code) # para o método funcionar, o nome da pasta obrigatóriamente deve se chamar 'templates'

# Websocket
@sokcetio.on('connect')
def handle_connect():
    print("Client connected to the server")

@sokcetio.on('disconnect')
def handle_disconnect():
    print("Client disconnected")

if __name__ == '__main__':
    sokcetio.run(app, debug=True)