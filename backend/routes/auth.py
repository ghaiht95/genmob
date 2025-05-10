# routes/auth.py
from flask import Blueprint, request, jsonify
from models import db, User
from services.email_sender import send_email
import random
import string

auth_bp = Blueprint('auth', __name__)

def generate_code(length=6):
    return ''.join(random.choices(string.digits, k=length))

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not all([username, email, password]):
        return jsonify({'error': 'Missing fields'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'User already exists'}), 400

    code = generate_code()
    user = User(username=username, email=email, verification_code=code)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    subject = "Your Verification Code"
    body = f"Hello {username},\n\nYour verification code is: {code}\n\nThank you."
    try:
        send_email(email, subject, body)
    except Exception as e:
        print(f"Email error: {e}")

    return jsonify({'message': 'User created. Check your email for the verification code.'})

@auth_bp.route('/verify', methods=['POST'])
def verify_code():
    data = request.get_json()
    email = data.get('email')
    code = data.get('code')

    if not email or not code:
        return jsonify({'error': 'Email and code are required'}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if user.verification_code != code:
        return jsonify({'error': 'Invalid code'}), 400

    user.verification_code = None
    db.session.commit()
    return jsonify({'message': 'Verification successful'}), 200


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({"error": "Email is required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    code = generate_code()
    user.verification_code = code
    db.session.commit()

    subject = "Password Reset Code"
    body = f"Hello {user.username},\n\nYour password reset code is: {code}\n\nThank you."
    try:
        send_email(email, subject, body)
    except Exception as e:
        print(f"Email error: {e}")
        return jsonify({"error": "Failed to send email"}), 500

    return jsonify({"message": "Verification code sent"}), 200

@auth_bp.route('/set-new-password', methods=['POST'])
def set_new_password():
    data = request.get_json()
    email = data.get("email")
    new_password = data.get("new_password")

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    user.set_password(new_password)
    user.verification_code = None
    db.session.commit()
    return jsonify({"message": "Password updated successfully"}), 200

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Missing email or password"}), 400

    user = User.query.filter_by(email=email).first()
    if user and user.check_password(password):
        return jsonify({"message": "Login successful", "username": user.username})
    else:
        return jsonify({"error": "Invalid email or password"}), 401