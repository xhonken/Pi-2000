#!/usr/bin/env python3
"""Root-only idempotent system-account integration shared by both installers."""
import grp
import json
import os
from pathlib import Path
import subprocess
import account_service as broker

def write(path, text, mode=0o644):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.new');tmp.write_text(text);tmp.chmod(mode);tmp.replace(path)

def install():
    if os.geteuid()!=0: raise RuntimeError('Run as root.')
    for name in ('pi2000-users','pi2000-terminal'):
        try: grp.getgrnam(name)
        except KeyError: subprocess.run(['groupadd','--system',name],check=True)
    write('/etc/pam.d/pi2000web','@include common-auth\n@include common-account\n@include common-password\n')
    Path('/run/sshd').mkdir(mode=0o755,exist_ok=True)
    subprocess.run(['ssh-keygen','-A'],check=True)
    # Separate listener; ordinary SSH continues to use the distribution configuration.
    write('/etc/pi2000web/sshd_config','''Port 2222
ListenAddress 127.0.0.1
PidFile /run/pi2000-terminal.pid
UsePAM yes
PasswordAuthentication yes
KbdInteractiveAuthentication no
PubkeyAuthentication no
PermitRootLogin no
PermitEmptyPasswords no
AllowGroups pi2000-terminal
DisableForwarding yes
PermitUserRC no
X11Forwarding no
PrintMotd no
MaxAuthTries 3
MaxStartups 4:50:8
''')
    write('/etc/ssh/sshd_config.d/00-pi2000-managed.conf','# Managed Pi-2000 identities use the private loopback listener only.\nDenyGroups pi2000-users\n')
    subprocess.run(['/usr/sbin/sshd','-t'],check=True)
    subprocess.run(['/usr/sbin/sshd','-t','-f','/etc/pi2000web/sshd_config'],check=True)
    effective=subprocess.check_output(['/usr/sbin/sshd','-T'],text=True)
    if not any(line.startswith('denygroups ') and 'pi2000-users' in line.split()[1:] for line in effective.splitlines()):
        raise RuntimeError('The host SSH configuration must include sshd_config.d to deny managed accounts.')
    keys=[p.read_text().strip() for p in sorted(Path('/etc/ssh').glob('ssh_host_*_key.pub'))]
    config=Path('/etc/pi2000web/local-terminal.json')
    data=json.loads(config.read_text()) if config.exists() else {}
    data['host_keys']=keys; write(config,json.dumps(data)+'\n')
    broker.setup_registry()
    if (broker.STATE/'admin.sqlite3').exists():
        with broker.database(broker.STATE/'admin.sqlite3') as db:
            row=db.execute('SELECT * FROM users WHERE is_creator=1').fetchone()
        if row: broker.reserve(dict(row))
    subprocess.run(['systemctl','daemon-reload'],check=True)
    subprocess.run(['systemctl','enable','--now','pi2000-accounts','pi2000-terminal'],check=True)
    subprocess.run(['systemctl','reload','ssh'],check=True)

if __name__=='__main__': install()
