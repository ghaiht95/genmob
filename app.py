import os
from dotenv import load_dotenv
from flask import Flask, request
from flask_cors import CORS  # تأكد من استيراد CORS
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from models import RoomPlayer, db, ChatMessage, Room  # تأكد من استيراد ChatMessage بشكل صحيح
from config import Config
from routes.auth import auth_bp
from routes.rooms import rooms_bp
from routes.friends import friends_bp  # استيراد وحدة الأصدقاء
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
import sqlalchemy.exc
import time
import threading
import requests
import atexit
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)

# تكوين JWT
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'super-secret')  # يجب تغييره في الإنتاج
jwt = JWTManager(app)

# Enable CORS
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# Initialize Database
db.init_app(app)

# Initialize Flask-Migrate
migrate = Migrate(app, db)

# Enable WebSocket
socketio = SocketIO(app, cors_allowed_origins="*", logger=True)

# Dictionary to track disconnected players and their timers
disconnected_players = {}

# Dictionary to track player sessions (sid -> (room_id, username))
player_sessions = {}

# آخر وقت تم فيه تنظيف الغرف
last_cleanup_time = datetime.now()

# تنظيف الغرف الفارغة
def cleanup_empty_rooms():
    with app.app_context():
        try:
            print("🧹 بدء عملية تنظيف الغرف الفارغة...")
            # البحث عن الغرف
            rooms = Room.query.all()
            cleaned_rooms = 0
            
            for room in rooms:
                # التحقق من عدد اللاعبين في الغرفة
                players_count = RoomPlayer.query.filter_by(room_id=room.id).count()
                
                # إذا كانت الغرفة فارغة، نقوم بتنظيفها
                if players_count == 0 or players_count != room.current_players:
                    # تصحيح عدد اللاعبين إذا كان غير متطابق
                    if players_count != room.current_players and players_count > 0:
                        print(f"⚠️ تصحيح عدد اللاعبين في الغرفة {room.id}: {room.current_players} -> {players_count}")
                        room.current_players = players_count
                        db.session.commit()
                    
                    # إذا كانت الغرفة فارغة فعلاً، نقوم بحذفها
                    if players_count == 0:
                        print(f"🗑️ حذف الغرفة الفارغة: {room.id} ({room.name})")
                        # حذف هاب VPN والتحقق من المحولات
                        try:
                            from services.softether import SoftEtherVPN
                            vpn = SoftEtherVPN()
                            hub_name = f"room_{room.id}"
                            
                            # التحقق من المحولات المرتبطة بالغرفة وتركها إذا كانت موجودة ومستخدمة
                            adapter_name = "VPN"  # استخدام اسم ثابت "VPN" مطابق للعميل
                            if vpn.adapter_exists(adapter_name):
                                # يمكن تنفيذ منطق إضافي هنا للتحقق مما إذا كان المحول مستخدمًا من قبل غرف أخرى
                                # إذا كان غير مستخدم، يمكن حذفه
                                # في هذه الحالة، نقرر تركه للاستخدام المستقبلي
                                print(f"🔌 تم العثور على المحول {adapter_name}، سيتم الاحتفاظ به للاستخدام مستقبلاً")
                            
                            vpn.delete_hub(hub_name)
                            print(f"✅ تم حذف هاب VPN: {hub_name}")
                        except Exception as e:
                            print(f"❌ خطأ أثناء حذف هاب VPN: {e}")
                        
                        # حذف رسائل الدردشة والغرفة
                        ChatMessage.query.filter_by(room_id=room.id).delete()
                        db.session.delete(room)
                        cleaned_rooms += 1
            
            # حفظ التغييرات
            db.session.commit()
            print(f"✅ اكتملت عملية التنظيف: تم حذف {cleaned_rooms} غرفة فارغة")
            
            # تنظيف بيانات الجلسات غير المستخدمة
            cleanup_inactive_sessions()
            
        except Exception as e:
            print(f"❌ خطأ أثناء تنظيف الغرف الفارغة: {e}")
            db.session.rollback()

