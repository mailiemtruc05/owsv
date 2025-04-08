from database import db

class AllowedMachine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(255), nullable=False)
    mac = db.Column(db.String(255), unique=False, nullable=False)
    tool_name = db.Column(db.String(255), nullable=False)  # NEW FIELD
    expiry_date = db.Column(db.DateTime, nullable=False)

    __table_args__ = (db.UniqueConstraint('mac', 'tool_name', name='unique_mac_tool'),)



class PendingMachine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(255), nullable=False)
    mac = db.Column(db.String(255), nullable=False)  # <-- bỏ unique=True
    tool_name = db.Column(db.String(255), nullable=False)

    __table_args__ = (db.UniqueConstraint('mac', 'tool_name', name='pending_unique_mac_tool'),)


