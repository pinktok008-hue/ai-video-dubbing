import ffmpeg


def merge_video_audio(
    video_path,
    audio_path,
    output_path
):

    video = ffmpeg.input(video_path)
    audio = ffmpeg.input(audio_path)

    (
        ffmpeg
        .output(
            video.video,
            audio.audio,
            output_path,
            vcodec="copy",
            acodec="aac",
            shortest=1
        )
        .overwrite_output()
        .run()
    )

    return output_path
