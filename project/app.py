from flask import Flask, render_template, request
import os
from MIDI_to_notation import convert_midi_to_jianpu  #import正媛程式碼
from flask import send_from_directory
from flask import send_file

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

    if file and allowed_file(file.filename):
        filename = file.filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(filepath)
        # ✅ 解析 bpm（如果沒填則用預設 80）
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

        response_html = f"""
        檔案上傳成功：{filename}<br>
        儲存於：{filepath}<br><br>
        簡譜結果：<br><pre>{text_output}</pre><br>
        """

        if pdf_path and os.path.exists(pdf_path):
            # 取得相對於 uploads/ 的路徑，並把反斜線換成斜線
            pdf_rel = os.path.relpath(pdf_path, start=app.config['UPLOAD_FOLDER']).replace("\\", "/")
            response_html += f"""<a href="/download/{pdf_rel}" target="_blank">👉 點我下載 PDF 樂譜</a>"""
        else:
            response_html += "❌ PDF 轉換失敗，請檢查 LilyPond 路徑或轉換過程。"

        return response_html
    else:
        return "錯誤：僅允許上傳 .mid 或 .midi 檔案。"

from flask import send_file

@app.route('/download/<path:subpath>')
def download_file(subpath):
    file_path = os.path.join("uploads", subpath)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return "❌ 找不到檔案。"
    

if __name__ == '__main__':
    app.run(debug=True)
