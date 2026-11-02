# PCDistant Wi-Fi — version gratuite sans Visual Studio

Agent **Python sous Windows** et interface web responsive pour **Android et PC**. Aucun abonnement, compte externe, service cloud ou logiciel payant requis. Les bibliothèques utilisées sont gratuites. Cette première étape fonctionne uniquement sur un réseau local privé : pas d'accès Internet ni de VPN à configurer.

## Installation sur le PC à consulter

1. Installer **Python 3.11 ou ultérieur** depuis python.org (inclure Tcl/Tk et pip, options standard de l'installateur Windows).
2. Télécharger le dépôt puis ouvrir PowerShell dans son dossier `wifi`.
3. Exécuter :

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe agent.py
```

4. Cliquer sur **Activer le partage**. Le programme affiche une ou plusieurs adresses et un code de 4 chiffres. Choisir l'IPv4 de la carte Wi-Fi/Ethernet connectée au même réseau que le téléphone (`ipconfig` permet de la vérifier).
5. Si Windows le demande, autoriser Python **uniquement sur les réseaux privés**. Ne pas désactiver le pare-feu.

L'agent n'est pas installé au démarrage de Windows. Il reste visible et peut être réduit dans la barre des tâches ; cette version n'a pas encore d'icône dans la zone de notification. Fermer sa fenêtre arrête le partage. Chaque activation génère un nouveau code.

**Ne pas lancer en même temps l'ancien hôte C# : les deux utilisent le port 5080.**

## Consulter depuis Android

1. Connecter le téléphone au même Wi-Fi que le PC. Un PC relié en Ethernet au même routeur convient aussi.
2. Dans Chrome, saisir l'adresse affichée, par exemple **`http://192.168.1.20:5080`**. Bien saisir `http://`, pas `https://`.
3. Recopier le code du PC.
4. Toucher **Voir l'écran** ou **Applications**.

La capture peut être ouverte en grand en la touchant. Il n'y a pas d'actualisation automatique. L'interface est une page adaptée au téléphone, **pas un APK ni une PWA hors ligne**. Selon le navigateur, un raccourci peut être ajouté à l'écran d'accueil ; l'installation complète d'une PWA nécessiterait HTTPS.

Sur un autre PC, ouvrir la même adresse dans un navigateur. Pour un essai sur le PC de l'agent, utiliser `http://localhost:5080`.

## Pare-feu si la page ne s'ouvre pas

Vérifier que le réseau Windows est défini comme **Privé**, et que le Wi-Fi invité / l'isolation des appareils n'est pas activé. Dans PowerShell administrateur, on peut autoriser uniquement le sous-réseau local :

```powershell
New-NetFirewallRule -DisplayName "PCDistant WiFi" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5080 -Profile Private -RemoteAddress LocalSubnet
```

Suppression :

```powershell
Remove-NetFirewallRule -DisplayName "PCDistant WiFi"
```

Ne pas rediriger ce port sur la box et ne pas ouvrir la règle au profil Public.

## Fonctionnalités et sécurité

- Capture de l'écran principal à la demande ; une capture maximum par seconde et une seule en cours.
- Liste des fenêtres visibles : nom de programme, PID, titre. Ce n'est pas la liste de tous les processus système.
- Code aléatoire de 4 chiffres (zéros initiaux possibles) requis par les API, renouvelé à chaque activation. Aucun code n'est enregistré sur disque par le programme ou dans le stockage web.
- Après 5 tentatives incorrectes consécutives, les API sont bloquées pendant 60 secondes pour tous les appareils, même avec le bon code. La page reste accessible. Un accès réussi remet le compteur à zéro. Un code court est moins sûr : réseau privé de confiance uniquement.
- Activité affichée dans la fenêtre du PC. Pas de journal contenant les captures ou le code.
- Pas de sauvegarde automatique des captures ; le navigateur peut toutefois permettre à l'utilisateur de les enregistrer.
- **HTTP n'est pas chiffré : code, titres et images peuvent être interceptés sur le réseau.** Utiliser seulement un réseau privé de confiance. Cette version n'est pas conçue pour Internet ou un Wi-Fi public ; un accès extérieur demandera un transport chiffré et une protection réseau adaptés.
- Le serveur écoute toutes les interfaces IPv4 ; le pare-feu est nécessaire pour limiter son accès au LAN.
- Pas de contrôle souris/clavier, d'exécution de commandes, de lancement automatique ou de mode caché.
- Le PC doit être éveillé et sa session ouverte/déverrouillée. Les écrans sécurisés et les sessions verrouillées ne sont pas pris en charge. Arrêter le partage bloque les nouvelles demandes mais n'efface pas les images déjà reçues.

## Créer un EXE (facultatif, gratuit)

Sur Windows, depuis le dossier `wifi`, après installation des dépendances :

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onedir --windowed --name PCDistant-WiFi --add-data "templates;templates" --add-data "static;static" --collect-all mss agent.py
```

Distribuer **tout le dossier** `dist/PCDistant-WiFi`, pas uniquement l'EXE. Un EXE non signé peut déclencher SmartScreen : aucune signature payante n'est nécessaire pour vos essais personnels. La génération et l'exécution de cet EXE restent à vérifier sur Windows.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests automatisés : authentification, absence de capture sans code, formats, limite de captures, erreurs, révocation par changement de code et en-têtes de sécurité. Les appels capture/processus sont simulés ; ces tests ne prouvent pas la capture réelle Windows.

Tests manuels Windows/Android à faire :

- Activer, ouvrir la page depuis Android, saisir un mauvais code puis le bon.
- Demander une capture ; ouvrir/fermer le Bloc-notes et actualiser la liste.
- Arrêter le partage : aucune nouvelle demande n'aboutit.
- Réactiver : l'ancien code échoue.
- Couper le Wi-Fi : le client affiche une erreur sans rester bloqué.
- Fermer l'agent : le port est fermé.
