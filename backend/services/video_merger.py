import ffmpeg


def merge_video_audio(
    video_path,
    audio_path,
    output_path
):

    video = ffmpeg.input(video_path)

    # Get original video duration
    probe = ffmpeg.probe(video_path)

    video_duration = float(
        probe["format"]["duration"]
    )


    # Adjust voice duration to video duration
    audio = (
        ffmpeg
        .input(audio_path)
        .filter(
            "atempo",
            video_duration /
            float(
                ffmpeg.probe(audio_path)["format"]["duration"]
            )
        )
    )


    (
        ffmpeg
        .output(
            video.video,
            audio,
            output_path,
            vcodec="copy",
            acodec="aac"
        )
        .overwrite_output()
        .run()
    )


    return output_path
