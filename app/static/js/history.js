async function load(){

    const res = await fetch("/history/data");
    const data = await res.json();

    const libre = data.rows.filter(r=>r.game_type==="libre");
    const band  = data.rows.filter(r=>r.game_type==="band");

    render("libre", libre);
    render("band", band);
}

function render(id, data){

    let html = `
    <tr>
        <th>Datum</th>
        <th>Speler</th>
        <th>Tegenstander</th>
        <th>Caramboles</th>
        <th>Moyenne</th>
        <th>Punten</th>
    </tr>`;

    data.forEach(r=>{
        html += `
        <tr>
            <td>${r.ts_recorded}</td>
            <td>${r.player}</td>
            <td>${r.opponent}</td>
            <td>${r.total}</td>
            <td>${(r.avg || 0).toFixed(3)}</td>
            <td>${r.points || 0}</td>
        </tr>`;
    });

    document.getElementById(id).innerHTML = html;
}

load();