# PCDistant

Deux applications C# pour **Visual Studio 2022 sous Windows** :

- **PCDistant.Host** : application Windows Forms installée sur le PC à consulter.
- **PCDistant.Client** : application .NET MAUI pour téléphone Android et PC Windows.

Le client envoie une requête au PC, qui répond avec une capture PNG de l'écran principal ou une liste des applications ayant une fenêtre ouverte (nom, PID, titre). Pas de prise de contrôle, d'enregistrement vidéo ni de surveillance cachée. Le partage doit être activé manuellement à chaque lancement.

## Prérequis

- Windows 10 version 1809 minimum / Windows 11 pour l'hôte ; Windows 10 version 2004 ou ultérieure recommandé pour développer.
- Visual Studio 2022 **17.12 ou ultérieur**, SDK **.NET 8** et charges de travail **Développement Desktop .NET** et **Développement d'interface utilisateur d'application multiplateforme .NET** (.NET MAUI, Android SDK et Windows SDK inclus).
- Téléphone Android **6.0 / API 23** minimum ; pour déboguer, activer les options développeur et le débogage USB.
- PC et téléphone sur le **même réseau privé**, sans isolation des clients Wi-Fi. Pour le client Windows, utiliser le même réseau ou le même PC.

## Démarrage dans Visual Studio

1. Ouvrir `PCDistant.sln` et laisser NuGet restaurer les dépendances.
2. Définir **PCDistant.Host** comme projet de démarrage et lancer avec F5.
3. Cliquer sur **Activer le partage**. Autoriser l'application dans le pare-feu Windows **uniquement sur les réseaux privés**.
4. Relever l'adresse IPv4 Wi-Fi/Ethernet affichée (`http://192.168.x.x:5080`) et le code de 32 caractères. Si plusieurs adresses sont proposées, choisir celle de la carte reliée au même réseau que le téléphone.
5. Définir **PCDistant.Client** comme projet de démarrage. Choisir un téléphone Android connecté en USB ou la cible **Windows Machine**, puis lancer. Garder l'hôte ouvert (on peut lancer son EXE séparément).
6. Saisir l'adresse et le code, puis toucher **Demander une capture** ou **Lister les applications**.
7. Cliquer sur **Arrêter le partage** sur le PC pour refuser les nouvelles demandes. Fermer l'hôte arrête également le serveur.

Le PC doit rester éveillé avec une session graphique ouverte et déverrouillée. La capture ne couvre que l'écran principal ; les écrans sécurisés de Windows ne sont pas pris en charge. Chaque bouton déclenche une seule requête, sans actualisation automatique. Les données restent en mémoire, sans enregistrement sur disque par l'application.

### Pare-feu (si nécessaire)

Dans PowerShell **en administrateur**, autoriser le port sur le profil privé seulement :

```powershell
New-NetFirewallRule -DisplayName "PCDistant LAN" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5080 -Profile Private -RemoteAddress LocalSubnet
```

Pour supprimer cette règle :

```powershell
Remove-NetFirewallRule -DisplayName "PCDistant LAN"
```

Ne désactivez pas le pare-feu. Ne créez pas de redirection de port sur le routeur.

## Générer des applications installables / distribuables

Dans un terminal développeur Visual Studio à la racine :

```powershell
# Hôte Windows autonome : distribuer tout le dossier artifacts/host.
dotnet publish src/PCDistant.Host -c Release -r win-x64 --self-contained true -o artifacts/host

# Client Android : APK de test signé avec la clé de débogage.
dotnet build src/PCDistant.Client -f net8.0-android -c Debug -p:AndroidPackageFormats=apk

# Client Windows (non empaqueté).
dotnet publish src/PCDistant.Client -f net8.0-windows10.0.19041.0 -c Release -r win-x64 -p:WindowsAppSDKSelfContained=true --self-contained true -o artifacts/client-windows
```

L'APK de test se trouve sous `src/PCDistant.Client/bin/Debug/net8.0-android/`, avec un nom se terminant par `-Signed.apk`. On peut l'installer par `adb install -r <chemin-vers-apk>` ou le copier sur le téléphone puis autoriser cette source d'installation. Pour une distribution publique, utiliser une clé de signature de production personnelle, conservée hors du dépôt. Aucun installateur MSI ni publication Play Store n'est fourni.

## Sécurité et limites importantes

- **Prototype réseau local : HTTP n'est pas chiffré.** Le code et les captures peuvent être interceptés par un tiers ayant accès au trafic. Le code limite les accès non autorisés mais **ne remplace pas TLS**. Utiliser uniquement un réseau privé de confiance ; pas de Wi-Fi public ni d'exposition Internet.
- Le code aléatoire de 128 bits est renouvelé à chaque lancement de l'hôte, n'est pas sauvegardé et doit rester secret. Redémarrer l'hôte pour le révoquer. Le client ne sauvegarde pas le code.
- L'hôte écoute sur toutes les interfaces IPv4, port 5080 ; la restriction réseau repose sur le pare-feu. Pas de découverte automatique, de serveur cloud, de service au démarrage ou de tâche cachée.
- Toute personne possédant le code et un accès réseau peut demander des captures pendant que le partage est actif. Les titres des fenêtres et les captures peuvent révéler des données personnelles. Une capture déjà reçue ne peut pas être révoquée.
- La liste inclut les processus avec une fenêtre principale visible, **pas tous les processus système ou d'arrière-plan**. Les processus inaccessibles ou terminés pendant la requête sont ignorés.
- Avant une utilisation hors LAN, prévoir HTTPS avec validation de certificat, appairage par appareil et limitation de débit. Cette version n'est pas destinée à Internet.

## API locale

Toutes les routes requièrent `Authorization: Bearer <code>`. Une requête non authentifiée reçoit `401`. Les réponses sont marquées `Cache-Control: no-store`.

| Méthode | Route | Réponse |
| --- | --- | --- |
| GET | `/api/screenshot` | `image/png`, écran principal |
| GET | `/api/apps` | JSON `[{ "id": 123, "name": "notepad", "title": "Notes" }]` |

Le code n'est jamais placé dans une URL. Aucune route ne permet de lancer/arrêter un programme ou d'exécuter une commande.

## Vérification manuelle

- [ ] Compiler les deux projets sur Windows avec les charges de travail indiquées.
- [ ] Avant activation / après arrêt : la connexion au port 5080 échoue.
- [ ] Sans code ou avec un mauvais code : réponse HTTP 401, aucune donnée.
- [ ] Code valide : capture du bureau actuel affichée sur Android puis sur Windows.
- [ ] Ouvrir le Bloc-notes : il apparaît dans la liste ; le fermer puis redemander : il disparaît.
- [ ] Demander une capture : l'heure de la demande apparaît dans la fenêtre de l'hôte.
- [ ] Redémarrer l'hôte : l'ancien code ne fonctionne plus.
- [ ] Adresse erronée / Wi-Fi coupé : le client affiche une erreur et réactive ses boutons.
- [ ] Tester refus de pare-feu, écran verrouillé et plusieurs moniteurs ; pas de promesse de capture d'une session verrouillée.

**État de validation :** les fichiers de projet, manifests et la structure de solution ont été contrôlés statiquement. La compilation et les tests Windows/Android restent à réaliser : l'environnement de création Linux ne dispose pas du SDK .NET, de Visual Studio ni d'un appareil Android.
