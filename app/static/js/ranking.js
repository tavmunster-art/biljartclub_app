let libreData = [];
let bandData = [];
let sortState = {};

async function load(){

    const res = await fetch("/ranking/data");
    const data = await res.json();

    libreData = data.libre;
    bandData  = data.band;

    render("libre", libreData);
    render("band", bandData);
}

function render(id, data){

    let html = `
    <tr>
        <th onclick="sort('${id}','player')">Speler</th>
        <th onclick="sort('${id}','avg')">Moyenne</th>
        <th onclick="sort('${id}','points')">Punten</th>
        <th>Caramboles</th>
        <th>Beurten</th>
    </tr>`;

    data.forEach(r=>{
        html += `
        <tr>
            <td>${r.player}</td>
            <td>${r.avg.toFixed(3)}</td>
            <td>${r.points}</td>
            <td>${r.caramboles}</td>
            <td>${r.turns}</td>
        </tr>`;
    });

    document.getElementById(id).innerHTML = html;
}

function sort(table, key){

    const stateKey = table + "_" + key;
    sortState[stateKey] = !sortState[stateKey];

    const asc = sortState[stateKey];

    let data = table === "libre" ? libreData : bandData;

    data.sort((a,b)=>{

        if(key === "player"){
            return asc
                ? a.player.localeCompare(b.player)
                : b.player.localeCompare(a.player);
        }

        return asc
            ? a[key] - b[key]
            : b[key] - a[key];
    });

    render(table, data);
}

load();