# تنظيف بيانات الجلسات غير المستخدمة
def cleanup_inactive_sessions():
    try:
        print("🧹 بدء عملية تنظيف الجلسات غير المستخدمة...")
        
        # جمع معرّفات الجلسات التي لها لاعبين في قاعدة البيانات
        active_players = {}
        players = RoomPlayer.query.all()
        for player in players:
            active_players[(str(player.room_id), player.player_username)] = True
        
        # حذف بيانات الجلسات المنقطعة التي لم تعد موجودة في قاعدة البيانات
        disconnected_to_remove = []
        for (room_id, username) in disconnected_players:
            if (room_id, username) not in active_players:
                disconnected_to_remove.append((room_id, username))
        
        for key in disconnected_to_remove:
            sid = disconnected_players[key]
            print(f"🗑️ حذف المستخدم المنقطع: {key[1]} من الغرفة {key[0]}")
            del disconnected_players[key]
            # إذا كان معرّف الجلسة موجودًا في player_sessions، قم بحذفه أيضًا
            if sid in player_sessions:
                del player_sessions[sid]
        
        # حذف بيانات الجلسات النشطة التي لم تعد موجودة في قاعدة البيانات
        sessions_to_remove = []
        for sid, (room_id, username) in player_sessions.items():
            if (room_id, username) not in active_players:
                sessions_to_remove.append(sid)
        
        for sid in sessions_to_remove:
            room_id, username = player_sessions[sid]
            print(f"🗑️ حذف جلسة غير مستخدمة: {username} من الغرفة {room_id}")
            del player_sessions[sid]
        
        print(f"✅ اكتملت عملية تنظيف الجلسات: {len(disconnected_to_remove)} منقطعة، {len(sessions_to_remove)} غير مستخدمة")
    
    except Exception as e:
        print(f"❌ خطأ أثناء تنظيف الجلسات غير المستخدمة: {e}")

# تشغيل التنظيف الدوري أثناء معالجة الطلبات
@app.before_request
def check_cleanup_needed():
    global last_cleanup_time
    # تنظيف كل 15 دقيقة
    if datetime.now() - last_cleanup_time > timedelta(minutes=15):
        last_cleanup_time = datetime.now()
        # تشغيل التنظيف في خيط منفصل لعدم تأخير الطلب الحالي
        threading.Thread(target=cleanup_empty_rooms, daemon=True).start()

# تنظيف عند إيقاف الخادم
@atexit.register
def cleanup_on_shutdown():
    print("🔴 تنظيف الغرف قبل إيقاف الخادم...")
    cleanup_empty_rooms()

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
app.register_blueprint(friends_bp, url_prefix='/friends')  # تسجيل وحدة الأصدقاء

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


# دالة للتعامل مع الـ commit مع محاولات إعادة في حالة قفل قاعدة البيانات
def commit_with_retry(max_retries=5, retry_delay=0.5):
    """Commit database changes with retry for locked database."""
    for attempt in range(max_retries):
        try:
            db.session.commit()
            return True  # نجاح
        except sqlalchemy.exc.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                db.session.rollback()  # التراجع عن العملية
                time.sleep(retry_delay * (attempt + 1))  # انتظار متزايد
                continue
            else:
                db.session.rollback()
                raise  # إعادة رفع الخطأ إذا لم يكن متعلق بالقفل أو استنفدنا المحاولات
    return False  # فشل بعد كل المحاولات

