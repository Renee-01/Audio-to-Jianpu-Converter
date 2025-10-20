import os
import sys
import webbrowser
import subprocess
from datetime import datetime
from dataclasses import dataclass
from tkinter import Tk, filedialog

import pretty_midi

# ===================== 參數 =====================
UNITS_PER_QUARTER = 16  # 四分音符 = 16 格（= 1 拍 = 16 格）
ALLOWED_UNITS = [64, 32, 16, 8, 4, 2, 1]  # 允許的時值格數
COMMON_UNITS  = [1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64]  # 常見音價，用來吸附誤差

# 同步你的安裝路徑
JIANPU_SCRIPT = r"C:\lilypond-2.24.4\jianpu-ly.py"
LILYPOND_EXE  = r"C:\lilypond-2.24.4\bin\lilypond.exe"

# 相鄰同音合併的間隔門檻（格），0 表示不合併；建議 0~2
MERGE_GAP_UNITS = 2

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
    """
    將時值（格）拆成 16/8/4/2/1 的序列。
    先用盡可能多的 16（四分音符），再用 8/4/2/1 補尾數。
    """
    out = []
    if units >= 16:
        n16 = units // 16
        out.extend([16] * n16)
        rem = units - 16 * n16
    else:
        rem = units

    for u in (8, 4, 2, 1):
        while rem >= u:
            out.append(u)
            rem -= u
        if rem == 0:
            break
    return out

def unit_to_prefix(u: int) -> str:
    if   u == 16: return ""
    elif u == 8:  return "q"
    elif u == 4:  return "s"
    elif u == 2:  return "d"
    elif u == 1:  return "h"
    else:         return ""

def tokens_from_units(symbol: str, units: int) -> str:
    """
    - 首段：16 -> '音符'；<16 -> '前綴+音符'（如 q4）
    - 續段：
        * 16  -> 獨立一個 '-'（用空白分隔）
        * 8/4/2/1 -> 獨立 '前綴-'（如 q- / s- / d- / h-）
    例：
      64 -> [16,16,16,16]   => '4 - - -'
      32 -> [16,16]         => '4 -'
      24 -> [16,8]          => '4 q-'
      40 -> [16,16,8]       => '4 - q-'
      17 -> [16,1]          => '4 h-'
      8  -> [8]             => 'q4'
    """
    chunks = decompose_units(units)
    if not chunks:
        return symbol

    tokens = []

    # 首段
    first = chunks[0]
    if first == 16:
        tokens.append(f"{symbol}")
    else:
        tokens.append(f"{unit_to_prefix(first)}{symbol}")

    # 續段：獨立 token
    for u in chunks[1:]:
        if u == 16:
            tokens.append("-")
        else:
            tokens.append(f"{unit_to_prefix(u)}-")

    return " ".join(tokens)

def make_rest_tokens_barwise(remain_units: int, denominator: int) -> list[str]:
    """
    以『大到小』補休止；優先用分母對應單位（但不超過四分=16格），
    再用 8、4、2、1 依序補，避免 32/64 這種休止單位造成視覺混亂。
    """
    units_per_note = int(UNITS_PER_QUARTER * (4 / denominator))
    base = min(UNITS_PER_QUARTER, units_per_note)

    order = [base, 8, 4, 2, 1]
    order = [u for u in order if u >= 1]

    tokens = []
    rem = remain_units

    for u in order:
        if rem <= 0:
            break
        count = rem // u
        if count > 0:
            pref = unit_to_prefix(u)
            tokens.extend([f"{pref}0"] * count)
            rem -= u * count

    for u in [1, 2, 4, 8]:
        while rem >= u:
            tokens.append(f"{unit_to_prefix(u)}0")
            rem -= u

    return tokens

# 開啟 PDF（具防呆）
def openPDF(pdf_path: str):
    if not pdf_path:
        print("⚠️ 沒有 PDF 路徑（可能編譯未產生 PDF）。")
        return
    if os.path.exists(pdf_path):
        webbrowser.open(pdf_path)
        print("✅ PDF 已開啟。")
    else:
        print("❌ 找不到 PDF 檔：", pdf_path)

