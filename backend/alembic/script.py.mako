"""
${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

============================================================================
AutoTwin AI - Database Migration
============================================================================
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# ============================================================================
# REVISION IDENTIFIERS
# ============================================================================

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}

# ============================================================================
# UPGRADE (apply migration)
# ============================================================================


def upgrade() -> None:
    """Apply schema changes."""
    ${upgrades if upgrades else "pass"}


# ============================================================================
# DOWNGRADE (rollback migration)
# ============================================================================


def downgrade() -> None:
    """Revert schema changes."""
    ${downgrades if downgrades else "pass"}