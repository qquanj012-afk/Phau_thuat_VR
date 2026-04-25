import yaml
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "config.yaml"

def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

config = load_config()

# Đường dẫn dữ liệu (dùng cho web)
DATA_ROOT = BASE_DIR / config['paths']['data_root']
RAW_DATA_DIR = BASE_DIR / config['paths']['raw_data']
PROCESSED_DIR = BASE_DIR / config['paths']['processed_data']
MESHES_DIR = BASE_DIR / config['paths']['meshes']
CHECKPOINTS_DIR = BASE_DIR / config['paths']['checkpoints']
TEMP_DIR = BASE_DIR / config['paths']['temp']
THUMBNAILS_DIR = BASE_DIR / config['paths']['thumbnails']

# Cấu hình web
WEB_HOST = config['web']['host']
WEB_PORT = config['web']['port']
WEB_DEBUG = config['web']['debug']
SECRET_KEY = config['web']['secret_key']
MAX_CONTENT_LENGTH = config['web']['max_content_length']

# Inference
INFERENCE_THRESHOLD = config['inference']['threshold']