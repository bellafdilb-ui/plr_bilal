# RAPPORT DE TESTS LOGICIEL

**Projet :** PLR Vet - Pupillary Light Reflex
**Version :** 5.0 (branche `main`, commit `79f1263`)
**Date :** 25 mars 2026
**Testeur :** Bilal Siembida
**Environnement :** Windows 11 Pro 10.0.26200 / Python 3.10.11 / PySide6 6.11.0 / Qt 6.11.0
**Framework de test :** pytest 9.0.2 + pytest-qt 4.5.0 + pytest-cov 7.1.0

---

## 1. RESUME EXECUTIF

| Indicateur             | Valeur       |
|------------------------|--------------|
| Tests exécutés         | **111**      |
| Tests réussis          | **111**      |
| Tests échoués          | **0**        |
| Taux de réussite       | **100%**     |
| Durée d'exécution      | **4.17 s**   |
| Couverture globale     | **20%**      |
| Modules critiques testés | 6 / 13    |

**Verdict global : PASS**

> Les 6 modules critiques du backend (protocole série, hardware, moteur PLR, caméra, base de données, configuration) sont couverts par des tests unitaires. Les modules d'interface graphique (UI) ne sont pas couverts à ce stade (test manuel uniquement).

---

## 2. PERIMETRE DE TEST

### 2.1 Modules testés (backend)

| Module                  | Fichier de test               | Nb tests | Couverture |
|-------------------------|-------------------------------|----------|------------|
| Protocole série         | `test_serial_protocol.py`     | 27       | 44%        |
| Hardware Manager        | `test_hardware_manager.py`    | 20       | 68%        |
| Moteur PLR              | `test_plr_engine.py`          | 10       | 93%        |
| Base de données         | `test_database.py`            | 21       | 89%        |
| Configuration           | `test_config.py`              | 11       | 15% *      |
| Camera Engine           | `test_camera_engine.py`       | 22       | 36% *      |

\* *La couverture de `settings_dialog.py` (15%) et `camera_engine.py` (36%) est faible car ces modules contiennent respectivement une UI Qt et du code hardware IC4 non mockable en totalité. Les fonctions logiques pures sont testées.*

### 2.2 Modules hors périmètre (UI / analyse)

| Module                     | Raison d'exclusion                        |
|----------------------------|-------------------------------------------|
| `main_application.py`      | Interface graphique principale (887 lignes) — test manuel |
| `settings_dialog.py` (UI)  | Dialogue Qt — test manuel                 |
| `plr_analyzer.py`          | Analyse post-traitement — données réelles nécessaires |
| `plr_results_viewer.py`    | Viewer de résultats — interface Qt        |
| `pdf_generator.py`         | Génération PDF — test d'intégration       |
| `calibration_dialog.py`    | Dialogue calibration — test avec caméra   |
| `welcome_screen.py`        | Écran d'accueil — cosmétique              |
| `serial_console_window.py` | Console de debug série — cosmétique       |
| `styles.py`                | Feuilles de style CSS — cosmétique        |

---

## 3. RESULTATS DETAILLES PAR MODULE

### 3.1 Protocole série (`test_serial_protocol.py`) — 27/27 PASS

**Objectif :** Vérifier le format des commandes PLR et le parsing du buffer série.

