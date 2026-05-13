let allData = [];
let players = [];

let libreChart;
let bandChart;

async function load(){

    const from = document.getElementById("from").value;
    const to   = document.getElementById("to").value;

    let url = "/dashboard/data";

    if(from) url += "?from=" + from;
    if(to)   url += (from ? "&" : "?") + "to=" + to;

    const res = await fetch(url);
    const data = await res.json();

    allData = data.matches;
    players = data.players;

    const sel = document.getElementById("playerSelect");

    sel.innerHTML = "";

    players.forEach(p=>{
        const opt = document.createElement("option");
        opt.value = String(p);
        opt.text  = p;
        sel.appendChild(opt);
    });

    if(players.length > 0){
        sel.selectedIndex = 0;
    }

    sel.onchange = render;

    setTimeout(render, 0);
}

function render(){

    const sel = document.getElementById("playerSelect");

    if(!sel || sel.selectedIndex === -1){
        return;
    }

    const name = String(sel.value);

    const playerData = allData.filter(r=>String(r.player) === name);

    if(playerData.length === 0){
        document.getElementById("avgText").innerText = "Geen data beschikbaar";
        return;
    }

    const libre = playerData.filter(r=>r.game_type==="libre");
    const band  = playerData.filter(r=>r.game_type==="band");

    draw("libreChart", libre, "Libre", c=>libreChart=c, libreChart);
    draw("bandChart", band, "Band", c=>bandChart=c, bandChart);

    const avgLibre = calcAvg(libre);
    const avgBand  = calcAvg(band);

    document.getElementById("avgText").innerText =
        `Libre: ${avgLibre.toFixed(3)}   |   Band: ${avgBand.toFixed(3)}`;
}

function calcAvg(data){

    if(data.length === 0) return 0;

    let sum = 0;
    data.forEach(d=> sum += d.avg);

    return sum / data.length;
}

function draw(id, data, label, setChart, chart){

    const ctx = document.getElementById(id);

    if(chart) chart.destroy();

    const labels = data.map((_,i)=>i+1);
    const values = data.map(d=>d.avg);

    const trend = trendline(values);

    const newChart = new Chart(ctx,{
        type:"line",
        data:{
            labels,
            datasets:[
                {
                    label: label,
                    data: values
                },
                {
                    label: "Trend",
                    data: trend,
                    borderDash:[5,5]
                }
            ]
        }
    });

    setChart(newChart);
}

function trendline(data){

    const n = data.length;
    if(n === 0) return [];

    let sumX=0, sumY=0, sumXY=0, sumXX=0;

    for(let i=0;i<n;i++){
        sumX += i;
        sumY += data[i];
        sumXY += i*data[i];
        sumXX += i*i;
    }

    const slope = (n*sumXY - sumX*sumY) / (n*sumXX - sumX*sumX || 1);
    const intercept = (sumY - slope*sumX) / n;

    return data.map((_,i)=> intercept + slope*i);
}

load();