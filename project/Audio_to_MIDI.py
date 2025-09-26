from pathlib import Path
from typing import Optional

from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH  # 可用來自訂模型路徑/後端
import pretty_midi

def audio_to_midi(input_audio: Path, output_midi: Path) -> Path:
    input_audio = Path(input_audio)
    output_midi = Path(output_midi)
    output_midi.parent.mkdir(parents=True, exist_ok=True)

    # Basic Pitch 直接給路徑即可；回傳的 midi_data 是 pretty_midi.PrettyMIDI 物件
    # （可用 .write() 輸出 MIDI 檔）
    model_output, midi_data, note_events = predict(str(input_audio))

    midi_data.write(str(output_midi))
    return output_midi