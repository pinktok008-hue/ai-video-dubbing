const API_URL = "https://ai-video-dubbing.onrender.com";

async function uploadVideo() {

    const file = document.getElementById("videoFile").files[0];
    const language = document.getElementById("language").value;

    if (!file) {
        alert("Please select a video.");
        return;
    }

    let formData = new FormData();
    formData.append("video", file);

    document.getElementById("status").innerHTML = "Uploading...";

    let response = await fetch(
        API_URL + "/dub-video?language=" + language,
        {
            method: "POST",
            body: formData
        }
    );

    let data = await response.json();

    const job_id = data.job_id;

    checkProgress(job_id);
}


async function checkProgress(job_id) {

    const timer = setInterval(async () => {

        let response = await fetch(
            API_URL + "/status/" + job_id
        );

        let data = await response.json();

        document.getElementById("status").innerHTML = data.status;

        document.getElementById("progress").value = data.progress;

        document.getElementById("percent").innerHTML =
            data.progress + "%";

        if (data.progress >= 100) {

            clearInterval(timer);

            const download = document.getElementById("download");

            download.href =
                API_URL + "/download-video/" + job_id;

            download.innerHTML = "Download Video";

            download.style.display = "block";
        }

    }, 2000);

}
