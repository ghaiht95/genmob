from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, UTC
import re

db = SQLAlchemy()

class User(db.Model):
    id                = db.Column(db.Integer, primary_key=True)
    username          = db.Column(db.String(80), nullable=False, unique=True, index=True)
    email             = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash     = db.Column(db.String(128), nullable=False)
    verification_code = db.Column(db.String(10), nullable=True)
    created_at        = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at        = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # العلاقات
    owned_rooms = db.relationship('Room', backref='owner', lazy='dynamic', foreign_keys='Room.owner_username')
    rooms = db.relationship('RoomPlayer', backref='player', lazy='dynamic')
    messages = db.relationship('ChatMessage', backref='sender', lazy='dynamic')

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    @staticmethod
    def validate_username(username):
        if not username or len(username) < 3:
            return False
        return bool(re.match(r'^[a-zA-Z0-9_]+$', username))

    @staticmethod
    def validate_email(email):
        if not email:
            return False
        return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))

# نموذج علاقات الصداقة
class Friendship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    friend_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'accepted', 'declined'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

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
    name            = db.Column(db.String(100), unique=True, nullable=False, index=True)
    owner_username  = db.Column(db.String(100), db.ForeignKey('user.username'), nullable=False, index=True)
    description     = db.Column(db.Text)
    is_private      = db.Column(db.Boolean, default=False)
    password        = db.Column(db.String(100))
    max_players     = db.Column(db.Integer, default=8)
    current_players = db.Column(db.Integer, default=0)
    created_at      = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at      = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # العلاقات
    players = db.relationship('RoomPlayer', backref='room', lazy='dynamic', cascade='all, delete-orphan')
    messages = db.relationship('ChatMessage', backref='room', lazy='dynamic', cascade='all, delete-orphan')

    @staticmethod
    def validate_name(name):
        if not name or len(name) < 3:
            return False
        return bool(re.match(r'^[a-zA-Z0-9_\s-]+$', name))

class RoomPlayer(db.Model):
    __tablename__ = 'room_player'
    __mapper_args__ = {'confirm_deleted_rows': False}
    
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id', ondelete='CASCADE'), nullable=False, index=True)
    player_username = db.Column(db.String(100), db.ForeignKey('user.username'), nullable=False, index=True)
    username = db.Column(db.String(100), nullable=False)
    is_host = db.Column(db.Boolean, default=False)
    joined_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    __table_args__ = (
        db.UniqueConstraint('room_id', 'player_username', name='unique_player_in_room'),
    )


class ChatMessage(db.Model):
    __tablename__ = 'chat_message'
    __mapper_args__ = {'confirm_deleted_rows': False}
    
    id        = db.Column(db.Integer, primary_key=True)
    room_id   = db.Column(db.Integer, db.ForeignKey('room.id', ondelete='CASCADE'), nullable=False, index=True)
    username  = db.Column(db.String(100), db.ForeignKey('user.username'), nullable=False, index=True)
    message   = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    @staticmethod
    def validate_message(message):
        if not message or len(message.strip()) == 0:
            return False
        return len(message) <= 1000  # حد أقصى للرسالة
