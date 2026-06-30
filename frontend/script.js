const API =
"https://YOUR-RENDER-BACKEND-URL";


async function uploadVideo(){


let file =
document.getElementById(
"videoFile"
).files[0];


let language =
document.getElementById(
"language"
).value;



let formData =
new FormData();


formData.append(
"video",
file
);


formData.append(
"language",
language
);



let response =
await fetch(
API + "/dub-video",
{
method:"POST",
body:formData
}
);



let data =
await response.json();


checkStatus(
data.job_id
);


}



async function checkStatus(job_id){


let timer =
setInterval(async()=>{


let response =
await fetch(
API + "/status/" + job_id
);



let data =
await response.json();



document.getElementById(
"status"
).innerHTML =
data.status;



document.getElementById(
"progress"
).value =
data.progress;



if(data.progress == 100){


clearInterval(timer);


let link =
document.getElementById(
"download"
);


link.href =
API + "/download-video";


link.style.display =
"block";


}


},3000);


}
