

// MATCHES
async function createMatches(){

    const players = [...document.querySelectorAll('input[name="players"]:checked')]
        .map(cb => cb.value);

    if(players.length < 2){
        alert("Minimaal 2 spelers");
        return;
    }

    const res = await fetch("/matches/create", {
        method:"POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({players})
    });

    const data = await res.json();

    if(data.unmatched && data.unmatched.length > 0){

        sessionStorage.setItem(
            "msg",
            "Geen tegenstander voor (" +
        data.unmatched.length +
        "): " +
        data.unmatched.join(", ")
                );
    }

    location.reload();
}

async function approve(id){

    await fetch("/match/approve", {
        method:"POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({
            match_id:id,
            manual_date:
                document.getElementById("manualDate").value
        })
    });

    location.reload();
}

// DELETE
async function deletePlayer(name){

    if(!confirm("Verwijder speler: " + name + "?")) return;

    await fetch("/players/delete", {
        method:"POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({name})
    });

    location.reload();
}

// MANUAL
let currentMatchId = null;

// HANDMATIGE MATCH
async function createManual(){

    const p1 = document.getElementById("p1").value;
    const p2 = document.getElementById("p2").value;
    const game = document.getElementById("gameType").value;

    if(p1 === p2){
        alert("Kies 2 verschillende spelers");
        return;
    }

    const res = await fetch("/matches/manual", {
        method:"POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({
            player1: p1,
            player2: p2,
            game_type: game
        })
    });

    const data = await res.json();

    if(data.error){
        alert(data.error);
        return;
    }

    location.reload();
}

function manualEntry(id){
    currentMatchId = id;

    document.getElementById("m_total1").value = "";
    document.getElementById("high_run1").value = "";
    document.getElementById("m_total2").value = "";
    document.getElementById("high_run2").value = "";
    document.getElementById("m_turns").value = "";

    document.getElementById("manualModal").style.display = "block";
}

function closeManual(){
    document.getElementById("manualModal").style.display = "none";
}

async function saveManual(){

    const t1 = parseInt(m_total1.value);
    const t2 = parseInt(m_total2.value);
    const tr = parseInt(m_turns.value);


    if(isNaN(t1) || isNaN(t2) || isNaN(tr)){
        alert("Ongeldige invoer");
        return;
    }

    try {
        const res = await fetch("/manual/result", {
            method:"POST",
            headers: {"Content-Type":"application/json"},
            body: JSON.stringify({
                match_id: currentMatchId,
                total1: t1,
                total2: t2,
                turns: tr,
                high_run1:
                parseInt(document.getElementById("high_run1").value) || 0,

                high_run2:
                parseInt(document.getElementById("high_run2").value) || 0,

                manual_date: document.getElementById("manualDate").value
            })
        });

        const data = await res.json();

        if(!res.ok || data.error){
            alert(data.error || "Opslaan mislukt");
            return;
        }

        location.reload();
    } catch(error) {
        alert("Opslaan mislukt: geen verbinding met de server");
    }
}

// SETTINGS

async function loadTurns(){

    const res = await fetch("/settings/get");
    const data = await res.json();

    document.getElementById("turnsInput").value = data.turns;
}

async function saveTurns(){

    const turns = parseInt(document.getElementById("turnsInput").value) || 20;

    await fetch("/settings/set", {
        method:"POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({turns})
    });

    // 🔥 waarde direct terugzetten (voorkomt leeg veld)
    document.getElementById("turnsInput").value = turns;

    location.reload();
}

async function changePassword(){
    const currentPassword = document.getElementById("currentPassword").value;
    const newPassword = document.getElementById("newPassword").value;
    const confirmation = document.getElementById("confirmPassword").value;

    const res = await fetch("/coordinator/password", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            current_password: currentPassword,
            new_password: newPassword,
            confirmation: confirmation
        })
    });
    const data = await res.json();

    if(data.error){
        alert(data.error);
        return;
    }

    alert("Wachtwoord gewijzigd");
    document.getElementById("currentPassword").value = "";
    document.getElementById("newPassword").value = "";
    document.getElementById("confirmPassword").value = "";
}

// BACKUP
async function makeBackup(){
    const res = await fetch("/backup/create", {method:"POST"});
    const data = await res.json();

    if(data.error){
        alert(data.error);
        return;
    }

    loadBackups();
}

async function loadBackups(){
    const res = await fetch("/backup/list");
    const data = await res.json();

    backupList.innerHTML = "";
    data.files.forEach(f=>{
        backupList.innerHTML += `<option>${f}</option>`;
    });
}

async function restoreBackup(){

    const res = await fetch("/backup/restore", {
        method:"POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({file: backupList.value})
    });

    const data = await res.json();

    if(data.error){
        alert(data.error);
        return;
    }

    location.reload();
}

// REPORT
async function generateReport(){
    await fetch("/report/generate", {method:"POST"});
    alert("Rapport gemaakt");
}

// SEASON
async function closeSeason(){

    if(!confirm("Seizoen afsluiten?")) return;

    await fetch("/season/close", {method:"POST"});
    location.reload();
}

// INIT
window.onload = function(){

    // ==============================
    // INSTELLINGEN
    // ==============================

    loadTurns();

    loadBackups();

    // ==============================
    // MELDINGEN
    // ==============================

    const msg = sessionStorage.getItem("msg");

    if(msg){

        document.getElementById("msg").innerText = msg;

        sessionStorage.removeItem("msg");
    }

    // ==============================
    // DATUM INITIALISEREN
    // ==============================

    const dateInput =
        document.getElementById("manualDate");

    if(dateInput){

        const today = new Date();

        const yyyy = today.getFullYear();

        const mm = String(
            today.getMonth() + 1
        ).padStart(2, "0");

        const dd = String(
            today.getDate()
        ).padStart(2, "0");

        const todayString = `${yyyy}-${mm}-${dd}`;

        // opgeslagen datum
        let savedDate =
            sessionStorage.getItem("manualDate");

        // geen opgeslagen datum
        if(!savedDate){

            savedDate = todayString;
        }

        

        dateInput.value = savedDate;

        // opslaan bij wijziging
        dateInput.addEventListener(
            "change",
            function(){

                sessionStorage.setItem(
                    "manualDate",
                    this.value
                );
            }
        );
    }
}

async function shutdownServer(){

    if(!confirm("Server afsluiten?")) return;

    await fetch("/shutdown", {
        method:"POST"
    });

    alert("Server wordt afgesloten");
}

// AUTO REFRESH

let lastActivity = Date.now();

// gebruiker actief?
document.addEventListener("input", () => {
    lastActivity = Date.now();
});

document.addEventListener("click", () => {
    lastActivity = Date.now();
});

// auto refresh alleen bij inactiviteit
setInterval(() => {

    // popup open?
    const modal =
        document.getElementById("manualModal");

    if(modal && modal.style.display === "block"){
        return;
    }

    // laatste activiteit minder dan 10 sec geleden?
    if(Date.now() - lastActivity < 10000){
        return;
    }

    location.reload();

}, 5000);