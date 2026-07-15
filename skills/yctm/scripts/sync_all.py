#!/usr/bin/env python3
"""
Script di sincronizzazione batch per YCTM.
Legge tutti i canali registrati nel database ed esegue il sync sequenziale.
"""

import os
import sqlite3
import subprocess
import sys

# Carica percorsi di default o da variabili d'ambiente
DATABASE_PATH = os.environ.get("YCTM_DATABASE_PATH", "data/yctm.sqlite3")


def get_registered_channels() -> list[tuple[str, str]]:
    """Recupera la lista dei canali (id, titolo) dal database."""
    if not os.path.exists(DATABASE_PATH):
        print(
            f"Errore: database non trovato in {DATABASE_PATH}.\n"
            "Inizializzalo prima con 'yctm init-db'."
        )
        return []

    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, title FROM channels")
        channels = cursor.fetchall()
        conn.close()
        return channels
    except Exception as e:
        print(f"Errore durante l'accesso al database: {e}")
        return []


def sync_all_channels() -> None:
    """Esegue il sync per ciascun canale registrato."""
    channels = get_registered_channels()
    if not channels:
        print("Nessun canale registrato da sincronizzare.")
        return

    print(f"Trovati {len(channels)} canali da sincronizzare.")
    success_count = 0
    fail_count = 0

    for channel_id, title in channels:
        print("\n" + "=" * 60)
        print(f"Sincronizzazione in corso: {title} ({channel_id})")
        print("=" * 60)

        # Costruisce ed esegue il comando CLI yctm sync
        cmd = ["yctm", "sync", channel_id]

        try:
            result = subprocess.run(cmd, capture_output=False, text=True, check=False)
            if result.returncode == 0:
                print(f"\n[OK] Sincronizzazione completata con successo per {title}.")
                success_count += 1
            else:
                print(f"\n[ERRORE] Il comando sync per {title} ha restituito: {result.returncode}")
                fail_count += 1
        except FileNotFoundError:
            # Riprova eseguendo come modulo python se yctm non è installato globalmente
            fallback_cmd = [sys.executable, "-m", "yctm.cli.app", "sync", channel_id]
            try:
                result = subprocess.run(fallback_cmd, capture_output=False, text=True, check=False)
                if result.returncode == 0:
                    print(f"\n[OK] Sincronizzazione completata con successo per {title}.")
                    success_count += 1
                else:
                    print(
                        f"\n[ERRORE] Il comando sync per {title} ha restituito: {result.returncode}"
                    )
                    fail_count += 1
            except Exception as e:
                print(f"\n[ERRORE] Impossibile avviare il processo di sync per {title}: {e}")
                fail_count += 1
        except Exception as e:
            print(f"\n[ERRORE] Errore inaspettato durante il sync di {title}: {e}")
            fail_count += 1

    print("\n" + "=" * 60)
    print("Riepilogo Sincronizzazione Batch:")
    print(f"Canali elaborati con successo: {success_count}/{len(channels)}")
    if fail_count > 0:
        print(f"Canali falliti o con errori: {fail_count}/{len(channels)}")
    print("=" * 60)


if __name__ == "__main__":
    sync_all_channels()
