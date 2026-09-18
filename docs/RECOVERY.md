# Backup recovery and encrypted export

This runbook applies to Alpha 6 and later. It is an OS
administrator operation; a web administrator cannot restore host accounts.
Rehearse on a disposable installation before relying on it for disaster recovery.

## What a backup contains

Format 2 archives retain application SQLite data (with login tokens removed),
private uploaded files, Browser profiles, Git workspaces and credential encryption
material. They also include the managed-account registry, generation key, managed
password records and managed homes, with original UID/GID and ordinary permission
bits recorded in private metadata. Application code/assets follow the installed
deployment manifests, including nested Python modules. SHA-256 is verified before
extraction and SQLite integrity and foreign keys are checked.

These archives contain secrets and must remain root-only. They are not full disk
images: running processes, linked OS accounts/homes, external databases, MariaDB
server data, host/network configuration, symlinks, special files, ACLs, extended
attributes and set-ID bits are not restored. Back up those separately as needed.
Checksums detect accidental corruption; they do not authenticate an archive from
an untrusted source. Only restore archives from a trusted backup destination.

Daily snapshots freeze Browser activity and lock application file operations.
Arbitrary programs in a managed home are not application-transaction-aware: finish
terminal, build and upload work before creating the recovery snapshot used below.
Application snapshots are not a checkpoint of an executing job.

## Inspect, then restore

1. Install the matching application build and its account/SSH policy on the target.
   Do not initialize unrelated managed users there. Preserve linked OS identities
   separately. Keep the original archive and its `.tar.sha256` file together.
2. Inspect without changing application data:

   ```sh
   sudo pi2000web recovery plan /var/backups/pi2000/ARCHIVE.tar --output /root/recovery-preview.json
   ```

   For a source installation, substitute `./scripts/restore-backup.sh` for
   `pi2000web recovery` throughout. The wrapper invokes the installed recovery code.
   Review the account list and blockers. An occupied UID/home, different managed
   identity, missing ownership metadata or unmapped linked account blocks restore.
   Current managed identities absent from the archive also block replacement.
3. Finish all users' jobs and close their sessions. In an agreed maintenance
   window, stop the writers explicitly:

   ```sh
   sudo systemctl stop pi2000-backup.timer pi2000-backup.service pi2000-admin pi2000-sessions pi2000-arduino pi2000-accounts pi2000-terminal pi2000-phpmyadmin
   sudo pi2000web recovery plan /var/backups/pi2000/ARCHIVE.tar --output /root/recovery-final.json
   ```

   Use a new output filename for each plan. Generate the final plan after stopping
   services; database checkpoints or identity changes invalidate an older plan.
4. Review the final plan and supply its full `id`:

   ```sh
   sudo pi2000web recovery apply /var/backups/pi2000/ARCHIVE.tar --plan /root/recovery-final.json --confirm PLAN_ID
   ```

   Apply refuses active services, managed-user processes, changed target state and
   a mismatched installed build. It restores managed identities with their original
   IDs, homes, shell/terminal policy and password records. Linked OS accounts and
   unrelated OS group memberships are preserved. Previous directories and a
   private operation journal remain under `/var/backups/pi2000/recovery-*`.
5. Services remain stopped. Inspect restored owners/modes and identity mappings,
   then start `pi2000-accounts`, `pi2000-terminal`, `pi2000-sessions`,
   `pi2000-arduino`, `pi2000-phpmyadmin`, `pi2000-admin` and `pi2000-backup.timer`.
   Run the installer doctor and verify login, per-user isolation, files and a
   managed terminal. Users must log in again; executing jobs do not resume.

Recoverable application exceptions trigger rollback of replaced directories and
managed identity changes. A power failure or forced termination requires manual
inspection of the private journal and retained directories; this is not an atomic
whole-machine transaction. Recovery currently requires the data/home destinations
and rollback directory to share a filesystem; a separate `/home` mount needs
manual staging and is rejected before account/data changes. Format 1 archives
remain extractable/inspectable but lack managed-home metadata for automated apply.

## Export to an external mounted filesystem

Install `age` (included as a dependency of new installation builds). On a trusted
recovery computer, create an age identity using `age-keygen -o recovery-key.txt`.
Keep the secret identity off the Pi and outside its backups; configure only the
printed public `age1...` recipient on the Pi. No destination or recovery key is
created automatically.

```sh
sudo pi2000web recovery export /var/backups/pi2000/ARCHIVE.tar --to /media/backup/ARCHIVE.tar.age --recipient age1PUBLIC_RECIPIENT
```

Export first verifies the original archive, encrypts with the official age CLI,
and creates a checksum beside the ciphertext. It refuses overwrites, a missing
destination and the same filesystem as the source. `--allow-same-device` exists
only for explicit local rehearsals. A different filesystem alone does not prove
protection from the same physical disk failing; select an actual external device
and verify its mount before export. Scheduled off-device rotation is not configured.

On the recovery computer, verify the ciphertext checksum, decrypt, and create the
plaintext checksum needed by the recovery verifier:

```sh
sha256sum --check ARCHIVE.tar.age.sha256
umask 077
age --decrypt --identity recovery-key.txt --output ARCHIVE.tar ARCHIVE.tar.age
sha256sum ARCHIVE.tar > ARCHIVE.tar.sha256
```

Rehearse decryption periodically and retain a second protected copy of the secret
identity. See [age's upstream documentation](https://github.com/FiloSottile/age).
