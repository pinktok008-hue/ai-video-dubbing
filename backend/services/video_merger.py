import ffmpeg


def merge_video_audio(
    video_path,
    audio_path,
    output_path
):

    try:

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
            .run(
                capture_stdout=True,
                capture_stderr=True
            )
        )


        print("MERGE SUCCESS")

        return output_path


    except ffmpeg.Error as e:

        print("===== FFMPEG ERROR =====")

        if e.stderr:
            print(e.stderr.decode())

        else:
            print("No stderr from ffmpeg")

        raise e
