import os
import pretty_midi
from tkinter import Tk, filedialog
from dataclasses import dataclass
import subprocess
from datetime import datetime
import webbrowser

# ======== 資料結構定義 ========
@dataclass
class NoteStruct:
    symbol_and_rhythm: str
    beats: float
    start: float
    end: float

# ======== 音高轉簡譜 ========
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

# ======== 拍數分類（含附點） ========
def quantize_beats(duration: float, beat_duration: float) -> float:
    if duration < beat_duration / 16: return 0.0625
    elif duration < beat_duration / 16 * 1.5: return 0.09375
    elif duration < beat_duration / 8: return 0.125
    elif duration < beat_duration / 8 * 1.5: return 0.1875
    elif duration < beat_duration / 4: return 0.25
    elif duration < beat_duration / 4 * 1.5: return 0.375
    elif duration < beat_duration / 2: return 0.5
    elif duration < beat_duration / 2 * 1.5: return 0.75
    elif duration < beat_duration: return 1
    elif duration < beat_duration * 1.5: return 1.5
    elif duration < beat_duration * 2: return 2
    elif duration < beat_duration * 2 * 1.5: return 3
    else: return 4

# ======== 節奏標記轉換 ========
def rhythm_marker(beats: float, symbol: str) -> str:
    if beats == 4.0: return f"{symbol} - - -"
    elif beats == 3.0: return f"{symbol} - -"
    elif beats == 2.0: return f"{symbol} -"
    elif beats == 1.5: return f"{symbol}."
    elif beats == 1.0: return f"{symbol}"
    elif beats == 0.75: return f"q{symbol}."
    elif beats == 0.5: return f"q{symbol}"
    elif beats == 0.375: return f"s{symbol}."
    elif beats == 0.25: return f"s{symbol}"
    elif beats == 0.1875: return f"d{symbol}."
    elif beats == 0.125: return f"d{symbol}"
    elif beats == 0.09375: return f"h{symbol}."
    elif beats == 0.0625: return f"h{symbol}"
    else: return f"?{symbol}"

# ======== 自動補齊不足拍的小節 ========
def fill_rest_line(line_text, current_beat, beats_per_bar):
    beat_remain = round(beats_per_bar - current_beat, 5)
    rest_parts = []
    while beat_remain > 0:
        if beat_remain >= 1:
            rest_parts.append("0")
            beat_remain -= 1
        elif beat_remain >= 0.5:
            rest_parts.append("q0")
            beat_remain -= 0.5
        elif beat_remain >= 0.25:
            rest_parts.append("s0")
            beat_remain -= 0.25
        elif beat_remain >= 0.125:
            rest_parts.append("d0")
            beat_remain -= 0.125
        elif beat_remain >= 0.0625:
            rest_parts.append("h0")
            beat_remain -= 0.0625
        else:
            break
    return line_text.strip() + " " + " ".join(rest_parts)


# ======== 開啟 MIDI 檔案 ========
Tk().withdraw()
midi_path = filedialog.askopenfilename(title="選擇 MIDI 檔案", filetypes=[("MIDI files", "*.mid *.midi")])
if not midi_path:
    print("❌ 未選取檔案。")
    exit()

print(f"✅ 載入檔案：{os.path.basename(midi_path)}")

# ======== 使用者輸入 BPM ========
try:
    bpm = float(input("請輸入 BPM（預設為 80）：") or 80)
except ValueError:
    print("⚠️ 無效輸入，使用預設 BPM = 80")
    bpm = 80

beat_duration = 60 / bpm
beats_per_bar = 4

# ======== 處理音符並轉換 ========
midi_data = pretty_midi.PrettyMIDI(midi_path)
instrument = midi_data.instruments[0]
notes = sorted(instrument.notes, key=lambda n: n.start)

note_structs = []
for note in notes:
    symbol = midi_to_jianpu(note.pitch)
    duration = note.end - note.start
    beat_length = quantize_beats(duration, beat_duration)
    symbol_and_rhythm = rhythm_marker(beat_length, symbol)
    note_structs.append(NoteStruct(symbol_and_rhythm, beat_length, note.start, note.end))

# ======== 每小節換行輸出 ========
current_beat = 0
line_buffer = ""
output_lines = []

for note in note_structs:
    line_buffer += f"{note.symbol_and_rhythm} "
    current_beat += note.beats
    if current_beat >= beats_per_bar:
        output_lines.append(line_buffer.strip())
        line_buffer = ""
        current_beat -= beats_per_bar

# 若最後一行還有剩下未滿小節的音
if line_buffer.strip():
    filled_line = fill_rest_line(line_buffer.strip(), current_beat, beats_per_bar)
    output_lines.append(filled_line)


# ======== 儲存 txt 檔案 ========
timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
base_name = f"output_{timestamp}"
output_dir = os.path.join(os.path.dirname(midi_path), "output", base_name)
os.makedirs(output_dir, exist_ok=True)

output_txt = os.path.join(output_dir, f"{base_name}.txt")
with open(output_txt, "w", encoding="utf-8") as f:
    for line in output_lines:
        f.write(line + "\n")

print(f"✅ 簡譜已儲存：{output_txt}")


# ======== 產出 PDF 檔 ========
JIANPU_SCRIPT = r"d:\Audio-to-Jianpu Converter\jianpu-ly.py"
LILYPOND_EXE = r"C:\Users\lulu1\lilypond-2.24.4\bin\lilypond.exe"
output_ly = os.path.join(output_dir, f"{base_name}.ly")
output_pdf = os.path.join(output_dir, f"{base_name}.pdf")

# Step 1: jianpu-ly.py → .ly
with open(output_txt, "r", encoding="utf-8") as fin, open(output_ly, "w", encoding="utf-8") as fout:
    subprocess.run(["python", JIANPU_SCRIPT], stdin=fin, stdout=fout)

# Step 2: LilyPond → PDF
subprocess.run([LILYPOND_EXE, "-o", base_name, f"{base_name}.ly"], cwd=output_dir)

# Step 3: 打開 PDF
if os.path.exists(output_pdf):
    webbrowser.open(output_pdf)
    print("✅ PDF 已開啟。")
else:
    print("❌ PDF 產出失敗。")
