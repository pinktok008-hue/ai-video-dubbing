import ffmpeg

def extract_audio(video_path, audio_path):
    (
        ffmpeg
        .input(video_path)
        .output(
            audio_path,
            acodec="pcm_s16le",
            ar="16000",
            ac=1
        )
        .overwrite_output()
        .run()
    )

    return audio_path
