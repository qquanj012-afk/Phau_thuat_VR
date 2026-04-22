import os
import sys
from pathlib import Path
from flask import Flask, send_from_directory

# Thêm thư mục gốc vào sys.path để import config
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Import config của web_flask
from web_flask.config import WEB_HOST, WEB_PORT, WEB_DEBUG, SECRET_KEY, MAX_CONTENT_LENGTH

# Import các blueprint
from web_flask.blueprints.dashboard.views import dashboard_bp
from web_flask.blueprints.train.views import train_bp
from web_flask.blueprints.archive.views import archive_bp

# Đường dẫn đến thư mục data (dùng để serve file tĩnh)
DATA_DIR = BASE_DIR / 'data'

def create_app():
    app = Flask(__name__)
    app.secret_key = SECRET_KEY
    app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

    # Đăng ký blueprint
    app.register_blueprint(dashboard_bp, url_prefix='/')
    app.register_blueprint(train_bp, url_prefix='/train')
    app.register_blueprint(archive_bp, url_prefix='/archive')

    # Route phục vụ file dữ liệu (ảnh, mesh...)
    @app.route('/data/<path:subpath>')
    def serve_data(subpath):
        return send_from_directory(DATA_DIR, subpath)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host=WEB_HOST, port=WEB_PORT, debug=WEB_DEBUG)