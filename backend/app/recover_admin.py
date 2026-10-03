"""Run only from an authorized PC/server console; never a public reset by email."""
import argparse
import os
from pathlib import Path
from urllib.parse import urlparse


def main():
    parser = argparse.ArgumentParser(description="Créer un lien local de récupération administrateur FUSAA (15 minutes).")
    parser.add_argument("--email", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--server", action="store_true", help="Utiliser la base configurée du serveur, uniquement depuis sa console autorisée.")
    args = parser.parse_args()
    parsed = urlparse(args.base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.query or parsed.fragment:
        parser.error("--base-url doit être l'adresse HTTP(S) de votre application")
    if not args.server:
        local_db = Path(__file__).resolve().parents[1] / "fusaa.db"
        if not local_db.is_file(): parser.error("Base locale introuvable. Démarrez d'abord l'application avec scripts/start-local.ps1.")
        # Explicitly ignore a hosted DATABASE_URL in .env for default local use.
        os.environ["DATABASE_URL"] = "sqlite:///" + local_db.as_posix()
    from sqlalchemy import inspect
    from .database import SessionLocal, engine
    from .models import User, OrganizationMember
    from .auth_actions import issue_link
    from .services import audit
    if not inspect(engine).has_table("auth_action_tokens") or "auth_version" not in {c["name"] for c in inspect(engine).get_columns("users")}:
        parser.error("Appliquez les migrations (alembic upgrade head) avant la récupération.")
    with SessionLocal() as db:
        user = db.query(User).filter_by(email=args.email.strip().lower(), is_active=True).first()
        if not user or not db.query(OrganizationMember).filter(OrganizationMember.user_id==user.id, OrganizationMember.role.in_(["OWNER", "ADMIN"])).first():
            parser.error("Aucun administrateur actif ne correspond à cette adresse.")
        link = issue_link(db, user, "RESET")
        audit(db, "LOCAL_CONSOLE", "ADMIN_RECOVERY_LINK_CREATED", "User", user.id)
        db.commit()
    print("Lien privé, valable 15 minutes et utilisable une seule fois. Ne le partagez pas :")
    print(args.base_url.rstrip("/") + link)


if __name__ == "__main__": main()
