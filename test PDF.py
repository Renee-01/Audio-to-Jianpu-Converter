import os
import sys
import subprocess
import shutil
from pathlib import Path
from tkinter import Tk, filedialog

# === 🛠 快速設定區 ===
# 1. 優先使用的指定 TXT 簡譜檔案路徑 (若不為空字串，將直接轉此檔案，免去手動選檔)
INPUT_TXT_PATH = r"D:\Audio-to-Jianpu-Converter\崴孟三百天禮物\崴孟三百天禮物.txt"

# 2. 產出的 PDF 存放資料夾
OUTPUT_DIR = r"D:\Audio-to-Jianpu-Converter\崴孟三百天禮物"

# 3. 系統工具路徑
JIANPU_SCRIPT = r"C:\lilypond-2.24.4\jianpu-ly.py"
LILYPOND_EXE  = r"C:\lilypond-2.24.4\bin\lilypond.exe"


def test_jianpu_conversion(txt_path: str, output_pdf_path: str):
    txt_path = Path(txt_path)
    output_pdf_path = Path(output_pdf_path)
    
    if not txt_path.exists():
        raise FileNotFoundError(f"找不到檔案: {txt_path}")

    # 確保輸出目錄存在，如果不存在則自動建立
    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    # 臨時在 txt 檔案旁產生中間產物 ly 檔
    base_dir = txt_path.parent
    ly_path = base_dir / "jianpu.ly"
    temp_pdf_path = base_dir / "jianpu.pdf"

    # Step 1️⃣ 呼叫 jianpu-ly.py 產生 jianpu.ly
    print("➡ 產生 jianpu.ly 中...")
    python_exe = sys.executable
    cmd = f'"{python_exe}" "{JIANPU_SCRIPT}" < "{txt_path}" > "{ly_path}"'
    
    subprocess.run(cmd, shell=True, cwd=base_dir, check=True)
        
    # 雙保險：萬一腳本又把檔案丟到 Temp
    if not ly_path.exists() or ly_path.stat().st_size == 0:
        import tempfile
        temp_dir = Path(tempfile.gettempdir())
        alt_ly_name = txt_path.with_suffix(".ly").name
        temp_ly_path = temp_dir / alt_ly_name
        
        if temp_ly_path.exists():
            shutil.move(str(temp_ly_path), str(ly_path))
        else:
            raise FileNotFoundError("未生成 jianpu.ly，請檢查 jianpu-ly.py 是否正確運作")

    print(f"✅ 已成功生成/對齊：{ly_path}")

    # Step 2️⃣ 用 LilyPond 生成 PDF
    print("➡ 轉成 PDF 中...")
    subprocess.run([LILYPOND_EXE, str(ly_path)], cwd=base_dir, check=True)

    # Step 3️⃣ 將產出的 PDF 移至使用者指定的位置
    if temp_pdf_path.exists():
        # 如果舊的 PDF 已經存在，先刪除以防 Windows 下權限衝突
        if output_pdf_path.exists():
            os.remove(output_pdf_path)
            
        shutil.move(str(temp_pdf_path), str(output_pdf_path))
        print(f"🎉 PDF 已成功儲存至指定位置：{output_pdf_path}")
        
        # 順手清理留在 txt 資料夾旁邊的臨時 .ly 檔，保持資料夾乾淨
        if ly_path.exists():
            os.remove(ly_path)
    else:
        print("⚠ 未找到輸出 PDF，請檢查 lilypond 設定。")


# === 執行主程式 ===
if __name__ == "__main__":
    txt_path = ""

    # 檢查是否已設定指定的輸入路徑
    if INPUT_TXT_PATH.strip():
        # 如果不為空字串，優先使用指定路徑
        temp_path = Path(INPUT_TXT_PATH)
        if temp_path.exists():
            txt_path = str(temp_path)
            print(f"⚡ [優先模式] 直接載入指定檔案：{os.path.basename(txt_path)}")
        else:
            print(f"⚠ 找不到指定的路徑 '{INPUT_TXT_PATH}'，將退回手動選檔模式。")

    # 如果沒有指定路徑，或者指定的檔案不存在，則彈出視窗手動選取
    if not txt_path:
        root = Tk()
        root.withdraw()
        txt_path = filedialog.askopenfilename(
            title="選擇簡譜文字檔 (.txt)", 
            filetypes=[("文字檔", "*.txt")]
        )
        
        if not txt_path:
            print("❌ 未選取檔案，程式中止。")
            raise SystemExit
            
        print(f"✅ 手動載入檔案：{os.path.basename(txt_path)}")

    # 自動組合出完整的輸出 PDF 路徑
    txt_name = Path(txt_path).stem  # 取得不含副檔名的主檔名
    output_pdf_path = os.path.join(OUTPUT_DIR, f"{txt_name}.pdf")

    try:
        test_jianpu_conversion(txt_path, output_pdf_path)
    except Exception as e:
        print(f"❌ 發生錯誤: {e}")