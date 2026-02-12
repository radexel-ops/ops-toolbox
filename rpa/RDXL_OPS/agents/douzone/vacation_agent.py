"""
Vacation Agent

Agent for managing vacation-related automation tasks.
Integrates with WEHAGO, Google Calendar, and Slack.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from ..base.agent_base import BaseAgent
from ..registry import register_agent
from .wehago_service import WehagoService, WehagoConfig

logger = logging.getLogger(__name__)


@register_agent("vacation")
class VacationAgent(BaseAgent):
    """
    Vacation management agent.

    Automates:
    - WEHAGO vacation data export
    - Google Calendar synchronization
    - Slack notifications
    - Vacation summary reports
    """

    name = "vacation"
    description = "휴가 관리 자동화 에이전트 (WEHAGO → Google Calendar → Slack)"
    version = "1.0.0"

    def __init__(self):
        super().__init__()
        self.wehago_service: Optional[WehagoService] = None
        self._calendar_service = None
        self._slack_service = None

    async def initialize(self) -> bool:
        """Initialize the vacation agent."""
        try:
            # Initialize WEHAGO service
            self.wehago_service = WehagoService()

            # Check required environment variables
            required_vars = ["WEHAGO_ID", "WEHAGO_PW"]
            missing = [v for v in required_vars if not os.environ.get(v)]

            if missing:
                logger.warning(f"Missing environment variables: {missing}")
                logger.warning("WEHAGO features will be limited")

            self._initialized = True
            logger.info("VacationAgent initialized")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize VacationAgent: {e}")
            return False

    async def execute(self, command: str = None) -> Dict[str, Any]:
        """
        Execute vacation agent command.

        Commands:
        - export: Export vacation data from WEHAGO
        - sync: Sync vacation data to Google Calendar
        - notify: Send vacation summary to Slack
        - summary: Get vacation summary
        - full: Run full pipeline (export → sync → notify)
        - status: Check agent status
        """
        if not self._initialized:
            await self.initialize()

        command = (command or "status").strip().lower()
        parts = command.split()
        action = parts[0] if parts else "status"
        args = parts[1:] if len(parts) > 1 else []

        try:
            if action == "export":
                return await self._export_vacation(args)
            elif action == "sync":
                return await self._sync_calendar(args)
            elif action == "notify":
                return await self._send_notification(args)
            elif action == "summary":
                return await self._get_summary(args)
            elif action == "full":
                return await self._run_full_pipeline(args)
            elif action == "status":
                return await self._get_status()
            elif action == "help":
                return self._get_help()
            else:
                return {
                    "status": "error",
                    "error": f"Unknown command: {action}",
                    "help": self._get_help()
                }

        except Exception as e:
            logger.error(f"VacationAgent error: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def _export_vacation(self, args: List[str]) -> Dict[str, Any]:
        """Export vacation data from WEHAGO."""
        months = int(args[0]) if args else 1

        if not self.wehago_service:
            return {
                "status": "error",
                "error": "WEHAGO service not initialized"
            }

        try:
            files = await self.wehago_service.export_vacation_data(months=months)
            return {
                "status": "success",
                "action": "export",
                "months": months,
                "files": files,
                "message": f"Exported {len(files)} vacation data files"
            }
        except Exception as e:
            return {
                "status": "error",
                "action": "export",
                "error": str(e)
            }

    async def _sync_calendar(self, args: List[str]) -> Dict[str, Any]:
        """Sync vacation data to Google Calendar."""
        # This would integrate with Google Calendar API
        # For now, return placeholder
        return {
            "status": "pending",
            "action": "sync",
            "message": "Google Calendar sync not yet implemented",
            "note": "Requires GOOGLE_CALENDAR_ID and OAuth credentials"
        }

    async def _send_notification(self, args: List[str]) -> Dict[str, Any]:
        """Send vacation summary to Slack."""
        channel = args[0] if args else os.environ.get("SLACK_CHANNEL_ATTENDANCE", "#attendance")

        # This would integrate with Slack API
        # For now, return placeholder
        return {
            "status": "pending",
            "action": "notify",
            "channel": channel,
            "message": "Slack notification not yet implemented",
            "note": "Requires SLACK_TOKEN and SLACK_CHANNEL"
        }

    async def _get_summary(self, args: List[str]) -> Dict[str, Any]:
        """Get vacation summary."""
        today = datetime.now()

        # This would query actual data
        # For now, return structure
        return {
            "status": "success",
            "action": "summary",
            "date": today.strftime("%Y-%m-%d"),
            "summary": {
                "on_vacation_today": [],
                "returning_tomorrow": [],
                "starting_vacation_tomorrow": [],
                "total_on_vacation": 0
            }
        }

    async def _run_full_pipeline(self, args: List[str]) -> Dict[str, Any]:
        """Run full vacation pipeline: export → sync → notify."""
        results = {
            "status": "success",
            "action": "full_pipeline",
            "steps": []
        }

        # Step 1: Export
        export_result = await self._export_vacation(args)
        results["steps"].append({"step": "export", "result": export_result})

        if export_result.get("status") != "success":
            results["status"] = "partial"
            return results

        # Step 2: Sync
        sync_result = await self._sync_calendar([])
        results["steps"].append({"step": "sync", "result": sync_result})

        # Step 3: Notify
        notify_result = await self._send_notification([])
        results["steps"].append({"step": "notify", "result": notify_result})

        return results

    async def _get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        wehago_configured = bool(os.environ.get("WEHAGO_ID") and os.environ.get("WEHAGO_PW"))
        calendar_configured = bool(os.environ.get("GOOGLE_CALENDAR_ID"))
        slack_configured = bool(os.environ.get("SLACK_TOKEN"))

        return {
            "status": "success",
            "agent": self.name,
            "version": self.version,
            "initialized": self._initialized,
            "services": {
                "wehago": {
                    "configured": wehago_configured,
                    "status": "ready" if wehago_configured else "not_configured"
                },
                "google_calendar": {
                    "configured": calendar_configured,
                    "status": "ready" if calendar_configured else "not_configured"
                },
                "slack": {
                    "configured": slack_configured,
                    "status": "ready" if slack_configured else "not_configured"
                }
            }
        }

    def _get_help(self) -> Dict[str, Any]:
        """Get help information."""
        return {
            "status": "success",
            "agent": self.name,
            "commands": {
                "export [months]": "Export vacation data from WEHAGO (default: 1 month)",
                "sync": "Sync vacation data to Google Calendar",
                "notify [channel]": "Send vacation summary to Slack",
                "summary": "Get current vacation summary",
                "full [months]": "Run full pipeline (export → sync → notify)",
                "status": "Check agent status",
                "help": "Show this help message"
            },
            "examples": [
                "vacation export 3",
                "vacation sync",
                "vacation notify #attendance",
                "vacation full",
                "vacation status"
            ]
        }

    async def health_check(self) -> Dict[str, Any]:
        """Check agent health."""
        status = await self._get_status()
        status["healthy"] = self._initialized
        return status

    async def cleanup(self):
        """Cleanup resources."""
        if self.wehago_service:
            self.wehago_service.close()
            self.wehago_service = None
        self._initialized = False
        logger.info("VacationAgent cleaned up")
