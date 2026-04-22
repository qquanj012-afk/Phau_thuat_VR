import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import nibabel as nib
import numpy as np
from skimage import measure

from config import MESHES_DIR


def generate_mesh(input_path: str, output_path: str, spacing: tuple = (1.0, 1.0, 1.0)):
    """Tạo mesh từ mask NIfTI."""
    print(f"🔄 Đang tạo mesh từ {input_path}")

    # 1. Đọc mask
    img = nib.load(input_path)
    mask = img.get_fdata().astype(np.uint8)

    if mask.ndim == 2:
        mask = mask[:, :, np.newaxis]

    # 2. Dùng marching cubes để trích xuất bề mặt
    verts, faces, _, _ = measure.marching_cubes(mask, level=0.5, spacing=spacing)

    # 3. Lưu file .obj
    with open(output_path, 'w') as f:
        for v in verts:
            f.write(f"v {v[0]} {v[1]} {v[2]}\n")
        for face in faces:
            f.write(f"f {face[0] + 1} {face[1] + 1} {face[2] + 1}\n")

    print(f"✅ Đã lưu mesh: {output_path} (Đỉnh: {len(verts)}, Mặt: {len(faces)})")


def main():
    parser = argparse.ArgumentParser(description="Tạo mesh 3D từ mask.")
    parser.add_argument("--input", required=True, help="Đường dẫn file mask (.nii/.nii.gz)")
    parser.add_argument("--output", help="Đường dẫn lưu mesh (.obj)")
    args = parser.parse_args()

    output_path = args.output or MESHES_DIR / f"{Path(args.input).stem}.obj"
    generate_mesh(args.input, output_path)


if __name__ == "__main__":
    main()