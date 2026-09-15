"""merge initial schema heads

Revision ID: 4e125ce868ca
Revises: 001_initial, 001
Create Date: 2026-09-14 02:32:56.184188
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e125ce868ca'
down_revision: Union[str, None] = ('001_initial', '001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
"""merge initial schema heads

Revision ID: 4e125ce868ca
Revises: 001_initial, 001
Create Date: 2026-09-14 02:32:56.184188

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e125ce868ca'
down_revision: Union[str, None] = ('001_initial', '001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
