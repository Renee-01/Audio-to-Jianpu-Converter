from flask import Flask, render_template, request, send_file, redirect, url_for
import os, json
from werkzeug.utils import secure_filename
from MIDI_to_notation import convert_midi_to_jianpu
from Audio_to_MIDI import audio_to_midi
import pretty_midi
from datetime import datetime

GRID_UNITS_PER_QUARTER = 16  # 與 MIDI_to_notation.py 一致

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AUDIO_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

# ---------- 純工具函式：讀 MIDI → 回傳 pretty_midi.Note 清單 ----------
def extract_notes_for_editor(midi_path: str):
    pm = pretty_midi.PrettyMIDI(midi_path)
    if not pm.instruments:
        return []
    inst = pm.instruments[0]
    notes = sorted(inst.notes, key=lambda n: (n.start, n.end))
    return notes

# ---------- 上傳音檔 → 轉 MIDI → 進入編輯頁 ----------
@app.route('/audio-upload', methods=['GET', 'POST'])
def upload_file():
    # 1) 檢查檔案
    if request.method == 'GET':
        return redirect(url_for('index'))   # 直接回首頁重新上傳
    file = request.files['file']
    if file.filename == '':
        return "錯誤：未選擇檔案。"
    if not (file and allowed_file(file.filename)):
        return "錯誤：僅允許上傳 .mp3 或 .wav 檔案。"

    # 2) 儲存音訊
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    filename = secure_filename(file.filename)
    audio_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(audio_path)

    # 3) 參數
    try:
        bpm = float(request.form.get('bpm', 80))
    except ValueError:
        bpm = 80
    try:
        numerator = int(request.form.get('numerator', 4))
        denominator = int(request.form.get('denominator', 4))
    except ValueError:
        numerator, denominator = 4, 4

    # 4) 音訊 -> MIDI
    try:
        midi_path = audio_to_midi(audio_path, out_dir=app.config['UPLOAD_FOLDER'])
        midi_path = os.path.abspath(midi_path)
    except Exception as e:
        return f"❌ 音訊轉 MIDI 失敗：{e}"

    # 5) 給前端的 notes（單位：格）
    beat_sec = 60.0 / bpm
    sec_per_unit = (beat_sec / GRID_UNITS_PER_QUARTER)

    raw_notes = extract_notes_for_editor(midi_path)
    notes_for_ui = []
    for n in raw_notes:
        start_u = int(round(n.start / sec_per_unit))
        end_u   = int(round(n.end   / sec_per_unit))
        if end_u <= start_u:
            end_u = start_u + 1
        notes_for_ui.append({"pitch": int(n.pitch), "start": start_u, "end": end_u})

    # 6) 轉到編輯頁
    midi_rel = os.path.relpath(midi_path, start=os.path.abspath(app.config['UPLOAD_FOLDER'])).replace(os.sep, '/')
    return render_template(
        'edit.html',
        filename=filename,
        midi_rel=midi_rel,
        bpm=bpm,
        numerator=numerator,
        denominator=denominator,
        units_per_quarter=GRID_UNITS_PER_QUARTER,
        notes_json=json.dumps(notes_for_ui, ensure_ascii=False)
    )

# ---------- 編輯頁送回的音符 → 單音化存 MIDI → 轉簡譜 ----------
@app.route('/save-midi', methods=['POST'])
def save_midi():
    data = request.get_json(force=True)
    notes = data.get("notes", [])
    bpm = float(data.get("bpm", 80))
    numerator = int(data.get("numerator", 4))
    denominator = int(data.get("denominator", 4))

    beat_sec = 60.0 / bpm
    sec_per_unit = beat_sec / GRID_UNITS_PER_QUARTER

    # 單音化：遇到新音就截斷前音
    notes_sorted = sorted(notes, key=lambda x: (x["start"], x["end"]))
    mono = []
    cur = None
    for n in notes_sorted:
        s = float(n["start"]) * sec_per_unit
        e = float(n["end"])   * sec_per_unit
        p = int(n["pitch"])
        if e <= s: e = s + sec_per_unit
        if cur is None:
            cur = {"start": s, "end": e, "pitch": p}
            continue
        if s >= cur["end"]:
            mono.append(cur); cur = {"start": s, "end": e, "pitch": p}
        else:
            if s > cur["start"]:
                cur["end"] = s
                if cur["end"] > cur["start"]:
                    mono.append(cur)
            cur = {"start": s, "end": e, "pitch": p}
    if cur and cur["end"] > cur["start"]:
        mono.append(cur)

    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=0)
    for n in mono:
        inst.notes.append(pretty_midi.Note(velocity=96, pitch=n["pitch"], start=n["start"], end=n["end"]))
    pm.instruments.append(inst)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(app.config['UPLOAD_FOLDER'], "edited")
    os.makedirs(out_dir, exist_ok=True)
    midi_out = os.path.join(out_dir, f"edited_{ts}.mid")
    pm.write(midi_out)

    result = convert_midi_to_jianpu(midi_out, bpm, numerator, denominator)
    text_output = result.get('text_output', '')
    pdf_path = result.get('pdf_path')

    pdf_rel = None
    if pdf_path and os.path.exists(pdf_path):
        pdf_rel = os.path.relpath(os.path.abspath(pdf_path),
                                  start=os.path.abspath(app.config['UPLOAD_FOLDER'])).replace(os.sep, '/')

    # 新增：把剛輸出的 MIDI 也轉成相對 uploads/ 的路徑
    midi_rel = os.path.relpath(os.path.abspath(midi_out),
                           start=os.path.abspath(app.config['UPLOAD_FOLDER'])).replace(os.sep, '/')

    # ...保留你處理 pdf_rel 的程式後...

    return render_template(
        'result.html',
        filename=os.path.basename(midi_out),
        filepath=midi_out,
        text_output=text_output,
        pdf_rel=pdf_rel,
        midi_rel=midi_rel,
    )

@app.route('/download/<path:subpath>')
def download_file(subpath):
    abs_path = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], subpath))
    if not os.path.isfile(abs_path):
        return f"❌ 找不到檔案：{abs_path}", 404
    return send_file(abs_path, as_attachment=True)

@app.route('/view/<path:subpath>')
def view_file(subpath):
    abs_path = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], subpath))
    if not os.path.isfile(abs_path):
        return f"❌ 找不到檔案：{abs_path}", 404
    return send_file(abs_path, mimetype='application/pdf', as_attachment=False)

if __name__ == '__main__':
    app.run(debug=True)
