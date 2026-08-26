let currentTournamentId = null;

function createTournament() {
  const name = document.getElementById("tName").value.trim();
  const gameType = document.getElementById("tGameType").value;
  const maxTurns = parseInt(document.getElementById("tMaxTurns").value, 10);

  const players = Array.from(
    document.querySelectorAll('input[name="tplayers"]:checked')
  ).map(el => el.value);

  document.getElementById("createMsg").textContent = "";

  fetch("/tournament/create", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name,
      game_type: gameType,
      max_turns: maxTurns,
      players
    })
  })
    .then(r => r.json())
    .then(data => {
      if (data.error) {
        document.getElementById("createMsg").textContent = data.error;
        return;
      }
      location.href = `/tournament?open=${data.id}`;
    });
}

function deleteTournament(id) {
  if (!confirm("Tournooi verwijderen?")) return;

  fetch(`/tournament/${id}/delete`, { method: "POST" })
    .then(r => r.json())
    .then(() => location.reload());
}

function loadTournament(id) {
  currentTournamentId = id;

  fetch(`/tournament/${id}/data`)
    .then(r => r.json())
    .then(renderTournament);
}

function renderTournament(data) {
  const el = document.getElementById("tournamentDetail");

  if (data.error) {
    el.innerHTML = `<p style="color:red">${data.error}</p>`;
    return;
  }

  const t = data.tournament;

  let html = `<h2>${t.name} (${t.game_type}, max ${t.max_turns} beurten)</h2>`;

  if (data.champion) {
    html += `<p class="champion">🏆 Tournooiwinnaar: ${data.champion}</p>`;
  }

  if (data.report) {
    html += `<p><a href="/reports/${data.report}" target="_blank">📄 Tournooirapport downloaden</a></p>`;
  }

  const groupNumbers = Object.keys(data.groups).map(Number).sort((a, b) => a - b);

  for (const groupNo of groupNumbers) {
    const group = data.groups[groupNo];
    html += renderGroup(`Groep ${groupNo}`, group, groupNo);
  }

  const allGroupsDone = groupNumbers.every(g => {
    const matches = data.groups[g].matches;
    return matches.length && matches.every(m => m.status === "done");
  });

  if (!data.final && allGroupsDone && groupNumbers.length > 1) {
    html += `<button type="button" onclick="startFinal()">Finale starten (groepswinnaars)</button>`;
  }

  if (data.final) {
    html += renderGroup("Finale", data.final, 0);

    const finalDone = data.final.matches.every(m => m.status === "done");
    if (finalDone && t.status !== "done") {
      html += `<button type="button" onclick="finishTournament()">Tournooi afsluiten</button>`;
    }
  } else if (allGroupsDone && t.status !== "done" && groupNumbers.length === 1) {
    html += `<button type="button" onclick="finishTournament()">Tournooi afsluiten</button>`;
  }

  el.innerHTML = html;
}

function renderGroup(title, group, groupNo) {
  let html = `<div class="group-box"><h3>${title}</h3>`;

  html += `<table class="standings"><tr><th>Speler</th><th>Punten</th><th>Weerstand</th><th>Moyenne</th></tr>`;
  for (const s of group.standings) {
    html += `<tr><td>${s.player}</td><td>${s.points}</td><td>${s.weerstand}</td><td>${s.seed_avg}</td></tr>`;
  }
  html += `</table>`;

  for (const m of group.matches) {
    html += renderMatch(m);
  }

  html += `</div>`;
  return html;
}

function renderMatch(m) {
  if (m.status === "done") {
    return `<div class="match-row done">
      ${m.player1} ${m.caramboles1} (${m.points1}p) - ${m.caramboles2} ${m.player2} (${m.points2}p)
      ${m.winner === "draw" ? "gelijk" : ""}
    </div>`;
  }

  return `<div class="match-row" id="match-${m.id}" data-target1="${m.target1}" data-target2="${m.target2}">
    <span>${m.player1} (te maken: ${m.target1})</span>
    <input type="number" min="0" placeholder="gemaakt" id="c1-${m.id}">
    vs
    <span>${m.player2} (te maken: ${m.target2})</span>
    <input type="number" min="0" placeholder="gemaakt" id="c2-${m.id}">
    <input type="number" min="1" placeholder="in beurt" id="tr-${m.id}">
    <button type="button" onclick="submitResult(${m.id})">Opslaan</button>
  </div>`;
}

function submitResult(matchId) {
  const row = document.getElementById(`match-${matchId}`);
  const target1 = parseInt(row.dataset.target1, 10);
  const target2 = parseInt(row.dataset.target2, 10);

  const caramboles1 = parseInt(document.getElementById(`c1-${matchId}`).value, 10) || 0;
  const caramboles2 = parseInt(document.getElementById(`c2-${matchId}`).value, 10) || 0;
  const trValue = document.getElementById(`tr-${matchId}`).value;
  const turn = trValue === "" ? null : parseInt(trValue, 10);

  fetch(`/tournament/${currentTournamentId}/result`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      match_id: matchId,
      caramboles1,
      caramboles2,
      turn_reached1: caramboles1 >= target1 ? turn : null,
      turn_reached2: caramboles2 >= target2 ? turn : null,
      turns_played: turn
    })
  })
    .then(r => r.json())
    .then(data => {
      if (data.error) {
        alert(data.error);
        return;
      }
      loadTournament(currentTournamentId);
    });
}

function startFinal() {
  fetch(`/tournament/${currentTournamentId}/final`, { method: "POST" })
    .then(r => r.json())
    .then(data => {
      if (data.error) {
        alert(data.error);
        return;
      }
      loadTournament(currentTournamentId);
    });
}

function finishTournament() {
  fetch(`/tournament/${currentTournamentId}/finish`, { method: "POST" })
    .then(r => r.json())
    .then(data => {
      if (data.error) {
        alert(data.error);
        return;
      }
      loadTournament(currentTournamentId);
    });
}

const openId = new URLSearchParams(location.search).get("open");
if (openId) {
  loadTournament(parseInt(openId, 10));
}
