import os
import sys
import webbrowser
import subprocess
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict

from typing import List, Tuple, Dict, Set
from tkinter import Tk, filedialog

import pretty_midi

"""
MIDI_to_notation.py（重寫版，單旋律）

目標：
- 以樂理與拍號為核心，產生符合 jianpu-ly.py 的簡譜 txt 內容
- 保證每小節拍數不超過拍號（必要時跨小節自動加入 tie "~"）
- 僅處理單旋律（monophonic）。若軌上有重疊音，視作換音並切斷前音。
- 休止符以 "0" 表示，時值同音符規則（q/s/d/h 前綴）。
- 只在「最後一小節」補齊休止（可調）。
- 自動呼叫 jianpu-ly.py 產生 .ly 與 LilyPond 輸出 .pdf

主要輸出格式：
% jianpu-ly.py 文檔\n
 title=歌名\n
 4/4\n
 \n
 <bar1> | <bar2> | ... |

注意：
- 本腳本不處理 Key（1=D 等），仍可由輸出 txt 之後人工加在標頭；或在此開啟 INPUT_KEY_SIGNATURE 以加入。
"""

# ===================== 可調參數 =====================
UNITS_PER_QUARTER = 16  # 四分音符=16 格（內部時間單位）
COMMON_UNITS = [1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64]

# 產生 .ly / .pdf 的外部工具路徑（請依你的安裝調整）
JIANPU_SCRIPT = r"C:\\lilypond-2.24.4\\jianpu-ly.py"
LILYPOND_EXE  = r"C:\\lilypond-2.24.4\\bin\\lilypond.exe"

# 相鄰同音的微小縫隙（單位：格）小於等於此值則合併（0 表示不合併）
MERGE_GAP_UNITS = 2

# 只在最後一小節補齊休止
FILL_LAST_BAR_ONLY = True

# 續段也顯示音高（True：q1 q1 ...；False：續段以 q- / s- / - 表示）
SHOW_PITCH_ON_CONTINUATIONS = True

# 若需要在標頭加入調號（1=D 等），設 True 並提供 INPUT_KEY_SIGNATURE 內容
ENABLE_KEY_SIGNATURE = False
INPUT_KEY_SIGNATURE = "1=C"  # 僅在 ENABLE_KEY_SIGNATURE=True 時會輸出

# 子行程採用 UTF-8，避免 Windows 亂碼
ENV_UTF8 = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}

# ===================== 資料結構 =====================
@dataclass
class GridNote:
    symbol: str
    start_u: int  # 起點（格）
    end_u: int    # 終點（格，非含）

