"""
Claude Code CLI Service

Integrates Claude Code CLI for interactive development via Bridge.
Supports both simple query and streaming modes.
"""

import asyncio
import subprocess
import os
import logging
from typing import Optional, AsyncGenerator, Callable, Any

logger = logging.getLogger(__name__)


class ClaudeCodeService:
    """
    Service for interacting with Claude Code CLI.

    Claude Code CLI is used for:
    - Interactive development conversations
    - Code generation and modification
    - Project-aware AI assistance

    Modes:
    - query(): Single response (non-streaming)
    - stream_query(): Streaming response (yields chunks)
    - interactive_session(): Full PTY-based session
    """

    def __init__(self):
        self.project_root = os.environ.get(
            "VIBEOPS_PROJECT_ROOT",
            "/home/vibeops/vibeops"
        )
        self.timeout = int(os.environ.get("CLAUDE_CODE_TIMEOUT", "300"))
        self._available = None
        self._version = None

    def check_availability(self) -> bool:
        """Check if Claude Code CLI is available and authenticated."""
        if self._available is not None:
            return self._available

        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            self._available = result.returncode == 0
            if self._available:
                self._version = result.stdout.strip()
                logger.info(f"Claude Code CLI available: {self._version}")
            return self._available
        except FileNotFoundError:
            logger.warning("Claude Code CLI not installed (claude command not found)")
            self._available = False
            return False
        except Exception as e:
            logger.error(f"Claude Code CLI check failed: {e}")
            self._available = False
            return False

    @property
    def is_available(self) -> bool:
        """Check if service is available."""
        return self.check_availability()

    @property
    def version(self) -> Optional[str]:
        """Get Claude Code CLI version."""
        self.check_availability()
        return self._version

    def _build_prompt(self, prompt: str, team_context: Optional[str] = None) -> str:
        """Build full prompt with optional team context."""
        if team_context:
            return f"""[Team Context]
{team_context}

[User Request]
{prompt}"""
        return prompt

    async def query(
        self,
        prompt: str,
        team_context: Optional[str] = None,
        working_dir: Optional[str] = None
    ) -> str:
        """
        Send a query to Claude Code CLI and get response.

        Args:
            prompt: User's message/question
            team_context: Team-specific context to inject
            working_dir: Working directory for Claude Code

        Returns:
            Claude Code response text
        """
        if not self.is_available:
            return self._fallback_response(prompt, team_context, "Claude Code CLI not available")

        full_prompt = self._build_prompt(prompt, team_context)
        cwd = working_dir or self.project_root

        try:
            process = await asyncio.create_subprocess_exec(
                "claude",
                "--print",
                full_prompt,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout
            )

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"Claude Code error: {error_msg}")
                return self._fallback_response(prompt, team_context, f"Error: {error_msg}")

            response = stdout.decode().strip()
            logger.info(f"Claude Code response received ({len(response)} chars)")
            return response

        except asyncio.TimeoutError:
            logger.error("Claude Code query timed out")
            return self._fallback_response(prompt, team_context, "Request timed out")
        except Exception as e:
            logger.error(f"Claude Code query failed: {e}")
            return self._fallback_response(prompt, team_context, str(e))

    async def stream_query(
        self,
        prompt: str,
        team_context: Optional[str] = None,
        working_dir: Optional[str] = None,
        chunk_callback: Optional[Callable[[str], Any]] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream response from Claude Code CLI.

        Yields response chunks as they are generated.

        Args:
            prompt: User's message/question
            team_context: Team-specific context to inject
            working_dir: Working directory for Claude Code
            chunk_callback: Optional callback for each chunk

        Yields:
            Response chunks
        """
        if not self.is_available:
            error_msg = "[Claude Code CLI not available]\n"
            if chunk_callback:
                await chunk_callback(error_msg)
            yield error_msg
            yield self._fallback_response(prompt, team_context, "Not available")
            return

        full_prompt = self._build_prompt(prompt, team_context)
        cwd = working_dir or self.project_root

        try:
            process = await asyncio.create_subprocess_exec(
                "claude",
                "--print",
                full_prompt,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Stream stdout line by line
            while True:
                try:
                    line = await asyncio.wait_for(
                        process.stdout.readline(),
                        timeout=60.0
                    )
                    if not line:
                        break

                    chunk = line.decode()
                    if chunk_callback:
                        await chunk_callback(chunk)
                    yield chunk

                except asyncio.TimeoutError:
                    logger.warning("Stream read timeout, continuing...")
                    continue

            # Wait for process to complete
            await process.wait()

            if process.returncode != 0:
                stderr_data = await process.stderr.read()
                error_msg = f"\n[Error: {stderr_data.decode()}]"
                if chunk_callback:
                    await chunk_callback(error_msg)
                yield error_msg

        except asyncio.TimeoutError:
            error_msg = "\n[Error: Request timed out]"
            if chunk_callback:
                await chunk_callback(error_msg)
            yield error_msg
        except Exception as e:
            error_msg = f"\n[Error: {str(e)}]"
            logger.error(f"Claude Code stream failed: {e}")
            if chunk_callback:
                await chunk_callback(error_msg)
            yield error_msg

    async def stream_to_websocket(
        self,
        prompt: str,
        team_context: Optional[str] = None,
        working_dir: Optional[str] = None,
        send_func: Optional[Callable[[dict], Any]] = None
    ) -> str:
        """
        Stream Claude Code response directly to WebSocket.

        Args:
            prompt: User's message
            team_context: Team context
            working_dir: Working directory
            send_func: Async function to send WebSocket messages

        Returns:
            Full response text
        """
        full_response = []

        async def on_chunk(chunk: str):
            full_response.append(chunk)
            if send_func:
                await send_func({
                    "type": "stream",
                    "payload": {
                        "chunk": chunk,
                        "status": "streaming"
                    }
                })

        async for chunk in self.stream_query(
            prompt=prompt,
            team_context=team_context,
            working_dir=working_dir,
            chunk_callback=on_chunk
        ):
            pass  # Already handled by callback

        return "".join(full_response)

    def _fallback_response(
        self,
        prompt: str,
        team_context: Optional[str],
        error: str
    ) -> str:
        """Generate fallback response when Claude Code is unavailable."""
        team_info = ""
        if team_context:
            # Extract team name from context if available
            lines = team_context.split('\n')
            for line in lines[:5]:
                if 'team' in line.lower() or 'Team' in line:
                    team_info = f"\nTeam Context: {line}"
                    break

        return f"""[Claude Code Response - Fallback Mode]

Status: {error}

Your Request:
{prompt[:500]}{'...' if len(prompt) > 500 else ''}
{team_info}

---
Claude Code CLI is not currently available on this server.
To enable Claude Code:
1. Install: npm install -g @anthropic-ai/claude-code
2. Authenticate: claude auth login
3. Verify: claude --version

For now, please try:
- Using the system AI (Gemini/GPT) for simple queries
- Checking server configuration
- Contacting the administrator
"""


# Global service instance
claude_service = ClaudeCodeService()
