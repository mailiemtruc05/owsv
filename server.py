import os
from flask import Flask, jsonify, request, render_template, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required
import psycopg2
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz
import requests
from dotenv import load_dotenv
import secrets

# Load biến môi trường từ .env
load_dotenv()

# Tạo một chuỗi bí mật ngẫu nhiên với độ dài 64 ký tự
secret_key = secrets.token_hex(32)  # Chuỗi hex dài 64 ký tự

# Khởi tạo Flask App
app = Flask(__name__)
app.secret_key = secret_key  # Gán chuỗi bí mật cho ứng dụng Flask

# Cấu hình PostgreSQL từ biến môi trường
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Import Database & Models
from database import db
from models import AllowedMachine, PendingMachine

db.init_app(app)

# Tạo database nếu chưa có
with app.app_context():
    db.create_all()

# Đăng ký tài khoản admin mặc định
USERNAME = "admin"
PASSWORD = "0934828105Trcdz@#"

# Cấu hình Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    if user_id == USERNAME:
        return User(user_id)
    return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == USERNAME and password == PASSWORD:
            user = User(username)
            login_user(user)
            flash("✅ Đăng nhập thành công!")
            return redirect(url_for('admin'))
        else:
            flash("⛔ Sai tài khoản hoặc mật khẩu!")
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    flash("👋 Đã đăng xuất!")
    return redirect(url_for('login'))

@app.route('/admin')
@login_required
def admin():
    vietnam_tz = pytz.timezone("Asia/Ho_Chi_Minh")
    now = datetime.now(vietnam_tz).replace(second=0, microsecond=0)

    allowed_machines = AllowedMachine.query.all()
    pending_machines = PendingMachine.query.all()

    PERMANENT_DATE = vietnam_tz.localize(datetime(2099, 12, 31, 23, 59))

    for machine in allowed_machines:
        expiry = machine.expiry_date

        if isinstance(expiry, str):
            try:
                expiry = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
            except:
                expiry = datetime.strptime(expiry, "%Y-%m-%dT%H:%M")

        expiry = expiry.replace(second=0, microsecond=0)

        if expiry.tzinfo is None:
            expiry = vietnam_tz.localize(expiry)

        if expiry == PERMANENT_DATE:
            machine.status = "Vĩnh viễn"
            machine.status_color = "blue"
        elif expiry >= now:
            machine.status = "Còn hạn"
            machine.status_color = "green"
        else:
            machine.status = "Hết hạn"
            machine.status_color = "red"

    return render_template(
        'admin.html',
        now=now.strftime('%Y-%m-%d %H:%M'),
        allowed_machines=allowed_machines,
        pending_machines=pending_machines
    )

@app.route('/')
def home():
    return "✅ Server is running!"

@app.route('/add_machine', methods=['POST'])
def add_machine():
    hostname = request.form.get('hostname')
    uuid = request.form.get('uuid')
    tool_name = request.form.get('tool_name')
    expiry_date_str = request.form.get('expiry_date')
    discord_name = request.form.get('discord_name')

    try:
        expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%dT%H:%M")
    except:
        flash("⛔ Lỗi định dạng thời gian!")
        return redirect(url_for('admin'))

    if not hostname or not uuid or not tool_name:
        flash("⛔ Vui lòng điền đầy đủ thông tin!")
        return redirect(url_for('admin'))

    # Kiểm tra máy đã có với uuid nhưng tên tool khác
    existing_machine = AllowedMachine.query.filter_by(uuid=uuid).first()
    if existing_machine and existing_machine.tool_name == tool_name:
        flash("⚠️ Máy này đã có trong danh sách hợp lệ!")
        return redirect(url_for('admin'))

    # Kiểm tra máy trong PendingMachine với cùng uuid và tool_name
    existing_pending_machine = PendingMachine.query.filter_by(uuid=uuid).first()
    if existing_pending_machine:
        flash("⚠️ Máy này đang chờ duyệt!")
        return redirect(url_for('admin'))

    new_machine = AllowedMachine(
        hostname=hostname,
        uuid=uuid,
        tool_name=tool_name,
        expiry_date=expiry_date,
        discord_name=discord_name
    )

    db.session.add(new_machine)
    db.session.commit()
    flash("✅ Thêm máy thành công!")
    return redirect(url_for('admin'))

@app.route('/allowed_machines', methods=['GET'])
def get_allowed_machines():
    tool_name = request.args.get('tool_name')
    now = datetime.now().replace(second=0, microsecond=0)

    if not tool_name:
        return jsonify({"status": "tool_name_required"}), 400

    valid_machines = AllowedMachine.query.filter(
        AllowedMachine.tool_name == tool_name,
        AllowedMachine.expiry_date >= now.strftime('%Y-%m-%d %H:%M')
    ).all()

    return jsonify([
        {'hostname': m.hostname, 'uuid': m.uuid, 'tool_name': m.tool_name, 'expiry_date': m.expiry_date, 'discord_name': m.discord_name}
        for m in valid_machines
    ])

