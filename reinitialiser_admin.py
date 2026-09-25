"""
reinitialiser_admin.py
Secours : définit un nouveau mot de passe pour le compte de l'administrateur principal
(identifiant « admin ») lorsqu'il a été oublié. Le compte est aussi réactivé et remis
administrateur éditeur si nécessaire.

Ce script se lance uniquement depuis la console du serveur : seule une personne ayant
accès au serveur peut donc l'utiliser.

  PythonAnywhere (console Bash) :
      cd ~/pta_mairie && python3.10 reinitialiser_admin.py

  Serveur de la Mairie :
      cd /srv/abojuto/app && sudo -u abojuto /srv/abojuto/venv/bin/python reinitialiser_admin.py

Auteur : GBOYOU A. Jupiter, DDLP, Mairie d'Adja-Ouèrè
"""
import getpass
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
# La clé secrète ne sert qu'aux sessions web : une valeur temporaire suffit ici
os.environ.setdefault('SECRET_KEY', 'reinitialisation-console')

from app import create_app          # noqa: E402
from models import db, User, AuditLog  # noqa: E402
from utils import valider_mdp       # noqa: E402

LOGIN_PRINCIPAL = 'admin'


def main():
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(login=LOGIN_PRINCIPAL).first()
        if not user:
            print(f"Aucun compte avec l'identifiant « {LOGIN_PRINCIPAL} » dans cette base.")
            return 1

        print("Réinitialisation du mot de passe de l'administrateur principal")
        print(f"Compte : {user.prenom} {user.nom} (identifiant « {user.login} »)")
        print("Règles : 10 caractères minimum, une majuscule, un chiffre, un caractère spécial.\n")

        for _ in range(3):
            mdp = getpass.getpass("Nouveau mot de passe (non affiché) : ")
            erreur = valider_mdp(mdp)
            if erreur:
                print(f"  {erreur}\n")
                continue
            if getpass.getpass("Confirmez le mot de passe : ") != mdp:
                print("  Les deux saisies ne correspondent pas.\n")
                continue
            break
        else:
            print("Trois essais sans succès : aucune modification n'a été faite.")
            return 1

        user.set_password(mdp)
        rappels = []
        if not user.actif:
            user.actif = True
            rappels.append('compte réactivé')
        if user.role != 'admin_editeur':
            user.role = 'admin_editeur'
            rappels.append('rôle administrateur éditeur rétabli')
        db.session.add(AuditLog(
            user_id=user.id, user_nom=f"{user.prenom} {user.nom}", user_role=user.role,
            action='mdp_reinit_console',
            details="Mot de passe de l'administrateur principal redéfini depuis la console du serveur"
                    + (f" ({', '.join(rappels)})" if rappels else ''),
            ip='console'))
        db.session.commit()

        print("\nMot de passe enregistré." + (f" ({', '.join(rappels)})" if rappels else ''))
        print("Vous pouvez vous connecter à la plateforme avec ce nouveau mot de passe.")
        print("Sur PythonAnywhere, aucun rechargement n'est nécessaire.")
        return 0


if __name__ == '__main__':
    sys.exit(main())
