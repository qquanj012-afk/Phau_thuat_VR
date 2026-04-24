import argparse
import nibabel as nib
import numpy as np
from pathlib import Path

def check_nifti(file_path: Path):
    print(f"\n🔍 Kiểm tra file: {file_path.name}")
    try:
        img = nib.load(file_path)
        data = img.get_fdata()
        print(f"  Shape: {data.shape}")
        print(f"  Dtype: {data.dtype}")
        print(f"  Min: {data.min():.2f}, Max: {data.max():.2f}")
        unique_vals = np.unique(data)
        print(f"  Unique values (first 10): {unique_vals[:10]}")
        is_binary = set(unique_vals).issubset({0, 1})
        print(f"  Is binary mask? {is_binary}")
        img_file = file_path.parent / file_path.name.replace('_mask', '')
        if img_file.exists():
            img2 = nib.load(img_file)
            data2 = img2.get_fdata()
            print(f"  CT image shape: {data2.shape}, mask shape: {data.shape} -> matches: {data2.shape == data.shape}")
        print("---")
    except Exception as e:
        print(f"  ❌ Lỗi: {e}")

def main():
    parser = argparse.ArgumentParser(description="Kiểm tra file NIfTI (ảnh CT hoặc mask)")
    parser.add_argument("--input", "-i", help="Đường dẫn đến file .nii hoặc .nii.gz")
    args = parser.parse_args()
    if args.input:
        check_nifti(Path(args.input))
    else:
        # Interactive mode: hỏi đường dẫn
        path = input("Nhập đường dẫn đến file .nii/.nii.gz: ").strip()
        if path:
            check_nifti(Path(path))
        else:
            print("Không có đường dẫn được cung cấp.")

if __name__ == "__main__":
    main()