"""
Knowledge Service

Handles knowledge inheritance system:
- Master guidelines (CLAUDE.md, knowledge/*.md)
- Team guidelines (teams/{slug}/TEAM_CLAUDE.md, teams/{slug}/knowledge/*.md)
- Guideline merging for AI prompts
"""

import os
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..config import settings
from ..models import Team, TeamGuideline, User


class KnowledgeService:
    """
    Service for managing and merging knowledge documents.

    Knowledge hierarchy:
    1. Master CLAUDE.md (project root)
    2. Master knowledge/*.md (optional, on-demand)
    3. Team TEAM_CLAUDE.md
    4. Team knowledge/*.md (optional, on-demand)
    """

    def __init__(self):
        self.project_root = settings.PROJECT_ROOT

    def _read_file(self, path: str) -> Optional[str]:
        """Read file content, return None if not exists"""
        full_path = os.path.join(self.project_root, path)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return None
        except Exception as e:
            return f"[Error reading {path}: {str(e)}]"

    def _write_file(self, path: str, content: str) -> bool:
        """Write content to file, create directories if needed"""
        full_path = os.path.join(self.project_root, path)
        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception:
            return False

    def _list_knowledge_files(self, directory: str) -> List[str]:
        """List all .md files in a knowledge directory"""
        full_path = os.path.join(self.project_root, directory)
        if not os.path.exists(full_path):
            return []

        files = []
        for f in os.listdir(full_path):
            if f.endswith(".md"):
                files.append(os.path.join(directory, f))
        return sorted(files)

    # ==================== Master Guidelines ====================

    def get_master_guideline(self) -> Optional[str]:
        """Get master CLAUDE.md content"""
        return self._read_file(settings.MASTER_CLAUDE_MD)

    def get_master_knowledge_list(self) -> List[str]:
        """Get list of master knowledge document paths"""
        return self._list_knowledge_files(settings.KNOWLEDGE_DIR)

    def get_master_knowledge(self, filename: str) -> Optional[str]:
        """Get specific master knowledge document content"""
        path = os.path.join(settings.KNOWLEDGE_DIR, filename)
        return self._read_file(path)

    def update_master_guideline(self, content: str, user: User) -> bool:
        """
        Update master CLAUDE.md (super_admin only).

        Returns True if successful.
        """
        if not user.can_edit_master_guidelines():
            return False
        return self._write_file(settings.MASTER_CLAUDE_MD, content)

    # ==================== Team Guidelines ====================

    def get_team_guideline_path(self, team_slug: str) -> str:
        """Get path to team's TEAM_CLAUDE.md"""
        return f"{settings.TEAMS_DIR}/{team_slug}/TEAM_CLAUDE.md"

    def get_team_knowledge_path(self, team_slug: str) -> str:
        """Get path to team's knowledge directory"""
        return f"{settings.TEAMS_DIR}/{team_slug}/knowledge"

    def get_team_guideline(self, team_slug: str) -> Optional[str]:
        """Get team's TEAM_CLAUDE.md content"""
        path = self.get_team_guideline_path(team_slug)
        return self._read_file(path)

    def get_team_knowledge_list(self, team_slug: str) -> List[str]:
        """Get list of team knowledge document paths"""
        knowledge_dir = self.get_team_knowledge_path(team_slug)
        return self._list_knowledge_files(knowledge_dir)

    def get_team_knowledge(self, team_slug: str, filename: str) -> Optional[str]:
        """Get specific team knowledge document content"""
        path = os.path.join(self.get_team_knowledge_path(team_slug), filename)
        return self._read_file(path)

    def update_team_guideline(
        self,
        team_slug: str,
        content: str,
        user: User,
        team_id: int
    ) -> bool:
        """
        Update team's TEAM_CLAUDE.md.

        Returns True if successful.
        """
        if not user.can_edit_team_guidelines(team_id):
            return False

        path = self.get_team_guideline_path(team_slug)
        return self._write_file(path, content)

    # ==================== Merged Guidelines ====================

    def get_merged_guidelines(
        self,
        team_slug: str,
        include_master_knowledge: bool = False,
        include_team_knowledge: bool = False,
        specific_knowledge_files: Optional[List[str]] = None
    ) -> str:
        """
        Get merged guidelines for AI prompt.

        Structure:
        ```
        # Master Guidelines
        [CLAUDE.md content]

        # Master Knowledge (optional)
        [knowledge/*.md contents]

        # Team Guidelines: {team_name}
        [TEAM_CLAUDE.md content]

        # Team Knowledge (optional)
        [teams/{slug}/knowledge/*.md contents]
        ```
        """
        parts = []

        # 1. Master Guidelines
        master = self.get_master_guideline()
        if master:
            parts.append("# Master Guidelines (Project-wide)\n\n" + master)

        # 2. Master Knowledge (optional)
        if include_master_knowledge:
            knowledge_files = specific_knowledge_files or self.get_master_knowledge_list()
            for kf in knowledge_files:
                if kf.startswith(settings.KNOWLEDGE_DIR):
                    content = self._read_file(kf)
                    if content:
                        filename = os.path.basename(kf)
                        parts.append(f"\n\n# Master Knowledge: {filename}\n\n{content}")

        # 3. Team Guidelines
        team_guideline = self.get_team_guideline(team_slug)
        if team_guideline:
            parts.append(f"\n\n# Team Guidelines: {team_slug}\n\n" + team_guideline)

        # 4. Team Knowledge (optional)
        if include_team_knowledge:
            team_knowledge = self.get_team_knowledge_list(team_slug)
            for kf in team_knowledge:
                content = self._read_file(kf)
                if content:
                    filename = os.path.basename(kf)
                    parts.append(f"\n\n# Team Knowledge ({team_slug}): {filename}\n\n{content}")

        return "\n".join(parts)

    # ==================== Team Context ====================

    def get_team_context(self, team_slug: str) -> dict:
        """
        Get complete team context for AI.

        Returns dict with:
        - team_slug
        - guidelines (merged)
        - knowledge_files (list of available files)
        """
        master_knowledge = self.get_master_knowledge_list()
        team_knowledge = self.get_team_knowledge_list(team_slug)

        return {
            "team_slug": team_slug,
            "guidelines": self.get_merged_guidelines(team_slug),
            "master_knowledge_files": master_knowledge,
            "team_knowledge_files": team_knowledge,
            "paths": {
                "master_claude": settings.MASTER_CLAUDE_MD,
                "master_knowledge": settings.KNOWLEDGE_DIR,
                "team_claude": self.get_team_guideline_path(team_slug),
                "team_knowledge": self.get_team_knowledge_path(team_slug),
                "team_data": f"{settings.TEAMS_DIR}/{team_slug}/data",
                "team_agents": f"{settings.TEAMS_DIR}/{team_slug}/agents",
            }
        }

    # ==================== Sync with Database ====================

    async def sync_team_guideline_to_db(
        self,
        db: AsyncSession,
        team: Team
    ) -> bool:
        """
        Sync team guideline from filesystem to database.

        This allows fast access during AI interactions without
        filesystem reads.
        """
        content = self.get_team_guideline(team.slug)
        if content is None:
            return False

        # Find or create guideline record
        result = await db.execute(
            select(TeamGuideline).where(
                TeamGuideline.team_id == team.id,
                TeamGuideline.is_main_guideline == True
            )
        )
        guideline = result.scalar_one_or_none()

        if guideline:
            guideline.content = content
        else:
            guideline = TeamGuideline(
                team_id=team.id,
                file_path=self.get_team_guideline_path(team.slug),
                content=content,
                is_main_guideline=True
            )
            db.add(guideline)

        await db.commit()
        return True

    async def sync_db_to_team_guideline(
        self,
        db: AsyncSession,
        team: Team
    ) -> bool:
        """
        Sync team guideline from database to filesystem.

        Use after editing via API.
        """
        result = await db.execute(
            select(TeamGuideline).where(
                TeamGuideline.team_id == team.id,
                TeamGuideline.is_main_guideline == True
            )
        )
        guideline = result.scalar_one_or_none()

        if not guideline or not guideline.content:
            return False

        return self._write_file(
            self.get_team_guideline_path(team.slug),
            guideline.content
        )


# Global service instance
knowledge_service = KnowledgeService()
