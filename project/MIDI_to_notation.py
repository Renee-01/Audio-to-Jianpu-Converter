import os
import pretty_midi
from tkinter import Tk, filedialog
from dataclasses import dataclass
import subprocess
from datetime import datetime
import webbrowser
import argparse

def convert_midi_to_jianpu(midi_path: str,bpm: float ,numerator: int ,denominator: int ) -> str:
    # ===================== 參數 =====================
    UNITS_PER_QUARTER = 16  # 四分音符 = 16 格（= 1 拍 = 16 格）
    ALLOWED_UNITS = [64, 32, 16, 8, 4, 2, 1]  # 允許的時值格數
    COMMON_UNITS  = [1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64]  # 常見音價，用來吸附誤差

    JIANPU_SCRIPT = r"C:\lilypond-2.24.4\jianpu-ly.py"
    LILYPOND_EXE  = r"C:\lilypond-2.24.4\bin\lilypond.exe"
    
    # ===================== 資料結構 =====================
    @dataclass
    class GridNote:
        symbol: str
        start_u: int
        end_u: int
    # ===================== 工具函式 =====================
    def midi_to_jianpu(pitch: int) -> str:
        scale_map = {
            0: '1', 1: '#1', 2: '2', 3: '#2', 4: '3',
            5: '4', 6: '#4', 7: '5', 8: '#5', 9: '6', 10: '#6', 11: '7'
        }
        octave = pitch // 12 - 1
        note_in_octave = pitch % 12
        base = scale_map.get(note_in_octave, '?')
        if octave == 4: return base
        elif octave == 5: return base + '\''
        elif octave == 3: return base + ','
        elif octave > 5: return base + '\'' * (octave - 4)
        elif octave < 3: return base + ',' * (4 - octave)
        else: return base

    def get_units_per_bar(numerator: int, denominator: int) -> int:
        """以四分=16格為基準，計算一小節的格數"""
        quarter_equiv = 4 / denominator
        units_per_note = UNITS_PER_QUARTER * quarter_equiv
        return int(numerator * units_per_note)
    
    def sec_to_unit(t_sec: float, sec_per_unit: float) -> int:
        return int(round(t_sec / sec_per_unit))
    
    def snap_to_common_units(real_units: float, tol: float = 4.0) -> int:
        nearest = min(COMMON_UNITS, key=lambda u: abs(real_units - u))
        if abs(real_units - nearest) <= tol:
            return int(nearest)
        return int(round(real_units))
    
    def split_across_bars(start_u: int, end_u: int, units_per_bar: int):
        parts = []
        pos = start_u
        while pos < end_u:
            bar_end = ((pos // units_per_bar) + 1) * units_per_bar
            piece_end = min(bar_end, end_u)
            parts.append((pos, piece_end))
            pos = piece_end
        return parts
    
    def decompose_units(units: int):
        out, rem = [], units
        for u in ALLOWED_UNITS:
            while rem >= u:
                out.append(u); rem -= u
            if rem == 0: break
        return out
    
    def decompose_units_small_first(units: int):
        out, rem = [], units
        for u in reversed(ALLOWED_UNITS):  # 1,2,4,8,16,32,64
            while rem >= u:
                out.append(u); rem -= u
            if rem == 0: break
        return out

    def unit_to_prefix(u: int) -> str:
        if   u == 16: return ""
        elif u == 8:  return "q"
        elif u == 4:  return "s"
        elif u == 2:  return "d"
        elif u == 1:  return "h"
        else:         return ""

    def tokens_from_units(symbol: str, units: int) -> str:
        chunks = decompose_units(units)
        return " ~ ".join(f"{unit_to_prefix(u)}{symbol}" for u in chunks)
    
    def make_rest_tokens_barwise(remain_units: int, denominator: int) -> list[str]:
        """
        以『大到小』補休止；優先用分母對應單位（但不超過四分=16格），
        再用 8、4、2、1 依序補。避免 32/64 這種休止單位造成視覺混亂。
        例如：
        4/4：先 16，再 8/4/2/1  → 會得到 0 0 0 這種清楚的四分休止
        6/8：先 8，再 4/2/1      → q0 q0 q0...
        """
        # 分母對應的單位（用四分=16格為基準）
        units_per_note = int(UNITS_PER_QUARTER * (4 / denominator))
        # 為了視覺清楚，不讓 32/64 變成單一休止：把最大休止單位限制在 16
        base = min(UNITS_PER_QUARTER, units_per_note)  # 例如 3/2 → 32 也會被視為 16+16

        order = [base, 8, 4, 2, 1]           # 大到小
        order = [u for u in order if u >= 1] # 保險過濾

        tokens = []
        rem = remain_units

        # 先用大單位盡量填滿
        for u in order:
            if rem <= 0:
                break
            count = rem // u
            if count > 0:
                pref = unit_to_prefix(u)
                tokens.extend([f"{pref}0"] * count)
                rem -= u * count

        # 若仍有極小尾數，改用小到大補完（通常不會進來）
        for u in [1, 2, 4, 8]:
            while rem >= u:
                tokens.append(f"{unit_to_prefix(u)}0")
                rem -= u

        return tokens
    # ===================== main =====================
    # 3) 換算
    beat_sec     = 60.0 / bpm
    sec_per_unit = beat_sec / UNITS_PER_QUARTER
    UNITS_PER_BAR = get_units_per_bar(numerator, denominator)
    print(f"✅ {numerator}/{denominator}：一小節 {UNITS_PER_BAR} 格；四分={UNITS_PER_QUARTER} 格；每格={sec_per_unit:.6f}s")

    # 4) 讀 MIDI → grid notes
    midi = pretty_midi.PrettyMIDI(midi_path)
    if not midi.instruments:
        print("❌ 這個 MIDI 沒有軌。")
        raise SystemExit
    notes = sorted(midi.instruments[0].notes, key=lambda n: (n.start, n.end))

    grid_notes = []
    for n in notes:
        symbol = midi_to_jianpu(n.pitch)
        su = sec_to_unit(n.start, sec_per_unit)
        real_units = (n.end - n.start) / sec_per_unit
        dur_u = snap_to_common_units(real_units, tol=2.0)
        eu = su + max(dur_u, 1)
        if eu <= su:
            continue
        grid_notes.append(GridNote(symbol, su, eu))

    # 5) 切分跨小節、加 ~
    bars_tokens = {}
    bars_used   = {}

    for note in grid_notes:
        slices = split_across_bars(note.start_u, note.end_u, UNITS_PER_BAR)
        for i, (s, e) in enumerate(slices):
            dur = e - s
            if dur <= 0:
                continue
            token_str = tokens_from_units(note.symbol, dur)
            bar_idx = s // UNITS_PER_BAR
            tie_to_next = (i < len(slices) - 1)
            if tie_to_next:
                token_str = token_str + " ~"
            bars_tokens.setdefault(bar_idx, []).append(token_str)
            bars_used[bar_idx] = bars_used.get(bar_idx, 0) + dur

    # 6) 組裝每小節，只補最後一小節休止
    max_bar = max(bars_tokens.keys())
    per_bar_texts = []
    for b in range(0, max_bar + 1):
        tokens = bars_tokens.get(b, [])
        if b == max_bar:  # 只補最後一小節
            used = bars_used.get(b, 0)
            remain = UNITS_PER_BAR - used
            if remain > 0:
                # 以分母對應單位優先，『大到小』補休止（避免碎）
                tokens += make_rest_tokens_barwise(remain, denominator)

        per_bar_texts.append(" ".join(tokens).strip())

    jianpu_text = " | ".join(per_bar_texts) + " |"

    # 7) 儲存 txt
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    base_name = f"output_{timestamp}"
    output_dir = os.path.join(os.path.dirname(midi_path), "output", base_name)
    os.makedirs(output_dir, exist_ok=True)

    output_txt = os.path.join(output_dir, f"{base_name}.txt")
    with open(output_txt, "w", encoding="utf-8") as f:
        f.write(jianpu_text + "\n")
    print(f"✅ 簡譜已儲存：{output_txt}")

    # 8) 產生 .ly
    output_ly  = os.path.join(output_dir, f"{base_name}.ly")
    output_pdf = os.path.join(output_dir, f"{base_name}.pdf")

    with open(output_txt, "r", encoding="utf-8") as fin, open(output_ly, "w", encoding="utf-8") as fout:
        subprocess.run(["python", JIANPU_SCRIPT], stdin=fin, stdout=fout, check=False)

    # 補上 \version
    try:
        with open(output_ly, "r", encoding="utf-8") as f:
            ly_src = f.read()
        if "\\version" not in ly_src:
            ly_src = '\\version "2.24.4"\n' + ly_src
            with open(output_ly, "w", encoding="utf-8") as f:
                f.write(ly_src)
    except Exception as e:
        print("⚠️ 處理 .ly 時發生例外：", e)

    # 9) LilyPond → PDF
    subprocess.run([LILYPOND_EXE, "-o", base_name, f"{base_name}.ly"], cwd=output_dir, check=False)

    if not os.path.exists(output_pdf):
        for f in os.listdir(output_dir):
            if f.lower().endswith(".pdf"):
                output_pdf = os.path.join(output_dir, f)
                break

    
    with open(output_txt, "r", encoding="utf-8") as f:
        text_output = f.read()
    
    return {
        "text_output": text_output,
        "pdf_path": output_pdf if os.path.exists(output_pdf) else None
    }

# 開啟 PDF
def openPDF(pdf_path: str):

    if os.path.exists(pdf_path):
        webbrowser.open(pdf_path)
        print("✅ PDF 已開啟。")
    else:
        print("❌ PDF 產出失敗。檔案夾：", pdf_path)


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

    openPDF(pdf_path)

if __name__ == "__main__":
    main()