# دالة لإزالة اللاعب من الغرفة بعد انقطاع الاتصال
def remove_player_after_timeout(room_id, username, sid):
    print(f"⏱️ انتظار 60 ثانية قبل إزالة اللاعب {username} من الغرفة {room_id}")
    time.sleep(60)  # انتظار 60 ثانية
    
    # تحقق مما إذا كان اللاعب لا يزال في قائمة المنقطعين
    # (إذا عاد للاتصال، سيتم إزالته من القائمة)
    if (room_id, username) in disconnected_players:
        with app.app_context():
            print(f"🔴 انقضت المهلة، إزالة اللاعب {username} من الغرفة {room_id}")
            # حذف اللاعب من قاعدة البيانات
            player = RoomPlayer.query.filter_by(room_id=room_id, player_username=username).first()
            if player:
                # استخدام API الخاص بنا لمغادرة الغرفة
                try:
                    # تحقق من عدد اللاعبين المتبقين
                    is_host = player.is_host  # حفظ قيمة is_host قبل حذف اللاعب
                    db.session.delete(player)
                    db.session.flush()
                    
                    players_left = RoomPlayer.query.filter_by(room_id=room_id).count()
                    room = Room.query.get(room_id)
                    is_last_player = players_left == 0
                    
                    # استدعاء API مع معلومة ما إذا كان هذا آخر لاعب
                    api_url = f"{os.getenv('API_BASE_URL', 'http://localhost:5000')}/leave_room"
                    response = requests.post(
                        api_url, 
                        json={
                            "room_id": room_id,
                            "username": username,
                            "is_last_player": is_last_player
                        },
                        timeout=5  # timeout de 5 segundos para evitar bloqueos
                    )
                    
                    if is_last_player:
                        print(f"✅ غرفة {room_id} فارغة وتم تنظيفها")
                    else:
                        print(f"✅ تم إخراج اللاعب {username} من الغرفة {room_id} والـ VPN hub")
                        
                        # إذا كان اللاعب هو المضيف، نقوم بتعيين مضيف جديد
                        if is_host and room:
                            new_host = RoomPlayer.query.filter_by(room_id=room_id).first()
                            if new_host:
                                new_host.is_host = True
                                room.owner_username = new_host.player_username
                                db.session.commit()
                                print(f"New host assigned: {new_host.player_username}")
                
                except Exception as e:
                    print(f"❌ خطأ أثناء استدعاء API لإزالة اللاعب: {e}")
                    # إذا فشل استدعاء API، نحذف اللاعب مباشرة من قاعدة البيانات
                    try:
                        # التحقق مما إذا كان اللاعب لا يزال موجودًا في قاعدة البيانات
                        player_still_exists = RoomPlayer.query.filter_by(room_id=room_id, player_username=username).first()
                        if player_still_exists:
                            db.session.delete(player_still_exists)
                        
                        # تحقق من عدد اللاعبين المتبقين
                        players_left = RoomPlayer.query.filter_by(room_id=room_id).count()
                        room = Room.query.get(room_id)
                        if players_left == 0 and room:
                            ChatMessage.query.filter_by(room_id=room_id).delete()
                            db.session.delete(room)
                        elif is_host and room:  # Si era host y no es el último jugador
                            new_host = RoomPlayer.query.filter_by(room_id=room_id).first()
                            if new_host:
                                new_host.is_host = True
                                room.owner_username = new_host.player_username
                        
                        commit_with_retry()
                    except Exception as inner_e:
                        print(f"❌❌ خطأ ثانوي أثناء تنظيف البيانات: {inner_e}")
                        db.session.rollback()
                
                # إزالة اللاعب من قائمة المنقطعين
                del disconnected_players[(room_id, username)]
                
                # تنظيف بيانات الجلسة إذا كانت لا تزال موجودة
                if sid in player_sessions:
                    del player_sessions[sid]
                
                # إخطار جميع اللاعبين في الغرفة
                socketio.emit('user_left', {'username': username}, room=room_id)
                
                # تحديث قائمة اللاعبين
                players = get_players_for_room(room_id)
                socketio.emit('update_players', {'players': players}, room=room_id)

