import os
import time
import random
import sqlite3
import unittest
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime

# ==============================================================================
# 1. CONFIGURAÇÕES GLOBAIS & CONSTANTES
# ==============================================================================

APP_TITLE = "Senha Secreta Pro - Mastermind"
VERSION = "2.0.0"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "game_data.db")

# Dificuldades: (Tamanho da Senha, Max Tentativas, Permite Repetição)
DIFFICULTIES = {
    "Fácil": {"length": 3, "max_attempts": 12, "allow_duplicates": False},
    "Médio": {"length": 4, "max_attempts": 10, "allow_duplicates": False},
    "Difícil": {"length": 5, "max_attempts": 8, "allow_duplicates": True},
    "Mestre": {"length": 6, "max_attempts": 6, "allow_duplicates": True}
}

THEME_DARK = {
    "bg": "#1e1e2e",
    "fg": "#cdd6f4",
    "panel": "#313244",
    "accent": "#89b4fa",
    "success": "#a6e3a1",
    "danger": "#f38ba8",
    "warning": "#f9e2af"
}


# ==============================================================================
# 2. GESTÃO DE BANCO DE DADOS (SQLite)
# ==============================================================================

class DatabaseManager:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ranking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_name TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    time_seconds REAL NOT NULL,
                    difficulty TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def save_score(self, player_name, score, time_seconds, difficulty, attempts):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ranking (player_name, score, time_seconds, difficulty, attempts)
                VALUES (?, ?, ?, ?, ?)
            """, (player_name, score, time_seconds, difficulty, attempts))
            conn.commit()

    def get_top_scores(self, limit=10):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT player_name, score, time_seconds, difficulty, attempts
                FROM ranking
                ORDER BY score DESC, time_seconds ASC
                LIMIT ?
            """, (limit,))
            return cursor.fetchall()


# ==============================================================================
# 3. MODELOS DE DADOS
# ==============================================================================

class Move:
    def __init__(self, guess, exact_matches, partial_matches):
        self.guess = guess
        self.exact_matches = exact_matches
        self.partial_matches = partial_matches
        self.timestamp = datetime.now()


class GameSession:
    def __init__(self, secret_code, max_attempts, difficulty_name):
        self.secret_code = secret_code
        self.max_attempts = max_attempts
        self.difficulty_name = difficulty_name
        self.history = []
        self.hints_used = 0
        self.start_time = None
        self.end_time = None

    def add_move(self, move):
        self.history.append(move)

    def get_attempts_left(self):
        return self.max_attempts - len(self.history)

    def calculate_score(self):
        if not self.end_time or not self.start_time:
            return 0
        
        duration = self.end_time - self.start_time
        base_score = 1000 * len(self.secret_code)
        penalty_attempts = len(self.history) * 50
        penalty_time = int(duration * 2)
        penalty_hints = self.hints_used * 150
        
        final_score = base_score - penalty_attempts - penalty_time - penalty_hints
        return max(10, final_score)


# ==============================================================================
# 4. MOTOR LÓGICO DO JOGO
# ==============================================================================

class SecretCodeEngine:
    @staticmethod
    def generate_code(length=4, allow_duplicates=False):
        digits = [str(i) for i in range(10)]
        if allow_duplicates:
            return "".join(random.choices(digits, k=length))
        else:
            random.shuffle(digits)
            return "".join(digits[:length])

    @staticmethod
    def evaluate_guess(secret, guess):
        exact_matches = 0
        partial_matches = 0

        secret_copy = list(secret)
        guess_copy = list(guess)

        # 1. Checa posições exatas
        for i in range(len(secret) - 1, -1, -1):
            if guess_copy[i] == secret_copy[i]:
                exact_matches += 1
                del secret_copy[i]
                del guess_copy[i]

        # 2. Checa posições parciais
        for digit in guess_copy:
            if digit in secret_copy:
                partial_matches += 1
                secret_copy.remove(digit)

        return exact_matches, partial_matches

    @staticmethod
    def validate_input(guess, length, allow_duplicates):
        if not guess.isdigit():
            return False, "A entrada deve conter apenas números."
        if len(guess) != length:
            return False, f"A senha deve ter exatamente {length} dígitos."
        if not allow_duplicates and len(set(guess)) != len(guess):
            return False, "A senha não pode conter dígitos repetidos nesta dificuldade."
        return True, ""


# ==============================================================================
# 5. INTERFACE GRÁFICA (GUI Tkinter)
# ==============================================================================

class MastermindGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("600x720")
        
        self.db = DatabaseManager()
        self.theme = THEME_DARK
        self.session = None
        
        self.configure_styles()
        self.create_widgets()

    def configure_styles(self):
        self.root.configure(bg=self.theme["bg"])

    def create_widgets(self):
        # Header
        self.header_label = tk.Label(
            self.root, text="SENHA SECRETA PRO", font=("Helvetica", 20, "bold"),
            bg=self.theme["bg"], fg=self.theme["accent"]
        )
        self.header_label.pack(pady=10)

        # Configurações Frame
        config_frame = tk.Frame(self.root, bg=self.theme["panel"], padx=10, pady=10)
        config_frame.pack(fill="x", padx=20)

        tk.Label(config_frame, text="Dificuldade:", bg=self.theme["panel"], fg=self.theme["fg"]).grid(row=0, column=0, padx=5)
        
        self.diff_var = tk.StringVar(value="Médio")
        diff_menu = ttk.Combobox(config_frame, textvariable=self.diff_var, values=list(DIFFICULTIES.keys()), state="readonly", width=10)
        diff_menu.grid(row=0, column=1, padx=5)

        self.btn_start = tk.Button(config_frame, text="Novo Jogo", command=self.start_new_game, bg=self.theme["accent"], fg="#000000", font=("Helvetica", 9, "bold"))
        self.btn_start.grid(row=0, column=2, padx=10)

        self.btn_rank = tk.Button(config_frame, text="Ranking", command=self.show_ranking, bg=self.theme["warning"], fg="#000000", font=("Helvetica", 9, "bold"))
        self.btn_rank.grid(row=0, column=3, padx=5)

        # Dashboard Informativo
        self.info_label = tk.Label(self.root, text="Selecione a dificuldade e clique em 'Novo Jogo'.", bg=self.theme["bg"], fg=self.theme["fg"], font=("Helvetica", 11))
        self.info_label.pack(pady=10)

        # Tabela de Histórico (Treeview)
        tree_frame = tk.Frame(self.root)
        tree_frame.pack(fill="both", expand=True, padx=20)

        self.tree = ttk.Treeview(tree_frame, columns=("Palpite", "Exatos", "Parciais"), show="headings")
        self.tree.heading("Palpite", text="Palpite")
        self.tree.heading("Exatos", text="🎯 Posição Certa")
        self.tree.heading("Parciais", text="🟡 Fora de Posição")
        self.tree.pack(fill="both", expand=True)

        # Frame de Entrada de Palpites
        input_frame = tk.Frame(self.root, bg=self.theme["panel"], pady=10)
        input_frame.pack(fill="x", padx=20, pady=10)

        self.entry_guess = tk.Entry(input_frame, font=("Helvetica", 14), state="disabled")
        self.entry_guess.pack(side="left", padx=10, expand=True, fill="x")

        self.btn_guess = tk.Button(input_frame, text="Enviar", command=self.process_guess, state="disabled", bg=self.theme["success"], fg="#000000", font=("Helvetica", 10, "bold"))
        self.btn_guess.pack(side="left", padx=5)

    def start_new_game(self):
        diff_name = self.diff_var.get()
        cfg = DIFFICULTIES[diff_name]
        
        secret = SecretCodeEngine.generate_code(cfg["length"], cfg["allow_duplicates"])
        self.session = GameSession(secret, cfg["max_attempts"], diff_name)
        self.session.start_time = time.time()

        for item in self.tree.get_children():
            self.tree.delete(item)

        self.entry_guess.config(state="normal")
        self.btn_guess.config(state="normal")
        self.entry_guess.delete(0, tk.END)

        self.info_label.config(text=f"Jogo iniciado ({diff_name})! Tamanho: {cfg['length']} dígitos. Máx Tentativas: {cfg['max_attempts']}")

    def process_guess(self):
        guess = self.entry_guess.get().strip()
        cfg = DIFFICULTIES[self.session.difficulty_name]

        valid, msg = SecretCodeEngine.validate_input(guess, cfg["length"], cfg["allow_duplicates"])
        if not valid:
            messagebox.showwarning("Validação", msg)
            return

        exact, partial = SecretCodeEngine.evaluate_guess(self.session.secret_code, guess)
        move = Move(guess, exact, partial)
        self.session.add_move(move)

        self.tree.insert("", 0, values=(guess, exact, partial))
        self.entry_guess.delete(0, tk.END)

        tentativas_restantes = self.session.get_attempts_left()

        if exact == cfg["length"]:
            self.session.end_time = time.time()
            score = self.session.calculate_score()
            duration = round(self.session.end_time - self.session.start_time, 1)
            
            messagebox.showinfo("Vitória!", f"🎉 Parabéns! Você descobriu a senha {self.session.secret_code}!\n\nPontuação: {score}\nTempo: {duration}s")
            self.db.save_score("Jogador", score, duration, self.session.difficulty_name, len(self.session.history))
            self.end_game()
        elif tentativas_restantes <= 0:
            messagebox.showerror("Game Over", f"💥 Tentativas esgotadas! A senha era: {self.session.secret_code}")
            self.end_game()
        else:
            self.info_label.config(text=f"Tentativas restantes: {tentativas_restantes}")

    def end_game(self):
        self.entry_guess.config(state="disabled")
        self.btn_guess.config(state="disabled")
        self.info_label.config(text="Fim de jogo. Clique em 'Novo Jogo' para jogar novamente.")

    def show_ranking(self):
        scores = self.db.get_top_scores(5)
        text = "🏆 TOP 5 MELHORES PONTUAÇÕES 🏆\n\n"
        if not scores:
            text += "Nenhum registro encontrado."
        else:
            for idx, (name, score, sec, diff, att) in enumerate(scores, 1):
                text += f"{idx}. {name} - {score} pts | {diff} | {sec}s | {att} tent.\n"
        messagebox.showinfo("Ranking", text)


# ==============================================================================
# 6. TESTES UNITÁRIOS AUTOMATIZADOS
# ==============================================================================

class TestSecretCodeEngine(unittest.TestCase):
    def test_code_generation_length(self):
        code = SecretCodeEngine.generate_code(length=4, allow_duplicates=False)
        self.assertEqual(len(code), 4)

    def test_unique_digits(self):
        code = SecretCodeEngine.generate_code(length=5, allow_duplicates=False)
        self.assertEqual(len(set(code)), 5)

    def test_evaluation_exact(self):
        exact, partial = SecretCodeEngine.evaluate_guess("1234", "1234")
        self.assertEqual(exact, 4)
        self.assertEqual(partial, 0)

    def test_evaluation_partial(self):
        exact, partial = SecretCodeEngine.evaluate_guess("1234", "4321")
        self.assertEqual(exact, 0)
        self.assertEqual(partial, 4)


# ==============================================================================
# 7. EXECUÇÃO DA APLICAÇÃO
# ==============================================================================

if __name__ == "__main__":
    root = tk.Tk()
    app = MastermindGUI(root)
    root.mainloop()