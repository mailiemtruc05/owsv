import os
from flask import Flask, jsonify, request, render_template, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required
import psycopg2
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz
import requests

# Khởi tạo Flask App
app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Cấu hình PostgreSQL trên Render
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://owuser:UHOVq7BWTYMIJmxC4nqGKidby1xyIlY9@dpg-cvq9rneuk2gs73d0icd0-a/ow_cf3t"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Import Database & Models
from database import db
db.init_app(app)

from models import AllowedMachine, PendingMachine

# Tạo database nếu chưa có
with app.app_context():
    db.create_all()

# Đăng ký tài khoản admin mặc định
USERNAME = "admin"
PASSWORD = "0934828105t"

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

# ------------------- MODELS -------------------

from models import AllowedMachine, PendingMachine

# ------------------- TRANG ĐĂNG NHẬP -------------------

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

# ------------------- TRANG ADMIN -------------------

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

        # Gán timezone nếu chưa có
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


# ------------------- TRANG CHÍNH -------------------

@app.route('/')
def home():
    return "✅ Server is running!"

# ------------------- THÊM MÁY MỚI -------------------

@app.route('/add_machine', methods=['POST'])
def add_machine():
    hostname = request.form.get('hostname')
    mac = request.form.get('mac')

    if not hostname or not mac:
        flash("⛔ Vui lòng điền đầy đủ thông tin!")
        return redirect(url_for('admin'))

    if AllowedMachine.query.filter_by(mac=mac).first():
        flash("⚠️ Máy này đã có trong danh sách hợp lệ!")
        return redirect(url_for('admin'))

    new_machine = AllowedMachine(
        hostname=hostname,
        mac=mac,
        tool_name="Default",  # hoặc thay đổi theo cách bạn xử lý tool_name mặc định
        expiry_date=datetime(2025, 12, 31, 23, 59)
    )

    db.session.add(new_machine)
    db.session.commit()
    flash("✅ Thêm máy thành công!")
    return redirect(url_for('admin'))

# ------------------- API MÁY HỢP LỆ -------------------

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
        {'hostname': m.hostname, 'mac': m.mac, 'tool_name': m.tool_name, 'expiry_date': m.expiry_date}
        for m in valid_machines
    ])



@app.route('/delete_machine/<mac>/<tool_name>')
def delete_machine(mac, tool_name):
    machine = AllowedMachine.query.filter_by(mac=mac, tool_name=tool_name).first()
    if machine:
        db.session.delete(machine)
        db.session.commit()
        flash("❌ Đã xóa máy khỏi danh sách hợp lệ!")
    return redirect(url_for('admin'))

@app.route('/edit_expiry/<mac>/<tool_name>', methods=['POST'])
def edit_expiry(mac, tool_name):
    new_expiry_date_str = request.form.get('new_expiry_date')
    try:
        new_expiry_date = datetime.strptime(new_expiry_date_str, "%Y-%m-%dT%H:%M")
        new_expiry_date = new_expiry_date.replace(second=0, microsecond=0)  # ✅ chuẩn hóa
    except ValueError:
        flash("⛔ Lỗi định dạng thời gian.")
        return redirect(url_for('admin'))

    machine = AllowedMachine.query.filter_by(mac=mac, tool_name=tool_name).first()
    if machine:
        machine.expiry_date = new_expiry_date
        db.session.commit()
        flash("✅ Cập nhật ngày hết hạn thành công!")

    return redirect(url_for('admin'))


# ------------------- XỬ LÝ MÁY CHỜ DUYỆT -------------------

@app.route('/pending_machines', methods=['GET'])
def get_pending_machines():
    pending_machines = PendingMachine.query.all()
    return jsonify([{'id': m.id, 'hostname': m.hostname, 'mac': m.mac} for m in pending_machines])

@app.route('/register_machine', methods=['POST'])
def register_machine():
    data = request.get_json()
    hostname = data.get('hostname')
    mac = data.get('mac')
    tool_name = data.get('tool_name')  # 👈 lấy thêm tool_name

    if hostname and mac and tool_name:
        if AllowedMachine.query.filter_by(mac=mac, tool_name=tool_name).first() or \
           PendingMachine.query.filter_by(mac=mac, tool_name=tool_name).first():
            return jsonify({"status": "duplicate"}), 409

        new_machine = PendingMachine(hostname=hostname, mac=mac, tool_name=tool_name)
        db.session.add(new_machine)
        db.session.commit()
        return jsonify({"status": "pending"}), 200

    return jsonify({"status": "failed"}), 400


@app.route('/approve_machine/<mac>/<tool_name>', methods=['POST'])
def approve_machine(mac, tool_name):
    expiry_date_str = request.form.get('expiry_date')
    try:
        expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%dT%H:%M")
        # Chuẩn hóa (cắt giây và microsecond) để so sánh chính xác sau này
        expiry_date = expiry_date.replace(second=0, microsecond=0)
    except ValueError:
        flash("⛔ Lỗi định dạng thời gian.")
        return redirect(url_for('admin'))

    machine = PendingMachine.query.filter_by(mac=mac, tool_name=tool_name).first()

    if machine:
        new_allowed_machine = AllowedMachine(
            hostname=machine.hostname,
            mac=machine.mac,
            tool_name=machine.tool_name,
            expiry_date=expiry_date
        )
        db.session.add(new_allowed_machine)
        db.session.delete(machine)
        db.session.commit()
        flash(f"✅ Duyệt máy thành công cho tool '{tool_name}'!")
    else:
        flash("⛔ Không tìm thấy máy cần duyệt.")

    return redirect(url_for('admin'))




@app.route('/delete_pending/<mac>/<tool_name>')
def delete_pending(mac, tool_name):
    machine = PendingMachine.query.filter_by(mac=mac, tool_name=tool_name).first()
    if machine:
        db.session.delete(machine)
        db.session.commit()
        flash("❌ Đã xóa máy khỏi danh sách chờ!")
    return redirect(url_for('admin'))

@app.route('/set_permanent/<mac>/<tool_name>')
def set_permanent(mac, tool_name):
    machine = AllowedMachine.query.filter_by(mac=mac, tool_name=tool_name).first()
    if machine:
        machine.expiry_date = datetime(2099, 12, 31, 23, 59)
        db.session.commit()
        flash("✅ Đã thiết lập máy dùng vĩnh viễn!")
    return redirect(url_for('admin'))

def is_machine_allowed(mac, tool_name):
    url = f"https://your-domain/allowed_machines?tool_name={tool_name}"
    response = requests.get(url)
    if response.status_code == 200:
        machines = response.json()
        return any(m['mac'] == mac for m in machines)
    return False

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
