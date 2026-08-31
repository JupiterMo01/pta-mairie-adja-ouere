"""
Script d'initialisation de la base de données.
A exécuter une seule fois après l'installation.
"""
import secrets
from app import create_app
from models import db, User, Annee

app = create_app()

with app.app_context():
    db.create_all()
    print("✅ Tables créées.")

    # Compte administrateur par défaut
    # Le mot de passe est généré aléatoirement à chaque installation — jamais codé en dur
    if not User.query.filter_by(login='admin').first():
        mdp_initial = secrets.token_urlsafe(14)
        admin = User(
            nom='Administrateur',
            prenom='Super',
            login='admin',
            role='admin_editeur',
            actif=True,
        )
        admin.set_password(mdp_initial)
        db.session.add(admin)
        print("👤 Compte admin créé.")
        print("═" * 50)
        print(f"  login         : admin")
        print(f"  mot de passe  : {mdp_initial}")
        print("  ⚠️  Notez ce mot de passe — il ne sera plus affiché.")
        print("═" * 50)
    else:
        print("ℹ️  Compte admin existant, ignoré.")

    # Année courante
    if not Annee.query.filter_by(annee=2026).first():
        db.session.add(Annee(annee=2026, actif=True))
        print("📅 Année 2026 créée et activée.")
    else:
        print("ℹ️  Année 2026 existante, ignorée.")

    db.session.commit()
    print("\n✅ Initialisation terminée !")
    print("═" * 50)
    print("  Lancez ensuite : run.bat")
    print("  Accès : http://localhost:5000")
    print("═" * 50)