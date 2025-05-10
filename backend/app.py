import os
import json
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from models import RoomPlayer, db, ChatMessage, Room
from config import Config
from routes.auth import auth_bp
from routes.rooms import rooms_bp
from routes.friends import friends_bp
import requests
import logging
from sqlalchemy import func
from datetime import datetime, timedelta
import threading
import queue

# إعداد السجلات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)

# Enable CORS
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# Initialize Database
db.init_app(app)

# Enable WebSocket with async mode
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, async_mode='gevent')

# Message queue for broadcasting
message_queue = queue.Queue()

def broadcast_worker():
    """Worker thread for handling broadcasts"""
    while True:
        try:
            event, data = message_queue.get()
            socketio.emit(event, data)
            message_queue.task_done()
        except Exception as e:
            logger.error(f"Error in broadcast worker: {e}")

# Start broadcast worker thread
broadcast_thread = threading.Thread(target=broadcast_worker, daemon=True)
broadcast_thread.start()

def initialize_database():
    db_path = os.path.join('dbdata', 'app.db')
    if not os.path.exists(db_path):
        logger.info("🔵 Database not found. Creating new database...")
        with app.app_context():
            db.create_all()
        logger.info("✅ Database created successfully!")
    else:
        logger.info("🟢 Database already exists.")

initialize_database()

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(rooms_bp)
app.register_blueprint(friends_bp, url_prefix='/friends')

# Cache for room players
room_players_cache = {}
CACHE_TIMEOUT = 5  # seconds

def get_players_for_room(room_id):
    """Get players for a room with caching"""
    current_time = datetime.now()
    cache_key = str(room_id)
    
    if cache_key in room_players_cache:
        cache_time, players = room_players_cache[cache_key]
        if current_time - cache_time < timedelta(seconds=CACHE_TIMEOUT):
            return players
    
    # If not in cache or cache expired, query database
    players = RoomPlayer.query.filter_by(room_id=room_id).all()
    player_list = [p.player_username for p in players]
    
    # Update cache
    room_players_cache[cache_key] = (current_time, player_list)
    return player_list

@socketio.on('join')
def handle_join(data):
    try:
        room_id = str(data['room_id'])
        username = data['username']
        
        logger.info(f"Player {username} attempting to join room {room_id}")
        
        # التحقق من وجود الغرفة
        room = Room.query.get(room_id)
        if not room:
            logger.error(f"Room {room_id} not found")
            return {'error': 'Room not found'}
            
        # التحقق من امتلاء الغرفة
        current_players = len(get_players_for_room(room_id))
        if current_players >= room.max_players:
            logger.error(f"Room {room_id} is full")
            return {'error': 'Room is full'}
        
        # التحقق من وجود اللاعب (باستثناء المالك)
        if room.owner_username != username:
            existing_player = RoomPlayer.query.filter_by(
                room_id=room_id,
                player_username=username
            ).first()
            
            if existing_player:
                logger.error(f"Player {username} already exists in room {room_id}")
                return {'error': 'Player already in room'}
        
        # إنشاء لاعب جديد إذا لم يكن موجوداً
        if not RoomPlayer.query.filter_by(room_id=room_id, player_username=username).first():
            new_player = RoomPlayer(
                room_id=room_id,
                player_username=username,
                is_host=(room.owner_username == username),
                username=username
            )
            db.session.add(new_player)
            
            # تحديث عدد اللاعبين
            room.current_players = current_players + 1
            db.session.commit()
            
            # مسح التخزين المؤقت
            room_players_cache.pop(str(room_id), None)
            
            logger.info(f"Player {username} successfully joined room {room_id}")
        
        join_room(room_id)
        emit('user_joined', {'username': username}, room=room_id)
        
        # تحديث قائمة اللاعبين
        players = get_players_for_room(room_id)
        emit('update_players', {'players': players}, room=room_id)
        
        return {'status': 'success'}
        
    except Exception as e:
        logger.error(f"Error in handle_join: {e}")
        db.session.rollback()
        return {'error': str(e)}

