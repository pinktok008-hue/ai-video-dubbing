const API_URL = "https://ai-video-dubbing.onrender.com";


async function uploadVideo(){

const file =
document.getElementById("videoFile").files[0];


const language =
document.getElementById("language").value;



if(!file){
alert("Select video first");
return;
}



let formData = new FormData();

formData.append("video",file);



document.getElementById("status").innerHTML =
"Uploading...";



let response = await fetch(

API_URL + "/dub-video?language=" + language,

{

method:"POST",

body:formData

}

);



if(!response.ok){

document.getElementById("status").innerHTML =
"Server Error ❌";

return;

}



let data = await response.json();


console.log(data);



let job_id = data.job_id;



checkProgress(job_id);



}





async function checkProgress(job_id){


let interval = setInterval(async()=>{


let res = await fetch(

API_URL + "/status/" + job_id

);



let data = await res.json();



console.log(data);



document.getElementById("status").innerHTML =

data.status;



let percent = data.progress || 0;



document.getElementById("progress").value =
percent;



document.getElementById("percent").innerHTML =
percent + "%";





if(percent >=100){


clearInterval(interval);



document.getElementById("status").innerHTML =
"Completed ✅";



let download =
document.getElementById("download");



download.href =
API_URL + "/download-video";



download.innerHTML =
"Download Video";



download.style.display =
"block";



}



},2000);



}
