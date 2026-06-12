import ffmpeg

def extract_audio(video_path, audio_path):
    ffmpeg.input(video_path).output(audio_path).run(
        overwrite_output=True
    )

    return audio_path
