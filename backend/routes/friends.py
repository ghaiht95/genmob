from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User, Friendship
import logging

# إعداد السجلات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

friends_bp = Blueprint('friends', __name__)

@friends_bp.route('/send_request', methods=['POST'])
@jwt_required()
def send_friend_request():
    data = request.get_json()
    current_user_email = get_jwt_identity()
    
    if not data.get("friend_username"):
        return jsonify({"error": "يرجى تحديد اسم المستخدم للصديق"}), 400
    
    # البحث عن المستخدم الحالي
    current_user = User.query.filter_by(email=current_user_email).first()
    if not current_user:
        return jsonify({"error": "المستخدم الحالي غير موجود"}), 404
    
    # البحث عن الصديق
    friend = User.query.filter_by(username=data.get("friend_username")).first()
    if not friend:
        return jsonify({"error": "المستخدم المطلوب غير موجود"}), 404
    
    # التحقق من عدم وجود طلب صداقة بالفعل
    existing_request = Friendship.query.filter(
        ((Friendship.user_id == current_user.id) & (Friendship.friend_id == friend.id)) |
        ((Friendship.user_id == friend.id) & (Friendship.friend_id == current_user.id))
    ).first()
    
    if existing_request:
        if existing_request.status == 'accepted':
            return jsonify({"error": "أنتما صديقان بالفعل"}), 400
        elif existing_request.status == 'pending':
            # إذا كان الطلب من الصديق إلى المستخدم الحالي، قم بقبوله تلقائيًا
            if existing_request.user_id == friend.id and existing_request.friend_id == current_user.id:
                existing_request.status = 'accepted'
                db.session.commit()
                return jsonify({"message": "تم قبول طلب الصداقة"}), 200
            else:
                return jsonify({"error": "لديك طلب صداقة معلق بالفعل مع هذا المستخدم"}), 400
    
    # إنشاء طلب صداقة جديد
    friendship = Friendship(
        user_id=current_user.id,
        friend_id=friend.id,
        status='pending'
    )
    
    db.session.add(friendship)
    db.session.commit()
    
    return jsonify({"message": "تم إرسال طلب الصداقة بنجاح"}), 201

@friends_bp.route('/accept_request/<int:request_id>', methods=['POST'])
@jwt_required()
def accept_friend_request(request_id):
    current_user_email = get_jwt_identity()
    
    # البحث عن المستخدم الحالي
    current_user = User.query.filter_by(email=current_user_email).first()
    if not current_user:
        return jsonify({"error": "المستخدم الحالي غير موجود"}), 404
    
    # البحث عن طلب الصداقة
    friendship = Friendship.query.filter_by(id=request_id, friend_id=current_user.id, status='pending').first()
    if not friendship:
        return jsonify({"error": "طلب الصداقة غير موجود أو تم معالجته بالفعل"}), 404
    
    # قبول طلب الصداقة
    friendship.status = 'accepted'
    db.session.commit()
    
    return jsonify({"message": "تم قبول طلب الصداقة بنجاح"}), 200

@friends_bp.route('/decline_request/<int:request_id>', methods=['POST'])
@jwt_required()
def decline_friend_request(request_id):
    current_user_email = get_jwt_identity()
    
    # البحث عن المستخدم الحالي
    current_user = User.query.filter_by(email=current_user_email).first()
    if not current_user:
        return jsonify({"error": "المستخدم الحالي غير موجود"}), 404
    
    # البحث عن طلب الصداقة
    friendship = Friendship.query.filter_by(id=request_id, friend_id=current_user.id, status='pending').first()
    if not friendship:
        return jsonify({"error": "طلب الصداقة غير موجود أو تم معالجته بالفعل"}), 404
    
    # رفض طلب الصداقة
    friendship.status = 'declined'
    db.session.commit()
    
    return jsonify({"message": "تم رفض طلب الصداقة"}), 200

@friends_bp.route('/cancel_request/<int:request_id>', methods=['POST'])
@jwt_required()
def cancel_friend_request(request_id):
    current_user_email = get_jwt_identity()
    
    # البحث عن المستخدم الحالي
    current_user = User.query.filter_by(email=current_user_email).first()
    if not current_user:
        return jsonify({"error": "المستخدم الحالي غير موجود"}), 404
    
    # البحث عن طلب الصداقة
    friendship = Friendship.query.filter_by(id=request_id, user_id=current_user.id, status='pending').first()
    if not friendship:
        return jsonify({"error": "طلب الصداقة غير موجود أو تم معالجته بالفعل"}), 404
    
    # حذف طلب الصداقة
    db.session.delete(friendship)
    db.session.commit()
    
    return jsonify({"message": "تم إلغاء طلب الصداقة"}), 200

