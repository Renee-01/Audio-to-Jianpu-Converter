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
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path


# ====== 這幾個路徑依你的環境調整一下 ======

# MuseScore CLI 執行檔
MUSESCORE_BIN = os.getenv(
    "MUSESCORE_BIN",
    r"C:\Program Files\MuseScore 4\bin\MuseScore4.exe",
)

# musicxml_to_jianpu 專案裡的 converter.py 路徑
MUSICXML_TO_JIANPU_CONVERTER = os.getenv(
    "MUSICXML_TO_JIANPU_CONVERTER",
    r"D:\tools\musicxml_to_jianpu\converter.py",
)

# jianpu-ly 指令（如果在 venv 裡有裝，通常就叫 jianpu-ly）
JIANPU_LY_CMD = os.getenv("JIANPU_LY_CMD", "jianpu-ly")

# lilypond 指令名
LILYPOND_CMD = os.getenv("LILYPOND_CMD", "lilypond")


# ====== 小工具：包一層 subprocess.run，順便丟出錯誤訊息 ======

def _run(cmd, **kwargs):
    """執行外部指令，失敗時丟 RuntimeError，方便 debug。"""
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        **kwargs,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(map(str, cmd))}\n"
            f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
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
    with open(txt_path, "w", encoding="utf-8") as f:
        result = _run(cmd)
        f.write(result.stdout)


def jianpu_text_to_ly(txt_path: str, ly_path: str) -> None:
    """用 jianpu-ly 把簡譜文字轉成 LilyPond 檔。"""
    cmd = [JIANPU_LY_CMD, txt_path]
    result = _run(cmd)
    with open(ly_path, "w", encoding="utf-8") as f:
        f.write(result.stdout)


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


# ====== 簡單 CLI，用來單機測試 ======
if __name__ == "__main__":
    import sys
    from tkinter import Tk, filedialog

    # 如果有給參數：python MIDI_to_notation.py foo.mid
    if len(sys.argv) > 1:
        midi_path = sys.argv[1]
    else:
        # 1) 用對話框選檔
        root = Tk()
        root.withdraw()  # 不要顯示主視窗
        midi_path = filedialog.askopenfilename(
            title="選擇 MIDI 檔案",
            filetypes=[("MIDI files", "*.mid *.midi")]
        )
        root.destroy()

    if not midi_path:
        print("❌ 未選取檔案。")
        raise SystemExit

    print(f"✅ 載入檔案：{os.path.basename(midi_path)}")

    # 2) 產生簡譜 PDF
    pdf_bytes = midi_to_jianpu_pdf_bytes(midi_path)

    # 輸出在「同一個資料夾」，檔名改成 .jianpu.pdf
    out_path = Path(midi_path).with_suffix(".jianpu.pdf")
    out_path.write_bytes(pdf_bytes)

    print(f"🎼 已輸出: {out_path}")

