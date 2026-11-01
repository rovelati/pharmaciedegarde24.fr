# PharmacieDeGarde24.fr 🇫🇷 💊

[![Site Officiel](https://img.shields.io/badge/Site%20Officiel-pharmaciedegarde24.fr-059669?style=for-the-badge&logo=google-chrome&logoColor=white)](https://pharmaciedegarde24.fr/)
[![Open Data France](https://img.shields.io/badge/Open%20Data-FINESS%20%2F%20data.gouv.fr-blue?style=for-the-badge&logo=datagov)](https://data.gouv.fr)
[![Statut](https://img.shields.io/badge/Statut-En%20Ligne%2024%2F7-brightgreen?style=for-the-badge)](https://pharmaciedegarde24.fr/)
[![Licence](https://img.shields.io/badge/Licence-MIT-yellow?style=for-the-badge)](LICENSE)

> **[PharmacieDeGarde24.fr](https://pharmaciedegarde24.fr/)** est la plateforme ouverte de référence pour localiser en temps réel les **pharmacies de garde ouvertes 24h/24, la nuit, le dimanche et les jours fériés** dans l'ensemble des 101 départements français.

---

## 🌟 Fonctionnalités Clés & Liens Directs

- **📍 [Outil Géolocalisé « Autour de moi »](https://pharmaciedegarde24.fr/autour-de-moi/)**  
  Recherche instantanée à 1 clic par coordonnées GPS : affiche les officines les plus proches avec itinéraire direct (Google Maps / Apple Maps / Waze) et statut d'ouverture en direct.
- **🗺️ [Annuaire National des Départements](https://pharmaciedegarde24.fr/pharmacie-de-garde/)**  
  Couverture exhaustive des 101 départements métropolitains et d'outre-mer (Guadeloupe, Martinique, Guyane, La Réunion, Mayotte).
- **🌙 Service d'Urgence Nuit & Dimanche**  
  Informations réglementaires sur le fonctionnement à volets fermés, ordonnances obligatoires de nuit, permanence téléphonique **3237** et numéros d'urgence (**15 SAMU**, **17 Police/Gendarmerie**, **112 Europe**).
- **⭐ Avis Vérifiés & Photos Street View**  
  Enrichissement cartographique quotidien comprenant les avis clients Google Places, notes moyennes et photos réelles de devanture pour repérer facilement l'officine de nuit.

---

## 🏙️ Accès Rapide par Métropole

| Métropole | Département | Lien Officiel |
| :--- | :---: | :--- |
| **Paris** | 75 | [Pharmacie de garde à Paris](https://pharmaciedegarde24.fr/pharmacie-de-garde/75/paris/) |
| **Marseille** | 13 | [Pharmacie de garde à Marseille](https://pharmaciedegarde24.fr/pharmacie-de-garde/13/marseille/) |
| **Lyon** | 69 | [Pharmacie de garde à Lyon](https://pharmaciedegarde24.fr/pharmacie-de-garde/69/lyon/) |
| **Toulouse** | 31 | [Pharmacie de garde à Toulouse](https://pharmaciedegarde24.fr/pharmacie-de-garde/31/toulouse/) |
| **Nice** | 06 | [Pharmacie de garde à Nice](https://pharmaciedegarde24.fr/pharmacie-de-garde/06/nice/) |
| **Nantes** | 44 | [Pharmacie de garde à Nantes](https://pharmaciedegarde24.fr/pharmacie-de-garde/44/nantes/) |
| **Montpellier** | 34 | [Pharmacie de garde à Montpellier](https://pharmaciedegarde24.fr/pharmacie-de-garde/34/montpellier/) |
| **Strasbourg** | 67 | [Pharmacie de garde à Strasbourg](https://pharmaciedegarde24.fr/pharmacie-de-garde/67/strasbourg/) |
| **Bordeaux** | 33 | [Pharmacie de garde à Bordeaux](https://pharmaciedegarde24.fr/pharmacie-de-garde/33/bordeaux/) |
| **Lille** | 59 | [Pharmacie de garde à Lille](https://pharmaciedegarde24.fr/pharmacie-de-garde/59/lille/) |
| **Rennes** | 35 | [Pharmacie de garde à Rennes](https://pharmaciedegarde24.fr/pharmacie-de-garde/35/rennes/) |
| **Toulon** | 83 | [Pharmacie de garde à Toulon](https://pharmaciedegarde24.fr/pharmacie-de-garde/83/toulon/) |
| **Reims** | 51 | [Pharmacie de garde à Reims](https://pharmaciedegarde24.fr/pharmacie-de-garde/51/reims/) |
| **Saint-Étienne** | 42 | [Pharmacie de garde à Saint-Étienne](https://pharmaciedegarde24.fr/pharmacie-de-garde/42/saint-etienne/) |
| **Le Havre** | 76 | [Pharmacie de garde à Le Havre](https://pharmaciedegarde24.fr/pharmacie-de-garde/76/le-havre/) |
| **Dijon** | 21 | [Pharmacie de garde à Dijon](https://pharmaciedegarde24.fr/pharmacie-de-garde/21/dijon/) |
| **Angers** | 49 | [Pharmacie de garde à Angers](https://pharmaciedegarde24.fr/pharmacie-de-garde/49/angers/) |
| **Grenoble** | 38 | [Pharmacie de garde à Grenoble](https://pharmaciedegarde24.fr/pharmacie-de-garde/38/grenoble/) |
| **Nîmes** | 30 | [Pharmacie de garde à Nîmes](https://pharmaciedegarde24.fr/pharmacie-de-garde/30/nimes/) |
| **Aix-en-Provence** | 13 | [Pharmacie de garde à Aix-en-Provence](https://pharmaciedegarde24.fr/pharmacie-de-garde/13/aix-en-provence/) |

---

## 📊 Données Publiques & Open Data

Les données d'établissements sont issues des répertoires officiels français :
- **FINESS** (*Fichier National des Établissements Sanitaires et Sociaux*) publié par le **Ministère de la Santé et de la Prévention** et la **DGS**.
- **Base Adresse Nationale (BAN)** pour le géocodage haute précision des adresses d'officines.
- **Assurance Maladie (Ameli)** pour les informations tarifaires et les honoraires conventionnés de garde (5 € le dimanche/jour férié, 8 € la nuit).

### API Publique Open Data (JSON Shards)
Chaque département dispose d'un endpoint JSON statique haute performance mis à jour en continu :
```
https://pharmaciedegarde24.fr/data/shards/{departement_code}.json
```
Exemple : [https://pharmaciedegarde24.fr/data/shards/75.json](https://pharmaciedegarde24.fr/data/shards/75.json) (Paris).

---

## 🛠️ Stack Technique & Architecture

- **Générateur Statica (SSG)** : [Astro 5](https://astro.build/) compilant plus de 5.360 pages en moins de 6 secondes.
- **Cartographie** : [Leaflet](https://leafletjs.com/) + Leaflet MarkerCluster avec tuiles OpenStreetMap et mode sombre dynamique.
- **Infrastructure Edge** : [Cloudflare Pages](https://pages.cloudflare.com/) avec purge globale du cache via API.
- **Conformité RGPD** : Google Consent Mode v2 & Google Funding Choices CMP (IAB TCF v2.2 certifié).
- **SEO & Données Structurées** :
  - `MedicalWebPage` & `Pharmacy` Schema.org
  - `BreadcrumbList` sur l'ensemble des niveaux d'arborescence
  - `FAQPage` pour l'obtention des Rich Snippets Google

---

## 🚀 Développement Local

```bash
# 1. Cloner le dépôt
git clone https://github.com/rovelati/pharmaciedegarde24.fr.git
cd pharmaciedegarde24.fr/site

# 2. Installer les dépendances
npm install

# 3. Lancer le serveur de développement
npm run dev

# 4. Compiler le site statique prêt pour le déploiement
npm run build
```

---

## 📄 Informations & Contact

- **Site Web** : [https://pharmaciedegarde24.fr](https://pharmaciedegarde24.fr)
- **Mentions Légales** : [https://pharmaciedegarde24.fr/mentions-legales/](https://pharmaciedegarde24.fr/mentions-legales/)
- **Politique de Confidentialité** : [https://pharmaciedegarde24.fr/politique-de-confidentialite/](https://pharmaciedegarde24.fr/politique-de-confidentialite/)
- **Contact** : info@pharmaciedegarde24.fr
- **Licence** : [MIT](LICENSE)
