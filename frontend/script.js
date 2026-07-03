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
    button.innerHTML = "⏳ Processing...";

    document.getElementById("progress-bar").style.width = "0%";
    document.getElementById("percent").innerHTML = "0%";
    document.getElementById("status").innerHTML = "Uploading...";
    document.getElementById("eta").innerHTML = "⏳ Calculating...";

    document.getElementById("download").style.display = "none";

    const formData = new FormData();
    formData.append("video", file);

    try {

        const response = await fetch(
            API_URL + "/dub-video?language=" + encodeURIComponent(language),
            {
                method: "POST",
                body: formData
            }
        );

        const data = await response.json();

        if (!data.job_id) {
            throw new Error("Job ID not received from server.");
        }

        checkProgress(data.job_id, button);

    } catch (error) {

        console.error(error);

        button.disabled = false;
        button.innerHTML = "🚀 Start Dubbing";

        document.getElementById("status").innerHTML = "❌ Upload Failed";

        alert("Upload failed. Please try again.");
    }
}


async function checkProgress(job_id, button) {

    const timer = setInterval(async () => {

        try {

            const response = await fetch(
                API_URL + "/status/" + job_id
            );

            const data = await response.json();

            if (data.error) {
                clearInterval(timer);
                button.disabled = false;
                button.innerHTML = "🚀 Start Dubbing";

                document.getElementById("status").innerHTML = data.error;
                return;
            }

            document.getElementById("status").innerHTML =
                data.status + " (" + data.progress + "%)";

            document.getElementById("progress-bar").style.width =
                data.progress + "%";

            document.getElementById("percent").innerHTML =
                data.progress + "%";

            let remaining = Math.max(
                0,
                Math.ceil((100 - data.progress) * 2)
            );

            if (data.progress < 100) {

                document.getElementById("eta").innerHTML =
                    "⏳ Estimated Time Remaining: " +
                    remaining +
                    " sec";

            } else {

                document.getElementById("eta").innerHTML =
                    "✅ Finished";

            }

            if (data.progress >= 100) {

                clearInterval(timer);

                document.getElementById("status").innerHTML =
                    "✅ Dubbing Completed";

                const download =
                    document.getElementById("download");

                download.href =
                    API_URL + "/download-video";

                download.innerHTML =
                    "⬇ Download Video";

                download.style.display =
                    "inline-block";

                button.disabled = false;
                button.innerHTML =
                    "🚀 Start Dubbing";
            }

        } catch (error) {

            clearInterval(timer);

            console.error(error);

            button.disabled = false;
            button.innerHTML = "🚀 Start Dubbing";

            document.getElementById("status").innerHTML =
                "❌ Connection Lost";
        }

    }, 1000);

}
