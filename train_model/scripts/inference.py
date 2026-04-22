import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import nibabel as nib
import numpy as np
import torch
import cv2

from config import CHECKPOINTS_DIR, INFERENCE_THRESHOLD, TARGET_SIZE
from utils.image_processing import load_and_preprocess_volume
from utils.helpers import get_device
from models.unet import UNet


def run_inference(input_path: str, output_path: str, model_type: str, threshold: float):
    """Chạy inference trên ảnh đầu vào."""
    device = get_device()

    # 1. Chọn checkpoint
    ckpt_name = "liver_model.pth" if model_type == "liver" else "tumor_model.pth"
    ckpt_path = CHECKPOINTS_DIR / ckpt_name
    if not ckpt_path.exists():
        print(f"❌ Không tìm thấy checkpoint: {ckpt_path}")
        sys.exit(1)

    # 2. Load model
    model = UNet(n_channels=3, n_classes=1).to(device)
    checkpoint = torch.load(ckpt_path, map_location=device, weights_only=False)
    state_dict = checkpoint['model_state_dict'] if 'model_state_dict' in checkpoint else checkpoint
    model.load_state_dict(state_dict)
    model.eval()

    # 3. Tiền xử lý ảnh
    print(f"🔄 Đang tiền xử lý ảnh: {input_path}")
    X = load_and_preprocess_volume(input_path, window_type=model_type)  # (Slices, H, W, C)

    # 4. Chạy inference
    all_masks = []
    with torch.no_grad():
        for slice_data in X:
            input_tensor = torch.from_numpy(slice_data).permute(2, 0, 1).unsqueeze(0).float().to(device)
            pred = torch.sigmoid(model(input_tensor))
            mask = (pred > threshold).cpu().numpy().squeeze()
            all_masks.append(mask)

    final_mask = np.stack(all_masks, axis=-1).astype(np.uint8)

    # 5. Lưu kết quả
    mask_img = nib.Nifti1Image(final_mask, affine=np.eye(4))
    nib.save(mask_img, output_path)

    # Lưu ảnh PNG preview lát giữa
    png_path = Path(output_path).with_suffix(".png")
    mid_slice = final_mask[:, :, final_mask.shape[2] // 2] * 255
    cv2.imwrite(str(png_path), mid_slice)

    print(f"✅ Đã lưu mask: {output_path}")
    print(f"✅ Đã lưu preview: {png_path}")


def main():
    parser = argparse.ArgumentParser(description="Inference ảnh CT đơn lẻ.")
    parser.add_argument("--input", required=True, help="Đường dẫn ảnh đầu vào")
    parser.add_argument("--output", required=True, help="Đường dẫn lưu mask (.nii.gz)")
    parser.add_argument("--model_type", choices=["liver", "tumor"], default="liver")
    parser.add_argument("--threshold", type=float, default=INFERENCE_THRESHOLD)
    args = parser.parse_args()

    run_inference(args.input, args.output, args.model_type, args.threshold)


if __name__ == "__main__":
    main()