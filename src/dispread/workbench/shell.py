"""Fresh child process acquires its PTY before exec; no Python after fork."""

import fcntl
import os
import termios

if __name__ == "__main__":
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)
    os.execve("/bin/bash", ["bash", "-i"], os.environ)