# إعدادات الاتصال بالـ WebSocket
@socketio.on('join')
def handle_join(data):
    room_id = str(data['room_id'])
    username = data['username']
    join_room(room_id)
    
    # Store the player's session ID
    player_sessions[request.sid] = (room_id, username)

    # إذا كان اللاعب في قائمة المنقطعين، نزيله منها
    if (room_id, username) in disconnected_players:
        print(f"🟢 اللاعب {username} عاد للاتصال بالغرفة {room_id}")
        del disconnected_players[(room_id, username)]

    # أولاً: حفظ اللاعب في قاعدة البيانات إذا مش موجود
    existing_player = RoomPlayer.query.filter_by(room_id=room_id, player_username=username).first()
    if not existing_player:
        new_player = RoomPlayer(room_id=room_id, player_username=username, is_host=False, username=username)
        db.session.add(new_player)
        try:
            commit_with_retry()
            print(f"Added player {username} to RoomPlayer table.")
        except Exception as e:
            print(f"Error adding player to database: {e}")
            emit('error', {'message': 'Database error'}, room=room_id)
            return

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
    is_last_player = data.get('is_last_player', False)
    
    print(f"[DEBUG] Player {username} leaving room {room_id}, is_last_player: {is_last_player}")
    
    # Remove the player's session
    if request.sid in player_sessions:
        del player_sessions[request.sid]

    # حذف اللاعب من قاعدة البيانات
    player = RoomPlayer.query.filter_by(room_id=room_id, player_username=username).first()
    if player:
        is_host = player.is_host  # حفظ قيمة is_host قبل حذف اللاعب
        db.session.delete(player)
        try:
            db.session.flush()  # نستخدم flush بدلاً من commit للتحقق من عدد اللاعبين المتبقين
            print(f"Removed player {username} from RoomPlayer table.")
            
            # التحقق من عدد اللاعبين المتبقين
            players_left = RoomPlayer.query.filter_by(room_id=room_id).count()
            room = Room.query.get(room_id)
            
            if room:
                room.current_players = players_left
                
                if is_last_player or players_left == 0:
                    # حذف هاب VPN عند خروج آخر لاعب
                    hub_name = f"room_{room_id}"
                    print(f"Deleting VPN hub: {hub_name} - Room is empty")
                    
                    try:
                        # استخدام API للتنظيف الكامل
                        api_url = f"{os.getenv('API_BASE_URL', 'http://localhost:5000')}/leave_room"
                        response = requests.post(
                            api_url, 
                            json={
                                "room_id": room_id,
                                "username": username,
                                "is_last_player": True
                            },
                            timeout=5
                        )
                        print(f"✅ Room {room_id} cleaned up via API, status: {response.status_code}")
                        
                        # حذف الغرفة من قاعدة البيانات
                        ChatMessage.query.filter_by(room_id=room_id).delete()
                        db.session.delete(room)
                        print(f"✅ Room {room_id} deleted from database")
                    except Exception as e:
                        print(f"❌ Error calling cleanup API: {e}")
                        # يمكن إضافة تنظيف يدوي هنا
                        try:
                            ChatMessage.query.filter_by(room_id=room_id).delete()
                            db.session.delete(room)
                            print(f"✅ Manual cleanup of room {room_id} successful")
                        except Exception as inner_e:
                            print(f"❌❌ Error during manual cleanup: {inner_e}")
                else:
                    # إذا كان اللاعب هو المضيف، نقوم بتعيين مضيف جديد
                    if is_host:
                        new_host = RoomPlayer.query.filter_by(room_id=room_id).first()
                        if new_host:
                            new_host.is_host = True
                            room.owner_username = new_host.player_username
                            print(f"New host assigned: {new_host.player_username}")
            
            commit_with_retry()
        except Exception as e:
            print(f"Error removing player from database: {e}")
            db.session.rollback()
            emit('error', {'message': 'Database error'}, room=room_id)
            return

    # إرسال إشعارات للاعبين الآخرين
    emit('user_left', {'username': username}, room=room_id)

    # تحديث قائمة اللاعبين
    players = get_players_for_room(room_id)
    print(f"Players for room {room_id}: {players}")
    emit('update_players', {'players': players}, room=room_id)
    
    # إذا كانت الغرفة فارغة، نقوم بتحديث قائمة الغرف للجميع
    if is_last_player or (room and room.current_players == 0):
        emit('rooms_updated', broadcast=True)
        
    # إرسال تأكيد للمستخدم الذي غادر
    emit('leave_confirmed', {'status': 'success'}, room=request.sid)


