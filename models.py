from database import db
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

# AllowedMachine Model
class AllowedMachine(db.Model):
    __tablename__ = 'allowed_machines'
    
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(255), nullable=False)
    uuid = db.Column(UUID(as_uuid=True), nullable=False)  # Use UUID type for PostgreSQL
    tool_name = db.Column(db.String(255), nullable=False)
    expiry_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    discord_name = db.Column(db.String(100), nullable=True)

    # Unique constraint for uuid and tool_name combination
    __table_args__ = (db.UniqueConstraint('uuid', 'tool_name', name='unique_uuid_tool'),)

# PendingMachine Model
class PendingMachine(db.Model):
    __tablename__ = 'pending_machines'
    
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(255), nullable=False)
    uuid = db.Column(UUID(as_uuid=True), nullable=False)  # Use UUID type for PostgreSQL
    tool_name = db.Column(db.String(255), nullable=False)
    discord_name = db.Column(db.String(100), nullable=True)

    # Unique constraint for uuid and tool_name combination
    __table_args__ = (db.UniqueConstraint('uuid', 'tool_name', name='pending_unique_uuid_tool'),)
