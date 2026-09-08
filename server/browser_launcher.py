"""Join the delegated resource group before starting any browser descendants."""
import os
from pathlib import Path
import sys

if __name__ == '__main__':
    (Path(sys.argv[1]) / 'cgroup.procs').write_text(str(os.getpid()))
    os.execv(sys.argv[2], sys.argv[2:])
