import ffmpeg

def merge_video_audio(
    video_path,
    audio_path,
    output_path
):

    video = ffmpeg.input(video_path)
    audio = ffmpeg.input(audio_path)

    try:

        (
            ffmpeg
            .output(
                video,
                audio,
                output_path,
                vcodec="libx264",
                acodec="aac",
                strict="experimental"
            )
            .overwrite_output()
            .run()
        )

        return output_path

    except ffmpeg.Error as e:
        print("FFMPEG ERROR:")
        print(e.stderr.decode())

        raise e
