"""Added language to posts

Revision ID: 799ac209c128
Revises: 40f74b4f4225
Create Date: 2020-05-26 20:24:08.213050

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "799ac209c128"
down_revision = "40f74b4f4225"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("post", sa.Column("language", sa.String(length=5), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("post", "language")
    # ### end Alembic commands ###
