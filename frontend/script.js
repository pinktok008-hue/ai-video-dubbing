const API_URL = "https://ai-video-dubbing.onrender.com";


async function uploadVideo(){


const file =
document.getElementById("videoFile").files[0];


const language =
document.getElementById("language").value;



if(!file){

alert("Pehle video select karo");

return;

}



let formData = new FormData();


formData.append("video",file);



document.getElementById("status").innerHTML =
"Uploading...";



try{


let response = await fetch(

API_URL + "/dub-video?language=" + language,

{

method:"POST",

body:formData

}

);



let data = await response.json();



console.log(data);



if(response.ok){



document.getElementById("status").innerHTML =
"VIDEO SAVED ✅";



let download =
document.getElementById("download");



download.href =
API_URL + "/download-video";



download.innerHTML =
"Download Dubbed Video";



download.style.display =
"block";



}

else{


document.getElementById("status").innerHTML =
"Server Error ❌";


}



}

catch(error){


console.log(error);


document.getElementById("status").innerHTML =
"Connection Error ❌";


}



}
