import ffmpeg


def merge_video_audio(
    video_path,
    audio_path,
    output_path
):

    try:

        print("VIDEO:", video_path)
        print("AUDIO:", audio_path)

        video = ffmpeg.input(video_path)
        audio = ffmpeg.input(audio_path)

        (
            ffmpeg
            .output(
                video.video,
                audio.audio,
                output_path,
                vcodec="libx264",
                acodec="aac",
                shortest=1
            )
            .overwrite_output()
            .run()
        )

        print("MERGE SUCCESS")

        return output_path


    except ffmpeg.Error as e:

        print("===== FFMPEG ERROR =====")
        print(e)

        raise e
