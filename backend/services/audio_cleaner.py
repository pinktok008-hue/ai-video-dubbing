import ffmpeg

def remove_original_audio(video_path, output_path):

    (
        ffmpeg
        .input(video_path)
        .output(
            output_path,
            an=None,
            vcodec="copy"
        )
        .overwrite_output()
        .run()
    )

    return output_path