| # | Test | Statut | Description |
|---|------|--------|-------------|
| 1 | `test_fmt_basic` | PASS | Format `!version=0;` correct |
| 2 | `test_fmt_empty` | PASS | Commande vide → `!;` |
| 3 | `test_fmt_with_spaces` | PASS | Espaces préservés dans la commande |
| 4 | `test_set_flash_color_blue` | PASS | `BLUE` → `!couleur flash=bleu;` |
| 5 | `test_set_flash_color_red` | PASS | `RED` → `!couleur flash=rouge;` |
| 6 | `test_set_flash_color_white` | PASS | `WHITE` → `!couleur flash=blanc;` |
| 7 | `test_set_flash_color_unknown_defaults_blanc` | PASS | Couleur inconnue → blanc par défaut |
| 8 | `test_set_flash_duration_normal` | PASS | Durée 3s → `!durée flash=003;` |
| 9 | `test_set_flash_duration_clamp_min` | PASS | Durée 0 clampée à 1 |
| 10 | `test_set_flash_duration_clamp_max` | PASS | Durée 99 clampée à 10 |
| 11 | `test_set_flash_intensity_normal` | PASS | Intensité 512 → `0512` (zéro-padded) |
| 12 | `test_set_flash_intensity_clamp_min` | PASS | Intensité -10 clampée à 0 |
| 13 | `test_set_flash_intensity_clamp_max` | PASS | Intensité 9999 clampée à 1023 |
| 14 | `test_set_flash_delay_normal` | PASS | Retard 2s → `!retard flash=002;` |
| 15 | `test_set_flash_delay_clamp_zero` | PASS | Retard 0 autorisé |
| 16 | `test_set_flash_delay_clamp_max` | PASS | Retard 10 clampé à 5 |
| 17 | `test_parse_test_ok` | PASS | Buffer `"TEST OK"` → token émis |
| 18 | `test_parse_ok` | PASS | Buffer `"OK"` → ACK reconnu |
| 19 | `test_parse_signal_D` | PASS | Signal examen `D` détecté |
| 20 | `test_parse_signal_F` | PASS | Signal flash `F` détecté |
| 21 | `test_parse_signal_f` | PASS | Signal flash retardé `f` détecté |
| 22 | `test_parse_signal_A` | PASS | Signal fin flash `A` détecté |
| 23 | `test_parse_version` | PASS | `"version 1.23"` extrait correctement |
| 24 | `test_parse_empty` | PASS | Buffer vide → aucun token |
| 25 | `test_parse_leading_newlines` | PASS | `\r\n` en tête nettoyés |
| 26 | `test_parse_unknown_kept` | PASS | Données inconnues conservées pour accumulation |
| 27 | `test_test_ok_priority_over_ok` | PASS | `"TEST OK"` prioritaire sur `"OK"` |

---

### 3.2 Hardware Manager (`test_hardware_manager.py`) — 20/20 PASS

**Objectif :** Vérifier la file d'attente des commandes, le handshake, les signaux d'examen et la gestion IR.

| # | Test | Statut | Description |
|---|------|--------|-------------|
| 1 | `test_enqueue_sends_immediately_when_idle` | PASS | Envoi immédiat si file vide |
| 2 | `test_enqueue_queues_when_busy` | PASS | Mise en file si commande en cours |
| 3 | `test_ok_triggers_next_command` | PASS | Réception OK → commande suivante |
| 4 | `test_queue_empty_resets_state` | PASS | File vide → `_waiting_ok = False` |
| 5 | `test_configure_flash_sequence_queues_4_commands` | PASS | Configuration flash = 4 commandes |
| 6 | `test_test_ok_completes_handshake` | PASS | `"TEST OK"` → connexion établie |
| 7 | `test_version_response_completes_handshake` | PASS | Réponse version → handshake OK |
| 8 | `test_messages_ignored_before_handshake` | PASS | Messages ignorés avant handshake |
| 9 | `test_signal_D_emits_exam_started` | PASS | Signal D → `exam_started` émis |
| 10 | `test_signal_F_emits_flash_fired` | PASS | Signal F → `flash_fired` émis |
| 11 | `test_signal_f_emits_flash_fired` | PASS | Signal f → `flash_fired` émis |
| 12 | `test_signal_A_emits_flash_ended` | PASS | Signal A → `flash_ended` émis |
| 13 | `test_set_ir_on` | PASS | IR ON → `!marche IR=1;` |
| 14 | `test_set_ir_off` | PASS | IR OFF → `!arret IR=0;` |
| 15 | `test_set_ir_when_disconnected` | PASS | IR ignoré si déconnecté |
| 16 | `test_disconnect_stops_worker` | PASS | Déconnexion → worker stoppé |
| 17 | `test_disconnect_sends_ir_off` | PASS | **Déconnexion éteint l'IR** (fix récent) |
| 18 | `test_start_exam_enqueues_depart` | PASS | Départ examen → `!depart=1234;` |
| 19 | `test_start_exam_blocked_if_already_running` | PASS | Double départ bloqué |
| 20 | `test_stop_flash_clears_queue` | PASS | Arrêt flash → file vidée |

