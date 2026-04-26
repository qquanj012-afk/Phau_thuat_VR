import sys
import argparse
from pathlib import Path
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

import nibabel as nib
import numpy as np
from scipy.ndimage import zoom, gaussian_filter
from skimage import measure

try:
    from config import MESHES_DIR, PROCESSED_DIR
except ImportError:
    MESHES_DIR = Path("meshes")
    PROCESSED_DIR = Path("processed")

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False


def load_mask(mask_path: str):
    """Đọc mask từ .npy hoặc .nii/.nii.gz, trả về (mask_array, spacing_tuple)."""
    p = Path(mask_path)
    if p.suffix == '.npy':
        mask = np.load(p)
        # Tìm file spacing đi kèm
        spacing_path = p.parent / (p.stem.replace('_mask', '') + '_spacing.npy')
        if spacing_path.exists():
            spacing = tuple(np.load(spacing_path))
        else:
            spacing = (1.0, 1.0, 2.5)  # fallback
        return mask, spacing
    else:
        img = nib.load(mask_path)
        return img.get_fdata(), img.header.get_zooms()[:3]


def generate_mesh(input_path: str, output_path: str, spacing=None,
                  threshold=0.5, upsample=4, sigma=0.5):
    """Tạo mesh 3D từ mask, lưu vào output_path chỉ định."""
    print(f"\n🔄 {Path(input_path).name} | Upsample={upsample} | Sigma={sigma}")
    start_time = time.time()

    mask, auto_spacing = load_mask(input_path)
    mask = mask.astype(np.float32)
    if spacing is None:
        spacing = np.array(auto_spacing)
    print(f"   Spacing: {spacing}")

    if mask.sum() < 10:
        print("⚠️ Mask quá nhỏ, bỏ qua.")
        return False

    if upsample > 1:
        print(f"   ↳ Upsampling x{upsample}...")
        mask    = zoom(mask, upsample, order=3)
        spacing = spacing / upsample

    if sigma > 0:
        print(f"   ↳ Gaussian smoothing (σ={sigma})...")
        mask = gaussian_filter(mask, sigma=sigma)

    print("   ↳ Marching cubes...")
    try:
        verts, faces, _, _ = measure.marching_cubes(mask, level=threshold, spacing=spacing)
    except Exception as e:
        print(f"❌ Marching cubes thất bại: {e}")
        return False

    # Lưu vào output_path do caller chỉ định
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w') as f:
        for v in verts:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        for face in faces:
            f.write(f"f {face[0] + 1} {face[1] + 1} {face[2] + 1}\n")

    elapsed = time.time() - start_time
    print(f"✅ {out.name} | Đỉnh: {len(verts):,} | Mặt: {len(faces):,} | ⏱ {elapsed:.1f}s")
    return True


def infer_output_path(input_path):
    """Tự suy ra output path khi không truyền --output (chế độ batch)."""
    p    = Path(input_path)
    full = str(p).lower()
    sub  = 'tumor' if 'tumor' in full else 'liver'
    return MESHES_DIR / sub / f"{p.stem.replace('_mask', '')}.obj"


def process_directory(input_dir: Path, upsample, sigma):
    if not input_dir.exists():
        print(f"❌ Thư mục không tồn tại: {input_dir}")
        return
    mask_files = sorted(input_dir.glob('*_mask.npy'))
    if not mask_files:
        print(f"ℹ️ Không thấy file *_mask.npy trong {input_dir}")
        return

    print(f"\n📂 Xử lý {len(mask_files)} file trong {input_dir}")
    total_start = time.time()
    iterator = (tqdm(mask_files, desc="Đang tạo mesh", unit="file")
                if TQDM_AVAILABLE else enumerate(mask_files, 1))

    for item in iterator:
        mask_path = item if TQDM_AVAILABLE else item[1]
        output_path = infer_output_path(mask_path)
        generate_mesh(str(mask_path), str(output_path), upsample=upsample, sigma=sigma)

    elapsed = time.time() - total_start
    print(f"\n🏁 {len(mask_files)} file | ⏱ {elapsed:.1f}s "
          f"({elapsed/len(mask_files):.1f}s/file)")


def main():
    parser = argparse.ArgumentParser(description="Tạo mesh 3D chất lượng cao.")
    parser.add_argument("--input",    help="File mask đơn lẻ (.npy / .nii / .nii.gz)")
    parser.add_argument("--output",   help="Đường dẫn lưu file .obj (chỉ dùng khi --input)")
    parser.add_argument("--upsample", type=int,   default=4,   help="Hệ số upsample (khuyến nghị 2)")
    parser.add_argument("--sigma",    type=float, default=0.5, help="Độ mịn Gaussian (0.5–1.5)")
    args = parser.parse_args()

    if args.input:
        # Chế độ đơn lẻ (dùng cho web / pipeline)
        output_path = args.output if args.output else str(infer_output_path(args.input))
        generate_mesh(args.input, output_path, upsample=args.upsample, sigma=args.sigma)
    else:
        # Chế độ batch (chạy tay toàn bộ data/processed)
        print("🔍 Đang quét dữ liệu hàng loạt...")
        process_directory(PROCESSED_DIR / 'liver', args.upsample, args.sigma)
        process_directory(PROCESSED_DIR / 'tumor', args.upsample, args.sigma)
        print("\n✅ Hoàn tất!")


if __name__ == "__main__":
    main()