import os
import subprocess
from pathlib import Path
from tkinter import Tk, filedialog

# === 自訂路徑 ===
JIANPU_SCRIPT = r"C:\lilypond-2.24.4\jianpu-ly.py"
LILYPOND_EXE  = r"C:\lilypond-2.24.4\bin\lilypond.exe"

def test_jianpu_conversion(txt_path: str):
    txt_path = Path(txt_path)
    if not txt_path.exists():
        raise FileNotFoundError(f"找不到檔案: {txt_path}")

    base_dir = txt_path.parent
    ly_path = base_dir / "jianpu.ly"

    # Step 1️⃣ 呼叫 jianpu-ly.py 產生 jianpu.ly
    print("➡ 產生 jianpu.ly 中...")
    subprocess.run(
        ["python", JIANPU_SCRIPT, str(txt_path)],
        cwd=base_dir,
        check=True
    )
    if not ly_path.exists():
        raise FileNotFoundError("未生成 jianpu.ly，請檢查 jianpu-ly.py 是否正確運作")

    print(f"✅ 已生成 {ly_path}")

    # Step 2️⃣ 用 LilyPond 生成 PDF
    print("➡ 轉成 PDF 中...")
    subprocess.run(
        [LILYPOND_EXE, str(ly_path)],
        cwd=base_dir,
        check=True
    )

    pdf_path = ly_path.with_suffix(".pdf")
    if pdf_path.exists():
        print(f"🎵 PDF 輸出成功：{pdf_path}")
    else:
        print("⚠ 未找到輸出 PDF，請檢查 lilypond 設定。")

# === 測試 ===
if __name__ == "__main__":
    # 1) 選檔
    Tk().withdraw()
    txt_path = filedialog.askopenfilename(title="選擇 MIDI 檔案", filetypes=[("text檔", "*.txt")])
    if not txt_path:
        print("❌ 未選取檔案。")
        raise SystemExit
    print(f"✅ 載入檔案：{os.path.basename(txt_path)}")

    test_jianpu_conversion(txt_path)
