from database import db

class AllowedMachine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(255), nullable=False)
    uuid = db.Column(db.String(255), nullable=False)
    tool_name = db.Column(db.String(255), nullable=False)  # NEW FIELD
    expiry_date = db.Column(db.DateTime, nullable=False)
    discord_name = db.Column(db.String(100), nullable=True)

    __table_args__ = (db.UniqueConstraint('uuid', 'tool_name', name='unique_uuid_tool'),)



class PendingMachine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(255), nullable=False)
    uuid = db.Column(db.String(255), nullable=False)
    tool_name = db.Column(db.String(255), nullable=False)
    discord_name = db.Column(db.String(100), nullable=True)
    

    __table_args__ = (db.UniqueConstraint('uuid', 'tool_name', name='pending_unique_uuid_tool'),)


