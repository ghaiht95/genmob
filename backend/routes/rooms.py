from flask import Blueprint, request, jsonify
from models import db, Room, RoomPlayer, ChatMessage
from services.softether import SoftEtherVPN
import random
import os
import logging
import time
from sqlalchemy.exc import OperationalError

# إعداد السجلات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

rooms_bp = Blueprint('rooms', __name__)
vpn = SoftEtherVPN()

def retry_on_db_lock(func):
    """ديكوريتور لإعادة المحاولة عند قفل قاعدة البيانات"""
    def wrapper(*args, **kwargs):
        max_retries = 3
        retry_delay = 0.5  # ثواني
        
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    logger.warning(f"Database locked, retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # زيادة وقت الانتظار مع كل محاولة
                else:
                    raise
    return wrapper

@retry_on_db_lock
def safe_db_operation(operation_func):
    """تنفيذ عمليات قاعدة البيانات بشكل آمن مع إعادة المحاولة"""
    try:
        return operation_func()
    except Exception as e:
        logger.error(f"Database operation failed: {e}")
        db.session.rollback()
        raise

@rooms_bp.route('/create_room', methods=['POST'])
def create_room():
    data = request.get_json()

    # التحقق من صحة المدخلات
    if not data.get("name") or not data.get("owner"):
        return jsonify({"error": "Room name and owner are required"}), 400

    existing = Room.query.filter_by(name=data["name"]).first()
    if existing:
        return jsonify({"error": "Room name already exists"}), 400

    room = Room(
        name=data["name"],
        owner_username=data["owner"],
        description=data.get("description", ""),
        is_private=data.get("is_private", False),
        password=data.get("password", ""),
        max_players=data.get("max_players", 8),
        current_players=1
    )
    db.session.add(room)
    db.session.flush()

    # إنشاء هاب جديد في SoftEther VPN
    hub_name = f"room_{room.id}"
    logger.info(f"Creating VPN hub: {hub_name}")
    if not vpn.create_hub(hub_name):
        logger.error(f"Failed to create VPN hub: {hub_name}")
        db.session.rollback()
        return jsonify({"error": "Failed to create VPN hub"}), 500
    logger.info(f"Successfully created VPN hub: {hub_name}")

    # إنشاء مستخدم للمالك
    username = data["owner"].split('@')[0]
    vpn_password = ''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=12))
    logger.info(f"Creating VPN user: {username} in hub: {hub_name}")
    if not vpn.create_user(hub_name, username, vpn_password):
        logger.error(f"Failed to create VPN user: {username} in hub: {hub_name}")
        vpn.delete_hub(hub_name)
        db.session.rollback()
        return jsonify({"error": "Failed to create VPN user"}), 500
    logger.info(f"Successfully created VPN user: {username} in hub: {hub_name}")

    rp = RoomPlayer(room_id=room.id, player_username=data["owner"], username=username, is_host=True)
    db.session.add(rp)
    db.session.commit()

    return jsonify({
        "room_id": room.id,
        "vpn_hub": hub_name,
        "vpn_username": username,
        "vpn_password": vpn_password,
        "server_ip": os.getenv("SOFTETHER_SERVER_IP", "localhost"),
        "port": int(os.getenv("SOFTETHER_SERVER_PORT", 443))
    }), 200

@rooms_bp.route('/join_room', methods=['POST'])
def join_room():
    data = request.get_json()
    
    # التحقق من صحة المدخلات
    if not data.get("room_id") or not data.get("username"):
        return jsonify({"error": "Room ID and username are required"}), 400
    
    room = Room.query.get(data["room_id"])
    if not room:
        return jsonify({"error": "Room not found"}), 404

    # التحقق من وجود المستخدم في نفس الغرفة
    existing_in_same_room = RoomPlayer.query.filter_by(
        room_id=data["room_id"], 
        player_username=data["username"]
    ).first()
    if existing_in_same_room:
        return jsonify({"error": "You are already in this room"}), 400

    # قبل ما ينضم، نتأكد إذا هو موجود بغرفة ثانية
    existing_membership = RoomPlayer.query.filter_by(player_username=data["username"]).first()
    if existing_membership:
        # نطرده من الغرفة القديمة
        old_room = Room.query.get(existing_membership.room_id)
        if old_room:
            old_hub = f"room_{old_room.id}"
            vpn.delete_user(old_hub, existing_membership.username)
            db.session.delete(existing_membership)
            old_room.current_players -= 1

            if old_room.current_players <= 0:
                vpn.delete_hub(old_hub)
                ChatMessage.query.filter_by(room_id=old_room.id).delete()
                db.session.delete(old_room)

    players_count = RoomPlayer.query.filter_by(room_id=room.id).count()
    if players_count >= room.max_players:
        return jsonify({"error": "Room is full"}), 400

    # إنشاء مستخدم VPN جديد
    hub_name = f"room_{room.id}"
    username = data["username"].split('@')[0]
    vpn_password = ''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=12))
    if not vpn.create_user(hub_name, username, vpn_password):
        return jsonify({"error": "Failed to create VPN user"}), 500

    rp = RoomPlayer(room_id=room.id, player_username=data["username"], username=username, is_host=False)
    db.session.add(rp)
    room.current_players = players_count + 1
    db.session.commit()

    return jsonify({
        "room_id": room.id,
        "vpn_hub": hub_name,
        "vpn_username": username,
        "vpn_password": vpn_password,
        "server_ip": os.getenv("SOFTETHER_SERVER_IP", "localhost"),
        "port": int(os.getenv("SOFTETHER_SERVER_PORT", 443))
    }), 200