---

### 3.3 Moteur PLR (`test_plr_engine.py`) — 10/10 PASS

**Objectif :** Vérifier la séquence d'examen (configuration, démarrage, synchronisation flash, arrêt).

| # | Test | Statut | Description |
|---|------|--------|-------------|
| 1 | `test_default_values` | PASS | Paramètres par défaut corrects |
| 2 | `test_configure_updates_params` | PASS | `configure()` met à jour les paramètres |
| 3 | `test_configure_duration_conversion` | PASS | Conversion ms → s correcte |
| 4 | `test_start_sets_running` | PASS | `start_test()` → `is_running = True` |
| 5 | `test_stop_clears_running` | PASS | `stop_test()` → arrêt enregistrement |
| 6 | `test_notify_sets_event` | PASS | `notify_flash_fired()` → timestamp capturé |
| 7 | `test_notify_when_not_running` | PASS | Notification sans enregistrement → pas de crash |
| 8 | `test_full_sequence_with_flash` | PASS | Séquence complète avec flash simulé |
| 9 | `test_sequence_timeout_without_flash` | PASS | Arrêt propre sans flash |
| 10 | `test_camera_not_ready` | PASS | Caméra absente → séquence non lancée |

---

### 3.4 Base de données (`test_database.py`) — 21/21 PASS

**Objectif :** Vérifier les opérations CRUD sur la BDD SQLite (patients, examens, clinique, macros).

| # | Test | Statut | Description |
|---|------|--------|-------------|
| 1 | `test_add_patient` | PASS | Ajout patient avec ID valide |
| 2 | `test_add_patient_duplicate_id_fails` | PASS | Doublon tatouage → erreur -1 |
| 3 | `test_search_by_name` | PASS | Recherche par nom |
| 4 | `test_search_by_tattoo` | PASS | Recherche par identifiant puce/tatouage |
| 5 | `test_search_empty_returns_nothing` | PASS | Recherche sans résultat |
| 6 | `test_update_patient` | PASS | Mise à jour race, sexe, date |
| 7 | `test_delete_patient` | PASS | Suppression cascade |
| 8 | `test_name_is_capitalized` | PASS | `"luna"` → `"Luna"` |
| 9 | `test_anonymized_hash_generated` | PASS | Hash SHA-256 (64 chars) |
| 10 | `test_save_exam` | PASS | Enregistrement examen basique |
| 11 | `test_save_exam_with_results` | PASS | Examen avec métriques JSON |
| 12 | `test_get_patient_history` | PASS | Historique multi-examens |
| 13 | `test_history_contains_parsed_results` | PASS | JSON désérialisé dans `results_data` |
| 14 | `test_delete_exam` | PASS | Suppression examen isolé |
| 15 | `test_update_exam_comment` | PASS | Modification commentaire |
| 16 | `test_set_and_get_clinic_info` | PASS | Infos clinique sauvées et relues |
| 17 | `test_clinic_info_empty_by_default` | PASS | Pas de clinique par défaut |
| 18 | `test_clinic_info_upsert` | PASS | Mise à jour (INSERT OR REPLACE) |
| 19 | `test_add_and_get_macro` | PASS | Ajout et lecture macro |
| 20 | `test_delete_macro` | PASS | Suppression macro |
| 21 | `test_multiple_macros` | PASS | Plusieurs macros simultanées |

---

### 3.5 Configuration (`test_config.py`) — 11/11 PASS

**Objectif :** Vérifier le ConfigManager (création, lecture/écriture JSON, valeurs par défaut).

