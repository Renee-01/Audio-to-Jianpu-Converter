import os
from pathlib import Path
from typing import Optional
from tkinter import Tk, filedialog
from datetime import datetime
from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH  # 可用來自訂模型路徑/後端
import pretty_midi

def audio_to_midi(input_audio: Path) -> Path:
    input_audio = Path(input_audio)

    if not input_audio.exists():
        raise FileNotFoundError(f"音訊不存在：{input_audio}")

    # 輸出檔名：同名 .mid
    output_dir = generater_output_dir(input_audio)
    output_midi = output_dir / (input_audio.stem + ".mid")

    # 轉檔
    _, midi_data, _ = predict(str(input_audio))
    midi_data.write(str(output_midi))

    return output_midi

def generater_output_dir(original_path: Path):
    # 輸出目錄：<音訊所在資料夾>/output/時間戳記/
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    output_dir = original_path.parent / "output" / f"output_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    return output_dir

#____main____

Tk().withdraw()

audio_path = filedialog.askopenfilename(
    title="選擇音訊",
    filetypes=[
        ("Audio files", "*.mp3 *.wav"),  # 主要濾器：同時顯示 mp3、wav
        ("MP3", "*.mp3"),
        ("WAV", "*.wav"),
        ("All files", "*.*"),
    ],
)

if not audio_path:
    print("❌ 未選取檔案。")

print(f"✅ 載入檔案：{os.path.basename(audio_path)}")

audio_to_midi(audio_path)