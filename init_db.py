"""
Script d'initialisation de la base de données.
A exécuter une seule fois après l'installation.
"""
from app import create_app
from models import db, User, Annee

app = create_app()

with app.app_context():
    db.create_all()
    print("✅ Tables créées.")

    # Compte administrateur par défaut
    if not User.query.filter_by(login='admin').first():
        admin = User(
            nom='Administrateur',
            prenom='Super',
            login='admin',
            role='admin_editeur',
            actif=True,
        )
        admin.set_password('admin2026')
        db.session.add(admin)
        print("👤 Compte admin créé : login='admin' / mot de passe='admin2026'")
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