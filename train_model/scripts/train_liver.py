import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import torch
import torch.optim as optim
from torch.utils.data import DataLoader
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm
import numpy as np

from config import (
    PROCESSED_DIR, CHECKPOINTS_DIR, LOGS_DIR,
    BATCH_SIZE, LEARNING_RATE, NUM_EPOCHS, VAL_SPLIT
)
from utils.data_loader import LiverTumorDataset
from utils.dice_loss import BCEDiceLoss
from utils.helpers import get_device, set_seed, save_checkpoint
from models.unet import UNet


def train_epoch(model, dataloader, optimizer, criterion, device):
    model.train()
    total_loss = 0.0
    for images, masks in tqdm(dataloader, desc="Training"):
        images = images.permute(0, 3, 1, 2).float().to(device)
        masks = masks.unsqueeze(1).float().to(device)

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
    data_dir = PROCESSED_DIR / "liver"
    if not data_dir.exists():
        print(f"❌ Chưa có dữ liệu đã tiền xử lý tại {data_dir}")
        sys.exit(1)

    dataset = LiverTumorDataset(data_dir)
    val_size = int(len(dataset) * VAL_SPLIT)
    train_size = len(dataset) - val_size
    train_set, val_set = torch.utils.data.random_split(dataset, [train_size, val_size])

    train_loader = DataLoader(train_set, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_set, batch_size=args.batch_size, shuffle=False)

    # 2. Model, Loss, Optimizer
    model = UNet(n_channels=3, n_classes=1).to(device)
    criterion = BCEDiceLoss()
    optimizer = optim.Adam(model.parameters(), lr=args.lr)

    writer = SummaryWriter(LOGS_DIR / "liver")
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
            ckpt_path = CHECKPOINTS_DIR / "liver_model.pth"
            save_checkpoint(model, optimizer, epoch, val_loss, ckpt_path)
            print(f"💾 Đã lưu model tốt nhất: {ckpt_path}")

    writer.close()
    print("✅ Huấn luyện hoàn tất.")


if __name__ == "__main__":
    main()