import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import nibabel as nib
import numpy as np
import cv2
from tqdm import tqdm

from config import RAW_DATA_DIR, PROCESSED_DIR, TARGET_SIZE


def find_nifti_files(directory: Path):
    """Tìm đệ quy tất cả file .nii/.nii.gz trong thư mục."""
    return list(directory.glob("**/*.nii")) + list(directory.glob("**/*.nii.gz"))


def find_label_for_image(image_path: Path, labels_dir: Path):
    """Tìm file nhãn tương ứng với ảnh (cùng tên)."""
    name = image_path.name.replace('.nii.gz', '').replace('.nii', '')
    for ext in ['.nii', '.nii.gz']:
        label_path = labels_dir / f"{name}{ext}"
        if label_path.exists():
            return label_path
    return None


def preprocess_tumor_dataset(raw_dir: Path, processed_dir: Path, target_size: tuple):
    """Trích xuất các lát cắt có khối u và lưu thành file .npy."""
    processed_dir.mkdir(parents=True, exist_ok=True)

    images_dir = raw_dir / "imagesTr"
    labels_dir = raw_dir / "labelsTr"
    if not images_dir.exists():
        images_dir = raw_dir
        labels_dir = raw_dir

    image_files = find_nifti_files(images_dir)
    if not image_files:
        print(f"⚠️ Không tìm thấy file .nii/.nii.gz nào trong {images_dir}")
        return

    tumor_images = []
    tumor_masks = []
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

    for img_path in tqdm(image_files, desc="Đang trích xuất khối u"):
        try:
            img_data = nib.load(img_path).get_fdata()
            if img_data.ndim == 4:
                img_data = img_data[..., 0]
            elif img_data.ndim == 2:
                img_data = img_data[:, :, np.newaxis]

            label_path = find_label_for_image(img_path, labels_dir)
            if label_path is None:
                print(f"⚠️ Không tìm thấy nhãn cho {img_path.name}, bỏ qua.")
                continue

            msk_data = nib.load(label_path).get_fdata()
            if msk_data.ndim == 4:
                msk_data = msk_data[..., 0]
            elif msk_data.ndim == 2:
                msk_data = msk_data[:, :, np.newaxis]

            for i in range(img_data.shape[2]):
                slice_img = img_data[:, :, i]
                slice_msk = msk_data[:, :, i]

                # Chỉ giữ lát cắt có khối u (label == 2)
                if not np.any(slice_msk == 2):
                    continue

                # Áp dụng window cho gan (giống bản cũ)
                img_win = np.clip(slice_img, -20, 100)
                img_res = cv2.resize(img_win, target_size, interpolation=cv2.INTER_LINEAR)

                # Chuẩn hóa về [0,1]
                img_norm = (img_res - img_res.min()) / (img_res.max() - img_res.min() + 1e-8)
                img_255 = (img_norm * 255).astype(np.uint8)
                img_enhanced = clahe.apply(img_255)
                img_final = img_enhanced / 255.0

                # Mask khối u
                t_mask = (slice_msk == 2).astype(np.uint8)
                t_mask_res = cv2.resize(t_mask, target_size, interpolation=cv2.INTER_NEAREST)

                tumor_images.append(img_final)
                tumor_masks.append(t_mask_res)

        except Exception as e:
            print(f"Lỗi khi xử lý {img_path.name}: {e}")

    if tumor_images:
        np.save(processed_dir / "tumor_images.npy", np.array(tumor_images).astype(np.float32))
        np.save(processed_dir / "tumor_masks.npy", np.array(tumor_masks).astype(np.uint8))
        print(f"✅ Đã lưu {len(tumor_images)} lát cắt khối u vào {processed_dir}")
    else:
        print("⚠️ Không có lát cắt nào chứa khối u được tìm thấy.")


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