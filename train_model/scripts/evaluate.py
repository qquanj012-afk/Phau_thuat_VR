import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import torch
import numpy as np
from tqdm import tqdm

from config import PROCESSED_DIR, CHECKPOINTS_DIR
from utils.data_loader import LiverTumorDataset
from utils.helpers import get_device
from models.unet import UNet


def dice_score(pred, target, smooth=1e-5):
    intersection = (pred * target).sum()
    return (2. * intersection + smooth) / (pred.sum() + target.sum() + smooth)


def evaluate_model(model_type: str):
    device = get_device()

    # 1. Load model
    ckpt_name = "liver_model.pth" if model_type == "liver" else "tumor_model.pth"
    ckpt_path = CHECKPOINTS_DIR / ckpt_name
    if not ckpt_path.exists():
        print(f"❌ Không tìm thấy checkpoint: {ckpt_path}")
        sys.exit(1)

    model = UNet(n_channels=3, n_classes=1).to(device)
    checkpoint = torch.load(ckpt_path, map_location=device, weights_only=False)
    state_dict = checkpoint['model_state_dict'] if 'model_state_dict' in checkpoint else checkpoint
    model.load_state_dict(state_dict)
    model.eval()

    # 2. Load test data
    data_dir = PROCESSED_DIR / model_type
    if not data_dir.exists():
        print(f"❌ Không tìm thấy dữ liệu test tại {data_dir}")
        sys.exit(1)

    dataset = LiverTumorDataset(data_dir)
    print(f"📊 Đánh giá trên {len(dataset)} mẫu...")

    dice_scores = []
    for idx in tqdm(range(len(dataset)), desc="Evaluating"):
        image, mask = dataset[idx]
        input_tensor = torch.from_numpy(image).permute(2, 0, 1).unsqueeze(0).float().to(device)

        with torch.no_grad():
            pred = torch.sigmoid(model(input_tensor))
            pred_bin = (pred > 0.5).cpu().numpy().squeeze()

        score = dice_score(pred_bin, mask)
        dice_scores.append(score)

    mean_dice = np.mean(dice_scores)
    std_dice = np.std(dice_scores)
    print(f"✅ Dice trung bình: {mean_dice:.4f} ± {std_dice:.4f}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_type", choices=["liver", "tumor"], default="liver")
    args = parser.parse_args()
    evaluate_model(args.model_type)


if __name__ == "__main__":
    main()