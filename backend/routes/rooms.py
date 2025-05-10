from flask import Blueprint, request, jsonify
from models import db, Room, RoomPlayer, ChatMessage
from services.softether import SoftEtherVPN
import random
import os
import logging
import time
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from contextlib import contextmanager
import threading

# إعداد السجلات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

rooms_bp = Blueprint('rooms', __name__)
vpn = SoftEtherVPN()

# قفل للتعامل مع عمليات قاعدة البيانات
db_lock = threading.Lock()

@contextmanager
def session_scope():
    """مدير سياق للتعامل مع جلسات قاعدة البيانات بشكل آمن"""
    session = db.session
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()

def retry_on_db_lock(func):
    """ديكوريتور لإعادة المحاولة عند قفل قاعدة البيانات"""
    def wrapper(*args, **kwargs):
        max_retries = 5  # زيادة عدد المحاولات
        base_delay = 0.5  # ثواني
        max_delay = 5.0  # أقصى وقت انتظار
        
        for attempt in range(max_retries):
            try:
                with db_lock:  # استخدام القفل للتحكم في الوصول
                    with session_scope():
                        return func(*args, **kwargs)
            except OperationalError as e:
                if "database is locked" in str(e):
                    if attempt < max_retries - 1:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        logger.warning(f"Database locked, retrying in {delay:.1f} seconds... (Attempt {attempt + 1}/{max_retries})")
                        time.sleep(delay)
                    else:
                        logger.error(f"Max retries ({max_retries}) reached. Database still locked.")
                        raise
                else:
                    raise
            except SQLAlchemyError as e:
                logger.error(f"Database error: {e}")
                raise
    return wrapper

def delete_vpn_hub(hub_name, max_retries=5):
    """دالة مساعدة لحذف هاب VPN مع إعادة المحاولة"""
    for attempt in range(max_retries):
        try:
            # التحقق من وجود الهاب أولاً
            if not vpn.hub_exists(hub_name):
                logger.info(f"Hub {hub_name} does not exist, considering deletion successful")
                return True

            # محاولة حذف الهاب
            if vpn.delete_hub(hub_name):
                # انتظار قليلاً للتأكد من اكتمال العملية
                time.sleep(1)
                
                # التحقق من حذف الهاب
                if not vpn.hub_exists(hub_name):
                    logger.info(f"Successfully deleted VPN hub: {hub_name}")
                    return True
                else:
                    logger.warning(f"VPN hub {hub_name} still exists after deletion attempt {attempt + 1}")
            else:
                logger.warning(f"Failed to delete VPN hub {hub_name} on attempt {attempt + 1}")
            
            # حساب وقت الانتظار للمحاولة التالية (exponential backoff)
            wait_time = (2 ** attempt) * 0.5  # 0.5, 1, 2, 4, 8 seconds
            if attempt < max_retries - 1:
                logger.info(f"Waiting {wait_time} seconds before next attempt...")
                time.sleep(wait_time)
        except Exception as e:
            logger.error(f"Error deleting VPN hub {hub_name} on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 0.5
                logger.info(f"Waiting {wait_time} seconds before next attempt...")
                time.sleep(wait_time)
    
    logger.error(f"Failed to delete VPN hub {hub_name} after {max_retries} attempts")
    return False

@retry_on_db_lock
def safe_db_operation(operation_func):
    """تنفيذ عمليات قاعدة البيانات بشكل آمن مع إعادة المحاولة"""
    try:
        return operation_func()
    except Exception as e:
        logger.error(f"Database operation failed: {e}")
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
            with session_scope() as session:
                rp = session.query(RoomPlayer).filter_by(
                    room_id=data["room_id"], 
                    player_username=data["username"]
                ).first()
                room = session.query(Room).get(data["room_id"])

                if not room:
                    return jsonify({"error": "Room not found"}), 404

                # علامة تشير إلى ما إذا كان هذا آخر لاعب (تأتي من Socket.IO)
                is_last_player = data.get("is_last_player", False)
                logger.info(f"Leave room request for {data['username']} from room {data['room_id']} - is_last_player: {is_last_player}")

                hub_name = f"room_{room.id}"
                
                # حذف مستخدم VPN في جميع الحالات
                if rp:
                    logger.info(f"Deleting VPN user: {rp.username} from hub: {hub_name}")
                    if not vpn.delete_user(hub_name, rp.username):
                        logger.error(f"Failed to delete VPN user: {rp.username} from hub: {hub_name}")

                # إذا كان آخر لاعب، نحذف الهاب VPN
                if is_last_player:
                    logger.info(f"Last player left room {room.id} - cleaning up room")
                    logger.info(f"Deleting VPN hub: {hub_name}")
                    if not delete_vpn_hub(hub_name):
                        logger.error(f"Failed to delete VPN hub after all retries: {hub_name}")

                # الآن نقوم بعمليات قاعدة البيانات
                try:
                    # التحقق من وجود السجلات قبل حذفها
                    if rp and session.query(RoomPlayer).get(rp.id):
                        session.delete(rp)
                        session.flush()

                    if is_last_player:
                        # حذف رسائل الدردشة
                        chat_messages = session.query(ChatMessage).filter_by(room_id=room.id).all()
                        for msg in chat_messages:
                            session.delete(msg)
                        
                        # التحقق من وجود الغرفة قبل حذفها
                        if session.query(Room).get(room.id):
                            session.delete(room)
                        
                        session.flush()
                        logger.info(f"Successfully deleted room {room.id} and its chat messages")
                    else:
                        # تحديث عدد اللاعبين المتبقين
                        players_left = session.query(RoomPlayer).filter_by(room_id=room.id).count()
                        room.current_players = players_left

                        if players_left == 0:
                            # حذف هاب VPN
                            logger.info(f"Deleting VPN hub: {hub_name}")
                            if not delete_vpn_hub(hub_name):
                                logger.error(f"Failed to delete VPN hub after all retries: {hub_name}")
                            
                            # حذف رسائل الدردشة
                            chat_messages = session.query(ChatMessage).filter_by(room_id=room.id).all()
                            for msg in chat_messages:
                                session.delete(msg)
                            
                            # التحقق من وجود الغرفة قبل حذفها
                            if session.query(Room).get(room.id):
                                session.delete(room)
                            
                            session.flush()
                            logger.info(f"Successfully deleted room {room.id} and its chat messages")
                        else:
                            if rp and rp.is_host:
                                new_host = session.query(RoomPlayer).filter_by(room_id=room.id).first()
                                if new_host:
                                    new_host.is_host = True
                                    room.owner_username = new_host.player_username
                                    logger.info(f"New host assigned: {new_host.player_username}")

                    logger.info(f"Player {data['username']} successfully left room {data['room_id']}")
                    return jsonify({
                        "message": "left",
                        "is_last_player": is_last_player,
                        "players_left": players_left if not is_last_player else 0
                    }), 200
                except Exception as e:
                    logger.error(f"Database operation failed: {e}")
                    raise

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

