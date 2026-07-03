const API_URL = "https://ai-video-dubbing.onrender.com";

async function uploadVideo() {

    const file = document.getElementById("videoFile").files[0];
    const language = document.getElementById("language").value;
    const button = document.getElementById("startBtn");

    if (!file) {
        alert("Please select a video.");
        return;
    }

    // Show Original Preview
    const original = document.getElementById("originalPreview");
    original.src = URL.createObjectURL(file);

    // Reset UI
    document.getElementById("progress-bar").style.width = "0%";
    document.getElementById("percent").innerHTML = "0%";
    document.getElementById("status").innerHTML = "Uploading...";
    document.getElementById("eta").innerHTML =
        "Preparing AI...";

    document.getElementById("download").style.display = "none";

    button.disabled = true;
    button.innerHTML = "Processing...";

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

        checkProgress(
            data.job_id,
            button
        );

    }

    catch (error) {

        alert(error);

        button.disabled = false;

        button.innerHTML =
            "🚀 Start Dubbing";

    }

}



async function checkProgress(job_id, button) {

    const timer = setInterval(async () => {

        try {

            const response = await fetch(

                API_URL + "/status/" + job_id

            );

            const data = await response.json();

            // Progress Bar

            document.getElementById(
                "progress-bar"
            ).style.width =
                data.progress + "%";

            // Percentage

            document.getElementById(
                "percent"
            ).innerHTML =
                data.progress + "%";

            // Status

            document.getElementById(
                "status"
            ).innerHTML =
                data.status;

            // ETA

            let remain = Math.max(
                0,
                Math.ceil((100 - data.progress) * 2)
            );

            if (data.progress < 100) {

                document.getElementById(
                    "eta"
                ).innerHTML =
                    "⏳ " +
                    remain +
                    " sec remaining";

            }

            // Completed

            if (data.progress >= 100) {

                clearInterval(timer);

                document.getElementById(
                    "status"
                ).innerHTML =
                    "✅ Dubbing Completed";

                document.getElementById(
                    "eta"
                ).innerHTML =
                    "Finished";

                const download =
                    document.getElementById(
                        "download"
                    );

                download.href =
                    API_URL +
                    "/download-video";

                download.style.display =
                    "inline-block";

                // Auto Preview

                const dubbed =
                    document.getElementById(
                        "dubbedPreview"
                    );

                dubbed.src =
                    API_URL +
                    "/download-video";

                button.disabled = false;

                button.innerHTML =
                    "🚀 Start Dubbing";

            }

        }

        catch (e) {

            console.log(e);

        }

    }, 1000);

}
