document.getElementById('login').onsubmit=async event=>{
 event.preventDefault();const field=document.getElementById('password'), message=document.getElementById('message');
 const password=field.value;field.value='';message.textContent='…';
 try{const response=await fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password}),signal:AbortSignal.timeout(15000)});
 if(response.ok)location.replace('/');else message.textContent=response.status===429?'Bitte später erneut versuchen.':'Anmeldung fehlgeschlagen.';
 }catch(_){message.textContent='Verbindung fehlgeschlagen.';}
};
