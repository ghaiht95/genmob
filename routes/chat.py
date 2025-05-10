from flask import request
from flask_socketio import SocketIO, emit, join_room, leave_room
from models import db, ChatMessage

socketio = SocketIO(cors_allowed_origins="*")

# لما لاعب ينضم لغرفة
@socketio.on('join')
def handle_join(data):
    room_id = str(data['room_id'])
    join_room(room_id)
    emit('status', {'msg': f"{data['username']} انضم للغرفة"}, room=room_id)

# لما لاعب يرسل رسالة
@socketio.on('send_message')
def handle_send_message(data):
    room_id = str(data['room_id'])
    sender = data['sender']
    message = data['message']

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

# لما لاعب يكتب (typing)
@socketio.on('typing')
def handle_typing(data):
    room_id = str(data['room_id'])
    username = data['username']

    emit('typing', {
        'username': username
    }, room=room_id, include_self=False)

# لما لاعب يغادر الغرفة
# @socketio.on('leave')
# def handle_leave(data):
#     room_id = str(data['room_id'])
#     leave_room(room_id)
    # emit('status', {'msg': f"{data['username']} غادر الغرفة"}, room=room_id)
