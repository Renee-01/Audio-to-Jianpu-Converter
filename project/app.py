from flask import Flask, render_template, request, send_file
import os, json
from werkzeug.utils import secure_filename
from Audio_to_MIDI import audio_to_midi
import pretty_midi
from datetime import datetime

# 每一格代表多少秒（這裡設 0.05 秒 = 一秒 20 格）
SEC_PER_UNIT = 0.05

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav'}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')


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
@app.route('/audio-upload', methods=['POST'])
def upload_file():
<<<<<<< HEAD
    # 1) 檢查檔案
    if 'file' not in request.files:
        return "錯誤：沒有檔案被上傳。"
=======
    if request.method == 'GET':
        return redirect(url_for('index'))
    if 'file' not in request.files:
        return redirect(url_for('index'))

>>>>>>> 971bdf6b4c9b62dbaad1f6fbea682fe0ac17ed4d
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

<<<<<<< HEAD
    # 3) 音訊 -> MIDI
=======
    # 3) 目前前端沒有 BPM/拍號欄位，先用預設值傳到編輯頁
    bpm = 80.0
    numerator = 4
    denominator = 4

    # 讀取「是否需要消除伴奏」核取方塊（有勾選 → True）
    remove_accompaniment = request.form.get('remove_accompaniment') == '1'

    # 4) 音訊 -> MIDI
>>>>>>> 971bdf6b4c9b62dbaad1f6fbea682fe0ac17ed4d
    try:
        midi_path = audio_to_midi(
            audio_path,
            out_dir=app.config['UPLOAD_FOLDER'],
            remove_accompaniment=remove_accompaniment
        )
        midi_path = os.path.abspath(midi_path)
    except Exception as e:
        return f"❌ 音訊轉 MIDI 失敗：{e}"

    # 4) 轉成前端要的 notes（單位：格）
    raw_notes = extract_notes_for_editor(midi_path)
    notes_for_ui = []
    for n in raw_notes:
<<<<<<< HEAD
        start_u = int(round(n.start / SEC_PER_UNIT))
        end_u = int(round(n.end / SEC_PER_UNIT))
=======
        start_u = int(round(n.start / sec_per_unit))
        end_u = int(round(n.end / sec_per_unit))
>>>>>>> 971bdf6b4c9b62dbaad1f6fbea682fe0ac17ed4d
        if end_u <= start_u:
            end_u = start_u + 1
        notes_for_ui.append({
            "pitch": int(n.pitch),
            "start": start_u,
            "end": end_u
        })

<<<<<<< HEAD
=======
    # 6) 轉到編輯頁
    midi_rel = os.path.relpath(
        midi_path,
        start=os.path.abspath(app.config['UPLOAD_FOLDER'])
    ).replace(os.sep, '/')

>>>>>>> 971bdf6b4c9b62dbaad1f6fbea682fe0ac17ed4d
    return render_template(
        'edit.html',
        filename=filename,
        notes_json=json.dumps(notes_for_ui, ensure_ascii=False),
    )


<<<<<<< HEAD
# ---------- 編輯頁送回的音符 → 單音化存 MIDI ----------
=======
# ---------- 編輯頁送回的音符 → 單音化存 MIDI → 轉簡譜 ----------
>>>>>>> 971bdf6b4c9b62dbaad1f6fbea682fe0ac17ed4d
@app.route('/save-midi', methods=['POST'])
def save_midi():
    data = request.get_json(force=True)
    notes = data.get("notes", [])
<<<<<<< HEAD

    # 單音化：依 start 排序，遇到新音就截斷前一音
    notes_sorted = sorted(notes, key=lambda x: (x["start"], x["end"]))
    mono = []
    cur = None
    for n in notes_sorted:
        s = float(n["start"]) * SEC_PER_UNIT
        e = float(n["end"]) * SEC_PER_UNIT
        p = int(n["pitch"])
        if e <= s:
            e = s + SEC_PER_UNIT
        if cur is None:
            cur = {"start": s, "end": e, "pitch": p}
            continue
        if s >= cur["end"]:
            mono.append(cur)
            cur = {"start": s, "end": e, "pitch": p}
        else:
            # 新音開始時間在前一音裡面 → 截斷前音到新音開始
            if s > cur["start"]:
                cur["end"] = s
                if cur["end"] > cur["start"]:
                    mono.append(cur)
            cur = {"start": s, "end": e, "pitch": p}
    if cur and cur["end"] > cur["start"]:
        mono.append(cur)

    # 寫出單音 MIDI
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=0)
    for n in mono:
        inst.notes.append(pretty_midi.Note(
            velocity=96,
            pitch=n["pitch"],
            start=n["start"],
            end=n["end"]
        ))
