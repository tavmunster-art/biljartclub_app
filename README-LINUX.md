# Biljart Club App voor Linux

Lokale webapplicatie voor biljartverenigingen met Libre- en Bandwedstrijden, mobiele tellers, rankings, historie, rapporten en backups.

## Vereisten

- Linux
- `dpkg`
- `python3`
- `python3-venv`
- Internetverbinding tijdens de eerste installatie om Python-packages in de virtual environment te installeren
- Alle coordinator-, teller- en serverapparaten op hetzelfde WiFi-netwerk of dezelfde hotspot

## Installatie

Installeer het Debian-pakket:

```bash
sudo dpkg -i build/biljartclubapp_1.0.14_amd64.deb
```

Tijdens de installatie worden automatisch een coordinator-wachtwoord en een sessiesleutel aangemaakt. Het coordinator-wachtwoord wordt één keer in de terminal getoond:

```text
Coordinator wachtwoord: <gegenereerd-wachtwoord>
```

Bewaar dit wachtwoord. Bij een bestaande installatie wordt het bestaande wachtwoord niet overschreven.

Start de app:

```bash
biljartclubapp
```

De terminal toont daarna het LAN-adres, bijvoorbeeld:

```text
BiljartClubApp draait op: http://192.168.2.14:5000
Open op teller-laptops: http://192.168.2.14:5000/teller
```

## Coordinator

Open op de coordinator-laptop:

```text
http://SERVER-IP:5000/coordinator
```

Log in met het coordinator-wachtwoord. De coordinator kan spelers en matches beheren, instellingen wijzigen, resultaten invoeren en goedkeuren, backups maken of herstellen, rapporten maken en het seizoen afsluiten.

Het wachtwoord wijzigen:

1. Log in als coordinator.
2. Open het paneel `Coordinator-wachtwoord`.
3. Vul het huidige wachtwoord in.
4. Vul het nieuwe wachtwoord tweemaal in.
5. Gebruik minimaal 8 tekens.

## Teller

Start de app alleen op de coordinator-laptop. Open op ieder teller-apparaat:

```text
http://SERVER-IP:5000/teller
```

Gebruik het LAN-adres dat de coordinator toont. Gebruik op een teller-apparaat niet `localhost` of `127.0.0.1`.

Een teller kan zonder coordinator-login alleen beschikbare matches bekijken, één match claimen, scores en series invoeren en een match afsluiten.

Als verbinding niet lukt, controleer dan:

- hetzelfde normale WiFi-netwerk op alle apparaten;
- geen gastnetwerk of client-isolatie;
- de coordinator-app draait;
- TCP-poort `5000` is toegestaan in de Linux-firewall.

## Wedstrijdworkflow

```text
Coordinator maakt matches
        -> teller claimt één match
        -> teller voert scores in
        -> teller sluit de match af
        -> coordinator controleert
        -> coordinator keurt goed
        -> resultaat wordt definitief opgeslagen
```

Een match kan maar door één teller worden geclaimd. Een tellerresultaat blijft pending totdat de coordinator het goedkeurt.

## Backups en rapporten

De gebruikersgegevens worden opgeslagen in de map van de ingelogde gebruiker:

```text
~/BiljartClup/instance/biljart.db
~/BiljartClup/Backups/
~/BiljartClup/Rapporten/
```

Ook het coordinator-wachtwoord en de sessiesleutel staan in `~/BiljartClup/`.
De virtual environment van het Debian-pakket staat apart onder
`/opt/biljartclub/venv`.

Backups maken of herstellen is geblokkeerd zolang er actieve of pending matches bestaan. Rond wedstrijden eerst af en keur pending resultaten goed.

Seizoen afsluiten maakt eerst een PDF-rapport en backup. Daarna worden de
seizoensresultaten verwijderd. Alleen spelersnamen en de nieuwe startmoyennes
blijven behouden. De nieuwe moyennes worden gebruikt voor doelcaramboles in het
nieuwe seizoen. Resultaten kunnen worden teruggehaald door de backup te herstellen.
Seizoen afsluiten is niet mogelijk zolang actieve of pending matches bestaan.

## Handmatig starten vanuit broncode

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 run.py
```

De app luistert op `0.0.0.0:5000`. Voor gebruik op het lokale netwerk moet de firewall TCP-poort `5000` toestaan.

## Technologie

- Python
- Flask
- Flask-SocketIO
- SQLite
- ReportLab
- HTML, CSS en JavaScript

## Gegevens en privacy

De database, backups, rapporten, sessiesleutel en coordinator-wachtwoord staan buiten de applicatiecode onder `~/BiljartClup`. Deze bestanden horen niet in een publieke GitHub-repository.