@socketio.on('leave')
def handle_leave(data):
    try:
        room_id = str(data['room_id'])
        username = data['username']
        
        player = RoomPlayer.query.filter_by(
            room_id=room_id,
            player_username=username
        ).first()
        
        if player:
            is_host = player.is_host
            vpn_username = player.username
            room = Room.query.get(room_id)
            
            if room:
                # إذا كان اللاعب هو المالك، نقوم بنقل الملكية للاعب التالي
                if is_host:
                    # البحث عن اللاعب التالي
                    next_player = RoomPlayer.query.filter(
                        RoomPlayer.room_id == room_id,
                        RoomPlayer.player_username != username
                    ).order_by(RoomPlayer.joined_at.asc()).first()
                    
                    if next_player:
                        # نقل الملكية للاعب التالي
                        next_player.is_host = True
                        room.owner_username = next_player.player_username
                        db.session.commit()
                        
                        # إرسال إشعار بنقل الملكية
                        emit('host_changed', {
                            'new_host': next_player.player_username
                        }, room=room_id)
                        
                        logger.info(f"Room ownership transferred to {next_player.player_username}")
                    else:
                        # إذا لم يكن هناك لاعبين آخرين، نقوم بحذف الغرفة
                        cleanup_room(room_id, username)
                        emit('room_closed', {'room_id': room_id}, broadcast=True)
                        return {'status': 'success', 'room_closed': True}
                
                # حذف اللاعب المغادر
                db.session.delete(player)
                room.current_players = max(0, room.current_players - 1)
                
                # حذف مستخدم VPN
                hub_name = f"room_{room_id}"
                try:
                    from services.softether import SoftEtherVPN
                    vpn = SoftEtherVPN()
                    vpn.delete_user(hub_name, vpn_username)
                except Exception as e:
                    logger.error(f"Error deleting VPN user: {e}")
                
                db.session.commit()
                
                # إرسال إشعارات للاعبين الآخرين
                leave_room(room_id)
                emit('user_left', {'username': username}, room=room_id)
                
                # تحديث قائمة اللاعبين
                players = get_players_for_room(room_id)
                emit('update_players', {'players': players}, room=room_id)
            
            return {'status': 'success', 'room_closed': False}
            
    except Exception as e:
        logger.error(f"Error in handle_leave: {e}")
        db.session.rollback()
        return {'error': str(e)}

def cleanup_room(room_id, username):
    """تنظيف موارد الغرفة"""
    try:
        # حذف جميع اللاعبين
        RoomPlayer.query.filter_by(room_id=room_id).delete()
        
        # حذف جميع الرسائل
        ChatMessage.query.filter_by(room_id=room_id).delete()
        
        # حذف الغرفة
        room = Room.query.get(room_id)
        if room:
            db.session.delete(room)
        
        # حذف هاب VPN
        hub_name = f"room_{room_id}"
        try:
            from services.softether import SoftEtherVPN
            vpn = SoftEtherVPN()
            vpn.delete_hub(hub_name)
        except Exception as e:
            logger.error(f"Error deleting VPN hub: {e}")
        
        db.session.commit()
        logger.info(f"Room {room_id} cleaned up successfully")
        
    except Exception as e:
        logger.error(f"Error cleaning up room {room_id}: {e}")
        db.session.rollback()
        raise

@socketio.on('send_message')
def handle_send_message(data):
    try:
        room_id = data.get('room_id')
        username = data.get('username')
        message = data.get('message')
        
        if not all([room_id, username, message]):
            return {'error': 'Missing required fields'}
        
        # Verify room and player
        room = Room.query.get(room_id)
        if not room:
            return {'error': 'Room not found'}
            
        player = RoomPlayer.query.filter_by(
            room_id=room_id,
            player_username=username
        ).first()
        
        if not player:
            return {'error': 'Player not in room'}
        
        # Create message
        msg = ChatMessage(
            room_id=room_id,
            username=username,
            message=message
        )
        db.session.add(msg)
        db.session.commit()
        
        # Broadcast message
        emit('new_message', {
            'id': msg.id,
            'username': msg.username,
            'message': msg.message,
            'created_at': msg.created_at.isoformat()
        }, room=room_id)
        
        return {'status': 'success'}
        
    except Exception as e:
        logger.error(f"Error in handle_send_message: {e}")
        db.session.rollback()
        return {'error': str(e)}

def broadcast_rooms_update():
    """Broadcast rooms update to all connected clients"""
    try:
        rooms = Room.query.all()
        rooms_data = [{
            'room_id': room.id,
            'name': room.name,
            'owner': room.owner_username,
            'description': room.description,
            'is_private': room.is_private,
            'max_players': room.max_players,
            'current_players': room.current_players
        } for room in rooms]
        
        message_queue.put(('rooms_updated', {'rooms': rooms_data}))
        
    except Exception as e:
        logger.error(f"Error in broadcast_rooms_update: {e}")

@socketio.on('connect')
def handle_connect():
    """Handle new client connection"""
    logger.info("Client connected")
    broadcast_rooms_update()

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info("Client disconnected")

@socketio.on('check_player')
def handle_check_player(data):
    try:
        room_id = data.get('room_id')
        username = data.get('username')
        
        if not all([room_id, username]):
            logger.error("Missing room_id or username in check_player request")
            return {'exists': False}
            
        # التحقق من وجود الغرفة
        room = Room.query.get(room_id)
        if not room:
            logger.error(f"Room {room_id} not found")
            return {'exists': False}
            
        # إذا كان اللاعب هو صاحب الغرفة، نسمح له بالدخول
        if room.owner_username == username:
            logger.info(f"Player {username} is room owner, allowing entry")
            return {'exists': False}
        
        # التحقق من وجود اللاعب في الغرفة
        player = RoomPlayer.query.filter_by(
            room_id=room_id,
            player_username=username
        ).first()
        
        exists = player is not None
        logger.info(f"Player {username} exists in room {room_id}: {exists}")
        return {'exists': exists}
        
    except Exception as e:
        logger.error(f"Error checking player: {e}")
        return {'exists': False}

# تشغيل الخادم
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=Config.DEBUG, use_reloader=False)
