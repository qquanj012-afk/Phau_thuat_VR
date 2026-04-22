import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import torch
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm
import numpy as np

from config import (
    PROCESSED_DIR, CHECKPOINTS_DIR, LOGS_DIR,
    BATCH_SIZE, LEARNING_RATE, NUM_EPOCHS, VAL_SPLIT
)
from utils.dice_loss import BCEDiceLoss
from utils.helpers import get_device, set_seed, save_checkpoint
from models.unet import UNet


class TumorDataset(Dataset):
    """Dataset cho dữ liệu khối u (đã tiền xử lý)."""
    def __init__(self, images_npy, masks_npy):
        self.images = np.load(images_npy)  # (N, H, W)
        self.masks = np.load(masks_npy)    # (N, H, W)

    def __len__(self):
        return len(self.images)

    def __getitem__(self, idx):
        image = self.images[idx]  # (H, W)
        mask = self.masks[idx]    # (H, W)
        # Thêm chiều kênh và tọa độ (giống bản cũ)
        h, w = image.shape
        coord_x, coord_y = np.meshgrid(np.linspace(0, 1, w), np.linspace(0, 1, h))
        image = np.stack([image, coord_x, coord_y], axis=-1)  # (H, W, 3)
        return image.astype(np.float32), mask.astype(np.float32)


def train_epoch(model, dataloader, optimizer, criterion, device):
    model.train()
    total_loss = 0.0
    for images, masks in tqdm(dataloader, desc="Training"):
        images = images.permute(0, 3, 1, 2).float().to(device)  # (B, 3, H, W)
        masks = masks.unsqueeze(1).float().to(device)           # (B, 1, H, W)

        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, masks)
        loss.backward()
        optimizer.step()

        total_loss += loss.item()
    return total_loss / len(dataloader)


def validate_epoch(model, dataloader, criterion, device):
    model.eval()
    total_loss = 0.0
    with torch.no_grad():
        for images, masks in tqdm(dataloader, desc="Validation"):
            images = images.permute(0, 3, 1, 2).float().to(device)
            masks = masks.unsqueeze(1).float().to(device)

            outputs = model(images)
            loss = criterion(outputs, masks)
            total_loss += loss.item()
    return total_loss / len(dataloader)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=NUM_EPOCHS)
    parser.add_argument("--batch_size", type=int, default=BATCH_SIZE)
    parser.add_argument("--lr", type=float, default=LEARNING_RATE)
    args = parser.parse_args()

    set_seed(42)
    device = get_device()
    print(f"🖥️  Device: {device}")

    # 1. Dataset & Dataloader
    data_dir = PROCESSED_DIR / "tumor"
    images_path = data_dir / "tumor_images.npy"
    masks_path = data_dir / "tumor_masks.npy"
    if not images_path.exists() or not masks_path.exists():
        print(f"❌ Chưa có dữ liệu đã tiền xử lý tại {data_dir}")
        sys.exit(1)

    dataset = TumorDataset(images_path, masks_path)
    val_size = int(len(dataset) * VAL_SPLIT)
    train_size = len(dataset) - val_size
    train_set, val_set = torch.utils.data.random_split(dataset, [train_size, val_size])

    train_loader = DataLoader(train_set, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_set, batch_size=args.batch_size, shuffle=False)

    # 2. Model, Loss, Optimizer
    model = UNet(n_channels=3, n_classes=1).to(device)
    criterion = BCEDiceLoss()
    optimizer = optim.Adam(model.parameters(), lr=args.lr)

    writer = SummaryWriter(LOGS_DIR / "tumor")
    best_val_loss = float("inf")

    # 3. Training loop
    for epoch in range(1, args.epochs + 1):
        print(f"\n--- Epoch {epoch}/{args.epochs} ---")
        train_loss = train_epoch(model, train_loader, optimizer, criterion, device)
        val_loss = validate_epoch(model, val_loader, criterion, device)

        writer.add_scalars("Loss", {"train": train_loss, "val": val_loss}, epoch)
        print(f"Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            ckpt_path = CHECKPOINTS_DIR / "tumor_model.pth"
            save_checkpoint(model, optimizer, epoch, val_loss, ckpt_path)
            print(f"💾 Đã lưu model tốt nhất: {ckpt_path}")

    writer.close()
    print("✅ Huấn luyện hoàn tất.")


if __name__ == "__main__":
    main()