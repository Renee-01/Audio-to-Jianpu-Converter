# Audio_to_MIDI.py
from __future__ import annotations
from pathlib import Path
from typing import Optional
from datetime import datetime

from basic_pitch.inference import predict   # pip install basic-pitch

def _ensure_out_dir(base: Path, out_dir: Optional[str]) -> Path:
    if out_dir:
        p = Path(out_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p
    # 預設：在音訊同層建立 output/output_時間戳 設定
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    p = base.parent / "output" / f"output_{ts}"
    p.mkdir(parents=True, exist_ok=True)
    return p

def audio_to_midi(input_audio_path: str, out_dir: Optional[str] = None) -> str:
    """把音訊轉成 MIDI，回傳 MIDI 檔的**絕對**路徑。"""
    audio = Path(input_audio_path).expanduser().resolve()
    if not audio.exists():
        raise FileNotFoundError(f"音訊不存在：{audio}")

    out_dir_path = _ensure_out_dir(audio, out_dir)
    midi_path = out_dir_path / f"{audio.stem}.mid"

    # 執行 basic-pitch 轉檔
    _, midi_data, _ = predict(str(audio))
    midi_data.write(str(midi_path))

    return str(midi_path)