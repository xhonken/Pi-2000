"""Run one isolated Chromium desktop, including its private display and audio."""
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time


def main():
    os.umask(0o077)
    home = Path('/home/browser')
    runtime = Path('/run/browser')
    deps = Path('/opt/browser-deps')
    children = []
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    def launch(args):
        child = subprocess.Popen(args)
        children.append(child)
        return child

    def binary(name):
        extra = deps / 'usr/bin' / name
        return str(extra) if extra.exists() else '/usr/bin/' + name

    def wait_for(path, child):
        for _ in range(100):
            if path.exists():
                return
            if child.poll() is not None or stopping:
                raise RuntimeError('Browser component stopped before becoming ready')
            time.sleep(0.1)
        raise RuntimeError('Browser component startup timed out')

    for directory in (home / 'Downloads', home / '.config/openbox', runtime / 'pulse'):
        directory.mkdir(parents=True, exist_ok=True)
    display_name = os.environ.get('BROWSER_DISPLAY', ':99')
    os.environ.update(DISPLAY=display_name, XAUTHORITY=str(runtime / 'Xauthority'),
                      PULSE_SERVER='unix:/run/browser/pulse/native',
                      PULSE_RUNTIME_PATH='/run/browser/pulse',
                      XDG_RUNTIME_DIR=str(runtime))
    (runtime / 'Xauthority').touch(mode=0o600)
    subprocess.run(['/usr/bin/xauth', '-f', str(runtime / 'Xauthority'), 'add', display_name, '.', secrets.token_hex(16)], check=True)
    (home / '.config/openbox/rc.xml').write_text('''<?xml version="1.0"?>
<openbox_config xmlns="http://openbox.org/3.4/rc"><desktops><number>1</number></desktops>
<applications><application class="*"><decor>no</decor><maximized>yes</maximized></application></applications>
<keyboard><keybind key="A-F4"><action name="Close"/></keybind></keyboard></openbox_config>''')
    (runtime / 'pulse.pa').write_text('''load-module module-native-protocol-unix socket=/run/browser/pulse/native auth-anonymous=1
load-module module-null-sink sink_name=browser rate=48000 channels=2
set-default-sink browser
set-default-source browser.monitor
''')
    # A private tmpfs keeps X's Unix socket out of the host filesystem. Xauthority
    # also protects its abstract socket, which shares the host's network namespace.
    try:
        # Xvfb fixes its RandR maximum at startup. Reserve enough room for
        # the stream client's 4080-pixel limit in either orientation; the
        # actual framebuffer is resized to the client when it connects.
        display = launch([binary('Xvfb'), display_name, '-screen', '0', '4096x4096x24', '-nolisten', 'tcp',
                          '-auth', str(runtime / 'Xauthority'), '-noreset', '-s', '0', '-dpms', '+extension', 'RANDR'])
        wait_for(Path('/tmp/.X11-unix/X' + display_name[1:]), display)
        subprocess.run(['/usr/bin/dbus-update-activation-environment', 'DISPLAY', 'XAUTHORITY', 'XDG_RUNTIME_DIR'], check=False)
        pulse_args = [binary('pulseaudio'), '-n', '--daemonize=no', '--exit-idle-time=-1',
                      '--disallow-exit', '--disable-shm=yes', '--log-level=error', '-F', str(runtime / 'pulse.pa')]
        module_dirs = list((deps / 'usr/lib').glob('pulse-*/modules'))
        if module_dirs:
            pulse_args.append('--dl-search-path=' + str(module_dirs[0]))
        pulse = launch(pulse_args)
        wait_for(runtime / 'pulse/native', pulse)
        wm = launch(['/usr/bin/openbox', '--config-file', str(home / '.config/openbox/rc.xml')])
        key_path = home / '.keyring-key'
        if not key_path.exists():
            key_path.write_text(secrets.token_urlsafe(48))
            key_path.chmod(0o600)
        keyring = subprocess.Popen(['/usr/bin/gnome-keyring-daemon', '--foreground', '--unlock',
                                    '--components=secrets', '--control-directory=/run/browser/keyring'],
                                   stdin=subprocess.PIPE)
        children.append(keyring)
        keyring.stdin.write(key_path.read_bytes())
        keyring.stdin.close()
        wait_for(runtime / 'keyring/control', keyring)
        chromium_args = ['/usr/bin/chromium', '--user-data-dir=/home/browser/chromium', '--no-first-run',
                         '--no-default-browser-check', '--start-maximized', '--restore-last-session',
                         '--disable-session-crashed-bubble', '--disable-features=WebRtcPipeWireCamera', '--password-store=gnome-libsecret', '--lang=en-GB']
        chromium = launch(chromium_args)
        streamer = launch([sys.executable, '-m', 'selkies', '--unix-socket=/run/browser/stream.sock',
                           '--subfolder=/api/browser/view', '--enable-basic-auth=false',
                           '--encoder=h264enc', '--use-cpu=true', '--framerate=30,8-30',
                           '--audio-device-name=browser.monitor', '--audio-enabled=true',
                           '--microphone-enabled=false|locked', '--webcam-enabled=false|locked',
                           '--gamepad-enabled=false|locked', '--command-enabled=false|locked',
                           '--enable-sharing=false', '--second-screen=false', '--enable-resize=true',
                           '--file-manager-path=/home/browser/Downloads', '--file-transfers=upload,download',
                           '--ui-title=Browser', '--ui-show-logo=false', '--ui-sidebar-show-sharing=false',
                           '--ui-sidebar-show-apps=false', '--ui-sidebar-show-gamepads=false',
                           '--ui-sidebar-show-webcam=false', '--ui-sidebar-show-gaming-mode=false',
                           '--auto-gpu=false'])
        while not stopping and not (runtime / 'stop').exists():
            if any(child.poll() is not None for child in (display, pulse, wm, streamer)):
                raise RuntimeError('Browser display, audio or streaming component stopped')
            if chromium.poll() is not None:
                children.remove(chromium)
                chromium = launch(chromium_args)
            time.sleep(0.3)
    finally:
        # Close Chromium first so that it can save its tabs and profile.
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=4)
            except subprocess.TimeoutExpired:
                child.kill()
        for child in children:
            child.wait()


if __name__ == '__main__':
    main()
