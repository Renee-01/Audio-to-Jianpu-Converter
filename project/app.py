from flask import Flask, render_template, request, send_file
import os
from werkzeug.utils import secure_filename
from MIDI_to_notation import convert_midi_to_jianpu
from Audio_to_MIDI import audio_to_midi

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AUDIO_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')


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

    # 2) 儲存音訊到 uploads/
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

    # 5) MIDI -> 簡譜 + PDF
    result = convert_midi_to_jianpu(midi_path, bpm, numerator, denominator)
    text_output = result.get('text_output', '')
    pdf_path = result.get('pdf_path')

    # 6) 給模板用的相對路徑（uploads/ 下）
    pdf_rel = None
    if pdf_path and os.path.exists(pdf_path):
        pdf_rel = os.path.relpath(
            os.path.abspath(pdf_path),
            start=os.path.abspath(app.config['UPLOAD_FOLDER'])
        ).replace(os.sep, '/')

    #  7) 一定要回傳東西（否則就會出你看到的 TypeError）
    return render_template(
        'result.html',
        filename=filename,        # 上傳的音訊檔名
        filepath=audio_path,      # 音訊儲存位置（給你顯示）
        text_output=text_output,  # 簡譜文字
        pdf_rel=pdf_rel           # PDF 供 /view 與 /download 使用
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
