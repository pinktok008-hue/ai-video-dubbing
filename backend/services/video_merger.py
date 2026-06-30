import subprocess
import ffmpeg


def merge_video_audio(
    video_path,
    audio_path,
    output_path
):

    # Get durations

    video_info = ffmpeg.probe(video_path)
    video_duration = float(
        video_info["format"]["duration"]
    )


    audio_info = ffmpeg.probe(audio_path)
    audio_duration = float(
        audio_info["format"]["duration"]
    )


    # Calculate speed
    speed = audio_duration / video_duration


    command = [
        "ffmpeg",
        "-i", video_path,
        "-i", audio_path,

        "-filter:a",
        f"atempo={speed}",

        "-map",
        "0:v:0",

        "-map",
        "1:a:0",

        "-c:v",
        "copy",

        "-c:a",
        "aac",

        "-shortest",

        "-y",

        output_path
    ]


    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )


    if result.returncode != 0:

        print(result.stderr.decode())

        raise Exception(
            "Audio speed adjustment failed"
        )


    return output_path
