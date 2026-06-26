import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'chuoi_bi_mat_sieu_bao_mat_cua_rieng_ban' # Dùng để bảo mật session

# --- CẤU HÌNH ĐƯỜNG DẪN VÀ DATABASE ---
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'avi', 'mov'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Khởi tạo database
db = SQLAlchemy(app)

# Tự động tạo thư mục chứa file upload nếu chưa có
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ==============================================================================
# ĐỊNH NGHĨA CƠ SỞ DỮ LIỆU (DATABASE MODELS)
# ==============================================================================

# Bảng người dùng (Lưu tài khoản & mật khẩu)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

# Bảng dữ liệu Media (Lưu thông tin ảnh/video đã upload)
class Media(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)  # 'image' hoặc 'video'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Tạo mối liên kết để lấy tên người đăng dễ dàng hơn
    user = db.relationship('User', backref=db.backref('medias', lazy=True))


# Hàm kiểm tra đuôi file xem có hợp lệ không
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ==============================================================================
# ĐIỀU HƯỚNG WEB (ROUTES)
# ==============================================================================

# 1. TRANG CHỦ: Hiển thị tất cả ảnh/video cho mọi người cùng xem
@app.route('/')
def index():
    # Lấy toàn bộ media từ mới nhất đến cũ nhất
    all_media = Media.query.order_by(Media.id.desc()).all()
    return render_template('index.html', media_list=all_media)


# 2. ĐĂNG KÝ TÀI KHOẢN
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        if not username or not password:
            flash('Vui lòng điền đầy đủ thông tin!')
            return redirect(url_for('register'))

        # Kiểm tra tài khoản đã tồn tại chưa
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Tên đăng nhập này đã có người sử dụng!')
            return redirect(url_for('register'))
            
        # Mã hóa mật khẩu trước khi lưu để bảo mật
        hashed_password = generate_password_hash(password, method='scrypt')
        
        # Lưu user mới vào database
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Đăng ký tài khoản thành công! Mời bạn đăng nhập.')
        return redirect(url_for('login'))
        
    return render_template('register.html')


# 3. ĐĂNG NHẬP
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        user = User.query.filter_by(username=username).first()
        
        # Xác minh mật khẩu
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Đăng nhập thành công! Chào mừng bạn quay trở lại.')
            return redirect(url_for('index'))
        else:
            flash('Tài khoản hoặc mật khẩu không chính xác!')
            
    return render_template('login.html')


# 4. ĐĂNG XUẤT
@app.route('/logout')
def logout():
    session.clear() # Xóa sạch phiên đăng nhập
    flash('Bạn đã đăng xuất thành công.')
    return redirect(url_for('index'))


# 5. XỬ LÝ UPLOAD ẢNH / VIDEO (Chỉ dành cho thành viên đã đăng nhập)
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'user_id' not in session:
        flash('Bạn cần phải đăng nhập để tải tệp lên!')
        return redirect(url_for('login'))
        
    if 'file' not in request.files:
        flash('Không tìm thấy tệp gửi lên!')
        return redirect(url_for('index'))
        
    file = request.files['file']
    if file.filename == '':
        flash('Bạn chưa chọn file nào cả!')
        return redirect(url_for('index'))
        
    if file and allowed_file(file.filename):
        # Làm sạch tên file để tránh lỗi hệ thống hoặc hack đường dẫn
        filename = secure_filename(file.filename)
        
        # Để tránh trùng tên file, thêm ID người dùng vào trước tên file
        filename = f"{session['user_id']}_{filename}"
        
        # Lưu file vật lý vào thư mục static/uploads/
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        # Phân loại xem file vừa up là ảnh hay video dựa vào đuôi file
        ext = filename.rsplit('.', 1)[1].lower()
        file_type = 'video' if ext in {'mp4', 'avi', 'mov'} else 'image'
        
        # Lưu thông tin file vào database
        new_media = Media(filename=filename, file_type=file_type, user_id=session['user_id'])
        db.session.add(new_media)
        db.session.commit()
        
        flash('Tải tệp lên bảng tin thành công!')
    else:
        flash('Định dạng file không được hỗ trợ (Chỉ nhận JPG, PNG, GIF, MP4, AVI, MOV)!')
        
    return redirect(url_for('index'))


# ==============================================================================
# KHỞI CHẠY DỰ ÁN
# ==============================================================================
if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Tự động tạo file database.db và các bảng nếu chưa có
    app.run(debug=True)