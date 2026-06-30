import subprocess


def merge_video_audio(
    video_path,
    audio_path,
    output_path
):

    command = [
        "ffmpeg",
        "-i", video_path,
        "-i", audio_path,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-y",
        output_path
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    if result.returncode != 0:
        print("FFMPEG ERROR:")
        print(result.stderr.decode())

        raise Exception(
            "FFmpeg merge failed"
        )

    print("MERGE SUCCESS")

    return output_path
