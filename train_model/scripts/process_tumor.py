# train_model/scripts/process_tumor.py
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import nibabel as nib
import numpy as np
import cv2
from tqdm import tqdm
from skimage.transform import resize
from scipy.ndimage import gaussian_filter

from config import RAW_DATA_DIR, PROCESSED_DIR, TARGET_SIZE


def find_files_in_subdirs(raw_dir: Path):
    """Tìm file ảnh và mask trong imagesTr/labelsTr (giống liver)."""
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


def preprocess_tumor_dataset(raw_dir: Path, processed_dir: Path, target_size: tuple):
    """Trích xuất lát có khối u, lưu từng cặp file và spacing."""
    processed_dir.mkdir(parents=True, exist_ok=True)
    pairs = find_files_in_subdirs(raw_dir)
    if not pairs:
        print(f"⚠️ Không tìm thấy file ảnh nào trong {raw_dir}")
        return

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    do_resize = target_size[0] > 0 and target_size[1] > 0

    for pair in tqdm(pairs, desc="Đang trích xuất khối u"):
        img_path = pair['image']
        mask_path = pair['mask']
        if mask_path is None:
            print(f"⚠️ Bỏ qua {img_path.name} vì không có mask")
            continue

        try:
            img_data = nib.load(img_path).get_fdata()
            if img_data.ndim == 4:
                img_data = img_data[..., 0]
            elif img_data.ndim == 2:
                img_data = img_data[:, :, np.newaxis]

            msk = nib.load(mask_path)
            msk_data = msk.get_fdata()
            if msk_data.ndim == 4:
                msk_data = msk_data[..., 0]
            elif msk_data.ndim == 2:
                msk_data = msk_data[:, :, np.newaxis]

            tumor_img_slices = []
            tumor_mask_slices = []

            for i in range(img_data.shape[2]):
                slice_img = img_data[:, :, i]
                slice_msk = msk_data[:, :, i]

                # Chỉ lấy lát có khối u (label == 2)
                if not np.any(slice_msk == 2):
                    continue

                # Preprocessing ảnh
                img_win = np.clip(slice_img, -20, 100)
                if do_resize:
                    img_res = cv2.resize(img_win, target_size, interpolation=cv2.INTER_LINEAR)
                else:
                    img_res = img_win
                img_norm = (img_res - img_res.min()) / (img_res.max() - img_res.min() + 1e-8)
                img_255 = (img_norm * 255).astype(np.uint8)
                img_enhanced = clahe.apply(img_255)
                img_final = img_enhanced / 255.0

                # Mask khối u (label 2)
                t_mask = (slice_msk == 2).astype(np.uint8)
                if do_resize:
                    t_mask_res = resize(t_mask, target_size, preserve_range=True,
                                        order=1, anti_aliasing=True).astype(np.uint8)
                else:
                    t_mask_res = t_mask

                tumor_img_slices.append(img_final)
                tumor_mask_slices.append(t_mask_res)

            if tumor_img_slices:
                img_volume = np.array(tumor_img_slices, dtype=np.float32)  # (D, H, W)
                mask_volume = np.array(tumor_mask_slices, dtype=np.uint8)  # (D, H, W)

                # Làm mịn 3D mask
                mask_smooth = gaussian_filter(mask_volume.astype(np.float32), sigma=0.8)
                mask_volume = (mask_smooth > 0.5).astype(np.uint8)

                # Lấy spacing từ mask gốc
                spacing = np.array(msk.header.get_zooms()[:3], dtype=np.float32)

                # Thêm kênh tọa độ cho ảnh
                h, w = mask_volume.shape[1], mask_volume.shape[2]
                coord_x, coord_y = np.meshgrid(np.linspace(0, 1, w),
                                               np.linspace(0, 1, h))
                coord_x = coord_x.astype(np.float32)
                coord_y = coord_y.astype(np.float32)
                img_with_coords = np.stack([img_volume,
                                            np.tile(coord_x, (len(tumor_img_slices), 1, 1)),
                                            np.tile(coord_y, (len(tumor_img_slices), 1, 1))],
                                           axis=-1)

                output_name = img_path.stem.replace('.nii', '')
                np.save(processed_dir / f"{output_name}_img.npy", img_with_coords)
                np.save(processed_dir / f"{output_name}_mask.npy", mask_volume)
                np.save(processed_dir / f"{output_name}_spacing.npy", spacing)
            else:
                print(f"⚠️ Không có lát u nào trong {img_path.name}")

        except Exception as e:
            print(f"Lỗi khi xử lý {img_path.name}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Tiền xử lý dữ liệu khối u.")
    parser.add_argument("--raw_subdir", type=str, default="liver",
                        help="Thư mục con trong data/raw chứa dữ liệu (mặc định: liver)")
    parser.add_argument("--output_name", type=str, default="tumor",
                        help="Tên thư mục đầu ra trong data/processed (mặc định: tumor)")
    args = parser.parse_args()

    raw_dir = RAW_DATA_DIR / args.raw_subdir
    processed_dir = PROCESSED_DIR / args.output_name

    if not raw_dir.exists():
        print(f"❌ Thư mục raw không tồn tại: {raw_dir}")
        sys.exit(1)

    print(f"🔄 Tiền xử lý dữ liệu khối u từ {raw_dir}...")
    preprocess_tumor_dataset(raw_dir, processed_dir, TARGET_SIZE)


if __name__ == "__main__":
    main()