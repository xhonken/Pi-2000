"""Snapshot mutable user directories without following raced links as root."""
import os
import stat
import tarfile


def add_private_tree(archive, source, arcname, include):
    # Each descent is relative to an already-open directory. Path.resolve plus
    # tar.add is insufficient: a user can swap a component between those calls.
    def visit(parent, name, target):
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                         dir_fd=parent)
        except (FileNotFoundError, NotADirectoryError):
            return
        except OSError as exc:
            import errno
            if exc.errno == errno.ELOOP: return  # links are never backup content
            raise
        try:
            metadata = os.fstat(fd)
            directory = stat.S_ISDIR(metadata.st_mode)
            if not directory and not stat.S_ISREG(metadata.st_mode): return
            info = tarfile.TarInfo(target)
            info.type = tarfile.DIRTYPE if directory else tarfile.REGTYPE
            info.size = 0 if directory else metadata.st_size
            info.uid, info.gid = metadata.st_uid, metadata.st_gid
            info.mode, info.mtime = stat.S_IMODE(metadata.st_mode), metadata.st_mtime
            info = include(info)
            if info is None: return
            if directory:
                archive.addfile(info)
                for child in sorted(os.listdir(fd)):
                    visit(fd, child, target + '/' + child)
            else:
                with os.fdopen(os.dup(fd), 'rb') as stream:
                    archive.addfile(info, stream)
        finally:
            os.close(fd)
    visit(None, source, arcname)