# ===================== 基本工具 =====================
def _decode_bytes(b: bytes) -> str:
    for enc in ("utf-8", "cp950", "latin-1"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", errors="replace")


def midi_to_jianpu(pitch: int) -> str:
    """MIDI pitch -> 簡譜音高（含升降記號與八度記號）。
    依 movable-do：0->1, 2->2, 4->3, 5->4, 7->5, 9->6, 11->7；其他以 # 標示升號。
    八度記號：4=原音高；5= '；3= ,；更高/低以連續 ' 或 ,。
    """
    scale_map = {
        0: '1', 1: '#1', 2: '2', 3: '#2', 4: '3',
        5: '4', 6: '#4', 7: '5', 8: '#5', 9: '6', 10: '#6', 11: '7'
    }
    octave = pitch // 12 - 1
    note_in_octave = pitch % 12
    base = scale_map.get(note_in_octave, '?')
    if octave == 4:
        return base
    elif octave == 5:
        return base + "'"
    elif octave == 3:
        return base + ","
    elif octave > 5:
        return base + "'" * (octave - 4)
    elif octave < 3:
        return base + "," * (4 - octave)
    else:
        return base


def get_units_per_bar(numerator: int, denominator: int) -> int:
    quarter_equiv = 4 / denominator
    units_per_note = UNITS_PER_QUARTER * quarter_equiv
    return int(numerator * units_per_note)


def sec_to_unit(t_sec: float, sec_per_unit: float) -> int:
    return int(round(t_sec / sec_per_unit))


def snap_to_common_units(real_units: float, tol: float = 4.0) -> int:
    """將實際格數貼近常用時值表；允許 tol 內視為同值。"""
    nearest = min(COMMON_UNITS, key=lambda u: abs(real_units - u))
    if abs(real_units - nearest) <= tol:
        return int(nearest)
    return int(round(real_units))


def split_across_bars(start_u: int, end_u: int, units_per_bar: int) -> List[Tuple[int, int]]:
    """將一顆音拆成不跨越小節的多段（每段 [s, e) 均在同一小節內）。"""
    parts: List[Tuple[int, int]] = []
    pos = start_u
    while pos < end_u:
        bar_end = ((pos // units_per_bar) + 1) * units_per_bar
        piece_end = min(bar_end, end_u)
        parts.append((pos, piece_end))
        pos = piece_end
    return parts


def decompose_units(units: int) -> List[int]:
    """將任意格數拆解為 16/8/4/2/1 的串列，盡量以 16 優先（=四分音符）。"""
    out: List[int] = []
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
    """將某音的持續格數轉成對應的 q/s/d/h 前綴組合。
    SHOW_PITCH_ON_CONTINUATIONS=True：每段都帶音高（q1 s1 ...）。
    False：首段帶音高，續段以 q-/s-/h-/ - 表示。
    """
    chunks = decompose_units(units)
    if not chunks:
        return symbol

    if SHOW_PITCH_ON_CONTINUATIONS:
        tokens: List[str] = []
        for u in chunks:
            if u == 16:
                tokens.append(f"{symbol}")
            else:
                tokens.append(f"{unit_to_prefix(u)}{symbol}")
        return " ".join(tokens)

    # 舊式：續段用延音符號
    tokens: List[str] = []
    first = chunks[0]
    if first == 16:
        tokens.append(f"{symbol}")
    else:
        tokens.append(f"{unit_to_prefix(first)}{symbol}")
    for u in chunks[1:]:
        if u == 16:
            tokens.append("-")
        else:
            tokens.append(f"{unit_to_prefix(u)}-")
    return " ".join(tokens)


def make_rest_tokens_barwise(remain_units: int, denominator: int) -> List[str]:
    """補齊小節剩餘格數的休止（0）。優先使用分母對應單位，至多四分（=16）。"""
    units_per_note = int(UNITS_PER_QUARTER * (4 / denominator))
    base = min(UNITS_PER_QUARTER, units_per_note)
    order = [u for u in [base, 8, 4, 2, 1] if u >= 1]

    tokens: List[str] = []
    rem = remain_units
    for u in order:
        if rem <= 0:
            break
        count = rem // u
        if count > 0:
            pref = unit_to_prefix(u)
            tokens.extend([f"{pref}0"] * count)
            rem -= u * count
    # 收尾防呆
    for u in [1, 2, 4, 8]:
        while rem >= u:
            tokens.append(f"{unit_to_prefix(u)}0")
            rem -= u
    return tokens


# ===================== 核心流程 =====================
def convert_midi_to_jianpu(midi_path: str, bpm: float, numerator: int, denominator: int) -> Dict[str, str]:
    """將單旋律 MIDI 轉 jianpu-ly 的 txt 內容，並嘗試產生 .ly/.pdf。"""
    beat_sec = 60.0 / bpm
    sec_per_unit = beat_sec / UNITS_PER_QUARTER
    UNITS_PER_BAR = get_units_per_bar(numerator, denominator)
    print(f"✅ {numerator}/{denominator}：一小節 {UNITS_PER_BAR} 格；四分={UNITS_PER_QUARTER} 格；每格={sec_per_unit:.6f}s")

    midi = pretty_midi.PrettyMIDI(midi_path)
    if not midi.instruments:
        raise RuntimeError("此 MIDI 不含任何樂器軌。")

    # 取第一條非打擊樂器的軌；若全部為打擊，仍取第 0 軌
    inst = next((ins for ins in midi.instruments if not ins.is_drum and ins.notes), midi.instruments[0])
    notes = sorted(inst.notes, key=lambda n: (n.start, n.end))
    if not notes:
        raise RuntimeError("選取的軌沒有任何音符。")

    # ① 量化到格線（四捨五入）
    for n in notes:
        q_start = round(n.start / sec_per_unit) * sec_per_unit
        q_end   = round(n.end   / sec_per_unit) * sec_per_unit
        if q_end <= q_start:
            q_end = q_start + sec_per_unit  # 至少 1 格
        n.start, n.end = q_start, q_end

    # ② 合併相鄰同音（小縫 <= MERGE_GAP_UNITS）
    if MERGE_GAP_UNITS > 0:
        merged: List[pretty_midi.Note] = []
        for n in notes:
            if merged:
                last = merged[-1]
                gap_units = (n.start - last.end) / sec_per_unit
                if n.pitch == last.pitch and 0 <= gap_units <= MERGE_GAP_UNITS:
                    last.end = n.end
                    continue
            merged.append(n)
        notes = merged

    # ③ 單聲化：移除重疊，遇到新音於前音期間出現時，截斷前音到新音開始
    mono: List[pretty_midi.Note] = []
    cur = None
    for n in notes:
        if cur is None:
            cur = pretty_midi.Note(start=n.start, end=n.end, pitch=n.pitch, velocity=getattr(n, "velocity", 100))
            continue
        if n.start >= cur.end:
            mono.append(cur)
            cur = pretty_midi.Note(start=n.start, end=n.end, pitch=n.pitch, velocity=getattr(n, "velocity", 100))
        else:
            # 有重疊：把目前音切到新音開始
            if n.start > cur.start:
                cur.end = n.start
                if cur.end > cur.start:
                    mono.append(cur)
            cur = pretty_midi.Note(start=n.start, end=n.end, pitch=n.pitch, velocity=getattr(n, "velocity", 100))
    if cur is not None and cur.end > cur.start:
        mono.append(cur)
    notes = mono

    # ④ 轉換為 grid notes（以格為單位）
    grid_notes: List[GridNote] = []
    for n in notes:
        symbol = midi_to_jianpu(n.pitch)
        su = sec_to_unit(n.start, sec_per_unit)
        real_units = (n.end - n.start) / sec_per_unit
        dur_u = snap_to_common_units(real_units, tol=4.0)
        dur_u = max(1, dur_u)
        eu = su + dur_u
        if eu <= su:
            continue
        grid_notes.append(GridNote(symbol, su, eu))

    # ⑤ 小節內切分、加 tie，並記錄小節覆蓋格數以便補休止
    bars_tokens: Dict[int, List[str]] = {}
    bars_cover: Dict[int, Set[int]] = defaultdict(set)

    for note in grid_notes:
        slices = split_across_bars(note.start_u, note.end_u, UNITS_PER_BAR)
        for i, (s, e) in enumerate(slices):
            dur = e - s
            if dur <= 0:
                continue
            token_str = tokens_from_units(note.symbol, dur)
            bar_idx = s // UNITS_PER_BAR
            if i < len(slices) - 1:
                token_str = token_str + " ~"  # 跨小節：加 tie
            bars_tokens.setdefault(bar_idx, []).append(token_str)

            # 記錄覆蓋格（僅作為檢查與補休止依據）
            local_s = s % UNITS_PER_BAR
            for u in range(local_s, local_s + dur):
                bars_cover[bar_idx].add(u)

    # ⑥ 組裝每小節：僅最後一小節補休止（可調），清掉尾端多餘 "~"
    max_bar = max(bars_tokens.keys()) if bars_tokens else -1
    per_bar_texts: List[str] = []
    for b in range(0, max_bar + 1):
        tokens = bars_tokens.get(b, []).copy()

        # 移除末尾孤立的 tie
        if tokens and tokens[-1].endswith(" ~"):
            tokens[-1] = tokens[-1][:-2].rstrip()

        used = len(bars_cover.get(b, set()))
        remain = UNITS_PER_BAR - used

        if remain < 0:
            print(f"⚠️ 第 {b+1} 小節覆蓋超過 {abs(remain)} 格（請檢查量化/單聲化）")
        elif remain > 0 and (b == max_bar if FILL_LAST_BAR_ONLY else True):
            tokens += make_rest_tokens_barwise(remain, denominator)

        # 再次清理末尾 tie
        if tokens and tokens[-1].endswith("~"):
            tokens[-1] = tokens[-1].rstrip("~").rstrip()

        per_bar_texts.append(" ".join(tokens).strip())

    # ⑦ 組裝文本（標頭 + 各小節）
    song_title = os.path.splitext(os.path.basename(midi_path))[0]
    header_lines = [
        "% jianpu-ly.py 文檔",
        f"title={song_title}",
        f"{numerator}/{denominator}",
    ]
    if ENABLE_KEY_SIGNATURE:
        header_lines.insert(2, INPUT_KEY_SIGNATURE)

    header = "\n".join(header_lines) + "\n\n"
    jianpu_body = " | ".join(per_bar_texts).strip()
    if jianpu_body and not jianpu_body.endswith("|"):
        jianpu_body += " |"

    full_text = header + jianpu_body + "\n"

    # ⑧ 輸出檔案
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    base_name = f"output_{timestamp}"
    output_dir = os.path.join(os.path.dirname(midi_path), "output", base_name)
    os.makedirs(output_dir, exist_ok=True)

    output_txt = os.path.join(output_dir, f"{base_name}.txt")
    with open(output_txt, "w", encoding="utf-8", newline="\n") as f:
        f.write(full_text)
    print(f"✅ 簡譜已儲存：{output_txt}")

    # ⑨ 呼叫 jianpu-ly.py → 產生 .ly
    output_ly  = os.path.join(output_dir, f"{base_name}.ly")
    output_pdf = os.path.join(output_dir, f"{base_name}.pdf")

    try:
        with open(output_txt, "r", encoding="utf-8") as fin, open(output_ly, "w", encoding="utf-8") as fout:
            res = subprocess.run(
                [sys.executable, JIANPU_SCRIPT],
                stdin=fin, stdout=fout,
                stderr=subprocess.PIPE, text=False, check=False, env=ENV_UTF8
            )
        if not os.path.exists(output_ly):
            err = _decode_bytes(res.stderr).strip()
            print("❌ 未生成 .ly，請確認 jianpu-ly.py 路徑與權限。")
            if err:
                print("── jianpu-ly.py stderr ──\n" + err)
            return {"text_output": full_text, "pdf_path": None}

        # 若缺 \version，補上以利 LilyPond 編譯
        try:
            with open(output_ly, "r", encoding="utf-8") as f:
                ly_src = f.read()
            if "\\version" not in ly_src:
                ly_src = '\\version "2.24.4"\n' + ly_src
                with open(output_ly, "w", encoding="utf-8") as f:
                    f.write(ly_src)
        except Exception as e:
            print("⚠️ 處理 .ly 時發生例外：", e)

    except FileNotFoundError:
        print("⚠️ 找不到 jianpu-ly.py，略過 .ly 產生步驟。")
        return {"text_output": full_text, "pdf_path": None}

    # ⑩ LilyPond → PDF
    try:
        res2 = subprocess.run(
            [LILYPOND_EXE, "-o", base_name, f"{base_name}.ly"],
            cwd=output_dir,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=False, check=False, env=ENV_UTF8
        )
    except FileNotFoundError:
        print("⚠️ 找不到 lilypond.exe，無法編譯 PDF。")
        res2 = None

    if not os.path.exists(output_pdf):
        # 有些版本輸出名可能不同，嘗試尋找資料夾內任何 pdf
        for f in os.listdir(output_dir):
            if f.lower().endswith(".pdf"):
                output_pdf = os.path.join(output_dir, f)
                break

    if not os.path.exists(output_pdf) and res2 is not None:
        err2 = _decode_bytes(res2.stderr).strip()
        if err2:
            print("⚠ LilyPond stderr：\n" + err2)

    return {"text_output": full_text, "pdf_path": output_pdf if os.path.exists(output_pdf) else None}


# ===================== 互動主程式 =====================
def openPDF(pdf_path: str):
    if not pdf_path:
        print("⚠️ 沒有 PDF 路徑（可能未產生）。")
        return
    if os.path.exists(pdf_path):
        webbrowser.open(pdf_path)
        print("✅ PDF 已開啟。")
    else:
        print("❌ 找不到 PDF：", pdf_path)


def main():
    # 以 GUI 開檔，然後互動輸入 BPM 與拍號
    Tk().withdraw()
    midi_path = filedialog.askopenfilename(
        title="選擇 MIDI 檔案",
        filetypes=[("MIDI files", "*.mid *.midi"), ("All files", "*.*")]
    )
    if not midi_path:
        print("❌ 未選取檔案。")
        sys.exit(1)

    print(f"✅ 載入檔案：{os.path.basename(midi_path)}")

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

    try:
        result = convert_midi_to_jianpu(midi_path, bpm, numerator, denominator)
    except Exception as e:
        print("❌ 轉換失敗：", e)
        sys.exit(1)

    text_output = result.get("text_output", "")
    pdf_path = result.get("pdf_path")

    print("===== Jianpu Output (前 600 字) =====")
    print(text_output[:600] + ("..." if len(text_output) > 600 else ""))

    if pdf_path and os.path.exists(pdf_path):
        openPDF(pdf_path)
    else:
        print("⚠ 沒有產生 PDF（可能缺 jianpu-ly.py 或 LilyPond）。")


if __name__ == "__main__":
    main()