| # | Test | Statut | Description |
|---|------|--------|-------------|
| 1 | `test_creates_default_on_missing_file` | PASS | Fichier absent → config par défaut créée |
| 2 | `test_load_existing_config` | PASS | Lecture config existante |
| 3 | `test_save_and_reload` | PASS | Persistance après save/reload |
| 4 | `test_save_with_argument` | PASS | `save(new_conf)` remplace la config |
| 5 | `test_get_nested_key` | PASS | `get("protocol", "flash_delay_s")` |
| 6 | `test_get_section` | PASS | `get("protocol")` → dict complet |
| 7 | `test_get_missing_key_returns_default` | PASS | Clé absente → valeur par défaut |
| 8 | `test_get_missing_section_returns_empty_dict` | PASS | Section absente → `{}` |
| 9 | `test_default_config_has_all_sections` | PASS | 5 sections obligatoires présentes |
| 10 | `test_default_detection_params` | PASS | Seuil=50, blur=5, ROI=400 |
| 11 | `test_default_flash_color` | PASS | Couleur par défaut = WHITE |

---

### 3.6 Camera Engine (`test_camera_engine.py`) — 22/22 PASS

**Objectif :** Vérifier l'initialisation, la détection pupillaire, le calcul ROI et l'enregistrement. Backend IC4 désactivé (mock OpenCV uniquement).

| # | Test | Statut | Description |
|---|------|--------|-------------|
| 1 | `test_camera_ready` | PASS | Caméra initialisée → `is_ready() = True` |
| 2 | `test_default_params` | PASS | Seuil, blur, mode par défaut |
| 3 | `test_camera_not_ready_if_closed` | PASS | Caméra fermée → `is_ready() = False` |
| 4 | `test_set_threshold` | PASS | Setter seuil binarisation |
| 5 | `test_set_blur_odd` | PASS | Kernel impair conservé |
| 6 | `test_set_blur_even_rounds_up` | PASS | Kernel pair → +1 (doit être impair) |
| 7 | `test_set_display_mode` | PASS | Changement mode affichage |
| 8 | `test_roi_centered` | PASS | ROI 100x100 centrée sur 640x480 |
| 9 | `test_roi_with_offset` | PASS | ROI avec décalage X/Y |
| 10 | `test_roi_clamped_to_image` | PASS | ROI > image → clampée aux bords |
| 11 | `test_roi_zero_image` | PASS | Image 0x0 → ROI (0,0,0,0) |
| 12 | `test_grab_returns_frame` | PASS | `grab_and_detect()` retourne une frame |
| 13 | `test_no_pupil_on_black_image` | PASS | Image noire → pas de détection |
| 14 | `test_grab_failure` | PASS | `read()` échoue → `(None, None)` |
| 15 | `test_grab_exception` | PASS | Exception → `(None, None)` |
| 16 | `test_not_ready_returns_none` | PASS | Caméra fermée → `(None, None)` |
| 17 | `test_mono_frame_converted_to_bgr` | PASS | Frame mono → conversion BGR |
| 18 | `test_start_stop_recording` | PASS | Cycle start/stop enregistrement |
| 19 | `test_csv_file_created` | PASS | Fichier CSV créé avec header |
| 20 | `test_double_stop_no_crash` | PASS | Double arrêt → pas d'exception |
| 21 | `test_release_calls_cap_release` | PASS | `release()` libère la caméra |
| 22 | `test_release_stops_recording` | PASS | `release()` arrête l'enregistrement |

---

## 4. COUVERTURE DE CODE

```
Module                       Lignes   Manquées   Couverture
-----------------------------------------------------------
plr_test_engine.py              83         6        93%
db_manager.py                  151        17        89%
hardware_manager.py            248        79        68%
serial_worker.py                91        51        44%
camera_engine.py               484       312        36%
settings_dialog.py             324       276        15%
main_application.py            887       887         0%
-----------------------------------------------------------
TOTAL (tous modules)          3258      2618        20%
TOTAL (modules testés)        1381       741        46%
```

### Analyse de la couverture

- **Excellent (> 80%)** : `plr_test_engine` (93%), `db_manager` (89%) — les deux modules les plus critiques pour la fiabilité des données.
- **Bon (60-80%)** : `hardware_manager` (68%) — les branches non couvertes sont principalement le code de détection de ports COM et les timeouts asynchrones.
- **Partiel (30-60%)** : `serial_worker` (44%), `camera_engine` (36%) — code fortement lié au hardware (port série physique, caméra IC4).
- **Non couvert (UI)** : `main_application`, `welcome_screen`, `plr_results_viewer`, etc. — interfaces graphiques, testées manuellement.

