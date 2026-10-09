from pymongo.errors import DuplicateKeyError

from app.core.security import hash_password, verify_password
from app.database.connection import get_database
from app.models.user import UserModel


class AuthService:
    def __init__(self):
        self.db = get_database()
        self.users = self.db[UserModel.collection_name]

    def create_user(
        self,
        name: str,
        email: str,
        password: str,
        role: str,
        phone: str | None = None,
    ) -> dict:

        email = email.strip().lower()

        existing_user = self.users.find_one({"email": email})

        if existing_user:
            raise ValueError("Email is already registered")

        password_hash = hash_password(password)

        document = UserModel.create_document(
            name=name,
            email=email,
            password_hash=password_hash,
            role=role,
            phone=phone,
        )

        try:
            result = self.users.insert_one(document)
        except DuplicateKeyError as exc:
            raise ValueError("Email is already registered") from exc

        document["_id"] = result.inserted_id

        return UserModel.serialize(document)

    def authenticate_user(
        self,
        email: str,
        password: str,
    ) -> dict | None:

        email = email.strip().lower()

        user = self.users.find_one({"email": email})

        if not user:
            return None

        password_hash = user.get("password_hash")
        if not password_hash or not verify_password(password, password_hash):
            return None

        if not user.get("is_active", True):
            return None

        return UserModel.serialize(user)