=======
    bpm = float(data.get("bpm", 80))
    numerator = int(data.get("numerator", 4))      # 先留著，之後要用也方便
    denominator = int(data.get("denominator", 4))  # 先留著，之後要用也方便

    # 1) 時間換算：一格有幾秒
    beat_sec = 60.0 / bpm
    sec_per_unit = beat_sec / GRID_UNITS_PER_QUARTER

    # 2) 不做單音化、不做小節切齊，直接把「格」換成秒，寫進 MIDI
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=0)

    for n in notes:
        s_u = int(round(n["start"]))
        e_u = int(round(n["end"]))
        p = int(n["pitch"])

        if e_u <= s_u:
            e_u = s_u + 1   # 至少一格

        start = s_u * sec_per_unit
        end   = e_u * sec_per_unit

        inst.notes.append(pretty_midi.Note(
            velocity=96,
            pitch=p,
            start=start,
            end=end,
        ))

>>>>>>> 971bdf6b4c9b62dbaad1f6fbea682fe0ac17ed4d
    pm.instruments.append(inst)

        # 3) 存成新的 MIDI 檔（/uploads/{曲目名稱}{時間戳}/）
    # 從前端資料拿曲目名稱（沒有就用預設 "song"）
    title = data.get("filename") or data.get("title") or "song"

    # 簡單做一下檔名/資料夾名稱清洗：去掉奇怪字元，避免 Windows 爆炸
    import re
    safe_title = re.sub(r'[^0-9A-Za-z\u4e00-\u9fff]+', '_', title).strip('_')
    if not safe_title:
        safe_title = "song"

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"{safe_title}{ts}"

    # /uploads/{曲目名稱}{時間戳}/
    out_dir = os.path.join(app.config['UPLOAD_FOLDER'], folder_name)
    os.makedirs(out_dir, exist_ok=True)

    # MIDI 檔名就叫 {曲目名稱}.mid
    midi_out = os.path.join(out_dir, f"{safe_title}.mid")
    pm.write(midi_out)

<<<<<<< HEAD
=======
    # 4) 丟給 convert_midi_to_jianpu 轉簡譜 + PDF
    text_output, pdf_rel = "", None
    try:
        result = convert_midi_to_jianpu(midi_out)
        text_output = result.get('text_output', '')

        # 先看函式有沒有回傳 pdf_path
        pdf_path = result.get('pdf_path')

        # 如果沒有，就用我們自己的規則推：同資料夾、同曲名，加 .jianpu.pdf
        if not pdf_path:
            pdf_path = os.path.splitext(midi_out)[0] + ".jianpu.pdf"

        if pdf_path and os.path.exists(pdf_path):
            pdf_rel = os.path.relpath(
                os.path.abspath(pdf_path),
                start=os.path.abspath(app.config['UPLOAD_FOLDER'])
            ).replace(os.sep, '/')
    except Exception as ex:
        text_output = f"（產生 PDF 失敗）{ex}"
        pdf_rel = None

    # 5) 編輯後 MIDI 的相對路徑（給下載用）
>>>>>>> 971bdf6b4c9b62dbaad1f6fbea682fe0ac17ed4d
    midi_rel = os.path.relpath(
        os.path.abspath(midi_out),
        start=os.path.abspath(app.config['UPLOAD_FOLDER'])
    ).replace(os.sep, '/')

    return render_template(
        'result.html',
        filename=os.path.basename(midi_out),
        midi_rel=midi_rel
    )



@app.route('/download/<path:subpath>')
def download_file(subpath):
    abs_path = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], subpath))
    if not os.path.isfile(abs_path):
        return f"❌ 找不到檔案：{abs_path}", 404
    return send_file(abs_path, as_attachment=True)

<<<<<<< HEAD
=======

@app.route('/view/<path:subpath>')
def view_file(subpath):
    abs_path = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], subpath))
    if not os.path.isfile(abs_path):
        return f"❌ 找不到檔案：{abs_path}", 404
    return send_file(abs_path, mimetype='application/pdf', as_attachment=False)
>>>>>>> 971bdf6b4c9b62dbaad1f6fbea682fe0ac17ed4d

@app.route('/play/<path:subpath>')
def play_midi(subpath):
    abs_path = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], subpath))
    if not os.path.isfile(abs_path):
        return f"❌ 找不到檔案：{abs_path}", 404
    # audio/midi 或 audio/x-midi 都有人用，這裡先用 audio/midi
    return send_file(abs_path, mimetype='audio/midi', as_attachment=False)


if __name__ == '__main__':
    app.run(debug=True)
