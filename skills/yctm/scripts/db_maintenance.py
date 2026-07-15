#!/usr/bin/env python3
"""
Script di manutenzione del database SQLite per YCTM.
Permette di visualizzare le statistiche e resettare gli stati di errore dei video.
"""

import argparse
import os
import sqlite3

DATABASE_PATH = os.environ.get("YCTM_DATABASE_PATH", "data/yctm.sqlite3")


def get_connection() -> sqlite3.Connection:
    if not os.path.exists(DATABASE_PATH):
        raise FileNotFoundError(f"Database non trovato in {DATABASE_PATH}.")
    return sqlite3.connect(DATABASE_PATH)


def show_stats() -> None:
    """Mostra le statistiche globali e suddivise per canale."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Statistiche globali
        cursor.execute("SELECT status, COUNT(*) FROM videos GROUP BY status")
        global_stats = cursor.fetchall()

        print("\n=== STATISTICHE GLOBALI VIDEO ===")
        if not global_stats:
            print("Nessun video presente nel database.")
        for status, count in global_stats:
            print(f"- {status:<15}: {count}")

        # Statistiche canali
        cursor.execute("""
            SELECT c.title, c.id, 
                   COUNT(v.id) as total,
                   SUM(CASE WHEN v.status = 'stored' THEN 1 ELSE 0 END) as stored,
                   SUM(CASE WHEN v.status = 'terminal_error' THEN 1 ELSE 0 END) as terminal_error,
                   SUM(CASE WHEN v.status = 'retryable_error' THEN 1 ELSE 0 END) as retryable,
                   SUM(CASE WHEN v.status = 'pending' THEN 1 ELSE 0 END) as pending
            FROM channels c
            LEFT JOIN videos v ON c.id = v.channel_id
            GROUP BY c.id
        """)
        channel_stats = cursor.fetchall()

        print("\n=== STATISTICHE DETTAGLIATE CANALI ===")
        for row in channel_stats:
            title, cid, total, stored, terminal, retryable, pending = row
            print(f"\nCanale: {title} ({cid})")
            print(f"  Totale video tracciati: {total}")
            print(f"  - Stored (acquisiti):  {stored or 0}")
            print(f"  - Pending:             {pending or 0}")
            print(f"  - Retryable Error:     {retryable or 0}")
            print(f"  - Terminal Error:      {terminal or 0}")

        conn.close()
    except Exception as e:
        print(f"Errore durante il recupero delle statistiche: {e}")


def reset_errors(channel_id: str | None = None, video_id: str | None = None) -> None:
    """Resetta gli stati di errore a pending per riprovare l'acquisizione."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        if video_id:
            cursor.execute("""
                UPDATE videos 
                SET status = 'pending', attempt_count = 0, last_error = NULL 
                WHERE id = ? AND status = 'terminal_error'
            """, (video_id,))
            affected = cursor.rowcount
            print(f"Resettato video {video_id}: {affected} record modificati.")
        elif channel_id:
            cursor.execute("""
                UPDATE videos 
                SET status = 'pending', attempt_count = 0, last_error = NULL 
                WHERE channel_id = ? AND status = 'terminal_error'
            """, (channel_id,))
            affected = cursor.rowcount
            print(f"Resettati video per il canale {channel_id}: {affected} record modificati.")
        else:
            cursor.execute("""
                UPDATE videos 
                SET status = 'pending', attempt_count = 0, last_error = NULL 
                WHERE status = 'terminal_error'
            """)
            affected = cursor.rowcount
            print(f"Resettati tutti i video in terminal_error: {affected} record modificati.")

        conn.commit()
        conn.close()
        print("Database aggiornato con successo.")
    except Exception as e:
        print(f"Errore durante l'aggiornamento del database: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Strumento di Manutenzione Database YCTM")
    subparsers = parser.add_subparsers(dest="command", help="Comando da eseguire")

    # Command stats
    subparsers.add_parser("stats", help="Visualizza statistiche di acquisizione")

    # Command reset
    reset_parser = subparsers.add_parser(
        "reset-errors", help="Resetta gli stati terminal_error a pending"
    )
    reset_parser.add_argument("--channel", help="ID del canale specifico (UC...)")
    reset_parser.add_argument("--video", help="ID del video specifico")

    args = parser.parse_args()

    if args.command == "stats":
        show_stats()
    elif args.command == "reset-errors":
        reset_errors(channel_id=args.channel, video_id=args.video)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
