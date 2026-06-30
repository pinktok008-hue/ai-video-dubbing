import ffmpeg


def merge_video_audio(
    video_path,
    audio_path,
    output_path
):

    try:

        video_info = ffmpeg.probe(video_path)
        video_duration = float(
            video_info["format"]["duration"]
        )

        audio_info = ffmpeg.probe(audio_path)
        audio_duration = float(
            audio_info["format"]["duration"]
        )

        speed = audio_duration / video_duration


        video = ffmpeg.input(video_path)

        audio = (
            ffmpeg
            .input(audio_path)
            .filter(
                "atempo",
                speed
            )
        )


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


    except ffmpeg.Error as e:

        print("FFMPEG ERROR:")
        print(e.stderr.decode())

        raise e
