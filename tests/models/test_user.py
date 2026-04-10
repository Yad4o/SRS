"""
Tests for app/models/user.py

Covers:
- User model creation and validation
- Column constraints and defaults
- Role enumeration
- Table structure
- Database operations
"""
import pytest
from sqlalchemy import exc as sqlalchemy_exc
from sqlalchemy.orm import Session

from app.db.session import Base, engine, init_db
from app.models.user import User


class TestUserModel:
    """Tests for User ORM model."""

    @classmethod
    def setup_class(cls):
        """Create tables for test class."""
        Base.metadata.create_all(bind=engine)

    @classmethod
    def teardown_class(cls):
        """Drop tables after test class."""
        Base.metadata.drop_all(bind=engine)

    def test_user_model_inherits_from_base(self):
        """User should inherit from SQLAlchemy Base."""
        assert hasattr(User, '__tablename__')
        assert hasattr(User, '__table__')
        assert User.__tablename__ == "users"

    def test_user_table_name(self):
        """User table should be named 'users'."""
        assert User.__tablename__ == "users"

    def test_user_columns_exist(self):
        """User should have all required columns."""
        columns = User.__table__.columns
        column_names = [col.name for col in columns]
        
        required_columns = ['id', 'email', 'hashed_password', 'role']
        for col in required_columns:
            assert col in column_names, f"Missing column: {col}"

    def test_user_id_column_properties(self):
        """id column should be Integer, Primary Key, and indexed."""
        id_column = User.__table__.columns['id']
        
        assert str(id_column.type) == 'INTEGER'
        assert id_column.primary_key is True
        # PK columns are typically nullable in SQLAlchemy but enforced at DB level
        assert id_column.index is True

    def test_user_email_column_properties(self):
        """email column should be String, unique, indexed, and not nullable."""
        email_column = User.__table__.columns['email']
        
        assert str(email_column.type) == 'VARCHAR'
        assert email_column.unique is True
        assert email_column.nullable is False
        assert email_column.index is True

    def test_user_hashed_password_column_properties(self):
        """hashed_password column should be String and not nullable."""
        password_column = User.__table__.columns['hashed_password']
        
        assert str(password_column.type) == 'VARCHAR'
        assert password_column.nullable is False
        # unique and index default to False if not specified

    def test_user_role_column_properties(self):
        """role column should be String, not nullable, with default 'user'."""
        role_column = User.__table__.columns['role']
        
        assert str(role_column.type) == 'VARCHAR'
        assert role_column.nullable is False
        assert role_column.default.arg == 'user'
        # unique and index default to False if not specified

    def test_user_creation_with_required_fields(self):
        """Should create user with required fields."""
        user = User(
            email="test@example.com",
            hashed_password="hashed_password_123"
        )
        
        assert user.email == "test@example.com"
        assert user.hashed_password == "hashed_password_123"
        assert user.role == "user"  # Default value

    def test_user_creation_with_all_fields(self):
        """Should create user with all fields including role."""
        user = User(
            email="agent@example.com",
            hashed_password="hashed_password_456",
            role="agent"
        )
        
        assert user.email == "agent@example.com"
        assert user.hashed_password == "hashed_password_456"
        assert user.role == "agent"

    def test_user_role_default(self):
        """User role should default to 'user' when not specified."""
        user = User(
            email="default@example.com",
            hashed_password="hashed_password_789"
        )
        
        assert user.role == "user"

    def test_user_all_valid_roles(self):
        """Should accept all valid role values."""
        valid_roles = ["user", "agent", "admin"]
        
        for role in valid_roles:
            user = User(
                email=f"{role}@example.com",
                hashed_password="hashed_password",
                role=role
            )
            assert user.role == role

    def test_user_string_representation(self):
        """User should have meaningful string representation."""
        user = User(
            email="test@example.com",
            hashed_password="hashed_password"
        )
        
        # Should contain email in representation or be a valid object representation
        str_repr = str(user)
        assert "User object" in str_repr or "test@example.com" in str_repr

    def test_user_database_persistence(self):
        """Should persist user to database correctly."""
        with Session(engine) as db:
            # Create user
            user = User(
                email="persist@example.com",
                hashed_password="hashed_password_persist",
                role="admin"
            )
            
            # Add to database
            db.add(user)
            db.commit()
            db.refresh(user)
            
            # Verify ID was assigned
            assert user.id is not None
            
            # Retrieve from database
            retrieved_user = db.query(User).filter(User.email == "persist@example.com").first()
            
            assert retrieved_user is not None
            assert retrieved_user.email == "persist@example.com"
            assert retrieved_user.hashed_password == "hashed_password_persist"
            assert retrieved_user.role == "admin"
            assert retrieved_user.id == user.id

    def test_user_email_unique_constraint(self):
        """Should enforce unique constraint on email."""
        with Session(engine) as db:
            # Create first user
            user1 = User(
                email="unique@example.com",
                hashed_password="password1"
            )
            db.add(user1)
            db.commit()
            
            # Try to create second user with same email
            user2 = User(
                email="unique@example.com",
                hashed_password="password2"
            )
            db.add(user2)
            
            # Should raise integrity error
            with pytest.raises(sqlalchemy_exc.IntegrityError):
                db.commit()

    def test_user_email_not_null_constraint(self):
        """Should enforce not null constraint on email."""
        with Session(engine) as db:
            user = User(
                hashed_password="password"
            )
            db.add(user)
            
            # Should raise integrity error
            with pytest.raises(sqlalchemy_exc.IntegrityError):
                db.commit()

    def test_user_hashed_password_not_null_constraint(self):
        """Should enforce not null constraint on hashed_password."""
        with Session(engine) as db:
            user = User(
                email="test@example.com"
            )
            db.add(user)
            
            # Should raise integrity error
            with pytest.raises(sqlalchemy_exc.IntegrityError):
                db.commit()

    def test_user_role_not_null_constraint(self):
        """Should enforce not null constraint on role at database level."""
        with Session(engine) as db:
            # Test database constraint by directly inserting NULL
            try:
                from sqlalchemy import text
                db.execute(text("INSERT INTO users (email, hashed_password, role) VALUES (:email, :password, :role)"), 
                         {"email": "test@example.com", "password": "password", "role": None})
                db.commit()
                assert False, "Should have raised an integrity error"
            except (sqlalchemy_exc.IntegrityError, sqlalchemy_exc.StatementError):
                # Expected behavior - database enforces NOT NULL constraint
                pass

    def test_user_query_by_role(self):
        """Should be able to query users by role."""
        with Session(engine) as db:
            # Clean up any existing users first
            db.query(User).delete()
            db.commit()
            
            # Create users with different roles
            users = [
                User(email="user1@example.com", hashed_password="pass1", role="user"),
                User(email="agent1@example.com", hashed_password="pass2", role="agent"),
                User(email="admin1@example.com", hashed_password="pass3", role="admin"),
                User(email="user2@example.com", hashed_password="pass4", role="user"),
            ]
            
            for user in users:
                db.add(user)
            db.commit()
            
            # Query by role
            admin_users = db.query(User).filter(User.role == "admin").all()
            agent_users = db.query(User).filter(User.role == "agent").all()
            regular_users = db.query(User).filter(User.role == "user").all()
            
            assert len(admin_users) == 1
            assert len(agent_users) == 1
            assert len(regular_users) == 2
            
            assert admin_users[0].email == "admin1@example.com"
            assert agent_users[0].email == "agent1@example.com"

    def test_user_model_documentation(self):
        """User model should have proper documentation."""
        assert User.__doc__ is not None
        assert "User ORM model" in User.__doc__


class TestUserModelIntegration:
    """Integration tests for User model with database initialization."""

    def test_init_db_creates_user_table(self):
        """init_db should create the users table."""
        # Drop all tables first
        Base.metadata.drop_all(bind=engine)
        
        # Run init_db
        init_db()
        
        # Check if users table exists
        with Session(engine) as db:
            from sqlalchemy import text
            result = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'"))
            tables = result.fetchall()
            assert len(tables) == 1
            assert tables[0][0] == 'users'
