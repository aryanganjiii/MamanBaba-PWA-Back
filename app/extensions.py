try:
    from flask_cors import CORS
except ImportError:  # pragma: no cover
    class CORS:
        def init_app(self, *args, **kwargs):
            return None


try:
    from flask_migrate import Migrate
except ImportError:  # pragma: no cover
    class Migrate:
        def init_app(self, *args, **kwargs):
            return None


try:
    from flask_sqlalchemy import SQLAlchemy
except ImportError:  # pragma: no cover
    import sqlalchemy as sa
    from sqlalchemy.orm import declarative_base, relationship, scoped_session, sessionmaker

    class _QueryDescriptor:
        def __get__(self, obj, cls):
            return db.session.query(cls)

    class _SimpleSQLAlchemy:
        Column = sa.Column
        Integer = sa.Integer
        String = sa.String
        Text = sa.Text
        Boolean = sa.Boolean
        DateTime = sa.DateTime
        Float = sa.Float
        ForeignKey = sa.ForeignKey
        UniqueConstraint = sa.UniqueConstraint
        func = sa.func
        relationship = staticmethod(relationship)

        def __init__(self):
            class Model(declarative_base()):
                __abstract__ = True
                query = _QueryDescriptor()

            self.Model = Model
            self.engine = None
            self.session = None

        def init_app(self, app):
            self.engine = sa.create_engine(
                app.config["SQLALCHEMY_DATABASE_URI"],
                future=True,
                connect_args={"check_same_thread": False}
                if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite")
                else {},
            )
            self.session = scoped_session(sessionmaker(bind=self.engine, autoflush=False))

            @app.teardown_appcontext
            def remove_session(exception=None):
                self.session.remove()

        def create_all(self):
            self.Model.metadata.create_all(self.engine)

        def drop_all(self):
            self.Model.metadata.drop_all(self.engine)

    SQLAlchemy = _SimpleSQLAlchemy


db = SQLAlchemy()
migrate = Migrate()
cors = CORS()
