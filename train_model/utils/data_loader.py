# train_model/utils/data_loader.py
import numpy as np
from pathlib import Path
from torch.utils.data import Dataset, DataLoader

# Import config
import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import PROCESSED_DIR

class LiverTumorDataset(Dataset):
    """
    Dataset cho ảnh đã tiền xử lý (định dạng .npy).
    Mỗi volume có hai file: {name}_img.npy (D, H, W, C) và {name}_mask.npy (D, H, W)
    Dataset trả về từng slice 2D.
    """
    def __init__(self, data_dir, transform=None):
        self.data_dir = Path(data_dir)
        # Lấy tất cả file ảnh (có đuôi _img.npy)
        self.img_files = sorted(self.data_dir.glob("*_img.npy"))
        # Tạo danh sách các slice index (volume_idx, slice_idx)
        self.slices = []
        self.mask_files = []
        for img_path in self.img_files:
            # Đọc shape để biết số slice
            # Dùng mmap để không load toàn bộ vào RAM
            img_shape = np.load(img_path, mmap_mode='r').shape
            num_slices = img_shape[0]
            # Tìm file mask tương ứng
            mask_path = img_path.with_name(img_path.stem.replace('_img', '_mask') + '.npy')
            if not mask_path.exists():
                print(f"⚠️ Không tìm thấy mask cho {img_path.name}, bỏ qua volume này.")
                continue
            self.mask_files.append(mask_path)
            for slice_idx in range(num_slices):
                self.slices.append((len(self.mask_files)-1, slice_idx))
        self.transform = transform
        print(f"📊 Dataset: {len(self.img_files)} volumes, {len(self.slices)} slices")

    def __len__(self):
        return len(self.slices)

    def __getitem__(self, idx):
        vol_idx, slice_idx = self.slices[idx]
        img_path = self.img_files[vol_idx]
        mask_path = self.mask_files[vol_idx]
        # Load ảnh (slice tương ứng)
        img_volume = np.load(img_path)  # (D, H, W, C)
        image = img_volume[slice_idx]  # (H, W, C)
        # Load mask (slice tương ứng)
        mask_volume = np.load(mask_path)  # (D, H, W)
        mask = mask_volume[slice_idx]    # (H, W)
        if self.transform:
            image = self.transform(image)
        return image.astype(np.float32), mask.astype(np.float32)

def get_dataloader(data_dir, batch_size=4, shuffle=True, num_workers=0):
    dataset = LiverTumorDataset(data_dir)
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, num_workers=num_workers)