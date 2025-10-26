# jianpu_api.py
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from mido import MidiFile
import os
from collections import defaultdict

bp = Blueprint("jianpu_api", __name__)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def parse_midi_to_units(midi_path, quant_units_per_quarter=8):
    """
    將 MIDI 量化為固定時間格（1 單位 = 四分音符的 1/8 = 32 分音符）。
    回傳 run-length 壓縮後的序列，每個元素包含 pitch(base) 與 duration(單位)。
    - pitch.base: 0 代表休止，其餘為 MIDI pitch (60=中央C)
    - duration: 整數，四分音符=8，二分=16，八分=4 ...
    """
    mid = MidiFile(midi_path)
    tpq = mid.ticks_per_beat  # ticks per quarter note

    # 收集所有 note 片段 (start_tick, end_tick, pitch)
    on_stacks = defaultdict(list)  # note -> [start_tick,...]
    notes = []  # (start_tick, end_tick, pitch)

    # 我們用 "絕對tick" 聚合所有track
    abs_time = [0 for _ in mid.tracks]
    for ti, track in enumerate(mid.tracks):
        for msg in track:
            abs_time[ti] += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                on_stacks[msg.note].append(abs_time[ti])
            elif msg.type in ("note_off",) or (msg.type == "note_on" and msg.velocity == 0):
                if on_stacks[msg.note]:
                    start = on_stacks[msg.note].pop(0)
                    end = abs_time[ti]
                    if end > start:
                        notes.append((start, end, msg.note))

    if not notes:
        return []

    # 設定量化單位： 1 單位 = tpq/8 ticks（因四分=8單位）
    unit_ticks = max(1, tpq // quant_units_per_quarter)

    # 建立時間線：以單位為格，掃描每格的「當下最高音」
    start_tick = min(n[0] for n in notes)
    end_tick = max(n[1] for n in notes)
    # 對齊到格
    def align_down(x): return (x // unit_ticks) * unit_ticks
    def align_up(x):   return ((x + unit_ticks - 1) // unit_ticks) * unit_ticks

    t0 = align_down(start_tick)
    t1 = align_up(end_tick)

    # 為加速查找，先按開始/結束做索引
    starts_idx = defaultdict(list)
    ends_idx = defaultdict(list)
    for s, e, p in notes:
        s_al = max(t0, align_down(s))
        e_al = min(t1, align_up(e))
        if e_al > s_al:
            starts_idx[s_al].append((s_al, e_al, p))
            ends_idx[e_al].append((s_al, e_al, p))

    active = []
    song_units = []  # 每一格的 pitch（0=rest or no active）
    t = t0
    while t < t1:
        # 激活在此格開始的音
        if t in starts_idx:
            active.extend(starts_idx[t])
        # 移除在此格結束的音
        if t in ends_idx:
            to_remove = set(ends_idx[t])
            active = [n for n in active if n not in to_remove]

        if active:
            # 取當下最高音（也可改成最大 velocity，但 mido 預設我們沒存）
            pitch = max(n[2] for n in active)
        else:
            pitch = 0  # 休止

        song_units.append(pitch)
        t += unit_ticks

    # Run-length compress → 轉成 react-jianpu 的結構
    out = []
    if not song_units:
        return out

    cur = song_units[0]
    run = 1
    for x in song_units[1:]:
        if x == cur:
            run += 1
        else:
            out.append({
                "pitch": {"base": int(cur), "accidental": 0},
                "duration": int(run),  # 幾個「單位」
                "options": {"rest": True} if cur == 0 else {},
                "lyrics": {"exists": False, "content": "", "hyphen": False}
            })
            cur = x
            run = 1
    # flush
    out.append({
        "pitch": {"base": int(cur), "accidental": 0},
        "duration": int(run),
        "options": {"rest": True} if cur == 0 else {},
        "lyrics": {"exists": False, "content": "", "hyphen": False}
    })
    return out

@bp.post("/api/midi-to-jianpujson")
def midi_to_jianpujson():
    if "file" not in request.files:
        return jsonify({"error": "no file"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "empty filename"}), 400
    path = os.path.join(UPLOAD_DIR, secure_filename(f.filename))
    f.save(path)

    # 量化參數可調：四分=8 單位（建議維持）
    song = parse_midi_to_units(path, quant_units_per_quarter=8)
    return jsonify({"song": song})