@rooms_bp.route('/leave_room', methods=['POST'])
def leave_room():
    data = request.get_json()

    # التحقق من صحة المدخلات
    if not data.get("room_id") or not data.get("username"):
        return jsonify({"error": "Room ID and username are required"}), 400

    try:
        def leave_room_operation():
            rp = RoomPlayer.query.filter_by(room_id=data["room_id"], player_username=data["username"]).first()
            room = Room.query.get(data["room_id"])

            if not room:
                return jsonify({"error": "Room not found"}), 404

            # علامة تشير إلى ما إذا كان هذا آخر لاعب (تأتي من Socket.IO)
            is_last_player = data.get("is_last_player", False)
            logger.info(f"Leave room request for {data['username']} from room {data['room_id']} - is_last_player: {is_last_player}")

            if rp:
                # حذف مستخدم VPN
                hub_name = f"room_{room.id}"
                logger.info(f"Deleting VPN user: {rp.username} from hub: {hub_name}")
                vpn.delete_user(hub_name, rp.username)
                db.session.delete(rp)
                db.session.flush()

            # إذا تم التحديد مسبقًا أن هذا آخر لاعب، نحذف الغرفة مباشرة
            if is_last_player:
                logger.info(f"Last player left room {room.id} - cleaning up room")
                # نحتفظ بمحول الشبكة للاستخدام المستقبلي - نستخدم اسم ثابت "VPN"
                adapter_name = "VPN"
                if vpn.adapter_exists(adapter_name):
                    logger.info(f"Keeping VPN adapter {adapter_name} for future use")
                
                # حذف هاب VPN
                hub_name = f"room_{room.id}"
                logger.info(f"Deleting VPN hub: {hub_name}")
                vpn.delete_hub(hub_name)
                logger.info(f"Successfully deleted VPN hub: {hub_name}")
                
                # حذف رسائل الدردشة والغرفة
                ChatMessage.query.filter_by(room_id=room.id).delete()
                db.session.delete(room)
                logger.info(f"Successfully deleted room {room.id} and its chat messages")
            else:
                # إذا لم نكن متأكدين، نتحقق من عدد اللاعبين المتبقين
                players_left = RoomPlayer.query.filter_by(room_id=room.id).count()
                room.current_players = players_left

                if players_left == 0:
                    # نحتفظ بمحول الشبكة للاستخدام المستقبلي - نستخدم اسم ثابت "VPN"
                    adapter_name = "VPN"
                    if vpn.adapter_exists(adapter_name):
                        logger.info(f"Keeping VPN adapter {adapter_name} for future use")
                    
                    # حذف هاب VPN
                    hub_name = f"room_{room.id}"
                    logger.info(f"Deleting VPN hub: {hub_name}")
                    vpn.delete_hub(hub_name)
                    logger.info(f"Successfully deleted VPN hub: {hub_name}")
                    
                    # حذف رسائل الدردشة والغرفة
                    ChatMessage.query.filter_by(room_id=room.id).delete()
                    db.session.delete(room)
                    logger.info(f"Successfully deleted room {room.id} and its chat messages")
                else:
                    if rp and rp.is_host:
                        new_host = RoomPlayer.query.filter_by(room_id=room.id).first()
                        if new_host:
                            new_host.is_host = True
                            room.owner_username = new_host.player_username
                            logger.info(f"New host assigned: {new_host.player_username}")

            db.session.commit()
            logger.info(f"Player {data['username']} successfully left room {data['room_id']}")
            return jsonify({
                "message": "left",
                "is_last_player": is_last_player,
                "players_left": players_left if not is_last_player else 0
            }), 200

        return safe_db_operation(leave_room_operation)

    except Exception as e:
        logger.error(f"Error in leave_room: {e}")
        return jsonify({"error": "Internal server error"}), 500

@rooms_bp.route('/rooms', methods=['GET'])
def get_rooms():
    rooms = Room.query.all()
    rooms_data = [{
        "room_id": room.id,
        "name": room.name,
        "owner": room.owner_username,
        "description": room.description,
        "is_private": room.is_private,
        "max_players": room.max_players,
        "current_players": room.current_players
    } for room in rooms]
    return jsonify({"rooms": rooms_data}), 200

