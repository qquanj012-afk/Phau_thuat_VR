import numpy as np
from pathlib import Path
from torch.utils.data import Dataset, DataLoader

# Import config
import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import PROCESSED_DIR

class LiverTumorDataset(Dataset):
    """Dataset cho ảnh đã tiền xử lý (định dạng .npy)."""
    def __init__(self, data_dir, transform=None):
        self.data_dir = Path(data_dir)
        self.files = list(self.data_dir.glob("*.npy"))
        self.transform = transform

    def __len__(self):
        return len(self.files)

    def __getitem__(self, idx):
        data = np.load(self.files[idx])  # (Slices, H, W, C)
        # Chọn ngẫu nhiên một slice (để tăng tính đa dạng khi training)
        slice_idx = np.random.randint(data.shape[0])
        image = data[slice_idx]  # (H, W, C)
        # Mask được giả định nằm trong thư mục processed cùng tên với hậu tố _mask
        # Có thể điều chỉnh tùy theo cách tổ chức dữ liệu
        mask_path = self.files[idx].with_name(self.files[idx].stem + "_mask.npy")
        if mask_path.exists():
            mask = np.load(mask_path)[slice_idx]
        else:
            mask = np.zeros(image.shape[:2], dtype=np.float32)
        if self.transform:
            image = self.transform(image)
        return image, mask

def get_dataloader(data_dir, batch_size=4, shuffle=True, num_workers=0):
    dataset = LiverTumorDataset(data_dir)
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, num_workers=num_workers)