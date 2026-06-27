import os
import secrets
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
# Đổi tên file db sang v6 để hệ thống tự động reset bảng sạch sẽ, không lo bị lỗi cũ chặn upload
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///share_media_v6.db'
app.config['TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static/uploads')
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
    is_temporary = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    comments = db.relationship('Comment', backref='media', cascade="all, delete-orphan", lazy=True)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(500), nullable=False)
    uploader = db.Column(db.String(50), nullable=False)
    media_id = db.Column(db.Integer, db.ForeignKey('media.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def clean_expired_media():
    now = datetime.utcnow()
    expired_items = Media.query.filter(Media.is_temporary == True, Media.created_at < now - timedelta(hours=24)).all()
    for item in expired_items:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], item.filename)
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass
        db.session.delete(item)
    if expired_items:
        db.session.commit()

# --- ROUTES CONTROL ---
@app.route('/')
def index():
    if 'username' not in session:
        return redirect('/login')
    clean_expired_media()
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
        flash('Đăng ký thành công! Hãy đăng nhập.')
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

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        new_password = request.form.get('new_password').strip()
        user = User.query.filter_by(username=username).first()
        if user:
            user.password = new_password
            db.session.commit()
            flash('Đặt lại mật khẩu thành công! Hãy đăng nhập lại.')
            return redirect('/login')
        else:
            flash('Tài khoản không tồn tại trên hệ thống!')
            return redirect('/forgot-password')
    return render_template('forgot_password.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'username' not in session:
        return redirect('/login')
    if 'file' not in request.files:
        flash('Không tìm thấy tệp gửi lên!')
        return redirect('/')
    
    file = request.files['file']
    if file.filename == '':
        flash('Bạn chưa chọn file ảnh/video nào!')
        return redirect('/')
        
    storage_type = request.form.get('storage_type')
    is_temporary = (storage_type == 'temporary')
    
    if file:
        ext = file.filename.split('.')[-1].lower()
        if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
            file_type = 'image'
        elif ext in ['mp4', 'mov', 'avi', 'mkv', 'webm']:
            file_type = 'video'
        else:
            flash('Định dạng file không hỗ trợ!')
            return redirect('/')
            
        random_hex = secrets.token_hex(8)
        secure_name = f"{random_hex}_{secure_filename(file.filename)}"
        
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], secure_name))
        
        new_media = Media(
            filename=secure_name,
            file_type=file_type,
            uploader=session['username'],
            is_temporary=is_temporary
        )
        db.session.add(new_media)
        db.session.commit()
        flash('Đăng tải bài viết thành công!')
    return redirect('/')

@app.route('/comment/<int:media_id>', methods=['POST'])
def add_comment(media_id):
    if 'username' not in session:
        return redirect('/login')
    content = request.form.get('content', '').strip()
    if content:
        new_comment = Comment(content=content, uploader=session['username'], media_id=media_id)
        db.session.add(new_comment)
        db.session.commit()
    return redirect('/')

# CHỨC NĂNG XÓA: Nhận diện đúng chủ bài đăng, thực hiện xóa tệp cứng và dữ liệu database
@app.route('/delete/<int:media_id>', methods=['POST'])
def delete_media(media_id):
    if 'username' not in session:
        return redirect('/login')
    item = Media.query.get_or_404(media_id)
    # Bảo mật: Chỉ cho phép người tải lên (hoặc tài khoản có tên là admin) mới xóa được bài
    if item.uploader == session['username'] or session['username'] == 'admin':
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], item.filename)
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass
        db.session.delete(item)
        db.session.commit()
        flash('Đã xóa bài viết thành công!')
    else:
        flash('Bạn không có quyền xóa bài viết này!')
    return redirect('/')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect('/login')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
