"""empty message

Revision ID: ff4b2dfccc9a
Revises: 2f59386acd33
Create Date: 2017-08-17 07:21:14.316045

"""

# revision identifiers, used by Alembic.
revision = 'ff4b2dfccc9a'
down_revision = '2f59386acd33'

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table('device_schedule',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('device_id', sa.Integer(), nullable=False),
                    sa.Column('action', sa.String(length=120), nullable=True),
                    sa.Column('payload', sa.Text(), nullable=True),
                    sa.Column('minutes', sa.Integer(), nullable=True),
                    sa.Column('hours', sa.Integer(), nullable=True),
                    sa.Column('mday', sa.Integer(), nullable=True),
                    sa.Column('month', sa.Integer(), nullable=True),
                    sa.Column('wday', sa.Integer(), nullable=True),
                    sa.Column('is_once', sa.Boolean(), nullable=False),
                    sa.ForeignKeyConstraint(['device_id'], ['device.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('water_consumption',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('device_id', sa.Integer(), nullable=False),
                    sa.Column('start_time', sa.DateTime(), nullable=False),
                    sa.Column('finish_time', sa.DateTime(), nullable=False),
                    sa.Column('consumption', sa.Integer(), nullable=True),
                    sa.ForeignKeyConstraint(['device_id'], ['device.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_index(op.f('ix_device_mac_address'), 'device', ['mac_address'], unique=True)
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_device_mac_address'), table_name='device')
    op.drop_table('water_consumption')
    op.drop_table('device_schedule')
    ### end Alembic commands ###
