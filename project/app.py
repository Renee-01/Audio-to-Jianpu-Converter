from flask import Flask, render_template, request, send_from_directory, send_file
import os
from MIDI_to_notation import convert_midi_to_jianpu

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'mid', 'midi'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

#儲存user上傳的檔案
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "錯誤：沒有檔案被上傳。"
    file = request.files['file']
    if file.filename == '':
        return "錯誤：未選擇檔案。"
    if not (file and allowed_file(file.filename)):
        return "錯誤：僅允許上傳 .mid 或 .midi 檔案。"

    filename = file.filename
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # 參數
    try:
        bpm = float(request.form.get('bpm', 80))
    except ValueError:
        bpm = 80
    try:
        numerator = int(request.form.get('numerator', 4))
        denominator = int(request.form.get('denominator', 4))
    except ValueError:
        numerator, denominator = 4, 4

    # 轉檔
    result = convert_midi_to_jianpu(filepath, bpm, numerator, denominator)
    text_output = result.get('text_output', '')
    pdf_path = result.get('pdf_path')

    # 把絕對路徑轉成 uploads/ 下的相對路徑，給模板用
    pdf_rel = None
    if pdf_path and os.path.exists(pdf_path):
        pdf_rel = os.path.relpath(pdf_path, start=app.config['UPLOAD_FOLDER']).replace(os.sep, '/')

    # 交給模板（你那份 result.html）
    return render_template(
        'result.html',
        filename=filename,
        filepath=filepath,
        text_output=text_output,
        pdf_rel=pdf_rel
    )

# 下載（強制下載）
@app.route('/download/<path:subpath>')
def download_file(subpath):
    abs_path = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], subpath))
    if not os.path.isfile(abs_path):
        return f"❌ 找不到檔案：{abs_path}", 404
    return send_file(abs_path, as_attachment=True)

# inline 預覽（給 iframe 用）
@app.route('/view/<path:subpath>')
def view_file(subpath):
    abs_path = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], subpath))
    if not os.path.isfile(abs_path):
        return f"❌ 找不到檔案：{abs_path}", 404
    return send_file(abs_path, mimetype='application/pdf', as_attachment=False)

if __name__ == '__main__':
    app.run(debug=True)
