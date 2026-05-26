import enum
import os
import pty
import select
import subprocess
import threading
import uuid
from dataclasses import dataclass, field


class RunStatus(enum.Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class RunHandle:
    run_id: str
    cmd_name: str
    repo_path: str
    repo_name: str
    worktree_path: str
    command: str
    status: RunStatus = RunStatus.RUNNING
    returncode: int | None = None
    output_lines: list = field(default_factory=list)


MAX_OUTPUT_LINES = 5000


class CommandRunner:
    def __init__(self):
        self._handles: dict[str, RunHandle] = {}
        self._procs: dict[str, subprocess.Popen] = {}
        self._master_fds: dict[str, int] = {}
        self._intentional_stops: set[str] = set()
        self.output_callback = None  # Callable[[run_id, line], None]
        self.exit_callback = None    # Callable[[run_id, returncode], None]

    def start(
        self,
        command_str: str,
        cwd: str | None = None,
        cmd_name: str = "",
        repo_path: str = "",
        repo_name: str = "",
        worktree_path: str = "",
    ) -> RunHandle:
        run_id = str(uuid.uuid4())
        handle = RunHandle(
            run_id=run_id,
            cmd_name=cmd_name,
            repo_path=repo_path,
            repo_name=repo_name,
            worktree_path=worktree_path,
            command=command_str,
        )
        source_cmd = (
            "[ -f ~/.zprofile ] && source ~/.zprofile; "
            "[ -f ~/.zshrc ] && source ~/.zshrc; "
            "[ -f ~/.bash_profile ] && source ~/.bash_profile; "
            "[ -f ~/.bashrc ] && source ~/.bashrc; "
        )
        master_fd, slave_fd = pty.openpty()
        proc = subprocess.Popen(
            ["bash", "-c", source_cmd + command_str],
            cwd=cwd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
        )
        os.close(slave_fd)
        self._handles[run_id] = handle
        self._procs[run_id] = proc
        self._master_fds[run_id] = master_fd
        handle.output_lines.append(f"$ {command_str}")
        if self.output_callback:
            self.output_callback(run_id, f"$ {command_str}")
        thread = threading.Thread(target=self._stream, args=(run_id,), daemon=True)
        thread.start()
        return handle

    def _stream(self, run_id: str) -> None:
        handle = self._handles[run_id]
        proc = self._procs[run_id]
        master_fd = self._master_fds[run_id]
        buf = b""
        try:
            while True:
                try:
                    rlist, _, _ = select.select([master_fd], [], [], 0.1)
                except (ValueError, OSError):
                    break
                if rlist:
                    try:
                        chunk = os.read(master_fd, 4096)
                    except OSError:
                        break
                    if not chunk:
                        break
                    buf += chunk
                    while b"\n" in buf:
                        line_bytes, buf = buf.split(b"\n", 1)
                        line = line_bytes.decode("utf-8", errors="replace").rstrip("\r")
                        handle.output_lines.append(line)
                        if len(handle.output_lines) > MAX_OUTPUT_LINES:
                            handle.output_lines = handle.output_lines[-MAX_OUTPUT_LINES:]
                        if self.output_callback:
                            self.output_callback(run_id, line)
                elif proc.poll() is not None:
                    break
        finally:
            try:
                os.close(master_fd)
            except OSError:
                pass
            self._master_fds.pop(run_id, None)
        if buf:
            line = buf.decode("utf-8", errors="replace").rstrip("\r")
            if line:
                handle.output_lines.append(line)
                if self.output_callback:
                    self.output_callback(run_id, line)
        proc.wait()
        handle.returncode = proc.returncode
        if proc.returncode == 0 or run_id in self._intentional_stops:
            handle.status = RunStatus.STOPPED
        else:
            handle.status = RunStatus.ERROR
        self._intentional_stops.discard(run_id)
        if self.exit_callback:
            self.exit_callback(run_id, proc.returncode)

    def terminate(self, run_id: str, intentional: bool = False) -> None:
        if intentional:
            self._intentional_stops.add(run_id)
        proc = self._procs.get(run_id)
        if proc and proc.poll() is None:
            proc.terminate()

    def forget(self, run_id: str) -> None:
        self._handles.pop(run_id, None)
        self._procs.pop(run_id, None)
        fd = self._master_fds.pop(run_id, None)
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        self._intentional_stops.discard(run_id)

    def get_handle(self, run_id: str) -> RunHandle | None:
        return self._handles.get(run_id)