def convert_midi_to_jianpu(midi_path: str, bpm: float, numerator: int, denominator: int) -> dict:
    # 換算
    beat_sec     = 60.0 / bpm
    sec_per_unit = beat_sec / UNITS_PER_QUARTER
    UNITS_PER_BAR = get_units_per_bar(numerator, denominator)
    print(f"✅ {numerator}/{denominator}：一小節 {UNITS_PER_BAR} 格；四分={UNITS_PER_QUARTER} 格；每格={sec_per_unit:.6f}s")

    # 讀 MIDI
    midi = pretty_midi.PrettyMIDI(midi_path)
    if not midi.instruments:
        print("❌ 這個 MIDI 沒有軌。")
        raise SystemExit
    notes = sorted(midi.instruments[0].notes, key=lambda n: (n.start, n.end))

    # === 方法2：量化到格線（先量化再計算格數） ===
    for n in notes:
        q_start = round(n.start / sec_per_unit) * sec_per_unit
        q_end   = round(n.end   / sec_per_unit) * sec_per_unit
        if q_end <= q_start:
            q_end = q_start + sec_per_unit  # 至少佔 1 格
        n.start, n.end = q_start, q_end

    # （可選）合併相鄰同音且間隔很小的音符，避免被誤切碎
    if MERGE_GAP_UNITS > 0:
        merged = []
        for n in notes:
            if merged:
                last = merged[-1]
                gap_units = (n.start - last.end) / sec_per_unit
                if n.pitch == last.pitch and gap_units >= 0 and gap_units <= MERGE_GAP_UNITS:
                    last.end = n.end
                    continue
            merged.append(n)
        notes = merged

    # 轉成 grid notes
    grid_notes = []
    for n in notes:
        symbol = midi_to_jianpu(n.pitch)
        su = sec_to_unit(n.start, sec_per_unit)
        real_units = (n.end - n.start) / sec_per_unit
        dur_u = snap_to_common_units(real_units, tol=4.0)  # 少許吸附
        eu = su + max(dur_u, 1)
        if eu <= su:
            continue
        grid_notes.append(GridNote(symbol, su, eu))

    # 切分跨小節、加 ~
    bars_tokens: dict[int, list[str]] = {}
    bars_used: dict[int, int] = {}

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

    # === 組裝每小節：所有小節都補休止、清除尾端 ~（避免 barcheck） ===
    max_bar = max(bars_tokens.keys()) if bars_tokens else -1
    per_bar_texts = []
    for b in range(0, max_bar + 1):
        tokens = bars_tokens.get(b, [])

        if tokens and tokens[-1].endswith(" ~"):
            tokens[-1] = tokens[-1][:-2].rstrip()

        used = bars_used.get(b, 0)
        remain = UNITS_PER_BAR - used
        if remain < 0:
            print(f"第 {b+1} 小節超過 {abs(remain)} 格（理論不該發生）")
        elif remain > 0:
            tokens += make_rest_tokens_barwise(remain, denominator)

        if tokens and tokens[-1].endswith("~"):
            tokens[-1] = tokens[-1].rstrip("~").rstrip()

        per_bar_texts.append(" ".join(tokens).strip())

    # 組好整段簡譜；只在結尾補一個 barline
    jianpu_text = " | ".join(per_bar_texts).strip()
    if jianpu_text and not jianpu_text.endswith("|"):
        jianpu_text += " |"

    # 以檔名當標題
    song_title = os.path.splitext(os.path.basename(midi_path))[0]

    # 依 jianpu-ly.py 範例加入檔頭
    header = (
        "% jianpu-ly.py 文檔\n"
        f"title={song_title}\n"
        f"{numerator}/{denominator}\n"
        "\n"
    )

    full_text = header + jianpu_text + "\n"

    # 儲存 txt（固定放在來源同層的 output/<timestamp>）
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    base_name = f"output_{timestamp}"
    output_dir = os.path.join(os.path.dirname(midi_path), "output", base_name)
    os.makedirs(output_dir, exist_ok=True)

    output_txt = os.path.join(output_dir, f"{base_name}.txt")
    with open(output_txt, "w", encoding="utf-8", newline="\n") as f:
        f.write(full_text)
    print(f"✅ 簡譜已儲存：{output_txt}")

    # 產生 .ly / .pdf
    output_ly  = os.path.join(output_dir, f"{base_name}.ly")
    output_pdf = os.path.join(output_dir, f"{base_name}.pdf")

    # 用同一支 Python 執行 jianpu-ly.py，保留 stderr 方便除錯
    with open(output_txt, "r", encoding="utf-8") as fin, open(output_ly, "w", encoding="utf-8") as fout:
        res = subprocess.run(
            [sys.executable, JIANPU_SCRIPT],
            stdin=fin, stdout=fout,
            stderr=subprocess.PIPE, text=True, check=False
        )
    if not os.path.exists(output_ly):
        err = (res.stderr or "").strip()
        print("未生成 .ly，請確認 jianpu-ly.py 是否可執行、路徑是否正確")
        if err:
            print("── jianpu-ly.py stderr ──")
            print(err)
        return {"text_output": full_text, "pdf_path": None}

    # 補上 \version
    try:
        with open(output_ly, "r", encoding="utf-8") as f:
            ly_src = f.read()
        if "\\version" not in ly_src:
            ly_src = '\\version "2.24.4"\n' + ly_src
            with open(output_ly, "w", encoding="utf-8") as f:
                f.write(ly_src)
    except Exception as e:
        print("處理 .ly 時發生例外：", e)

    # LilyPond → PDF
    res2 = subprocess.run(
    [LILYPOND_EXE, "-o", base_name, f"{base_name}.ly"],
    cwd=output_dir,
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,  # 收 bytes
    text=False, check=False,
    env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}  # 提示子行程用 UTF-8
    )

    if not os.path.exists(output_pdf):
        # 掃描目錄找實際輸出的 pdf 名稱
        for f in os.listdir(output_dir):
            if f.lower().endswith(".pdf"):
                output_pdf = os.path.join(output_dir, f)
                break

    if not os.path.exists(output_pdf):
        err2 = (res2.stderr or "").strip()
        if err2:
            print("LilyPond stderr：")
            print(err2)

    with open(output_txt, "r", encoding="utf-8") as f:
        text_output = f.read()

    return {"text_output": text_output, "pdf_path": output_pdf if os.path.exists(output_pdf) else None}