@app.route('/delete_machine/<uuid>/<tool_name>')
def delete_machine(uuid, tool_name):
    machine = AllowedMachine.query.filter_by(uuid=uuid, tool_name=tool_name).first()
    if machine:
        db.session.delete(machine)
        db.session.commit()
        flash("❌ Đã xóa máy khỏi danh sách hợp lệ!")
    return redirect(url_for('admin'))

@app.route('/edit_expiry/<uuid>/<tool_name>', methods=['POST'])
def edit_expiry(uuid, tool_name):
    new_expiry_date_str = request.form.get('new_expiry_date')
    discord_name = request.form.get('discord_name')
    try:
        new_expiry_date = datetime.strptime(new_expiry_date_str, "%Y-%m-%dT%H:%M")
        new_expiry_date = new_expiry_date.replace(second=0, microsecond=0)
    except ValueError:
        flash("⛔ Lỗi định dạng thời gian.")
        return redirect(url_for('admin'))

    machine = AllowedMachine.query.filter_by(uuid=uuid, tool_name=tool_name).first()
    if machine:
        machine.expiry_date = new_expiry_date
        machine.discord_name = discord_name
        db.session.commit()
        flash("✅ Cập nhật thành công!")

    return redirect(url_for('admin'))

@app.route('/set_permanent/<uuid>/<tool_name>')
def set_permanent(uuid, tool_name):
    machine = AllowedMachine.query.filter_by(uuid=uuid, tool_name=tool_name).first()
    if machine:
        machine.expiry_date = datetime(2099, 12, 31, 23, 59)
        db.session.commit()
        flash("✅ Đã thiết lập máy dùng vĩnh viễn!")
    return redirect(url_for('admin'))

@app.route('/pending_machines', methods=['GET'])
def get_pending_machines():
    pending_machines = PendingMachine.query.all()
    return jsonify([{'id': m.id, 'hostname': m.hostname, 'uuid': m.uuid} for m in pending_machines])

@app.route('/register_machine', methods=['POST'])
def register_machine():
    data = request.get_json()
    hostname = data.get('hostname')
    uuid = data.get('uuid')
    tool_name = data.get('tool_name')

    if hostname and uuid and tool_name:
        if AllowedMachine.query.filter_by(uuid=uuid, tool_name=tool_name).first() or \
           PendingMachine.query.filter_by(uuid=uuid, tool_name=tool_name).first():
            return jsonify({"status": "duplicate"}), 409

        new_machine = PendingMachine(hostname=hostname, uuid=uuid, tool_name=tool_name)
        db.session.add(new_machine)
        db.session.commit()
        return jsonify({"status": "pending"}), 200

    return jsonify({"status": "failed"}), 400

@app.route('/approve_machine/<uuid>/<tool_name>', methods=['POST'])
def approve_machine(uuid, tool_name):
    expiry_date_str = request.form.get('expiry_date')
    discord_name = request.form.get('discord_name')  # Lấy discord_name từ form
    
    try:
        expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%dT%H:%M")
        expiry_date = expiry_date.replace(second=0, microsecond=0)
    except ValueError:
        flash("⛔ Lỗi định dạng thời gian.")
        return redirect(url_for('admin'))

    machine = PendingMachine.query.filter_by(uuid=uuid, tool_name=tool_name).first()

    if machine:
        new_allowed_machine = AllowedMachine(
            hostname=machine.hostname,
            uuid=machine.uuid,
            tool_name=machine.tool_name,
            expiry_date=expiry_date,
            discord_name=discord_name  # Gán discord_name từ form
        )
        db.session.add(new_allowed_machine)
        db.session.delete(machine)
        db.session.commit()
        flash(f"✅ Duyệt máy thành công cho tool '{tool_name}'!")
    else:
        flash("⛔ Không tìm thấy máy cần duyệt.")

    return redirect(url_for('admin'))

@app.route('/delete_pending/<uuid>/<tool_name>')
def delete_pending(uuid, tool_name):
    machine = PendingMachine.query.filter_by(uuid=uuid, tool_name=tool_name).first()
    if machine:
        db.session.delete(machine)
        db.session.commit()
        flash("❌ Đã xóa máy khỏi danh sách chờ!")
    return redirect(url_for('admin'))

def is_machine_allowed(uuid, tool_name):
    url = f"https://your-domain/allowed_machines?tool_name={tool_name}"
    response = requests.get(url)
    if response.status_code == 200:
        machines = response.json()
        return any(m['uuid'] == uuid for m in machines)
    return False

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
