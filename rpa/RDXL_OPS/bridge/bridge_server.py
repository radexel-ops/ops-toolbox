"""
Bridge Server - PTY-based Terminal Connection

Manages pseudo-terminal connections for Claude Code CLI sessions.
Provides real-time streaming of CLI output to WebSocket clients.
"""

import asyncio
import os
import pty
import subprocess
import signal
import logging
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TerminalSession:
    """Represents an active terminal session."""
    session_id: str
    pid: int
    fd: int  # File descriptor for PTY master
    working_dir: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


class BridgeServer:
    """
    PTY-based bridge server for Claude Code CLI.

    Manages terminal sessions and provides async streaming
    of command output.
    """

    def __init__(self):
        self._sessions: Dict[str, TerminalSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        session_id: str,
        working_dir: str = "/home/vibeops/vibeops"
    ) -> TerminalSession:
        """
        Create a new terminal session.

        Args:
            session_id: Unique session identifier
            working_dir: Working directory for the shell

        Returns:
            TerminalSession instance
        """
        async with self._lock:
            if session_id in self._sessions:
                # Return existing session
                return self._sessions[session_id]

            # Create pseudo-terminal
            master_fd, slave_fd = pty.openpty()

            # Fork process
            pid = os.fork()

            if pid == 0:
                # Child process
                os.setsid()
                os.dup2(slave_fd, 0)  # stdin
                os.dup2(slave_fd, 1)  # stdout
                os.dup2(slave_fd, 2)  # stderr
                os.close(master_fd)
                os.close(slave_fd)

                # Change to working directory
                os.chdir(working_dir)

                # Start shell
                os.execvp("/bin/bash", ["/bin/bash", "-i"])

            else:
                # Parent process
                os.close(slave_fd)

                session = TerminalSession(
                    session_id=session_id,
                    pid=pid,
                    fd=master_fd,
                    working_dir=working_dir
                )
                self._sessions[session_id] = session

                logger.info(f"Created terminal session: {session_id} (PID: {pid})")
                return session

    async def send_command(
        self,
        session_id: str,
        command: str
    ) -> bool:
        """
        Send command to terminal session.

        Args:
            session_id: Session identifier
            command: Command to execute

        Returns:
            True if command was sent successfully
        """
        session = self._sessions.get(session_id)
        if not session or not session.is_active:
            logger.error(f"Session not found or inactive: {session_id}")
            return False

        try:
            # Add newline to execute command
            cmd_bytes = (command + "\n").encode('utf-8')
            os.write(session.fd, cmd_bytes)
            return True
        except Exception as e:
            logger.error(f"Failed to send command: {e}")
            return False

    async def read_output(
        self,
        session_id: str,
        timeout: float = 0.1
    ) -> Optional[str]:
        """
        Read output from terminal session (non-blocking).

        Args:
            session_id: Session identifier
            timeout: Read timeout in seconds

        Returns:
            Output string or None if no data available
        """
        session = self._sessions.get(session_id)
        if not session or not session.is_active:
            return None

        try:
            import select
            ready, _, _ = select.select([session.fd], [], [], timeout)

            if ready:
                data = os.read(session.fd, 4096)
                return data.decode('utf-8', errors='replace')

            return None

        except Exception as e:
            logger.error(f"Failed to read output: {e}")
            return None

    async def stream_output(
        self,
        session_id: str,
        callback: Callable[[str], Any],
        timeout: float = 300.0,
        end_marker: Optional[str] = None
    ):
        """
        Stream output from terminal session.

        Args:
            session_id: Session identifier
            callback: Async callback for each output chunk
            timeout: Total timeout in seconds
            end_marker: Optional string that marks end of output
        """
        session = self._sessions.get(session_id)
        if not session or not session.is_active:
            return

        start_time = asyncio.get_event_loop().time()
        buffer = ""

        while True:
            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                logger.warning(f"Stream timeout for session: {session_id}")
                break

            # Read output
            output = await self.read_output(session_id, timeout=0.1)

            if output:
                buffer += output
                await callback(output)

                # Check for end marker
                if end_marker and end_marker in buffer:
                    break

            else:
                # No data, wait a bit
                await asyncio.sleep(0.05)

    async def run_claude_command(
        self,
        session_id: str,
        prompt: str,
        team_context: Optional[str] = None,
        callback: Optional[Callable[[str], Any]] = None,
        timeout: float = 300.0
    ) -> str:
        """
        Run Claude Code CLI command and stream output.

        Args:
            session_id: Session identifier
            prompt: User prompt
            team_context: Optional team context to inject
            callback: Async callback for streaming chunks
            timeout: Command timeout in seconds

        Returns:
            Full response text
        """
        session = self._sessions.get(session_id)
        if not session or not session.is_active:
            raise RuntimeError(f"Session not found: {session_id}")

        # Prepare command
        # Escape quotes in prompt for shell
        escaped_prompt = prompt.replace('"', '\\"').replace('$', '\\$')

        if team_context:
            # Create temp file with context
            context_escaped = team_context.replace('"', '\\"').replace('$', '\\$')
            full_prompt = f"[Context]\\n{context_escaped}\\n\\n[Request]\\n{escaped_prompt}"
        else:
            full_prompt = escaped_prompt

        # Build claude command
        command = f'claude --print "{full_prompt}"'

        # Send command
        await self.send_command(session_id, command)

        # Collect output
        output_buffer = []

        async def collect_output(chunk: str):
            output_buffer.append(chunk)
            if callback:
                await callback(chunk)

        # Stream output
        await self.stream_output(
            session_id,
            callback=collect_output,
            timeout=timeout,
            end_marker="$"  # Shell prompt indicates command complete
        )

        return "".join(output_buffer)

    async def close_session(self, session_id: str):
        """Close a terminal session."""
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return

            try:
                # Send exit command
                os.write(session.fd, b"exit\n")
                await asyncio.sleep(0.5)

                # Kill process if still running
                try:
                    os.kill(session.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass

                # Close file descriptor
                os.close(session.fd)

                session.is_active = False
                del self._sessions[session_id]

                logger.info(f"Closed terminal session: {session_id}")

            except Exception as e:
                logger.error(f"Error closing session {session_id}: {e}")

    async def close_all_sessions(self):
        """Close all terminal sessions."""
        session_ids = list(self._sessions.keys())
        for session_id in session_ids:
            await self.close_session(session_id)

    def get_session(self, session_id: str) -> Optional[TerminalSession]:
        """Get session by ID."""
        return self._sessions.get(session_id)

    @property
    def active_sessions(self) -> int:
        """Number of active sessions."""
        return len(self._sessions)


# Global bridge server instance
bridge_server = BridgeServer()


# ============================================================
# Alternative: Simple subprocess-based execution
# (For when PTY is not needed)
# ============================================================

async def run_claude_simple(
    prompt: str,
    working_dir: str = "/home/vibeops/vibeops",
    timeout: float = 300.0
) -> str:
    """
    Simple subprocess-based Claude Code execution.

    Use this when you don't need full terminal emulation.

    Args:
        prompt: User prompt
        working_dir: Working directory
        timeout: Command timeout

    Returns:
        Claude Code response
    """
    try:
        process = await asyncio.create_subprocess_exec(
            "claude",
            "--print",
            prompt,
            cwd=working_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout
        )

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            raise RuntimeError(f"Claude Code failed: {error_msg}")

        return stdout.decode().strip()

    except asyncio.TimeoutError:
        raise RuntimeError("Claude Code request timed out")


async def stream_claude_simple(
    prompt: str,
    working_dir: str = "/home/vibeops/vibeops",
    timeout: float = 300.0
):
    """
    Simple subprocess-based Claude Code streaming.

    Yields output lines as they are generated.

    Args:
        prompt: User prompt
        working_dir: Working directory
        timeout: Command timeout

    Yields:
        Output lines
    """
    try:
        process = await asyncio.create_subprocess_exec(
            "claude",
            "--print",
            prompt,
            cwd=working_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        while True:
            try:
                line = await asyncio.wait_for(
                    process.stdout.readline(),
                    timeout=60.0
                )
                if not line:
                    break
                yield line.decode()
            except asyncio.TimeoutError:
                break

        await process.wait()

    except Exception as e:
        yield f"[Error: {str(e)}]"