@friends_bp.route('/remove_friend/<int:friend_id>', methods=['POST'])
@jwt_required()
def remove_friend(friend_id):
    current_user_email = get_jwt_identity()
    
    # البحث عن المستخدم الحالي
    current_user = User.query.filter_by(email=current_user_email).first()
    if not current_user:
        return jsonify({"error": "المستخدم الحالي غير موجود"}), 404
    
    # البحث عن علاقة الصداقة
    friendship = Friendship.query.filter(
        (((Friendship.user_id == current_user.id) & (Friendship.friend_id == friend_id)) |
        ((Friendship.user_id == friend_id) & (Friendship.friend_id == current_user.id))) &
        (Friendship.status == 'accepted')
    ).first()
    
    if not friendship:
        return jsonify({"error": "علاقة الصداقة غير موجودة"}), 404
    
    # حذف علاقة الصداقة
    db.session.delete(friendship)
    db.session.commit()
    
    return jsonify({"message": "تم إزالة الصديق بنجاح"}), 200

@friends_bp.route('/my_friends', methods=['GET'])
@jwt_required()
def get_friends():
    current_user_email = get_jwt_identity()
    
    # البحث عن المستخدم الحالي
    current_user = User.query.filter_by(email=current_user_email).first()
    if not current_user:
        return jsonify({"error": "المستخدم الحالي غير موجود"}), 404
    
    # البحث عن الأصدقاء (العلاقات المقبولة)
    sent_friendships = Friendship.query.filter_by(user_id=current_user.id, status='accepted').all()
    received_friendships = Friendship.query.filter_by(friend_id=current_user.id, status='accepted').all()
    
    friends = []
    
    # إضافة الأصدقاء من الطلبات المرسلة
    for friendship in sent_friendships:
        friend = User.query.get(friendship.friend_id)
        if friend:
            friends.append({
                "id": friend.id,
                "username": friend.username,
                "email": friend.email
            })
    
    # إضافة الأصدقاء من الطلبات المستلمة
    for friendship in received_friendships:
        friend = User.query.get(friendship.user_id)
        if friend:
            friends.append({
                "id": friend.id,
                "username": friend.username,
                "email": friend.email
            })
    
    return jsonify({"friends": friends}), 200

@friends_bp.route('/pending_requests', methods=['GET'])
@jwt_required()
def get_pending_requests():
    current_user_email = get_jwt_identity()
    
    # البحث عن المستخدم الحالي
    current_user = User.query.filter_by(email=current_user_email).first()
    if not current_user:
        return jsonify({"error": "المستخدم الحالي غير موجود"}), 404
    
    # الطلبات المستلمة
    pending_requests = Friendship.query.filter_by(friend_id=current_user.id, status='pending').all()
    
    requests = []
    for request in pending_requests:
        sender = User.query.get(request.user_id)
        if sender:
            requests.append({
                "request_id": request.id,
                "user_id": sender.id,
                "username": sender.username,
                "email": sender.email,
                "created_at": request.created_at.isoformat()
            })
    
    return jsonify({"pending_requests": requests}), 200

@friends_bp.route('/sent_requests', methods=['GET'])
@jwt_required()
def get_sent_requests():
    current_user_email = get_jwt_identity()
    
    # البحث عن المستخدم الحالي
    current_user = User.query.filter_by(email=current_user_email).first()
    if not current_user:
        return jsonify({"error": "المستخدم الحالي غير موجود"}), 404
    
    # الطلبات المرسلة
    sent_requests = Friendship.query.filter_by(user_id=current_user.id, status='pending').all()
    
    requests = []
    for request in sent_requests:
        receiver = User.query.get(request.friend_id)
        if receiver:
            requests.append({
                "request_id": request.id,
                "user_id": receiver.id,
                "username": receiver.username,
                "email": receiver.email,
                "created_at": request.created_at.isoformat()
            })
    
    return jsonify({"sent_requests": requests}), 200 