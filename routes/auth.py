# routes/auth.py
from flask import Blueprint, request, jsonify
from models import db, User
from services.email_sender import send_email
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
import random
import string
import time
import sqlalchemy.exc
from datetime import timedelta

auth_bp = Blueprint('auth', __name__)

def generate_code(length=6):
    return ''.join(random.choices(string.digits, k=length))

def commit_with_retry(max_retries=5, retry_delay=0.5):
    """Commit database changes with retry for locked database."""
    for attempt in range(max_retries):
        try:
            db.session.commit()
            return True  # Success
        except sqlalchemy.exc.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                db.session.rollback()  # Rollback the transaction
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                continue
            else:
                db.session.rollback()
                raise  # Re-raise the exception if it's not a lock issue or we've exhausted retries
    return False  # Failed after all retries

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
    
    try:
        commit_with_retry()
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500

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
    try:
        commit_with_retry()
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
        
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
    
    try:
        commit_with_retry()
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
        
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
    
    try:
        commit_with_retry()
    except Exception as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
        
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
        # إنشاء رمز JWT
        access_token = create_access_token(identity=email, expires_delta=timedelta(days=1))
        return jsonify({
            "message": "Login successful", 
            "username": user.username,
            "email": user.email,
            "access_token": access_token
        })
    else:
        return jsonify({"error": "Invalid email or password"}), 401

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_user_info():
    """الحصول على معلومات المستخدم الحالي باستخدام JWT"""
    current_user_email = get_jwt_identity()
    
    user = User.query.filter_by(email=current_user_email).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    return jsonify({
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "created_at": user.created_at.isoformat() if user.created_at else None
    }), 200

@auth_bp.route('/search_users', methods=['GET'])
@jwt_required()
def search_users():
    """البحث عن مستخدمين بناءً على اسم المستخدم أو البريد الإلكتروني"""
    search_term = request.args.get('q', '')
    if not search_term or len(search_term) < 3:
        return jsonify({"error": "Search term must be at least 3 characters"}), 400
    
    # البحث عن المستخدمين المطابقين
    users = User.query.filter(
        (User.username.like(f'%{search_term}%')) | 
        (User.email.like(f'%{search_term}%'))
    ).limit(10).all()
    
    # استبعاد المستخدم الحالي من النتائج
    current_user_email = get_jwt_identity()
    users_list = [
        {"id": user.id, "username": user.username, "email": user.email}
        for user in users if user.email != current_user_email
    ]
    
    return jsonify({"users": users_list}), 200