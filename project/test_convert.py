import argparse
import os
from tkinter import Tk, filedialog
from MIDI_to_notation import convert_midi_to_jianpu

def main():
    parser = argparse.ArgumentParser(description="測試 convert_midi_to_jianpu")
    parser.add_argument("--bpm", type=float, default=80, help="每分鐘拍數 (BPM)，預設=80")
    parser.add_argument("--numerator", type=int, default=4, help="拍號分子，預設=4")
    parser.add_argument("--denominator", type=int, default=4, help="拍號分母，預設=4")
    args = parser.parse_args()

    # 開檔案選擇視窗
    Tk().withdraw()
    midi_path = filedialog.askopenfilename(
        title="選擇 MIDI 檔案",
        filetypes=[("MIDI files", "*.mid *.midi")]
    )
    if not midi_path:
        print("❌ 未選取檔案。")
        return

    print(f"✅ 載入檔案：{os.path.basename(midi_path)}")
    print(f"▶ 開始轉檔: {midi_path}")
    print(f"  BPM={args.bpm}, 拍號={args.numerator}/{args.denominator}")

    result = convert_midi_to_jianpu(midi_path, args.bpm, args.numerator, args.denominator)

    text_output = result.get("text_output", "")
    pdf_path = result.get("pdf_path")

    print("\n===== Jianpu Output (前 500 字) =====")
    print(text_output[:500] + ("..." if len(text_output) > 500 else ""))

    if pdf_path and os.path.exists(pdf_path):
        print(f"\n✅ PDF 已輸出: {pdf_path}")
    else:
        print("\n⚠ 沒有產生 PDF。")

if __name__ == "__main__":
    main()