# حدث انقطاع الاتصال
@socketio.on('disconnect')
def handle_disconnect():
    print(f"🔌 انقطاع اتصال من المستخدم SID: {request.sid}")
    
    # Check if this session belongs to a player
    if request.sid in player_sessions:
        room_id, username = player_sessions[request.sid]
        print(f"🟡 اللاعب {username} انقطع اتصاله من الغرفة {room_id}, سيتم الانتظار 60 ثانية قبل الإزالة")
        
        # تأكد من أن اللاعب لا يزال في قاعدة البيانات (قد يكون غادر بالفعل)
        player = RoomPlayer.query.filter_by(room_id=room_id, player_username=username).first()
        if player:
            # Add to disconnected players list
            disconnected_players[(room_id, username)] = request.sid
            
            # Start a timer to remove the player after 60 seconds
            timer_thread = threading.Thread(
                target=remove_player_after_timeout,
                args=(room_id, username, request.sid)
            )
            timer_thread.daemon = True
            timer_thread.start()
        else:
            print(f"🔵 اللاعب {username} قد غادر الغرفة {room_id} بالفعل، لن يتم إطلاق مؤقت")
            # تنظيف البيانات
            if request.sid in player_sessions:
                del player_sessions[request.sid]

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
    try:
        commit_with_retry()
    except Exception as e:
        print(f"Error saving message to database: {e}")
        emit('error', {'message': 'Database error'}, room=room_id)
        return

    # نرسل الرسالة لكل الموجودين بالغرفة
    emit('new_message', {
        'sender': sender,
        'message': message,
        'time': msg.timestamp.strftime("%H:%M:%S")
    }, room=room_id)

# حدث الـ heartbeat للتأكد من اتصال اللاعب
@socketio.on('heartbeat')
def handle_heartbeat(data):
    room_id = str(data['room_id'])
    username = data['username']
    
    # إذا كان اللاعب في قائمة المنقطعين، نزيله منها لأنه أرسل نبضة
    if (room_id, username) in disconnected_players:
        print(f"💓 استلام نبضة من اللاعب {username} في الغرفة {room_id} - إعادة الاتصال")
        del disconnected_players[(room_id, username)]
    else:
        print(f"💓 استلام نبضة من اللاعب {username} في الغرفة {room_id}")
        
    # تحديث معرف الجلسة في حالة تغيره
    player_sessions[request.sid] = (room_id, username)

# تشغيل الخادم
if __name__ == '__main__':
    # تشغيل مهمة مجدولة لتنظيف الاتصالات غير النشطة واللاعبين المنقطعين
    def check_inactive_connections():
        current_time = time.time()
        print(f"🔍 فحص الاتصالات غير النشطة - {len(player_sessions)} اتصال نشط، {len(disconnected_players)} اتصال منقطع")
        
        # تنظيف قاعدة البيانات من الغرف الفارغة
        cleanup_empty_rooms()
        
        # جدولة المهمة التالية
        socketio.sleep(300)  # كل 5 دقائق
        socketio.start_background_task(check_inactive_connections)
    
    # بدء المهمة المجدولة
    socketio.start_background_task(check_inactive_connections)
    
    # تشغيل الخادم
    socketio.run(app, host='0.0.0.0', port=5000, debug=Config.DEBUG, use_reloader=False)
