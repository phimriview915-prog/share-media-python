   import os
import secrets
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, flash, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

# Chỉ định rõ ràng thư mục chứa giao diện (templates) và tệp tải lên (static)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
template_dir = os.path.join(BASE_DIR, 'Share_media', 'templates')
static_dir = os.path.join(BASE_DIR, 'Share_media', 'static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///share_media.db'
app.config['TRACK_MODIFICATIONS'] = False

app.config['UPLOAD_FOLDER'] = os.path.join(static_dir, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)

# --- DATABASE MODELS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

class Media(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)
    uploader = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(500), nullable=False)
    uploader = db.Column(db.String(50), nullable=False)
    media_id = db.Column(db.Integer, db.ForeignKey('media.id'), nullable=False)

Media.comments = db.relationship('Comment', backref='media', cascade="all, delete-orphan", lazy=True)

@app.route('/')
def index():
    if 'username' not in session:
        return redirect('/login')
    all_media = Media.query.order_by(Media.created_at.desc()).all()
    return render_template('index.html', media_list=all_media, current_user=session['username'])

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()
        if not username or not password:
            flash('Vui lòng điền đầy đủ thông tin!')
            return redirect('/register')
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Tài khoản này đã tồn tại!')
            return redirect('/register')
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash('Đăng ký thành công!')
        return redirect('/login')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['username'] = username
            return redirect('/')
        else:
            flash('Sai tài khoản hoặc mật khẩu!')
            return redirect('/login')
    return render_template('login.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'username' not in session:
        return redirect('/login')
    if 'file' not in request.files:
        flash('Không tìm thấy tệp!')
        return redirect('/')
    file = request.files['file']
    if file.filename == '':
        flash('Bạn chưa chọn file!')
        return redirect('/')
    if file:
        ext = file.filename.split('.')[-1].lower()
        file_type = 'image' if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp'] else 'video'
        random_hex = secrets.token_hex(8)
        secure_name = f"{random_hex}_{secure_filename(file.filename)}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], secure_name))
        new_media = Media(filename=secure_name, file_type=file_type, uploader=session['username'])
        db.session.add(new_media)
        db.session.commit()
        flash('Đăng tải thành công!')
    return redirect('/')

@app.route('/delete/<int:media_id>', methods=['POST'])
def delete_media(media_id):
    if 'username' not in session:
        return redirect('/login')
    item = Media.query.get_or_404(media_id)
    if item.uploader == session['username'] or session['username'] == 'admin':
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], item.filename)
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass
        db.session.delete(item)
        db.session.commit()
        flash('Đã xóa bài viết thành công!')
    return redirect('/')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect('/login')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
