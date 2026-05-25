import enum
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
        proc = subprocess.Popen(
            ["bash", "-c", command_str],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        self._handles[run_id] = handle
        self._procs[run_id] = proc
        thread = threading.Thread(target=self._stream, args=(run_id,), daemon=True)
        thread.start()
        return handle

    def _stream(self, run_id: str) -> None:
        handle = self._handles[run_id]
        proc = self._procs[run_id]
        for line in proc.stdout:
            line = line.rstrip("\n")
            handle.output_lines.append(line)
            if len(handle.output_lines) > MAX_OUTPUT_LINES:
                handle.output_lines = handle.output_lines[-MAX_OUTPUT_LINES:]
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
        self._intentional_stops.discard(run_id)

    def get_handle(self, run_id: str) -> RunHandle | None:
        return self._handles.get(run_id)
