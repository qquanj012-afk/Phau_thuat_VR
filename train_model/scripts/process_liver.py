# train_model/scripts/process_liver.py
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import nibabel as nib
import numpy as np
from tqdm import tqdm
from skimage.transform import resize
from scipy.ndimage import gaussian_filter

from config import RAW_DATA_DIR, PROCESSED_DIR, TARGET_SIZE
from utils.image_processing import apply_liver_window, preprocess_slice


def find_files_in_subdirs(raw_dir: Path):
    """
    Tìm tất cả file .nii* trong raw_dir, tự động nhận diện cấu trúc:
    - Nếu có thư mục con imagesTr và labelsTr, lấy ảnh từ imagesTr, mask từ labelsTr
    - Trả về danh sách dict: {'image': path, 'mask': path or None}
    """
    img_dir = raw_dir / "imagesTr"
    mask_dir = raw_dir / "labelsTr"
    if img_dir.exists() and mask_dir.exists():
        image_files = list(img_dir.glob("*.nii*"))
        pairs = []
        for img_path in image_files:
            mask_path = mask_dir / img_path.name
            if not mask_path.exists():
                mask_path = mask_dir / (img_path.stem + ".nii.gz")
            pairs.append({'image': img_path, 'mask': mask_path if mask_path.exists() else None})
        return pairs
    else:
        image_files = list(raw_dir.glob("*.nii*"))
        return [{'image': f, 'mask': None} for f in image_files]


def preprocess_dataset(raw_dir: Path, processed_dir: Path, target_size: tuple):
    """Tiền xử lý gan, lưu từng cặp _img.npy, _mask.npy và _spacing.npy."""
    processed_dir.mkdir(parents=True, exist_ok=True)
    pairs = find_files_in_subdirs(raw_dir)
    if not pairs:
        print(f"⚠️ Không tìm thấy file ảnh nào trong {raw_dir}")
        return

    do_resize = target_size[0] > 0 and target_size[1] > 0

    for pair in tqdm(pairs, desc="Đang tiền xử lý gan"):
        img_path = pair['image']
        mask_path = pair['mask']
        try:
            # Đọc ảnh CT
            img = nib.load(img_path)
            data = img.get_fdata()
            if data.ndim == 4:
                data = data[..., 0]
            elif data.ndim == 2:
                data = data[:, :, np.newaxis]

            processed_slices = []
            for i in range(data.shape[2]):
                slice_img = data[:, :, i]
                processed = preprocess_slice(slice_img, apply_liver_window, target_size)
                processed_slices.append(processed)
            img_processed = np.array(processed_slices, dtype=np.float32)  # (D, H, W, C)

            # Xử lý mask nếu có
            if mask_path and mask_path.exists():
                msk = nib.load(mask_path)
                msk_data = msk.get_fdata()
                if msk_data.ndim == 4:
                    msk_data = msk_data[..., 0]
                elif msk_data.ndim == 2:
                    msk_data = msk_data[:, :, np.newaxis]

                # Gan: label = 1
                binary_mask = (msk_data == 1).astype(np.uint8)
                mask_slices = []
                for i in range(binary_mask.shape[2]):
                    slice_msk = binary_mask[:, :, i]
                    if do_resize:
                        msk_resized = resize(slice_msk, target_size,
                                             preserve_range=True, order=1,
                                             anti_aliasing=True).astype(np.uint8)
                    else:
                        msk_resized = slice_msk
                    mask_slices.append(msk_resized)

                mask_processed = np.array(mask_slices, dtype=np.uint8)  # (D, H, W)

                # Làm mịn 3D để loại bỏ bậc thang giữa các lát
                mask_smooth = gaussian_filter(mask_processed.astype(np.float32), sigma=0.8)
                mask_processed = (mask_smooth > 0.5).astype(np.uint8)

                # Lấy spacing từ mask gốc
                spacing = np.array(msk.header.get_zooms()[:3], dtype=np.float32)

            else:
                mask_processed = None
                spacing = None

            # Lưu file
            output_name = img_path.stem.replace('.nii', '')
            np.save(processed_dir / f"{output_name}_img.npy", img_processed)
            if mask_processed is not None:
                np.save(processed_dir / f"{output_name}_mask.npy", mask_processed)
                np.save(processed_dir / f"{output_name}_spacing.npy", spacing)

        except Exception as e:
            print(f"Lỗi khi xử lý {img_path.name}: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=["liver", "tumor"], default="liver")
    args = parser.parse_args()

    raw_dir = RAW_DATA_DIR / args.dataset
    processed_dir = PROCESSED_DIR / args.dataset

    if not raw_dir.exists():
        print(f"❌ Thư mục raw không tồn tại: {raw_dir}")
        sys.exit(1)

    print(f"🔄 Tiền xử lý dữ liệu {args.dataset}...")
    preprocess_dataset(raw_dir, processed_dir, TARGET_SIZE)
    print(f"✅ Hoàn thành! Dữ liệu đã lưu tại {processed_dir}")


if __name__ == "__main__":
    main()