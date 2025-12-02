from flask import Flask, render_template, request, send_file
from MIDI_to_notation import convert_midi_to_jianpu
import os, json
import re
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
    # 1) 檢查檔案
    if 'file' not in request.files:
        return "錯誤：沒有檔案被上傳。"
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


    # 3) 音訊 -> MIDI
    remove_accompaniment = (request.form.get("remove_accompaniment") == "on")

    try:
        midi_path = audio_to_midi(
            audio_path,
            out_dir=app.config['UPLOAD_FOLDER'],
             remove_accompaniment = remove_accompaniment,
        )
        midi_path = os.path.abspath(midi_path)
    except Exception as e:
        return f"❌ 音訊轉 MIDI 失敗：{e}"

    # 4) 轉成前端要的 notes（單位：格）
    raw_notes = extract_notes_for_editor(midi_path)
    notes_for_ui = []
    for n in raw_notes:
        start_u = int(round(n.start / SEC_PER_UNIT))
        end_u = int(round(n.end / SEC_PER_UNIT))
        if end_u <= start_u:
            end_u = start_u + 1
        notes_for_ui.append({
            "pitch": int(n.pitch),
            "start": start_u,
            "end": end_u
        })

    return render_template(
        'edit.html',
        filename=filename,
        notes_json=json.dumps(notes_for_ui, ensure_ascii=False),
    )


# ---------- 編輯頁送回的音符 → 單音化存 MIDI ----------
@app.route('/save-midi', methods=['POST'])
def save_midi():
    data = request.get_json(force=True)
    notes = data.get("notes", [])

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

    # 1) 寫出單音 MIDI
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=0)
    for n in mono:
        inst.notes.append(pretty_midi.Note(
            velocity=96,
            pitch=n["pitch"],
            start=n["start"],
            end=n["end"]
        ))
    pm.instruments.append(inst)

    # 2) 存成新的 MIDI 檔（/uploads/{曲目名稱}{時間戳}/）
    title = data.get("filename") or data.get("title") or "song"


    safe_title = re.sub(r'[^0-9A-Za-z\u4e00-\u9fff]+', '_', title).strip('_')
    if not safe_title:
        safe_title = "song"

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"{safe_title}{ts}"

    out_dir = os.path.join(app.config['UPLOAD_FOLDER'], folder_name)
    os.makedirs(out_dir, exist_ok=True)

    midi_out = os.path.join(out_dir, f"{safe_title}.mid")
    pm.write(midi_out)

    midi_abs = os.path.abspath(midi_out)
    midi_rel = os.path.relpath(
        midi_abs,
        start=os.path.abspath(app.config['UPLOAD_FOLDER'])
    ).replace(os.sep, '/')

    # 3) 嘗試把 MIDI 轉成簡譜 PDF
    pdf_rel = None
    jianpu_text = None
    pdf_error = None

    try:
        result = convert_midi_to_jianpu(midi_abs)  # 呼叫你在 MIDI_to_notation.py 寫的高階函式:contentReference[oaicite:2]{index=2}
        jianpu_text = result.get("text_output")

        pdf_abs = result.get("pdf_path")
        if pdf_abs:
            pdf_rel = os.path.relpath(
                os.path.abspath(pdf_abs),
                start=os.path.abspath(app.config['UPLOAD_FOLDER'])
            ).replace(os.sep, '/')
    except Exception as e:
        pdf_error = str(e)
        # 印在 console，方便你看是哪一段（MuseScore / musicxml_to_jianpu / jianpu-ly / LilyPond）爆掉
        import sys
        print("❌ 轉簡譜 PDF 失敗：", e, file=sys.stderr, flush=True)

    # 4) 丟到 result.html
    return render_template(
        'result.html',
        filename=os.path.basename(midi_out),
        midi_rel=midi_rel,
        pdf_rel=pdf_rel,         # ← 給「PDF 樂譜」那一塊用
        jianpu_text=jianpu_text, # ← 你如果想在頁面上顯示簡譜文字可以用
        pdf_error=pdf_error,     # ← 轉檔失敗時顯示詳細錯誤（可選）
    )


@app.route('/download/<path:subpath>')
def download_file(subpath):
    abs_path = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], subpath))
    if not os.path.isfile(abs_path):
        return f"❌ 找不到檔案：{abs_path}", 404
    return send_file(abs_path, as_attachment=True)


@app.route('/play/<path:subpath>')
def play_midi(subpath):
    abs_path = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], subpath))
    if not os.path.isfile(abs_path):
        return f"❌ 找不到檔案：{abs_path}", 404
    # audio/midi 或 audio/x-midi 都有人用，這裡先用 audio/midi
    return send_file(abs_path, mimetype='audio/midi', as_attachment=False)

@app.route('/view/<path:subpath>')
def view_file(subpath):
    abs_path = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], subpath))
    if not os.path.isfile(abs_path):
        return f"❌ 找不到檔案：{abs_path}", 404

    # 簡單用副檔名判斷 MIME type
    ext = os.path.splitext(abs_path)[1].lower()
    if ext == ".pdf":
        return send_file(abs_path, mimetype="application/pdf", as_attachment=False)

    # 其他檔案就單純 inline 回去
    return send_file(abs_path, as_attachment=False)


if __name__ == '__main__':
    app.run(debug=True)
