#!/bin/bash

# ==========================================
# BiljartClubApp Debian Package Builder
# ==========================================
command -v dpkg-deb >/dev/null || {
    echo "dpkg-deb niet gevonden."
    exit 1
}

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

APPNAME="biljartclubapp"
DISPLAY_NAME="BiljartClubApp"
VERSION="1.0.14"
ARCH="amd64"

BUILD_DIR="$SCRIPT_DIR/build"
PKG_DIR="${BUILD_DIR}/${APPNAME}_${VERSION}_${ARCH}"

echo "---------------------------------------"
echo " BiljartClubApp Debian Builder"
echo "---------------------------------------"

# Oude build verwijderen
rm -rf "$BUILD_DIR"

# Mappenstructuur aanmaken
mkdir -p "$PKG_DIR/DEBIAN"
mkdir -p "$PKG_DIR/opt/biljartclub"
mkdir -p "$PKG_DIR/usr/share/applications"
mkdir -p "$PKG_DIR/usr/share/pixmaps"

##########################################################
echo "Controlbestand maken..."

cat > "$PKG_DIR/DEBIAN/control" <<EOF
Package: $APPNAME
Version: $VERSION
Section: games
Priority: optional
Architecture: $ARCH
Maintainer: Teun
Depends: python3, python3-venv
Description: BiljartClubApp
 Biljartadministratie voor verenigingen.
 Inclusief spelersbeheer, wedstrijden,
 ranking, historie, rapportage en backups.
EOF

echo "Controlbestand gereed."

################################################################
echo "Desktopbestand maken..."

cat > "$PKG_DIR/usr/share/applications/biljartclubapp.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=BiljartClubApp
GenericName=BiljartClub
Comment=Begeleiding en administratie van biljartwedstrijden
Exec=/usr/bin/biljartclubapp
Icon=biljartclubapp
Terminal=false
Categories=Game;Sports;
Keywords=biljart;billiards;club;wedstrijd;score;
StartupNotify=true
EOF

echo "Desktopbestand gereed."

######################################################################

echo "Programma kopiëren..."

rsync -av \
    --exclude="__pycache__" \
    --exclude="*.pyc" \
    --exclude=".git" \
    "$SCRIPT_DIR/app/" \
    "$PKG_DIR/opt/biljartclub/app/"

cp "$SCRIPT_DIR/run.py" "$PKG_DIR/opt/biljartclub/"
cp "$SCRIPT_DIR/requirements.txt" "$PKG_DIR/opt/biljartclub/"
cp "$SCRIPT_DIR/README-LINUX.md" "$PKG_DIR/opt/biljartclub/README.md"

echo "Programma gekopieerd."

#####################################################################

echo "Startscript maken..."

mkdir -p "$PKG_DIR/usr/bin"

cat > "$PKG_DIR/usr/bin/biljartclubapp" << 'EOF'
#!/bin/bash

#!/bin/bash

APP_DIR="/opt/biljartclub"
VENV_DIR="$APP_DIR/venv"
DATA_DIR="$HOME/BiljartClubApp"

mkdir -p "$DATA_DIR"
mkdir -p "$DATA_DIR/instance"
mkdir -p "$DATA_DIR/reports"
mkdir -p "$DATA_DIR/backups"

cd "$APP_DIR"

"$VENV_DIR/bin/python" run.py &
SERVER_PID=$!

sleep 3

SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
SERVER_IP=${SERVER_IP:-127.0.0.1}

echo "BiljartClubApp draait op: http://${SERVER_IP}:5000"
echo "Open op teller-laptops: http://${SERVER_IP}:5000/teller"

wait $SERVER_PID
EOF

chmod 755 "$PKG_DIR/usr/bin/biljartclubapp"

echo "Startscript gereed."
##################################################################

echo "Post-install script maken..."

cat > "$PKG_DIR/DEBIAN/postinst" << 'EOF'
#!/bin/bash

set -e

APP_DIR="/opt/biljartclub"
VENV_DIR="$APP_DIR/venv"
USER_NAME=${SUDO_USER:-$(logname 2>/dev/null)}
USER_HOME=$(getent passwd "$USER_NAME" | cut -d: -f6)
USER_HOME=${USER_HOME:-/root}
DATA_DIR="$USER_HOME/BiljartClubApp"

mkdir -p "$DATA_DIR"
mkdir -p "$DATA_DIR/instance"
mkdir -p "$DATA_DIR/reports"
mkdir -p "$DATA_DIR/backups"

if [ ! -s "$DATA_DIR/coordinator.password" ]; then
    umask 077
    python3 -c 'import secrets; print(secrets.token_urlsafe(12))' > "$DATA_DIR/coordinator.password"
fi

if [ ! -s "$DATA_DIR/session.secret" ]; then
    umask 077
    python3 -c 'import secrets; print(secrets.token_hex(32))' > "$DATA_DIR/session.secret"
fi

if [ -n "$USER_NAME" ]; then
    chown -R "$USER_NAME:$USER_NAME" "$DATA_DIR"
fi

chmod 700 "$DATA_DIR" "$DATA_DIR/instance" "$DATA_DIR/reports" "$DATA_DIR/backups"

python3 -m venv "$VENV_DIR"

"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt"

chmod 600 "$DATA_DIR/coordinator.password" "$DATA_DIR/session.secret"

echo "Coordinator wachtwoord: $(cat "$DATA_DIR/coordinator.password")"

echo "Installatie voltooid."

exit 0
EOF

chmod 755 "$PKG_DIR/DEBIAN/postinst"

echo "Post-install script gereed."

echo
echo "Debian package bouwen..."

dpkg-deb --build \
    "$PKG_DIR" \
    "$BUILD_DIR/${APPNAME}_${VERSION}_${ARCH}.deb"

echo
echo "Pakket gemaakt:"
echo "${APPNAME}_${VERSION}_${ARCH}.deb"

echo "$BUILD_DIR/${APPNAME}_${VERSION}_${ARCH}.deb"
