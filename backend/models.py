from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id                = db.Column(db.Integer, primary_key=True)
    username          = db.Column(db.String(80), nullable=False)
    email             = db.Column(db.String(120), unique=True, nullable=False)
    password_hash     = db.Column(db.String(128), nullable=False)
    verification_code = db.Column(db.String(10), nullable=True)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)
# نموذج علاقات الصداقة
class Friendship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    friend_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'accepted', 'declined'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # العلاقات
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('sent_requests', lazy='dynamic'))
    friend = db.relationship('User', foreign_keys=[friend_id], backref=db.backref('received_requests', lazy='dynamic'))

    # ضمان عدم تكرار علاقات الصداقة
    __table_args__ = (
        db.UniqueConstraint('user_id', 'friend_id', name='unique_friendship'),
    )
    
class Room(db.Model):
    __tablename__ = 'room'
    __mapper_args__ = {'confirm_deleted_rows': False}
    
    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(100), unique=True, nullable=False)
    owner_username  = db.Column(db.String(100), nullable=False)
    description     = db.Column(db.Text)
    is_private      = db.Column(db.Boolean, default=False)
    password        = db.Column(db.String(100))
    max_players     = db.Column(db.Integer, default=8)
    current_players = db.Column(db.Integer, default=0)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

class RoomPlayer(db.Model):
    __tablename__ = 'room_player'
    __mapper_args__ = {'confirm_deleted_rows': False}
    
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    player_username = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(100), nullable=False)
    is_host = db.Column(db.Boolean, default=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('room_id', 'player_username', name='unique_player_in_room'),
    )


class ChatMessage(db.Model):
    __tablename__ = 'chat_message'
    __mapper_args__ = {'confirm_deleted_rows': False}
    
    id        = db.Column(db.Integer, primary_key=True)
    room_id   = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    username  = db.Column(db.String(100), nullable=False)
    message   = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