#________________main________________
def main():
    # 1) 選檔
    Tk().withdraw()
    midi_path = filedialog.askopenfilename(title="選擇 MIDI 檔案", filetypes=[("MIDI files", "*.mid *.midi")])
    if not midi_path:
        print("❌ 未選取檔案。")
        raise SystemExit
    print(f"✅ 載入檔案：{os.path.basename(midi_path)}")

    # 2) BPM / 拍號
    try:
        bpm = float(input("請輸入 BPM（預設 80）：") or 80)
    except ValueError:
        print("⚠️ 無效輸入，使用預設 BPM = 80")
        bpm = 80.0
    try:
        numerator = int(input("請輸入拍號分子 (預設=4)：") or 4)
        denominator = int(input("請輸入拍號分母 (預設=4)：") or 4)
    except ValueError:
        print("⚠️ 無效輸入，使用預設 4/4")
        numerator, denominator = 4, 4

    print(f"▶ 開始轉檔: {midi_path}")
    print(f"  BPM={bpm}, 拍號={numerator}/{denominator}")

    result = convert_midi_to_jianpu(midi_path, bpm, numerator, denominator)
    text_output = result.get("text_output", "")
    pdf_path = result.get("pdf_path")

    print("\n===== Jianpu Output (前 500 字) =====")
    print(text_output[:500] + ("..." if len(text_output) > 500 else ""))

    if pdf_path and os.path.exists(pdf_path):
        print(f"\n✅ PDF 已輸出: {pdf_path}")
        openPDF(pdf_path)
    else:
        print("\n⚠ 沒有產生 PDF。")
        openPDF(pdf_path)  # 這裡有防呆，不會噴錯

if __name__ == "__main__":
    main()
