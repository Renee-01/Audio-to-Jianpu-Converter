# MIDI_to_notation.py
"""
把 MIDI 檔轉成簡譜（jianpu-ly + LilyPond 排版）的工具函式。

Pipeline:
    MIDI
      └─(MuseScore)──> MusicXML (.mxl)
            └─(musicxml_to_jianpu)──> jianpu-ly 簡譜文字 (.txt)
                  └─(jianpu-ly)──> LilyPond 檔 (.ly)
                        └─(lilypond)──> PDF

主要提供兩個高階 API：
    - midi_to_jianpu_pdf_bytes(midi_path) -> bytes
    - midi_to_jianpu_text(midi_path) -> str

外部相依程式請先裝好：
    - MuseScore 4 CLI
    - Python 版 musicxml_to_jianpu（converter.py）
    - jianpu-ly（pip 安裝）
    - lilypond
"""

import os
import sys, shutil
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path
from tkinter import Tk, filedialog
from datetime import datetime


# ====== 這幾個路徑依你的環境調整一下 ======

# MuseScore CLI 執行檔
MUSESCORE_BIN = os.getenv(
    "MUSESCORE_BIN",
    r"C:\Program Files\MuseScore 4\bin\MuseScore4.exe",
)

# musicxml_to_jianpu 專案裡的 converter.py 路徑
MUSICXML_TO_JIANPU_CONVERTER = os.getenv(
    "MUSICXML_TO_JIANPU_CONVERTER",
    r"D:\Audio-to-Jianpu-Converter\musicxml_to_jianpu\converter.py",
)
 
# lilypond 指令名
LILYPOND_CMD = os.getenv("LILYPOND_CMD", r"C:\lilypond-2.24.4\bin\lilypond.exe")


# ====== 小工具：包一層 subprocess.run，順便丟出錯誤訊息 ======

def _jianpu_cmd():
    """
    取得可執行 jianpu-ly 的命令（list 形式）。
    優先序：
      1. 環境變數 JIANPU_LY_CMD（可填完整路徑或指令名）
      2. PATH 中的 'jianpu-ly'
      3. 目前 Python 的模組執行：python -m jianpu_ly
    """
    env_cmd = os.getenv("JIANPU_LY_CMD")
    if env_cmd:
        # 允許填「一整串命令」，也允許只有路徑
        # 若你想更嚴謹可用 shlex.split，這裡簡化處理
        return [env_cmd]

    which = shutil.which("jianpu-ly")
    if which:
        return [which]

    # 萬用保底：用當前解譯器跑模組
    return [sys.executable, "-m", "jianpu_ly"]

def _run(cmd, **kwargs):
    """
    執行外部指令，捕捉 stdout/stderr（用 bytes），失敗時丟 RuntimeError。
    不使用 text=True，避免 Windows cp950 解碼炸掉。
    """
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        # 不要加 text=True / encoding=...
        **kwargs,
    )

    if result.returncode != 0:
        # 安全解碼：先試 UTF-8，不行就 cp950，都用 errors="ignore"
        def _safe_decode(b):
            if b is None:
                return ""
            try:
                return b.decode("utf-8", errors="ignore")
            except Exception:
                return b.decode("cp950", errors="ignore")

        stdout_text = _safe_decode(result.stdout)
        stderr_text = _safe_decode(result.stderr)

        raise RuntimeError(
            f"Command failed: {' '.join(map(str, cmd))}\n"
            f"stdout:\n{stdout_text}\n\nstderr:\n{stderr_text}"
        )

    return result



# ====== 單一步驟的封裝 ======

def midi_to_musicxml(midi_path: str, xml_path: str) -> None:
    """用 MuseScore 把 MIDI 轉成 MusicXML (.mxl / .musicxml)"""
    _run([MUSESCORE_BIN, midi_path, "-o", xml_path])


def musicxml_to_jianpu_text(xml_path: str, txt_path: str) -> None:
    """
    用 musicxml_to_jianpu 把 MusicXML 轉成 jianpu-ly 語法的簡譜文字。
    """
    converter = MUSICXML_TO_JIANPU_CONVERTER
    cmd = ["python", converter, "--grammar", "jianpu-ly", xml_path]

    result = _run(cmd)  # stdout 是 bytes

    # 安全解碼成 str
    try:
        text = result.stdout.decode("utf-8")
    except Exception:
        text = result.stdout.decode("cp950", errors="ignore")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)


def jianpu_text_to_ly(txt_path: str, ly_path: str) -> None:
    """用 jianpu-ly 把簡譜文字轉成 LilyPond 檔。"""
    cmd = _jianpu_cmd() + [txt_path]  # ← 不再寫死路徑
    result = _run(cmd)                 # 你先前寫的 _run()（回傳 stdout bytes）
    try:
        ly_text = result.stdout.decode("utf-8")
    except Exception:
        ly_text = result.stdout.decode("cp950", errors="ignore")
    with open(ly_path, "w", encoding="utf-8") as f:
        f.write(ly_text)