---

## 5. BUGS IDENTIFIES ET CORRIGES PENDANT LES TESTS

### BUG-001 : IR non éteint à la fermeture du logiciel
- **Sévérité :** Majeure
- **Module :** `hardware_manager.py` → `disconnect_device()`
- **Symptôme :** L'IR reste physiquement allumé quand le logiciel se ferme.
- **Cause :** `disconnect_device()` appelait `stop_flash()` mais pas `set_ir(False)`.
- **Correction :** Ajout de `self.set_ir(False)` avant la fermeture du port série.
- **Statut :** Corrigé et vérifié par `test_disconnect_sends_ir_off`.

### BUG-002 : Désynchronisation état IR au démarrage
- **Sévérité :** Modérée
- **Module :** `main_application.py` → `_send_initial_hardware_config()`
- **Symptôme :** Si l'IR est physiquement allumé et que le logiciel redémarre, l'UI affiche "IR OFF" sans envoyer la commande au µC.
- **Cause :** La commande IR n'était envoyée que si le bouton était coché (`if btn_ir.isChecked()`).
- **Correction :** Envoi systématique de l'état IR (ON ou OFF) au µC après le handshake.
- **Statut :** Corrigé.

### BUG-003 : Effet "zoom" caméra IC4
- **Sévérité :** Majeure
- **Module :** `camera_engine.py` → `open_camera()` et `_restore_ic4_properties()`
- **Symptôme :** L'image apparaît zoomée au lancement, nécessitant IC Capture pour corriger.
- **Cause :** Les propriétés BinningHorizontal/Vertical et DecimationHorizontal/Vertical n'étaient pas réinitialisées à 1 avant de configurer Width/Height.
- **Correction :** Ajout de la réinitialisation du binning/decimation dans les deux chemins d'initialisation.
- **Statut :** Corrigé.

---

## 6. RECOMMANDATIONS

### Priorité haute
1. **Tests d'intégration hardware** — Ajouter un script de test semi-automatique qui vérifie la chaîne complète : connexion série → handshake → envoi commande → réception OK (nécessite le µC branché).
2. **Test de l'analyseur PLR** (`plr_analyzer.py`) — Créer un jeu de données CSV de référence et vérifier les métriques calculées (latence, constriction, vélocité).

### Priorité moyenne
3. **Couverture camera_engine** — Ajouter des tests avec des frames synthétiques contenant un cercle noir (pupille simulée) pour tester la détection de contours.
4. **Test du PDF** — Vérifier la génération PDF avec des données de référence.

### Priorité basse
5. **Tests UI automatisés** — Utiliser pytest-qt pour automatiser les scénarios utilisateur critiques (démarrer examen, changer paramètres, sauvegarder patient).
6. **Intégration continue** — Mettre en place un pipeline CI (GitHub Actions) pour exécuter les tests à chaque push.

---

## 7. ENVIRONNEMENT DE TEST

| Composant | Version |
|-----------|---------|
| OS | Windows 11 Pro 10.0.26200 |
| Python | 3.10.11 |
| pytest | 9.0.2 |
| pytest-qt | 4.5.0 |
| pytest-cov | 7.1.0 |
| PySide6 | 6.11.0 |
| Qt Runtime | 6.11.0 |
| OpenCV | 4.11.0 |
| pyserial | 3.5 |
| SQLite | 3.37.2 (intégré Python) |
| Caméra | DMM 32UVR024-ML (IC4) — présente mais mockée pour les tests |

---

## 8. COMMANDES DE REPRODUCTION

```bash
# Exécuter la suite complète
python -m pytest -v

# Exécuter avec couverture
python -m pytest --cov=. --cov-report=html

# Exécuter un module spécifique
python -m pytest tests/test_hardware_manager.py -v

# Exécuter un test spécifique
python -m pytest tests/test_serial_protocol.py::TestFlashCommands::test_set_flash_color_blue -v
```

---

*Rapport généré le 25/03/2026 — PLR Vet v5.0*
*111 tests | 100% PASS | 3 bugs corrigés*
