import os
from datetime import datetime, timedelta, date
from flask import Blueprint, render_template, jsonify, request
from pathlib import Path

dashboard_bp = Blueprint('dashboard', __name__, template_folder='../../templates')

# Đường dẫn dữ liệu
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent  # web_flask/blueprints/dashboard -> gốc dự án
BACKEND_DATA_DIR = BASE_DIR / 'data'
MEDICAL_EXTS = {'.nii', '.nii.gz', '.dcm', '.dicom', '.png', '.jpg', '.jpeg'}
MESH_EXTS = {'.obj', '.stl', '.ply'}

def count_files_in_dir(path, extensions):
    if not path.exists():
        return 0
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            if any(f.lower().endswith(ext) for ext in extensions):
                total += 1
    return total

def get_raw_count():
    raw_path = BACKEND_DATA_DIR / 'raw' / 'liver'   # Giả định ảnh gan nằm trong raw/liver/
    return count_files_in_dir(raw_path, MEDICAL_EXTS)

def get_processed_count():
    processed_path = BACKEND_DATA_DIR / 'processed' / 'liver'
    return count_files_in_dir(processed_path, MEDICAL_EXTS)

def get_mesh_count():
    mesh_path = BACKEND_DATA_DIR / 'meshes'
    return count_files_in_dir(mesh_path, MESH_EXTS)

def get_daily_counts(directory, extensions, start_date, end_date):
    counts = {}
    if not directory.exists():
        return counts
    for root, _, files in os.walk(directory):
        for f in files:
            if any(f.lower().endswith(ext) for ext in extensions):
                full = Path(root) / f
                mtime = datetime.fromtimestamp(full.stat().st_mtime)
                if start_date <= mtime < end_date:
                    day = mtime.strftime('%Y-%m-%d')
                    counts[day] = counts.get(day, 0) + 1
    return counts

@dashboard_bp.route('/')
def dashboard_page():
    raw = get_raw_count()
    processed = get_processed_count()
    mesh = get_mesh_count()

    stats = {
        'raw': raw,
        'processed': processed,
        'mesh': mesh,
    }

    end = date.today()
    start = end - timedelta(days=7)
    start_date = start.isoformat()
    end_date = end.isoformat()

    labels = []
    current = start
    while current <= end:
        labels.append(current.strftime('%m-%d'))
        current += timedelta(days=1)

    chart_data = {
        'labels': labels,
        'raw': [0] * len(labels),
        'processed': [0] * len(labels),
        'mesh': [0] * len(labels)
    }

    return render_template('dashboard.html',
                           stats=stats,
                           chart_data=chart_data,
                           start_date=start_date,
                           end_date=end_date)

@dashboard_bp.route('/api/stats/timeseries')
def api_timeseries():
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    try:
        start_date = datetime.strptime(start_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_str, '%Y-%m-%d') + timedelta(days=1)
    except:
        return jsonify({'error': 'Định dạng ngày không hợp lệ'}), 400

    raw_dir = BACKEND_DATA_DIR / 'raw' / 'liver'
    proc_dir = BACKEND_DATA_DIR / 'processed' / 'liver'
    mesh_dir = BACKEND_DATA_DIR / 'meshes'

    raw_counts = get_daily_counts(raw_dir, MEDICAL_EXTS, start_date, end_date)
    proc_counts = get_daily_counts(proc_dir, MEDICAL_EXTS, start_date, end_date)
    mesh_counts = get_daily_counts(mesh_dir, MESH_EXTS, start_date, end_date)

    all_days = []
    current = start_date
    while current < end_date:
        all_days.append(current.strftime('%Y-%m-%d'))
        current += timedelta(days=1)

    raw_series = [raw_counts.get(day, 0) for day in all_days]
    proc_series = [proc_counts.get(day, 0) for day in all_days]
    mesh_series = [mesh_counts.get(day, 0) for day in all_days]

    return jsonify({
        'labels': all_days,
        'raw': raw_series,
        'processed': proc_series,
        'mesh': mesh_series,
        'total_raw': sum(raw_series),
        'total_processed': sum(proc_series),
        'total_mesh': sum(mesh_series)
    })