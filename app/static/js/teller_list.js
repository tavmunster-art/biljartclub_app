async function claim(id){

    const res = await fetch("/match/claim", {
        method:"POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({match_id:id})
    });

    const data = await res.json();

    if(data.error){
        alert("Al in gebruik");
        return;
    }

    localStorage.setItem("claim_token", data.token);

    window.location.href = "/teller/" + id;
}