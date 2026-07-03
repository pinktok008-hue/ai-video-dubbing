const API_URL = "https://ai-video-dubbing.onrender.com";

async function uploadVideo() {

    const file = document.getElementById("videoFile").files[0];
    const language = document.getElementById("language").value;
    const button = document.querySelector("button");

    if (!file) {
        alert("Please select a video.");
        return;
    }

    button.disabled = true;
    button.innerHTML = "Processing...";

    document.getElementById("progress").value = 0;
    document.getElementById("percent").innerHTML = "0%";
    document.getElementById("status").innerHTML = "Uploading...";

    const formData = new FormData();
    formData.append("video", file);

    try {

        const response = await fetch(
            API_URL + "/dub-video?language=" + language,
            {
                method: "POST",
                body: formData
            }
        );

        const data = await response.json();

        checkProgress(data.job_id, button);

    } catch (error) {

        button.disabled = false;
        button.innerHTML = "🚀 Start Dubbing";

        document.getElementById("status").innerHTML =
            "Upload Failed";

        alert(error);

    }

}


async function checkProgress(job_id, button) {

    const timer = setInterval(async () => {

        const response = await fetch(
            API_URL + "/status/" + job_id
        );

        const data = await response.json();

        document.getElementById("status").innerHTML =
            data.status + " (" + data.progress + "%)";

        document.getElementById("progress").value =
            data.progress;

        document.getElementById("percent").innerHTML =
            data.progress + "%";

        if (data.progress >= 100) {

            clearInterval(timer);

            document.getElementById("status").innerHTML =
                "✅ Dubbing Completed";

            const download =
                document.getElementById("download");

            download.href =
                API_URL + "/download-video/" + job_id;

            download.style.display = "block";

            download.innerHTML =
                "⬇ Download Video";

            button.disabled = false;
            button.innerHTML =
                "🚀 Start Dubbing";
        }

    }, 1000);

}
