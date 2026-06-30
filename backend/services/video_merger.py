import subprocess
import ffmpeg


def build_atempo_filter(speed):

    filters = []

    while speed > 2:
        filters.append("atempo=2.0")
        speed /= 2

    while speed < 0.5:
        filters.append("atempo=0.5")
        speed *= 2

    filters.append(f"atempo={speed}")

    return ",".join(filters)



def merge_video_audio(
    video_path,
    audio_path,
    output_path
):

    video_info = ffmpeg.probe(video_path)

    video_duration = float(
        video_info["format"]["duration"]
    )


    audio_info = ffmpeg.probe(audio_path)

    audio_duration = float(
        audio_info["format"]["duration"]
    )


    speed = audio_duration / video_duration


    audio_filter = build_atempo_filter(speed)


    command = [

        "ffmpeg",

        "-i",
        video_path,

        "-i",
        audio_path,


        "-filter:a",
        audio_filter,


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
            "FFmpeg audio sync failed"
        )


    return output_path
