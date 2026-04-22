import os
import random
import numpy as np
import torch
from pathlib import Path

def set_seed(seed=42):
    """Thiết lập seed cho tất cả các thư viện để tái lập kết quả."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

def save_checkpoint(model, optimizer, epoch, loss, filepath):
    """Lưu checkpoint model."""
    checkpoint = {
        'epoch': epoch,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
        'loss': loss
    }
    torch.save(checkpoint, filepath)

def load_checkpoint(filepath, model, optimizer=None):
    """Nạp checkpoint."""
    checkpoint = torch.load(filepath, map_location='cpu')
    model.load_state_dict(checkpoint['model_state_dict'])
    if optimizer:
        optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
    return checkpoint.get('epoch', 0), checkpoint.get('loss', 0.0)

def ensure_dir(path):
    """Tạo thư mục nếu chưa tồn tại."""
    Path(path).mkdir(parents=True, exist_ok=True)

def get_device():
    """Trả về device (cuda nếu có)."""
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")