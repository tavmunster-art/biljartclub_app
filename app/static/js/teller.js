let total1 = 0;
let total2 = 0;
let turns = [];
let current1 = 0;
let current2 = 0;

const target1 = TARGET1;
const target2 = TARGET2;

// punten toevoegen binnen beurt
function add(player, value){

    if(player === 1){
        current1 = Math.max(0, current1 + value);
        document.getElementById("t1").innerText = total1 + current1;
    } else {
        current2 = Math.max(0, current2 + value);
        document.getElementById("t2").innerText = total2 + current2;
    }
}

// volgende beurt opslaan
function nextTurn(){

    turns.push({p1: current1, p2: current2});

    total1 += current1;
    total2 += current2;

    current1 = 0;
    current2 = 0;

    updateUI();
}

// undo laatste beurt
function undo(){

    if(turns.length === 0) return;

    const last = turns.pop();

    total1 -= last.p1;
    total2 -= last.p2;

    updateUI();
}

// UI update
function updateUI(){

    document.getElementById("t1").innerText = total1;
    document.getElementById("t2").innerText = total2;

    document.getElementById("turns").innerText = turns.length;

    // kleur bij target
    document.getElementById("t1").style.color =
        total1 >= target1 ? "green" : "black";

    document.getElementById("t2").style.color =
        total2 >= target2 ? "green" : "black";
}

// afsluiten
let finished = false;

function finish(){

    if(finished) return;
    finished = true;

    fetch("/match/finish", {
        method:"POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({
            match_id: MATCH_ID,
            claim_token: localStorage.getItem("claim_token"),
            total1: total1,
            total2: total2,
            turns: turns.length
        })
    })
    .then(res => res.json())
    .then(data => {

        if(data.error){
            alert(data.error);
            return;
        }

        alert("Match opgeslagen");
        localStorage.removeItem("claim_token");
        window.location.href = "/teller";
    });
}


function addSeries(player){

    let input = player === 1 ? "s1" : "s2";
    let val = parseInt(document.getElementById(input).value);

    if(isNaN(val) || val <= 0){
        alert("Ongeldige serie");
        return;
    }

    add(player, val);

    document.getElementById(input).value = "";
}