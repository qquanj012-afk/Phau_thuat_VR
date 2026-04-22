import os
import sys
import shutil
from datetime import datetime
from pathlib import Path
from flask import Blueprint, render_template, jsonify, request, url_for

archive_bp = Blueprint('archive', __name__, template_folder='../../templates')

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
WEB_FLASK_DIR = BASE_DIR / 'web_flask'
sys.path.append(str(WEB_FLASK_DIR))
from utils.image_converter import generate_thumbnail

DATA_DIR = BASE_DIR / 'data'
TRASH_DIR = DATA_DIR / '.trash'
os.makedirs(TRASH_DIR / 'raw', exist_ok=True)
os.makedirs(TRASH_DIR / 'processed', exist_ok=True)
os.makedirs(TRASH_DIR / 'meshes', exist_ok=True)

MEDICAL_EXTS = {'.nii', '.nii.gz', '.dcm', '.dicom', '.mhd', '.mha', '.nrrd', '.png', '.jpg', '.jpeg'}
MESH_EXTS = {'.obj', '.stl', '.ply', '.glb', '.gltf'}

def count_files(path, extensions):
    if not path.exists():
        return 0
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            if any(f.lower().endswith(ext) for ext in extensions):
                total += 1
    return total

def get_raw_count():
    return count_files(DATA_DIR / 'raw' / 'liver', MEDICAL_EXTS)

def get_processed_count():
    return count_files(DATA_DIR / 'processed' / 'liver', MEDICAL_EXTS)

def get_mesh_count():
    return count_files(DATA_DIR / 'meshes', MESH_EXTS)

def get_trash_count():
    return count_files(TRASH_DIR, MEDICAL_EXTS | MESH_EXTS)

def scan_directory(subdir, extensions, type_name, sort_by='date_desc', is_trash=False):
    items = []
    root_path = (TRASH_DIR if is_trash else DATA_DIR) / subdir
    if not root_path.exists():
        return items

    for root, _, files in os.walk(root_path):
        for f in files:
            if any(f.lower().endswith(ext) for ext in extensions):
                full = Path(root) / f
                stat = full.stat()
                if is_trash:
                    rel = str(full.relative_to(TRASH_DIR)).replace('\\', '/')
                else:
                    rel = str(full.relative_to(DATA_DIR)).replace('\\', '/')
                url = url_for('serve_data', subpath=rel) if not is_trash else '#'

                items.append({
                    'name': f,
                    'date': stat.st_mtime,
                    'date_str': datetime.fromtimestamp(stat.st_mtime).strftime('%d/%m/%Y %H:%M'),
                    'size': f"{stat.st_size/1024/1024:.1f} MB" if stat.st_size > 1024*1024 else f"{stat.st_size/1024:.0f} KB",
                    'url': url,
                    'file_path': rel,
                    'thumb': url_for('static', filename='placeholder.png'),
                    'type': type_name,
                    'original_type': subdir
                })

    if sort_by == 'name_asc':
        items.sort(key=lambda x: x['name'].lower())
    elif sort_by == 'name_desc':
        items.sort(key=lambda x: x['name'].lower(), reverse=True)
    elif sort_by == 'date_asc':
        items.sort(key=lambda x: x['date'])
    else:
        items.sort(key=lambda x: x['date'], reverse=True)
    return items

@archive_bp.route('/')
def archive_page():
    sort = request.args.get('sort', 'date_desc')
    raw_items = scan_directory('raw/liver', MEDICAL_EXTS, 'raw', sort)
    processed_items = scan_directory('processed/liver', MEDICAL_EXTS, 'processed', sort)
    mesh_items = scan_directory('meshes', MESH_EXTS, 'mesh', sort)

    return render_template('archive.html',
                           raw_count=get_raw_count(),
                           processed_count=get_processed_count(),
                           mesh_count=get_mesh_count(),
                           trash_count=get_trash_count(),
                           raw_items=raw_items,
                           processed_items=processed_items,
                           mesh_items=mesh_items,
                           current_sort=sort)

@archive_bp.route('/api/thumbnail')
def api_thumbnail():
    file_path = request.args.get('file')
    if not file_path:
        return jsonify({'error': 'Missing file parameter'}), 400
    if '..' in file_path or file_path.startswith('/'):
        return jsonify({'error': 'Invalid file path'}), 400

    full = DATA_DIR / file_path
    if not full.exists():
        full = TRASH_DIR / file_path
        if not full.exists():
            return jsonify({'error': 'File not found'}), 404

    try:
        thumb_url = generate_thumbnail(str(full))
        return jsonify({'thumb_url': thumb_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@archive_bp.route('/delete/<type>/<path:filepath>', methods=['DELETE'])
def delete_file(type, filepath):
    if type not in ('raw', 'processed', 'meshes'):
        return jsonify({'success': False, 'error': 'Loại không hợp lệ'}), 400
    if '..' in filepath or filepath.startswith('/'):
        return jsonify({'success': False, 'error': 'Đường dẫn không an toàn'}), 400

    full_path = DATA_DIR / filepath
    if not full_path.exists():
        return jsonify({'success': False, 'error': 'File không tồn tại'}), 404

    try:
        rel_to_type = full_path.relative_to(DATA_DIR / type)
        trash_dest = TRASH_DIR / type / rel_to_type
        os.makedirs(trash_dest.parent, exist_ok=True)
        shutil.move(str(full_path), str(trash_dest))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Thêm vào archive/views.py
@archive_bp.route('/trash/items')
def trash_items():
    sort = request.args.get('sort', 'date_desc')
    raw = scan_directory('raw', MEDICAL_EXTS, 'raw', sort, is_trash=True)
    processed = scan_directory('processed', MEDICAL_EXTS, 'processed', sort, is_trash=True)
    meshes = scan_directory('meshes', MESH_EXTS, 'mesh', sort, is_trash=True)
    all_items = raw + processed + meshes
    # Sắp xếp
    if sort == 'name_asc':
        all_items.sort(key=lambda x: x['name'].lower())
    elif sort == 'name_desc':
        all_items.sort(key=lambda x: x['name'].lower(), reverse=True)
    elif sort == 'date_asc':
        all_items.sort(key=lambda x: x['date'])
    else:
        all_items.sort(key=lambda x: x['date'], reverse=True)
    return jsonify(all_items)

@archive_bp.route('/trash/restore/<path:filepath>', methods=['POST'])
def restore_file(filepath):
    if '..' in filepath or filepath.startswith('/'):
        return jsonify({'success': False, 'error': 'Đường dẫn không an toàn'}), 400
    trash_path = TRASH_DIR / filepath
    if not trash_path.exists():
        return jsonify({'success': False, 'error': 'File không tồn tại'}), 404
    dest_path = DATA_DIR / filepath
    try:
        os.makedirs(dest_path.parent, exist_ok=True)
        shutil.move(str(trash_path), str(dest_path))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@archive_bp.route('/trash/permanent/<path:filepath>', methods=['DELETE'])
def permanent_delete(filepath):
    if '..' in filepath or filepath.startswith('/'):
        return jsonify({'success': False, 'error': 'Đường dẫn không an toàn'}), 400
    trash_path = TRASH_DIR / filepath
    if not trash_path.exists():
        return jsonify({'success': False, 'error': 'File không tồn tại'}), 404
    try:
        os.remove(trash_path)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500