from flask import Flask, render_template, request
import os
from MIDI_to_notation import convert_midi_to_jianpu  #import正媛程式碼
from flask import send_from_directory
from flask import send_file, make_response

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'mid', 'midi'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    
#======index.html介面======#
@app.route('/')
def index():
    return render_template('index.html')
 
#======檢查上傳檔案有無成功======#
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

    # 讀表單參數
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
    text_output = result.get("text_output", "")
    pdf_path = result.get("pdf_path")
    pdf_rel = None
    if pdf_path and os.path.exists(pdf_path):
        pdf_rel = os.path.relpath(pdf_path, start=app.config['UPLOAD_FOLDER']).replace("\\", "/")
         # 轉檔
        result = convert_midi_to_jianpu(filepath, bpm, numerator, denominator)
        text_output = result.get("text_output", "")
        pdf_path = result.get("pdf_path")

        # 回傳模板（在頁面直接嵌 PDF）
    return render_template(
        'result.html',
        filename=filename,
        filepath=filepath,
        text_output=text_output,
        pdf_rel=pdf_rel
    )

# 保留下載路由（強制下載）
@app.route('/download/<path:subpath>')
def download_file(subpath):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], subpath)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return "❌ 找不到檔案。", 404

# 新增 inline 檢視路由（內嵌顯示）
@app.route('/view/<path:subpath>')
def view_file(subpath):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], subpath)
    if not os.path.exists(file_path):
        return "❌ 找不到檔案。", 404
    resp = make_response(send_file(file_path, mimetype='application/pdf'))
    resp.headers['Content-Disposition'] = f'inline; filename="{os.path.basename(file_path)}"'
    return resp
    

if __name__ == '__main__':
    app.run(debug=True)
