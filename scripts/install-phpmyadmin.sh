#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if ! dpkg-query -W phpmyadmin php8.4-fpm 2>/dev/null | awk 'END {exit NR!=2}'; then
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends phpmyadmin php-fpm php-mysql php-mbstring php-xml php-zip php-gd
fi
id pi2000-phpmyadmin >/dev/null 2>&1 || useradd --system --no-create-home --home-dir /var/lib/pi2000-phpmyadmin --shell /usr/sbin/nologin pi2000-phpmyadmin
install -d -m 755 /opt/win2k-admin/phpmyadmin
install -m 644 "$project_dir"/server/phpmyadmin/* /opt/win2k-admin/phpmyadmin/
if [ ! -f /etc/phpmyadmin/config.inc.php.pi2000-before ]; then
  install -m 600 /etc/phpmyadmin/config.inc.php /etc/phpmyadmin/config.inc.php.pi2000-before
fi
install -m 644 "$project_dir/server/phpmyadmin/config.inc.php" /etc/phpmyadmin/config.inc.php
install -m 644 "$project_dir/server/phpmyadmin/config.header.inc.php" /usr/share/phpmyadmin/config.header.inc.php
install -m 644 "$project_dir/server/phpmyadmin/pi2000-phpmyadmin.service" /etc/systemd/system/
printf '%s\n' 'e /var/lib/pi2000-phpmyadmin 0700 pi2000-phpmyadmin pi2000-phpmyadmin 1h' > /etc/tmpfiles.d/pi2000-phpmyadmin.conf
systemctl daemon-reload
systemctl enable --now pi2000-phpmyadmin
systemctl restart pi2000-phpmyadmin
