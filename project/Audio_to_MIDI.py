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


from pathlib import Path
from typing import Optional

def audio_to_midi(
    input_audio_path: str,
    out_dir: Optional[str] = None,   # 可以是目錄或完整 .mid 路徑
    remove_accompaniment: bool = False,
) -> str:
    """
    把音訊轉成 MIDI，回傳 MIDI 檔的絕對路徑。

    - out_dir 可以是資料夾，也可以是完整的 .mid 路徑。
    - remove_accompaniment = True 時：
        先用 Demucs 抽出人聲 vocals.wav，再用該人聲音檔跑 basic-pitch。
    """
    audio = Path(input_audio_path).expanduser().resolve()
    if not audio.exists():
        raise FileNotFoundError(f"音訊不存在：{audio}")

    # --- 決定輸出路徑：支援「目錄」或「完整 .mid 檔」兩種用法 ---
    if out_dir is None:
        # 沒給 out_dir，就輸出在音檔同一個資料夾，用音檔檔名命名
        out_dir_path = audio.parent
        midi_path = out_dir_path / f"{audio.stem}.mid"
    else:
        out_path = Path(out_dir).expanduser().resolve()
        if out_path.suffix.lower() == ".mid":
            # 給的是完整 MIDI 檔路徑，例如 D:\...\uploads\15s.mid
            midi_path = out_path
            out_dir_path = midi_path.parent
        else:
            # 給的是資料夾，例如 D:\...\uploads
            out_dir_path = out_path
            midi_path = out_dir_path / f"{audio.stem}.mid"

    # 確保輸出資料夾存在
    out_dir_path.mkdir(parents=True, exist_ok=True)

    # --- 快取：如果 MIDI 已經存在，直接回傳 ---
    if midi_path.exists():
        print(f"✅ 已存在 MIDI：{midi_path}，直接回傳，不重新轉檔。")
        return str(midi_path)

    # 若需要消除伴奏，先用 Demucs 抽出人聲
    source_audio = audio
    if remove_accompaniment:
        vocals_path = _extract_vocals_with_demucs(audio)
        source_audio = vocals_path

    # 執行 basic-pitch 轉檔
    _, midi_data, _ = predict(str(source_audio))
    midi_data.write(str(midi_path))
    print(f"🎵 已產生新的 MIDI：{midi_path}")

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

    audio_to_midi(audio_path, remove_accompaniment=False)  # 這裡不消伴奏（remove_accompaniment=False）


if __name__ == "__main__":
    main()