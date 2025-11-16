# Audio_to_MIDI.py
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional
from tkinter import Tk, filedialog
from datetime import datetime
from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH
import pretty_midi
import subprocess


def _ensure_out_dir(base: Path, out_dir: Optional[str]) -> Path:
    if out_dir:
        p = Path(out_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    p = base.parent / "output" / f"output_{ts}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _extract_vocals_with_demucs(audio: Path) -> Path:
    """
    使用 Demucs 把音檔拆出人聲，回傳 vocals.wav 的路徑。

    需要先在 pitch-env 裡安裝 demucs：
        pip install -U demucs

    Demucs 會在目前工作目錄下建立
        separated/<MODEL_NAME>/<檔名不含副檔>/vocals.wav
    """
    # ✅ 用目前正在執行這支程式的 python 來跑 demucs 模組
    cmd = [
        sys.executable,        # C:\Users\...\envs\pitch-env\python.exe
        "-m", "demucs",        # 等於在命令列打：python -m demucs ...
        "--two-stems=vocals",  # 只分出 vocals / accompaniment 兩軌
        "-d", "cpu",           # 強制用 CPU
        str(audio),
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            "Demucs 分離人聲失敗：\n"
            f"Command: {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
        )

    # 預設輸出位置：./separated/<model>/<stemless_name>/vocals.wav
    sep_root = Path.cwd() / "separated"
    candidates = list(sep_root.glob(f"*/{audio.stem}/vocals.wav"))
    if not candidates:
        raise FileNotFoundError(
            f"找不到 Demucs 產生的 vocals.wav，預期位置在：{sep_root}/<model>/{audio.stem}/vocals.wav"
        )

    return candidates[0]



def audio_to_midi(
    input_audio_path: str,
    out_dir: Optional[str] = None,
    remove_accompaniment: bool = False,
) -> str:
    """
    把音訊轉成 MIDI，回傳 MIDI 檔的絕對路徑。

    remove_accompaniment = True 時：
        先用 Demucs 抽出人聲 vocals.wav，再用該人聲音檔跑 basic-pitch。
    """
    audio = Path(input_audio_path).expanduser().resolve()
    if not audio.exists():
        raise FileNotFoundError(f"音訊不存在：{audio}")

    # 若需要消除伴奏，先用 Demucs 抽出人聲
    source_audio = audio
    if remove_accompaniment:
        vocals_path = _extract_vocals_with_demucs(audio)
        source_audio = vocals_path

    # 決定輸出目錄（仍然以原始 audio 來命名 MIDI 檔）
    out_dir_path = _ensure_out_dir(audio, out_dir)
    midi_path = out_dir_path / f"{audio.stem}.mid"

    # 執行 basic-pitch 轉檔（用 source_audio：可能是原檔或人聲 stem）
    _, midi_data, _ = predict(str(source_audio))
    midi_data.write(str(midi_path))

    return str(midi_path)


def main():
    root = Tk()
    root.withdraw()
    root.call('wm', 'attributes', '.', '-topmost', True)

    audio_path = filedialog.askopenfilename(
        title="選擇音訊",
        filetypes=[
            ("Audio files", "*.mp3 *.wav"),
            ("MP3", "*.mp3"),
            ("WAV", "*.wav"),
            ("All files", "*.*"),
        ],
    )

    if not audio_path:
        print("❌ 未選取檔案。")
        return

    print(f"✅ 載入檔案：{os.path.basename(audio_path)}")

    audio_to_midi(audio_path, remove_accompaniment=True)  # 這裡不消伴奏（remove_accompaniment=False）


if __name__ == "__main__":
    main()