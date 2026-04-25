import yaml
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "config.yaml"

def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

config = load_config()

# Đường dẫn dữ liệu
DATA_ROOT = BASE_DIR / config['paths']['data_root']
RAW_DATA_DIR = BASE_DIR / config['paths']['raw_data']
PROCESSED_DIR = BASE_DIR / config['paths']['processed_data']
MESHES_DIR = BASE_DIR / config['paths']['meshes']
CHECKPOINTS_DIR = BASE_DIR / config['paths']['checkpoints']
TEMP_DIR = BASE_DIR / config['paths']['temp']
LOGS_DIR = BASE_DIR / config['paths']['logs']
THUMBNAILS_DIR = BASE_DIR / config['paths']['thumbnails']

# Tiền xử lý
TARGET_SIZE = tuple(config['preprocessing']['target_size'])
LIVER_WINDOW = (config['preprocessing']['liver_window']['center'],
                config['preprocessing']['liver_window']['width'])
TUMOR_WINDOW = (config['preprocessing']['tumor_window']['center'],
                config['preprocessing']['tumor_window']['width'])
ADD_COORDINATE_CHANNELS = config['preprocessing']['add_coordinate_channels']

# Huấn luyện
BATCH_SIZE = config['training']['batch_size']
LEARNING_RATE = config['training']['learning_rate']
NUM_EPOCHS = config['training']['epochs']
VAL_SPLIT = config['training']['val_split']
EARLY_STOPPING_PATIENCE = config['training'].get('early_stopping_patience', 10)

# Inference
INFERENCE_THRESHOLD = config['inference']['threshold']