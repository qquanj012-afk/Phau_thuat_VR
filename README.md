## 1. Cấu trúc thư mục

```
Phau_thuat_VR/
├── .venv/                          # Môi trường
│
├── data/                           # Lưu trữ dữ liệu raw, huấn luyện, thùng rác, file tạm
│   ├── .trash/                     # Thùng rác hiển thị trong archive
│   │   ├── meshes/
│   │   │   ├── liver/
│   │   │   └── tumor/
│   │   ├── processed/
│   │   │   ├── liver/
│   │   │   └── tumor/
│   │   └── raw/
│   │       └── liver/
│   │           ├── imagesTr/
│   │           └── labelsTr/
│   ├── meshes/                     # File .obj sau khi chạy 'mesh_generator,py' để xuất vào unity
│   │   ├── liver/
│   │   └── tumor/
│   ├── processed/                  # File .npy sau khi chạy 'process_liver/tumor'
│   │   ├── liver/
│   │   └── tumor/
│   ├── raw/                        # File dữ liệu thô
│   │   └── liver/                  # Dữ liệu gan
│   │       ├── imagesTr/           # File ảnh CT .nii (liver_'số'.nii)
│   │       │                         Ví dụ: Shape: (180, 180, 125) (có thể có shape vs thông số khác), 125 lát cắt, mỗi lát 180x180.
│   │       │                                Giá trị: từ -1024 đến 1343 (Hounsfield))
│   │       └── labelsTr/           # File Mask .nii (liver_'số'.nii)
│   │                                 Ví dụ: Shape: (180, 180, 125) (luôn cùng kích thước với ảnh CT).
│   │                                        Giá trị: 0, 1, 2 (mask đa nhãn - multi‑class).
│   └── temp/                       # Lưu file tạm khi chạy chương trình trong webflask 'train'
│       ├── input/                  # Ảnh đâu vào (sau khi chọn lưu thì sẽ lưu vào data/raw/liver/imagesTr và labelsTr, lọc theo loại file là CT hay mask)
│       └── output/                 # Ảnh xuất ra (sau khi chọn lưu thì sẽ lưu vào data/processed và data/mesh, cũng lọc theo loại file)
│
├── train_model/                    # Chương trình huấn luyện
│   ├── checkpoints/                # Lưu kết quả model
│   ├── logs/                       # Logs chi tiết quá trình huấn luyện (xuất file dạng .csv), cập nhật thêm cột và thời gian sau mỗi lần train (hoặc tự xóa nếu tạo mới tệp)
│   │   ├── liver/
│   │   │   ├── Loss_train/
│   │   │   └── Loss_val/
│   │   └── tumor/
│   │       ├── Loss_train/
│   │       └── Loss_val/
│   ├── models/                     # Mô hình phân đoạn ảnh sử dụng U-NET
│   │   ├── __init__.py
│   │   └── unet.py
│   ├── scripts/                    # Scripts huấn luyện
│   │   ├── __init__.py
│   │   ├── check_format            # Kiểm tra thông số raw
│   │   ├── evaluate.py             # Đánh giá mô hình train
│   │   ├── inference.py            # Case test 1 raw bất kỳ
│   │   ├── mesh_generator.py       # Xử lý ảnh 3D, xuất file .obj vào data/meshes/..
│   │   ├── process_liver.py        # Tiền xử lý dữ liệu gan (tổng thể) từ data/raw/liver/.., xuất vào data/processed/liver
│   │   ├── process_tumor.py        # Tiền xử lý dữ liệu khối u trong gan, xuất vào data/processed/tumor
│   │   ├── train_liver.py          # Huấn luyện mô hình U-NET cho phân đoạn gan từ data/processed/liver, xuất vào train_model/checkpoints
│   │   └── train_tumor.py          # Huấn luyện mô hình U-NET cho phân đoạn khối u từ data/processed/tumor, xuất mô hình vào train_model/checkpoints
│   ├── utils/                  
│   │   ├── __init__.py     
│   │   ├── data_loader.py          # Lấy dữ liệu từ data phục vụ train
│   │   ├── dice_loss.py            # Tính dice_loss
│   │   ├── helpers.py              # Các hàm bổ trợ
│   │   └── image_processing.py     # Các hàm xử lý ảnh
│   ├── __init__.py
│   └── config.py                   # Đọc file cấu hình 'config.yaml', cấu hình các tham số trong 'train_model'
│
├── web_flask/                      # Quản lý dữ liệu trên web
│   ├── blueprints/             
│   │   ├── archive/
│   │   │   ├── __init__.py
│   │   │   └── views.py
│   │   ├── dashboard/
│   │   │   ├── __init__.py
│   │   │   └── views.py
│   │   └── train/
│   │       ├── __init__.py
│   │       └── views.py
│   ├── static/
│   │   ├── css/
│   │   │   ├── archive.css
│   │   │   ├── base.css
│   │   │   ├── dashboard.css
│   │   │   └── train.css
│   │   ├── js/
│   │   │   ├── archive.js
│   │   │   ├── base.js
│   │   │   ├── dashboard.js
│   │   │   └── train.js
│   │   ├── thumbnails/             # Lưu ảnh 2D và 3D dùng để quản lý trực quan hóa trong archive (đặt tên ảnh giống tên file gốc)
│   │   │   ├── meshes/
│   │   │   │   ├── liver/
│   │   │   │   └── tumor/
│   │   │   ├── processed/
│   │   │   │   ├── liver/
│   │   │   │   └── tumor/
│   │   │   └── raw/
│   │   │       └── liver/
│   │   │           ├── imagesTr/
│   │   │           └── labelsTr/
│   │   └── placeholder.png         # Ảnh trống khi chưa load được thumbnails
│   ├── templates/
│   │   ├── archive.html            # Quản lý database trực quan (các thẻ trực quan hóa có dạng 2D đối với raw + processed và 3D đối với meshes)
│   │   ├── base.html       
│   │   ├── dashboard.html          # Xem số lượng file trong database, quản lý với biểu đồ cập nhật theo ngày
│   │   └── train.html              # Nhập file CT .nii và mask (nếu có), huấn luyện và xuất vào processed + meshes (có hiển thị thẻ trực quan)
│   ├── utils/                  
│   │   ├── __init__.py
│   │   ├── data_counts.py          # Đếm số lượng data
│   │   ├── image_converter.py      # Chuyển định dạng ảnh từ data/raw, data/processed, data/mesh thành dạng 2D lưu vào 
│   │   │                             thumbnails phục vụ quản lý trực quan trong web archive
│   │   └── pipeline.py             # Pipeline huấn luyện từ train_model, phục vụ cho chức năng huấn luyện trong web train
│   ├── __init__.py
│   ├── app.py                      # Chạy webflask
│   └── config.py                   # Đọc file config.yaml
├── config.yaml                     # File cấu hình toàn cục (xác định đường dẫn), tham số toàn cục
├── README.txt
└── requirements.txt
```


---

## 2. Luồng hoạt động chính

### A. Chuẩn bị dữ liệu
- Đặt ảnh CT (.nii) vào `data/raw/liver/imagesTr/`
- Mask tương ứng (nhãn gan/u) vào `data/raw/liver/labelsTr/`

### B. Huấn luyện mô hình
```bash
# Tiền xử lý ảnh gan
python train_model/scripts/process_liver.py

# Huấn luyện U‑Net gan
python train_model/scripts/train_liver.py

# Tiền xử lý & huấn luyện khối u
python train_model/scripts/process_tumor.py
python train_model/scripts/train_tumor.py
```
- Checkpoint được lưu vào `train_model/checkpoints/`

### C. Tạo mesh
```bash
# Tạo ảnh 3D .obj
python train_model/scripts/mesh_generator.py
```

## 3. Quản lý dữ liệu
- Archive (/archive): Xem, tải, xóa file raw/processed/meshes, thùng rác.
- Dashboard (/dashboard): biểu đồ thống kê số lượng file theo thời gian.