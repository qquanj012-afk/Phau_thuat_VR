import os
from datetime import datetime, timedelta, date
from flask import Blueprint, render_template, jsonify, request
from pathlib import Path
from web_flask.utils.data_counts import *

dashboard_bp = Blueprint('dashboard', __name__, template_folder='../../templates')

# Hàm đếm số file _img.npy theo ngày (cho processed)
def get_daily_processed_counts(directory, start_date, end_date):
    """Đếm số file _img.npy trong thư mục, nhóm theo ngày."""
    counts = {}
    if not directory.exists():
        return counts
    for root, _, files in os.walk(directory):
        for f in files:
            if f.endswith('_img.npy'):
                full = Path(root) / f
                mtime = datetime.fromtimestamp(full.stat().st_mtime)
                if start_date <= mtime < end_date:
                    day = mtime.strftime('%Y-%m-%d')
                    counts[day] = counts.get(day, 0) + 1
    return counts

# Hàm đếm theo extensions chung cho raw và mesh
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

    # Raw: gồm cả liver và tumor
    raw_dirs = [
        DATA_DIR / 'raw' / 'liver' / 'imagesTr',
        DATA_DIR / 'raw' / 'tumor'
    ]
    raw_counts = {}
    for d in raw_dirs:
        for day, cnt in get_daily_counts(d, MEDICAL_EXTS, start_date, end_date).items():
            raw_counts[day] = raw_counts.get(day, 0) + cnt

    # Processed: chỉ đếm _img.npy
    proc_dirs = [
        DATA_DIR / 'processed' / 'liver',
        DATA_DIR / 'processed' / 'tumor'
    ]
    proc_counts = {}
    for d in proc_dirs:
        for day, cnt in get_daily_processed_counts(d, start_date, end_date).items():
            proc_counts[day] = proc_counts.get(day, 0) + cnt

    # Mesh: toàn bộ meshes
    mesh_dir = DATA_DIR / 'meshes'
    mesh_counts = get_daily_counts(mesh_dir, MESH_EXTS, start_date, end_date)

    all_days = []
    current = start_date
    while current < end_date:
        all_days.append(current.strftime('%Y-%m-%d'))
        current += timedelta(days=1)

    raw_cumulative = []
    proc_cumulative = []
    mesh_cumulative = []
    raw_total = 0
    proc_total = 0
    mesh_total = 0

    for day in all_days:
        raw_total += raw_counts.get(day, 0)
        proc_total += proc_counts.get(day, 0)
        mesh_total += mesh_counts.get(day, 0)
        raw_cumulative.append(raw_total)
        proc_cumulative.append(proc_total)
        mesh_cumulative.append(mesh_total)

    return jsonify({
        'labels': all_days,
        'raw': raw_cumulative,
        'processed': proc_cumulative,
        'mesh': mesh_cumulative,
        'total_raw': raw_total,
        'total_processed': proc_total,
        'total_mesh': mesh_total
    })