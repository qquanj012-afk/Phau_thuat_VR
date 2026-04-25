import os
import sys
import shutil
from datetime import datetime
from pathlib import Path
from flask import Blueprint, render_template, jsonify, request, url_for
from web_flask.utils.data_counts import *
from web_flask.utils.image_converter import *

archive_bp = Blueprint('archive', __name__, template_folder='../../templates')

os.makedirs(TRASH_DIR / 'raw', exist_ok=True)
os.makedirs(TRASH_DIR / 'processed', exist_ok=True)
os.makedirs(TRASH_DIR / 'meshes', exist_ok=True)

def scan_directory(subdir, extensions, type_name, sort_by='date_desc', is_trash=False, raw_subfolder=None):
    items = []
    base = TRASH_DIR if is_trash else DATA_DIR
    root_path = base / subdir
    if raw_subfolder and type_name == 'raw':
        root_path = root_path / raw_subfolder
    if not root_path.exists():
        return items

    for root, _, files in os.walk(root_path):
        root_str = str(root).lower()
        if 'liver' in root_str:
            subtype = 'liver'
        elif 'tumor' in root_str:
            subtype = 'tumor'
        else:
            subtype = 'unknown'

        for f in files:
            # Lọc file: nếu type là processed, chỉ lấy *_img.npy
            if type_name == 'processed' and not f.endswith('_img.npy'):
                continue
            # Nếu type là raw, lấy tất cả file trong imagesTr (đã giới hạn bởi raw_subfolder)
            if any(f.lower().endswith(ext) for ext in extensions):
                full = Path(root) / f
                stat = full.stat()
                if is_trash:
                    rel = str(full.relative_to(TRASH_DIR)).replace('\\', '/')
                else:
                    rel = str(full.relative_to(DATA_DIR)).replace('\\', '/')
                url = url_for('serve_data', subpath=rel) if not is_trash else '#'

                thumb_rel = rel.replace('data/', '')
                thumb_rel = thumb_rel.replace('.nii.gz', '.png').replace('.nii', '.png').replace('.npy', '.png').replace('.obj', '.png')
                thumb_url = url_for('static', filename=f'thumbnails/{thumb_rel}')

                items.append({
                    'name': f,
                    'date': stat.st_mtime,
                    'date_str': datetime.fromtimestamp(stat.st_mtime).strftime('%d/%m/%Y %H:%M'),
                    'size': f"{stat.st_size/1024/1024:.1f} MB" if stat.st_size > 1024*1024 else f"{stat.st_size/1024:.0f} KB",
                    'url': url,
                    'file_path': rel,
                    'thumb': thumb_url,
                    'type': type_name,
                    'subtype': subtype,
                    'original_type': subdir
                })

    # Sắp xếp
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

    raw_liver_items = scan_directory('raw/liver', MEDICAL_EXTS, 'raw', sort, raw_subfolder='imagesTr')
    raw_tumor_items = scan_directory('raw/tumor', MEDICAL_EXTS, 'raw', sort)
    for item in raw_liver_items:
        item['subtype'] = 'liver'
    for item in raw_tumor_items:
        item['subtype'] = 'tumor'
    raw_items = raw_liver_items + raw_tumor_items

    processed_items = scan_directory('processed', MEDICAL_EXTS, 'processed', sort)
    mesh_items = scan_directory('meshes', MESH_EXTS, 'mesh', sort)

    # Đếm theo subtype cho dropdown
    raw_liver_count = count_subtype(raw_items, 'liver')
    raw_tumor_count = count_subtype(raw_items, 'tumor')
    processed_liver_count = count_subtype(processed_items, 'liver')
    processed_tumor_count = count_subtype(processed_items, 'tumor')
    mesh_liver_count = count_subtype(mesh_items, 'liver')
    mesh_tumor_count = count_subtype(mesh_items, 'tumor')

    return render_template('archive.html',
                           raw_count=len(raw_items),
                           processed_count=get_processed_count(),
                           mesh_count=get_mesh_count(),
                           trash_count=get_trash_count(),
                           raw_items=raw_items,
                           processed_items=processed_items,
                           mesh_items=mesh_items,
                           current_sort=sort,
                           raw_liver=raw_liver_count,
                           raw_tumor=raw_tumor_count,
                           processed_liver=processed_liver_count,
                           processed_tumor=processed_tumor_count,
                           mesh_liver=mesh_liver_count,
                           mesh_tumor=mesh_tumor_count)

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