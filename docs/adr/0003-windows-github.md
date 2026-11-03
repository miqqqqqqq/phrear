# 0003 – Piattaforma Windows, hosting e CI su GitHub

- Data: 2026-11-03
- Stato: accettata

## Contesto

Gli utenti target lavorano su Windows con QGIS. Le questioni aperte su hosting e sistemi operativi (sez. 25) bloccavano l'avvio di M1a.

## Decisione

- Piattaforma supportata, per ora, solo Windows. Linux si usa per lo sviluppo, senza garanzie di supporto.
- Repository e CI su GitHub. La CI gira su `windows-latest` con lint, type check e test nell'ambiente bloccato (`pixi run lint`, `typecheck`, `test`).

## Alternative scartate

- GitLab, perché l'ecosistema QGIS, MODFLOW 6 e FloPy sta su GitHub e Actions offre runner Windows senza configurazione.
- Windows e Linux supportati da subito, per non raddoppiare test e casi limite prima che serva.

## Conseguenze

- Percorsi, codifiche e lock dei file vanno trattati con la semantica di Windows, per esempio il lock HDF5 delle istantanee (sez. 16).
- Estendere il supporto a Linux o macOS richiede di aggiungere la piattaforma al lockfile e una job di CI dedicata.
