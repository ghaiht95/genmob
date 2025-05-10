from flask import Blueprint, request, jsonify
from models import db, Room, RoomPlayer, ChatMessage
from services.softether import SoftEtherVPN
import random
import os
import logging

# إعداد السجلات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

rooms_bp = Blueprint('rooms', __name__)
vpn = SoftEtherVPN()

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

    rp = RoomPlayer.query.filter_by(room_id=data["room_id"], player_username=data["username"]).first()
    room = Room.query.get(data["room_id"])

    if not room:
        return jsonify({"error": "Room not found"}), 404

    if rp:
        # حذف مستخدم VPN
        hub_name = f"room_{room.id}"
        logger.info(f"Deleting VPN user: {rp.username} from hub: {hub_name}")
        vpn.delete_user(hub_name, rp.username)
        db.session.delete(rp)
        db.session.flush()

    players_left = RoomPlayer.query.filter_by(room_id=room.id).count()
    room.current_players = players_left

    # إذا كان اللاعب المخرج هو المالك، نقوم بتعيين مالك جديد
    if rp and rp.is_host:
        new_host = RoomPlayer.query.filter_by(room_id=room.id).first()
        if new_host:
            new_host.is_host = True
            room.owner_username = new_host.player_username

    # إذا كان آخر لاعب، نقوم بحذف الغرفة
    if players_left == 0:
        logger.info(f"Room {room.id} is empty, cleaning up...")
        try:
            # حذف هاب VPN
            hub_name = f"room_{room.id}"
            vpn.delete_hub(hub_name)
            logger.info(f"Deleted VPN hub: {hub_name}")

            # حذف رسائل الدردشة
            ChatMessage.query.filter_by(room_id=room.id).delete()
            logger.info(f"Deleted chat messages for room: {room.id}")

            # حذف الغرفة
            db.session.delete(room)
            logger.info(f"Deleted room: {room.id}")
        except Exception as e:
            logger.error(f"Error cleaning up room {room.id}: {e}")
            return jsonify({"error": "Failed to clean up room"}), 500

    try:
        db.session.commit()
        logger.info(f"Player {data['username']} successfully left room {data['room_id']}")
        return jsonify({
            "message": "left",
            "is_last_player": players_left == 0,
            "players_left": players_left
        }), 200
    except Exception as e:
        logger.error(f"Error committing changes: {e}")
        db.session.rollback()
        return jsonify({"error": "Database error"}), 500

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

