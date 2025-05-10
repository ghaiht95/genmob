import os
import json
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS  # تأكد من استيراد CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from models import RoomPlayer, db, ChatMessage, Room
from config import Config
from routes.auth import auth_bp
from routes.rooms import rooms_bp
from routes.friends import friends_bp

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)

# Enable CORS
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# Initialize Database
db.init_app(app)

# Enable WebSocket
socketio = SocketIO(app, cors_allowed_origins="*", logger=True)

def initialize_database():
    db_path = os.path.join('dbdata', 'app.db')
    if not os.path.exists(db_path):
        print("🔵 Database not found. Creating new database...")
        with app.app_context():
            db.create_all()
        print("✅ Database created successfully!")
    else:
        print("🟢 Database already exists.")


initialize_database()

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(rooms_bp)
app.register_blueprint(friends_bp, url_prefix='/friends')  # تسجيل و

players_in_rooms = {}  # Dictionary to حفظ اللاعبين حسب room_id

# استماع لحدث "get_players" في الـ namespace '/game'
@socketio.on('get_players')
  # استخدام namespace عند استقبال البيانات
def handle_get_players(data):
    room_id = data['room_id']
    players = get_players_for_room(room_id)
    if players:
        print(f"Players for room {room_id}: {players}")
    else:
        print(f"No players found for room {room_id}")
    emit('update_players', {'players': players}, room=room_id)


# دالة لاسترجاع اللاعبين من قاعدة البيانات بناءً على room_id
def get_players_for_room(room_id):
    players = RoomPlayer.query.filter_by(room_id=room_id).all()
    return [p.player_username for p in players]  # استرجاع أسماء اللاعبين


# إعدادات الاتصال بالـ WebSocket
@socketio.on('join')
def handle_join(data):
    room_id = str(data['room_id'])
    username = data['username']
    join_room(room_id)

    # أولاً: حفظ اللاعب في قاعدة البيانات إذا مش موجود
    existing_player = RoomPlayer.query.filter_by(room_id=room_id, player_username=username).first()
    if not existing_player:
        new_player = RoomPlayer(room_id=room_id, player_username=username, is_host=False, username=username)
        db.session.add(new_player)
        db.session.commit()
        print(f"Added player {username} to RoomPlayer table.")



    emit('user_joined', {'username': username}, room=room_id)

    # الآن لما نحدث اللاعبين، نسترجعهم من القاعدة مو من الرام
    players = get_players_for_room(room_id)
    print(f"Players for room {room_id}: {players}")
    emit('update_players', {'players': players}, room=room_id)



# مغادرة الغرفة
@socketio.on('leave')
def handle_leave(data):
    room_id = str(data['room_id'])
    username = data['username']
    leave_room(room_id)

    # حذف اللاعب من قاعدة البيانات
    player = RoomPlayer.query.filter_by(room_id=room_id, player_username=username).first()
    if player:
        db.session.delete(player)
        db.session.commit()
        print(f"Removed player {username} from RoomPlayer table.")


    emit('user_left', {'username': username}, room=room_id)

    # الآن لما نحدث اللاعبين، نسترجعهم من القاعدة
    players = get_players_for_room(room_id)
    print(f"Players for room {room_id}: {players}")
    emit('update_players', {'players': players}, room=room_id)


# # كتابة رسالة
@socketio.on('send_message')
def handle_send_message(data):
    room_id = str(data['room_id'])
    sender = data.get('sender') or data.get('username')
    message = data['message']

    # التحقق من أن الرسالة غير فارغة
    if not message or not sender:
        emit('error', {'message': 'Message or sender cannot be empty'}, room=room_id)
        return

    # نسجل الرسالة في قاعدة البيانات
    msg = ChatMessage(
        room_id=room_id,
        sender=sender,
        message=message
    )
    db.session.add(msg)
    db.session.commit()

    # نرسل الرسالة لكل الموجودين بالغرفة
    emit('new_message', {
        'sender': sender,
        'message': message,
        'time': msg.timestamp.strftime("%H:%M:%S")
    }, room=room_id)

def broadcast_rooms_update():
    """إرسال تحديث قائمة الغرف لجميع المستخدمين المتصلين"""
    try:
        rooms = Room.query.all()
        rooms_data = [{
            'room_id': room.id,
            'name': room.name,
            'owner': room.owner_username,
            'description': room.description,
            'is_private': room.is_private,
            'max_players': room.max_players,
            'current_players': len(get_players_for_room(room.id))
        } for room in rooms]
        print(f"Broadcasting rooms update: {rooms_data}")  # للتأكد من البيانات
        socketio.emit('rooms_updated', {'rooms': rooms_data})
    except Exception as e:
        print(f"Error in broadcast_rooms_update: {str(e)}")
        raise

@socketio.on('connect')
def handle_connect():
    """معالجة اتصال مستخدم جديد"""
    print("Client connected")
    try:
        # إرسال قائمة الغرف الحالية للمستخدم الجديد
        broadcast_rooms_update()
    except Exception as e:
        print(f"Error in handle_connect: {str(e)}")

@socketio.on('disconnect')
def handle_disconnect():
    """معالجة قطع اتصال مستخدم"""
    print("Client disconnected")

@socketio.on('room_created')
def handle_room_created(data):
    """معالجة إنشاء غرفة جديدة"""
    room_id = data.get('room_id')
    if room_id:
        print(f"New room created: {room_id}")
        try:
            broadcast_rooms_update()
        except Exception as e:
            print(f"Error in handle_room_created: {str(e)}")

@socketio.on('room_closed')
def handle_room_closed(data):
    """معالجة إغلاق غرفة"""
    room_id = data.get('room_id')
    if room_id:
        print(f"Room closed: {room_id}")
        try:
            broadcast_rooms_update()
        except Exception as e:
            print(f"Error in handle_room_closed: {str(e)}")

@app.route('/version', methods=['GET'])
def get_version():
    try:
        with open('version.json', 'r', encoding='utf-8') as f:
            version_data = json.load(f)
        return jsonify(version_data)
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/updates/<filename>', methods=['GET'])
def download_update(filename):
    try:
        return send_from_directory('updates', filename, as_attachment=True)
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 404

# تشغيل الخادم
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=Config.DEBUG, use_reloader=False)
