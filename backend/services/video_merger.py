import ffmpeg

def merge_video_audio(
    video_path,
    audio_path,
    output_path
):

    (
        ffmpeg
        .output(
            ffmpeg.input(video_path),
            ffmpeg.input(audio_path),
            output_path,
            vcodec="copy",
            acodec="aac"
        )
        .run(
            overwrite_output=True
        )
    )

    return output_path