def ly_to_pdf(ly_path: str, pdf_base: str) -> str:
    """
    用 LilyPond 把 .ly 轉成 PDF。
    pdf_base 不含副檔名，最後會回傳實際的 pdf 路徑。
    """
    cmd = [LILYPOND_CMD, "-o", pdf_base, ly_path]
    _run(cmd)
    pdf_path = pdf_base + ".pdf"
    if not os.path.exists(pdf_path):
        raise RuntimeError(f"LilyPond did not produce PDF at {pdf_path}")
    return pdf_path


# ====== 對外主要 API ======

def midi_to_jianpu_text(midi_path: str) -> str:
    """
    輸入 MIDI 檔路徑，回傳 jianpu-ly 簡譜文字（方便你丟到 HTML / 其他系統用）。

    這個函式只做到 MusicXML -> 簡譜文字，不會產生 PDF。
    """
    midi_path = str(midi_path)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        xml_path = tmpdir / "score.mxl"
        txt_path = tmpdir / "score.txt"

        # 1) MIDI -> MusicXML
        midi_to_musicxml(midi_path, str(xml_path))

        # 2) MusicXML -> jianpu-ly 文字
        musicxml_to_jianpu_text(str(xml_path), str(txt_path))

        # 讀出文字結果
        return txt_path.read_text(encoding="utf-8")


def midi_to_jianpu_pdf_bytes(midi_path: str) -> bytes:
    """
    輸入 MIDI 檔路徑，回傳簡譜 PDF 的 bytes。
    可以直接給 Flask 的 send_file(BytesIO(...)) 使用。
    """
    midi_path = str(midi_path)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        xml_path = tmpdir / "score.mxl"
        txt_path = tmpdir / "score.txt"
        ly_path = tmpdir / "score.ly"
        pdf_base = tmpdir / "score"

        # 1) MIDI -> MusicXML
        midi_to_musicxml(midi_path, str(xml_path))

        # 2) MusicXML -> jianpu-ly 文字
        musicxml_to_jianpu_text(str(xml_path), str(txt_path))

        # 3) 簡譜文字 -> .ly
        jianpu_text_to_ly(str(txt_path), str(ly_path))

        # 4) .ly -> PDF
        pdf_path = ly_to_pdf(str(ly_path), str(pdf_base))

        # 讀回 bytes
        return Path(pdf_path).read_bytes()
    
def convert_midi_to_jianpu(midi_path: str) -> dict:
    """
    給 Flask app 用的高階函式：

        - 輸入: MIDI 檔路徑
        - 動作:
            1) 呼叫 midi_to_jianpu_text() 取得簡譜文字
            2) 呼叫 midi_to_jianpu_pdf_bytes() 產生 PDF bytes
            3) 在 MIDI 檔所在目錄底下建立 output_YYYY-MM-DD_HHMM 資料夾
            4) 將 PDF 寫成 <原檔名>.jianpu.pdf
            5) （可選）也把簡譜文字存成 .jianpu.txt 方便 debug
        - 回傳:
            {
              "text_output": <簡譜文字字串>,
              "pdf_path":    <PDF 絕對路徑字串>
            }
    """
    midi_path = Path(midi_path).resolve()

    # 1) 先取得簡譜文字
    text_output = midi_to_jianpu_text(str(midi_path))

    # 2) 產生 PDF bytes
    pdf_bytes = midi_to_jianpu_pdf_bytes(str(midi_path))

    # 3) 在 MIDI 同一層建立 output_YYYY-MM-DD_HHMM 資料夾
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    out_dir = midi_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # 4) PDF 檔名：<原檔名>.jianpu.pdf
    pdf_path = out_dir / f"{midi_path.stem}.jianpu.pdf"
    pdf_path.write_bytes(pdf_bytes)

    # 5) （可選）把簡譜文字存成 .txt 一份，方便你 debug / 查看
    txt_path = out_dir / f"{midi_path.stem}.jianpu.txt"
    try:
        txt_path.write_text(text_output, encoding="utf-8")
    except Exception:
        pass

    return {
        "text_output": text_output,
        "pdf_path": str(pdf_path),
    }



# ====== 簡單 CLI，用來單機測試 ======
if __name__ == "__main__":
    

    root = Tk()
    root.withdraw()
    midi_path = filedialog.askopenfilename(
        title="選擇 MIDI 檔案",
        filetypes=[("MIDI files", "*.mid *.midi")]
    )
    root.destroy()

    if not midi_path:
        print("❌ 未選取檔案。")
        raise SystemExit

    print(f"✅ 載入檔案：{os.path.basename(midi_path)}")

    pdf_bytes = midi_to_jianpu_pdf_bytes(midi_path)

    midi_path = Path(midi_path)

    # 建立 output_YYYY-MM-DD_HHMM 資料夾（在 MIDI 同一層）
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    out_dir = midi_path.parent / f"output\output_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # PDF 檔名用 原 MIDI 檔名 + .jianpu.pdf
    out_path = out_dir / (midi_path.stem + ".jianpu.pdf")
    out_path.write_bytes(pdf_bytes)

    print(f"🎼 已輸出: {out_path}")


