const API_URL = "https://ai-video-dubbing.onrender.com";

/* ===========================
UPLOAD VIDEO
=========================== */

async function uploadVideo() {

    const file = document.getElementById("videoFile").files[0];

    const language = document.getElementById("language").value;

    const button = document.getElementById("startBtn");

    if (!file) {

        alert("Please select a video.");

        return;

    }

    // Preview Original Video
    document.getElementById("originalPreview").src =
        URL.createObjectURL(file);

    // Reset UI
    button.disabled = true;

    button.innerHTML =
        "<i class='fa-solid fa-spinner fa-spin'></i> Processing...";

    document.getElementById("status").innerHTML =
        "Uploading...";

    document.getElementById("eta").innerHTML =
        "Calculating...";

    document.getElementById("percent").innerHTML =
        "0%";

    document.getElementById("progress-bar").style.width =
        "0%";

    document.getElementById("download").style.display =
        "none";

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

    catch (err) {

        alert(err);

        button.disabled = false;

        button.innerHTML =
            "Start AI Dubbing";

    }

}

/* ===========================
CHECK PROGRESS
=========================== */

async function checkProgress(job_id, button) {

    const timer = setInterval(async () => {

        const response = await fetch(

            API_URL + "/status/" + job_id

        );

        const data = await response.json();

        // Status
        document.getElementById("status").innerHTML =
            data.status;

        // Percent
        document.getElementById("percent").innerHTML =
            data.progress + "%";

        // Progress Line
        document.getElementById("progress-bar").style.width =
            data.progress + "%";

        // ETA

        let eta = Math.ceil((100 - data.progress) * 2);

        if (eta < 0) eta = 0;

        document.getElementById("eta").innerHTML =
            "Estimated Time : " + eta + " sec";

        // Circle Animation

        document.querySelector(".progress-circle").style.background =
            `conic-gradient(
            #7c5cff ${data.progress * 3.6}deg,
            rgba(255,255,255,.08) 0deg
            )`;

        // Timeline

        const steps = document.querySelectorAll(".step");

        steps.forEach(step => step.classList.remove("active"));

        if (data.progress < 20)

            steps[0].classList.add("active");

        else if (data.progress < 40)

            steps[1].classList.add("active");

        else if (data.progress < 60)

            steps[2].classList.add("active");

        else if (data.progress < 90)

            steps[3].classList.add("active");

        else

            steps[4].classList.add("active");

        // FINISHED

        if (data.progress >= 100) {

            clearInterval(timer);

            document.getElementById("status").innerHTML =
                "✅ AI Dubbing Completed";

            document.getElementById("eta").innerHTML =
                "Finished";

            // Download Button

            const download =
                document.getElementById("download");

            download.href =
                API_URL + "/download-video";

            download.style.display =
                "inline-block";

            // Preview Dubbed Video

            document.getElementById("dubbedPreview").src =
                API_URL + "/download-video";

            button.disabled = false;

            button.innerHTML =
                '<i class="fa-solid fa-play"></i> Start AI Dubbing';

        }

    }, 1000);

}

/* ===========================
DRAG & DROP
=========================== */

const uploadBox =
    document.querySelector(".upload-box");

const input =
    document.getElementById("videoFile");

uploadBox.addEventListener("dragover", e => {

    e.preventDefault();

    uploadBox.style.borderColor = "#00d4ff";

});

uploadBox.addEventListener("dragleave", () => {

    uploadBox.style.borderColor =
        "rgba(255,255,255,.2)";

});

uploadBox.addEventListener("drop", e => {

    e.preventDefault();

    input.files = e.dataTransfer.files;

    uploadBox.style.borderColor =
        "rgba(255,255,255,.2)";

});

/* ===========================
PREVIEW
=========================== */

input.addEventListener("change", () => {

    if (input.files.length > 0) {

        document.getElementById("originalPreview").src =
            URL.createObjectURL(input.files[0]);

    }

});
