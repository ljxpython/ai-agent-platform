from alembic import context

context.configure(
    connection=context.config.attributes["connection"],
    version_table="runtime_app_alembic_version",
    transactional_ddl=True,
)
with context.begin_transaction():
    context.run_migrations()
