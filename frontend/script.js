const API_URL = "https://ai-video-dubbing.onrender.com";


async function uploadVideo(){

const file =
document.getElementById("videoFile").files[0];

const language =
document.getElementById("language").value;


let formData = new FormData();

formData.append("video",file);


document.getElementById("status").innerHTML =
"Uploading...";


let response = await fetch(
API_URL + "/dub-video?language=" + language,
{
method:"POST",
body:formData
});


let data = await response.json();


console.log(data);


document.getElementById("status").innerHTML =
"Completed";


let download =
document.getElementById("download");


download.href =
API_URL + "/download-video";


download.innerHTML =
"Download Video";


download.style.display =
"block";


}
