 import os
import secrets
from flask import Flask, render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

# Định nghĩa đường dẫn đồng bộ với cấu trúc thư mục Share_media trên GitHub
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

class Media(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)
    uploader = db.Column(db.String(50), default='admin')

@app.route('/')
def index():
    all_media = Media.query.all()
    return render_template('index.html', media_list=all_media)

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return redirect('/')
    file = request.files['file']
    if file.filename == '':
        return redirect('/')
    if file:
        ext = file.filename.split('.')[-1].lower()
        file_type = 'image' if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp'] else 'video'
        random_hex = secrets.token_hex(8)
        secure_name = f"{random_hex}_{secure_filename(file.filename)}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], secure_name))
        
        new_media = Media(filename=secure_name, file_type=file_type)
        db.session.add(new_media)
        db.session.commit()
    return redirect('/')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
