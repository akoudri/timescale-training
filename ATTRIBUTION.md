# Attribution

Les jeux de données de la formation MISTRAL sont **synthétiques** : aucune
ligne n'est copiée d'un jeu réel. Le générateur (répertoire `generateur/`)
est en revanche **calibré statistiquement** sur des données SCADA réelles :

> Données de calibration issues des jeux SCADA **Kelmarsh** et
> **Penmanshiel**, publiés par **Cubico Sustainable Investments Ltd** sous
> licence **CC-BY-4.0**.

- Kelmarsh : DOI [10.5281/zenodo.8252025](https://doi.org/10.5281/zenodo.8252025) — utilisé (année 2020, 6 × Senvion MM92)
- Penmanshiel : DOI [10.5281/zenodo.5946808](https://doi.org/10.5281/zenodo.5946808) — source de réserve, même format

Détail de la méthode d'extraction : `generateur/CALIBRATION.md`.
Les empreintes et la mention d'attribution figurent aussi dans le
`MANIFESTE.json` produit avec les artefacts.
