#!/usr/bin/env python3
"""
Assistente Virtual de Secretaria Escolar
Versão 2.0 - Telegram Bot (Render-ready)
"""
import asyncio
import sqlite3
import os
import logging
import threading
from datetime import datetime
from typing import Optional, List, Dict, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
import pickle

from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ============================================================
# CONFIGURAÇÕES
# ============================================================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DB_NAME = "secretaria_escolar.db"
MODEL_FILE = "modelo_intencoes.pkl"
PORT = int(os.environ.get("PORT", 10000))

(
    AGUARDANDO_MATRICULA,
    MENU_PRINCIPAL,
    CONVERSA_LIVRE,
    AGUARDANDO_MOTIVO_ATENDIMENTO,
) = range(4)

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ============================================================
# BANCO DE DADOS
# ============================================================
def criar_banco():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alunos (
            matricula TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            serie TEXT NOT NULL,
            turma TEXT NOT NULL,
            ensino TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula TEXT NOT NULL,
            disciplina TEXT NOT NULL,
            periodo TEXT NOT NULL,
            nota REAL NOT NULL,
            FOREIGN KEY (matricula) REFERENCES alunos(matricula)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faltas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula TEXT NOT NULL,
            disciplina TEXT NOT NULL,
            data TEXT NOT NULL,
            justificativa TEXT,
            FOREIGN KEY (matricula) REFERENCES alunos(matricula)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula TEXT NOT NULL,
            data_hora TEXT NOT NULL,
            mensagem_usuario TEXT,
            mensagem_bot TEXT,
            tipo TEXT,
            FOREIGN KEY (matricula) REFERENCES alunos(matricula)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS atendimento_humano (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula TEXT NOT NULL,
            data_hora TEXT NOT NULL,
            motivo TEXT,
            status TEXT DEFAULT 'pendente',
            FOREIGN KEY (matricula) REFERENCES alunos(matricula)
        )
    """)
    conn.commit()
    conn.close()

def popular_dados_demonstracao():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM alunos")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    alunos = [
        ("2024001", "Roberto Cruz", "2º Semestre", "IA", "Téc. IA"),
        ("2024002", "José Lopes", "2º Semestre", "IA", "Téc. IA"),
        ("2024003", "Pedro", "2º Semestre", "IA", "Téc. IA"),
        ("2024004", "Lucas Ferreira", "2º Semestre", "IA", "Téc. IA"),
        ("2024005", "Sofia Mendes", "2º Semestre", "IA", "Téc. IA"),
    ]
    cursor.executemany(
        "INSERT INTO alunos (matricula, nome, serie, turma, ensino) VALUES (?, ?, ?, ?, ?)",
        alunos,
    )

    notas = [
        ("2024001", "Fundamentos de Informática, Sistemas Operacionais e Ferramentas de Programação", "1º Semestre", 8.5),
        ("2024001", "Lógica de programação e Algoritmos", "1º Semestre", 8.5),
        ("2024001", "Programação em PYTHON", "1º Semestre", 7.0),
        ("2024001", "Banco de Dados e Big Data", "1º Semestre", 9.0),
        ("2024001", "Matemática e Estatística Aplicada à IA", "1º Semestre", 8.5),
        ("2024001", "Fundamentos de IA e Aprendizado de Máquina", "1º Semestre", 7.5),
        
        ("2024001", "Python para Ciência de Dados", "2º Semestre", 8.0),
        ("2024001", "Machine Learning Aplicada", "2º Semestre", 9.5),
        ("2024001", "Rede Neurais Artificiais e Deep Learning", "2º Semestre", 9.0),
        ("2024001", "Processamento de Linguagem Natural (PLN) Chatbots", "2º Semestre", 10.0),
        ("2024001", "Metodologia para Elaboração de Produções Técnicas", "2º Semestre", 9.0),
        ("2024001", "Prática Profissional Supervissionada I", "2º Semestre", 0.0),
        
        ("2024001", "Noções de Segurança, Governança de Dados LGPD Aplicada a Dados", "3º Semestre", 0.0),
        ("2024001", "Engenharia de Solftware para IA", "3º Semestre", 0.0),
        ("2024001", "MLOPS e Deploy", "3º Semestre", 0.0),
        ("2024001", "Planejamento de Assistentes em Inteligência Artificial", "3º Semestre", 0.0),
        ("2024001", "LLMS e Inteligência Artificaial", "3º Semestre", 0.0),
        ("2024001", "Visão Computacional Aplicada", "3º Semestre", 0.0),
        ("2024001", "Gestão de Projetos em Inteligência Artificial", "3º Semestre", 0.0),
        ("2024001", "Prática Profissional Supervissionada II", "3º Semestre", 0.0),

        ("2024002", "Fundamentos de Informática, Sistemas Operacionais e Ferramentas de Programação", "1º Semestre", 8.5),
        ("2024002", "Lógica de programação e Algoritmos", "1º Semestre", 0.0),
        ("2024002", "Programação em PYTHON", "1º Semestre", 0.0),
        ("2024002", "Banco de Dados e Big Data", "1º Semestre", 0.0),
        ("2024002", "Matemática e Estatística Aplicada à IA", "1º Semestre", 0.0),
        ("2024002", "Fundamentos de IA e Aprendizado de Máquina", "1º Semestre", 0.0),

        ("2024002", "Python para Ciência de Dados", "2º Semestre", 8.0),
        ("2024002", "Machine Learning Aplicada", "2º Semestre", 9.5),
        ("2024002", "Rede Neurais Artificiais e Deep Learning", "2º Semestre", 9.0),
        ("2024002", "Processamento de Linguagem Natural (PLN) Chatbots", "2º Semestre", 10.0),
        ("2024002", "Metodologia para Elaboração de Produções Técnicas", "2º Semestre", 9.0),
        ("2024002", "Prática Profissional Supervissionada I", "2º Semestre", 0.0),
        
        ("2024002", "Noções de Segurança, Governança de Dados LGPD Aplicada a Dados", "3º Semestre", 0.0),
        ("2024002", "Engenharia de Solftware para IA", "3º Semestre", 0.0),
        ("2024002", "MLOPS e Deploy", "3º Semestre", 0.0),
        ("2024002", "Planejamento de Assistentes em Inteligência Artificial", "3º Semestre", 0.0),
        ("2024002", "LLMS e Inteligência Artificaial", "3º Semestre", 0.0),
        ("2024002", "Visão Computacional Aplicada", "3º Semestre", 0.0),
        ("2024002", "Gestão de Projetos em Inteligência Artificial", "3º Semestre", 0.0),
        ("2024002", "Prática Profissional Supervissionada II", "3º Semestre", 0.0),
        
        ("2024003", "Fundamentos de Informática, Sistemas Operacionais e Ferramentas de Programação", "1º Semestre", 8.5),
        ("2024003", "Lógica de programação e Algoritmos", "1º Semestre", 0.0),
        ("2024003", "Programação em PYTHON", "1º Semestre", 0.0),
        ("2024003", "Banco de Dados e Big Data", "1º Semestre", 0.0),
        ("2024003", "Matemática e Estatística Aplicada à IA", "1º Semestre", 0.0),
        ("2024003", "Fundamentos de IA e Aprendizado de Máquina", "1º Semestre", 0.0),

        ("2024003", "Python para Ciência de Dados", "2º Semestre", 8.0),
        ("2024003", "Machine Learning Aplicada", "2º Semestre", 9.5),
        ("2024003", "Rede Neurais Artificiais e Deep Learning", "2º Semestre", 9.0),
        ("2024003", "Processamento de Linguagem Natural (PLN) Chatbots", "2º Semestre", 10.0),
        ("2024003", "Metodologia para Elaboração de Produções Técnicas", "2º Semestre", 9.0),
        ("2024003", "Prática Profissional Supervissionada I", "2º Semestre", 0.0),
        
        ("2024003", "Noções de Segurança, Governança de Dados LGPD Aplicada a Dados", "3º Semestre", 0.0),
        ("2024003", "Engenharia de Solftware para IA", "3º Semestre", 0.0),
        ("2024003", "MLOPS e Deploy", "3º Semestre", 0.0),
        ("2024003", "Planejamento de Assistentes em Inteligência Artificial", "3º Semestre", 0.0),
        ("2024003", "LLMS e Inteligência Artificaial", "3º Semestre", 0.0),
        ("2024003", "Visão Computacional Aplicada", "3º Semestre", 0.0),
        ("2024003", "Gestão de Projetos em Inteligência Artificial", "3º Semestre", 0.0),
        ("2024003", "Prática Profissional Supervissionada II", "3º Semestre", 0.0),

        ("2024004", "Fundamentos de Informática, Sistemas Operacionais e Ferramentas de Programação", "1º Semestre", 8.5),
        ("2024004", "Lógica de programação e Algoritmos", "1º Semestre", 0.0),
        ("2024004", "Programação em PYTHON", "1º Semestre", 0.0),
        ("2024004", "Banco de Dados e Big Data", "1º Semestre", 0.0),
        ("2024004", "Matemática e Estatística Aplicada à IA", "1º Semestre", 0.0),
        ("2024004", "Fundamentos de IA e Aprendizado de Máquina", "1º Semestre", 0.0),

        ("2024004", "Python para Ciência de Dados", "2º Semestre", 8.0),
        ("2024004", "Machine Learning Aplicada", "2º Semestre", 9.5),
        ("2024004", "Rede Neurais Artificiais e Deep Learning", "2º Semestre", 9.0),
        ("2024004", "Processamento de Linguagem Natural (PLN) Chatbots", "2º Semestre", 10.0),
        ("2024004", "Metodologia para Elaboração de Produções Técnicas", "2º Semestre", 9.0),
        ("2024004", "Prática Profissional Supervissionada I", "2º Semestre", 0.0),
        
        ("2024004", "Noções de Segurança, Governança de Dados LGPD Aplicada a Dados", "3º Semestre", 0.0),
        ("2024004", "Engenharia de Solftware para IA", "3º Semestre", 0.0),
        ("2024004", "MLOPS e Deploy", "3º Semestre", 0.0),
        ("2024004", "Planejamento de Assistentes em Inteligência Artificial", "3º Semestre", 0.0),
        ("2024004", "LLMS e Inteligência Artificaial", "3º Semestre", 0.0),
        ("2024004", "Visão Computacional Aplicada", "3º Semestre", 0.0),
        ("2024004", "Gestão de Projetos em Inteligência Artificial", "3º Semestre", 0.0),
        ("2024004", "Prática Profissional Supervissionada II", "3º Semestre", 0.0),

        ("2024005", "Fundamentos de Informática, Sistemas Operacionais e Ferramentas de Programação", "1º Semestre", 8.5),
        ("2024005", "Lógica de programação e Algoritmos", "1º Semestre", 0.0),
        ("2024005", "Programação em PYTHON", "1º Semestre", 0.0),
        ("2024005", "Banco de Dados e Big Data", "1º Semestre", 0.0),
        ("2024005", "Matemática e Estatística Aplicada à IA", "1º Semestre", 0.0),
        ("2024005", "Fundamentos de IA e Aprendizado de Máquina", "1º Semestre", 0.0),

        ("2024005", "Python para Ciência de Dados", "2º Semestre", 8.0),
        ("2024005", "Machine Learning Aplicada", "2º Semestre", 9.5),
        ("2024005", "Rede Neurais Artificiais e Deep Learning", "2º Semestre", 9.0),
        ("2024005", "Processamento de Linguagem Natural (PLN) Chatbots", "2º Semestre", 10.0),
        ("2024005", "Metodologia para Elaboração de Produções Técnicas", "2º Semestre", 9.0),
        ("2024005", "Prática Profissional Supervissionada I", "2º Semestre", 0.0),
        
        ("2024005", "Noções de Segurança, Governança de Dados LGPD Aplicada a Dados", "3º Semestre", 0.0),
        ("2024005", "Engenharia de Solftware para IA", "3º Semestre", 0.0),
        ("2024005", "MLOPS e Deploy", "3º Semestre", 0.0),
        ("2024005", "Planejamento de Assistentes em Inteligência Artificial", "3º Semestre", 0.0),
        ("2024005", "LLMS e Inteligência Artificaial", "3º Semestre", 0.0),
        ("2024005", "Visão Computacional Aplicada", "3º Semestre", 0.0),
        ("2024005", "Gestão de Projetos em Inteligência Artificial", "3º Semestre", 0.0),
        ("2024005", "Prática Profissional Supervissionada II", "3º Semestre", 0.0),
    ]
    cursor.executemany(
        "INSERT INTO notas (matricula, disciplina, periodo, nota) VALUES (?, ?, ?, ?)",
        notas,
    )

    faltas = [
        ("2024001", "(PLN) Chatbots", "2024-03-12", "Consulta médica"),
        ("2024001", "(PLN) Chatbots", "2024-04-05", None),
        ("2024001", "(PLN) Chatbots", "2024-05-20", "Atestado"),
        ("2024002", "(PLN) Chatbots", "2024-03-15", None),
        ("2024002", "(PLN) Chatbots", "2024-04-10", "Problema de transporte"),
        ("2024003", "(PLN) Chatbots", "2024-03-22", "Consulta médica"),
    ]
    cursor.executemany(
        "INSERT INTO faltas (matricula, disciplina, data, justificativa) VALUES (?, ?, ?, ?)",
        faltas,
    )
    conn.commit()
    conn.close()
    logger.info("Dados de demonstração inseridos com sucesso.")

# ============================================================
# FUNÇÕES DE CONSULTA
# ============================================================
def buscar_aluno(matricula: str) -> Optional[Dict]:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT matricula, nome, serie, turma, ensino FROM alunos WHERE matricula = ?",
        (matricula,),
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "matricula": row[0],
            "nome": row[1],
            "serie": row[2],
            "turma": row[3],
            "ensino": row[4],
        }
    return None

def consultar_notas(matricula: str) -> List[Tuple]:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT disciplina, periodo, nota
        FROM notas
        WHERE matricula = ?
        ORDER BY
            CASE periodo
                WHEN '1º Semestre' THEN 1
                WHEN '2º Semestre' THEN 2
                WHEN '3º Semestre' THEN 3
                WHEN '4º Semestre' THEN 4
                WHEN '5º Semestre' THEN 5
                WHEN '6º Semestre' THEN 6
                ELSE 99
            END,
            id
        """,
        (matricula,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

def consultar_faltas(matricula: str) -> List[Tuple]:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT disciplina, data, justificativa
        FROM faltas
        WHERE matricula = ?
        ORDER BY data DESC
        """,
        (matricula,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

def salvar_historico(matricula: str, msg_usuario: str, msg_bot: str, tipo: str = "conversa"):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO historico (matricula, data_hora, mensagem_usuario, mensagem_bot, tipo)
        VALUES (?, ?, ?, ?, ?)
        """,
        (matricula, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg_usuario, msg_bot, tipo),
    )
    conn.commit()
    conn.close()

def registrar_atendimento_humano(matricula: str, motivo: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO atendimento_humano (matricula, data_hora, motivo, status)
        VALUES (?, ?, ?, 'pendente')
        """,
        (matricula, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), motivo),
    )
    conn.commit()
    conn.close()

# ============================================================
# MACHINE LEARNING
# ============================================================
def treinar_modelo():
    exemplos = [
        ("quero ver minhas notas", "consultar_notas"),
        ("mostrar notas", "consultar_notas"),
        ("como estão minhas notas", "consultar_notas"),
        ("notas do bimestre", "consultar_notas"),
        ("quero saber as notas", "consultar_notas"),
        ("boletim", "consultar_notas"),
        ("resultado das provas", "consultar_notas"),
        ("notas de matemática", "consultar_notas"),
        ("minhas notas por favor", "consultar_notas"),
        ("ver as notas", "consultar_notas"),
        ("quantas faltas eu tenho", "consultar_faltas"),
        ("mostrar faltas", "consultar_faltas"),
        ("quero ver minhas faltas", "consultar_faltas"),
        ("faltas justificadas", "consultar_faltas"),
        ("meus atrasos", "consultar_faltas"),
        ("frequência", "consultar_faltas"),
        ("quantas vezes faltei", "consultar_faltas"),
        ("lista de faltas", "consultar_faltas"),
        ("faltas por disciplina", "consultar_faltas"),
        ("ver faltas", "consultar_faltas"),
        ("quero falar com alguém", "atendimento_humano"),
        ("falar com a secretaria", "atendimento_humano"),
        ("preciso de atendimento humano", "atendimento_humano"),
        ("quero um atendente", "atendimento_humano"),
        ("falar com pessoa real", "atendimento_humano"),
        ("transferir para atendente", "atendimento_humano"),
        ("preciso de ajuda humana", "atendimento_humano"),
        ("chamar a secretaria", "atendimento_humano"),
        ("quero conversar com alguém da escola", "atendimento_humano"),
        ("atendimento presencial", "atendimento_humano"),
        ("olá", "saudacao"),
        ("oi", "saudacao"),
        ("bom dia", "saudacao"),
        ("boa tarde", "saudacao"),
        ("boa noite", "saudacao"),
        ("olá tudo bem", "saudacao"),
        ("oi como vai", "saudacao"),
        ("e aí", "saudacao"),
        ("tchau", "despedida"),
        ("até logo", "despedida"),
        ("obrigado", "despedida"),
        ("valeu", "despedida"),
        ("até mais", "despedida"),
        ("encerrar", "despedida"),
        ("sair", "despedida"),
        ("obrigada", "despedida"),
        ("muito obrigado", "despedida"),
        ("ajuda", "ajuda"),
        ("o que você pode fazer", "ajuda"),
        ("quais opções", "ajuda"),
        ("menu", "ajuda"),
        ("como funciona", "ajuda"),
        ("me ajuda", "ajuda"),
        ("não sei o que fazer", "ajuda"),
        ("opções disponíveis", "ajuda"),
        ("qual o horário da secretaria", "informacao_geral"),
        ("quando abre a secretaria", "informacao_geral"),
        ("endereço da escola", "informacao_geral"),
        ("telefone da escola", "informacao_geral"),
        ("como tirar documento", "informacao_geral"),
        ("preciso de declaração", "informacao_geral"),
        ("calendário escolar", "informacao_geral"),
        ("feriados", "informacao_geral"),
    ]
    textos = [e[0] for e in exemplos]
    labels = [e[1] for e in exemplos]
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
        ("clf", MultinomialNB()),
    ])
    pipeline.fit(textos, labels)
    with open(MODEL_FILE, "wb") as f:
        pickle.dump(pipeline, f)
    return pipeline

def carregar_modelo():
    if os.path.exists(MODEL_FILE):
        with open(MODEL_FILE, "rb") as f:
            return pickle.load(f)
    return treinar_modelo()

def prever_intencao(modelo, texto: str) -> str:
    return modelo.predict([texto.lower().strip()])[0]

# ============================================================
# MEMÓRIA DE SESSÃO
# ============================================================
class MemoriaSessao:
    def __init__(self):
        self.contexto = []
        self.ultima_intencao = None
        self.aluno = None

    def adicionar(self, usuario: str, bot: str):
        self.contexto.append((usuario, bot))
        if len(self.contexto) > 10:
            self.contexto.pop(0)

sessoes: Dict[int, MemoriaSessao] = {}

def get_memoria(chat_id: int) -> MemoriaSessao:
    if chat_id not in sessoes:
        sessoes[chat_id] = MemoriaSessao()
    return sessoes[chat_id]

# ============================================================
# RESPOSTAS
# ============================================================
def formatar_notas(matricula: str) -> str:
    notas = consultar_notas(matricula)
    if not notas:
        return "Você ainda não possui notas registradas no sistema."
    texto = "📚 *Suas notas:*\n"
    disciplina_atual = None
    for disc, periodo, nota in notas:
        if disc != disciplina_atual:
            texto += f"\n*{disc}:*\n"
            disciplina_atual = disc
        texto += f"  • {periodo}: {nota:.1f}\n"
    return texto.strip()

def formatar_faltas(matricula: str) -> str:
    faltas = consultar_faltas(matricula)
    if not faltas:
        return "Você não possui faltas registradas. Parabéns pela frequência! 👏"
    texto = "📅 *Suas faltas:*\n\n"
    for disc, data, just in faltas:
        just_txt = f" (Justificativa: {just})" if just else " (Sem justificativa)"
        texto += f"  • {data} - {disc}{just_txt}\n"
    return texto.strip()

def responder_intencao(intencao: str, aluno: Dict) -> str:
    if intencao == "consultar_notas":
        return formatar_notas(aluno["matricula"])
    elif intencao == "consultar_faltas":
        return formatar_faltas(aluno["matricula"])
    elif intencao == "atendimento_humano":
        return (
            "Vou registrar sua solicitação de atendimento humano.\n"
            "Por favor, digite brevemente o *motivo* do atendimento "
            "(ou digite *cancelar* para voltar):"
        )
    elif intencao == "saudacao":
        return f"Olá, {aluno['nome'].split()[0]}! Como posso ajudar você hoje?"
    elif intencao == "despedida":
        return f"Até logo, {aluno['nome'].split()[0]}! Qualquer dúvida, é só voltar. 👋"
    elif intencao == "ajuda":
        return (
            "Posso te ajudar com:\n"
            "  • Consultar suas notas\n"
            "  • Consultar suas faltas\n"
            "  • Solicitar atendimento com a secretaria\n"
            "  • Responder perguntas gerais sobre a escola\n\n"
            "Você também pode usar o menu abaixo."
        )
    elif intencao == "informacao_geral":
        return (
            "ℹ️ *Informações gerais da escola (demonstração):*\n"
            "  • Secretaria: Seg-Sex 08h–17h\n"
            "  • Telefone: (11) 3000-0000\n"
            "  • E-mail: secretaria@escola.exemplo.edu.br\n"
            "  • Para declarações e documentos, solicite atendimento humano."
        )
    else:
        return (
            "Desculpe, não entendi completamente. "
            "Você pode tentar novamente ou digitar *ajuda* para ver as opções."
        )

# ============================================================
# TECLADOS
# ============================================================
def teclado_menu() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("📚 Consultar notas"), KeyboardButton("📅 Consultar faltas")],
        [KeyboardButton("👤 Falar com atendente"), KeyboardButton("💬 Conversar livre")],
        [KeyboardButton("ℹ️ Ajuda"), KeyboardButton("🚪 Sair")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def teclado_voltar() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[KeyboardButton("⬅️ Voltar ao menu")]], resize_keyboard=True)

# ============================================================
# HANDLERS
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    memoria = get_memoria(chat_id)
    memoria.aluno = None

    mensagem = (
        "🏫 *Assistente Virtual da Secretaria Escolar*\n\n"
        "Olá! Para iniciar o atendimento, digite sua "
        "*matrícula escolar*.\n\n"
    )

    await update.message.reply_text(
        mensagem,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )

    return AGUARDANDO_MATRICULA

async def receber_matricula(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    texto = update.message.text.strip()
    if not texto:
        await update.message.reply_text("⚠️ Matrícula não pode ser vazia. Tente novamente.")
        return AGUARDANDO_MATRICULA

    aluno = buscar_aluno(texto)
    if not aluno:
        await update.message.reply_text(
            "❌ Matrícula não encontrada. Verifique o número e tente novamente.\n\n"
            "Matrículas de demonstração: `2024001` a `2024005`",
            parse_mode="Markdown",
        )
        return AGUARDANDO_MATRICULA

    memoria = get_memoria(chat_id)
    memoria.aluno = aluno
    saudacao = (
        f"✅ Bem-vindo(a), *{aluno['nome']}*!\n"
        f"{aluno['ensino']} • {aluno['serie']} • Turma {aluno['turma']}"
    )
    salvar_historico(aluno["matricula"], "[Início da sessão]", saudacao, "sistema")
    await update.message.reply_text(
        saudacao + "\n\nComo posso ajudar você?",
        parse_mode="Markdown",
        reply_markup=teclado_menu(),
    )
    return MENU_PRINCIPAL

async def menu_principal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    memoria = get_memoria(chat_id)
    aluno = memoria.aluno
    if not aluno:
        await update.message.reply_text("Sessão expirada. Digite /start para começar.")
        return ConversationHandler.END

    texto = update.message.text.strip().lower()

    if "consultar notas" in texto or texto == "1":
        resp = formatar_notas(aluno["matricula"])
        await update.message.reply_text(resp, parse_mode="Markdown")
        salvar_historico(aluno["matricula"], "Consultar notas", resp, "menu")
        memoria.adicionar("Consultar notas", resp)
        return MENU_PRINCIPAL

    elif "consultar faltas" in texto or texto == "2":
        resp = formatar_faltas(aluno["matricula"])
        await update.message.reply_text(resp, parse_mode="Markdown")
        salvar_historico(aluno["matricula"], "Consultar faltas", resp, "menu")
        memoria.adicionar("Consultar faltas", resp)
        return MENU_PRINCIPAL

    elif "falar com atendente" in texto or "atendente" in texto or texto == "3":
        await update.message.reply_text(
            "Vou registrar sua solicitação de atendimento humano.\n"
            "Digite o *motivo* do atendimento (ou *cancelar* para voltar):",
            parse_mode="Markdown",
            reply_markup=teclado_voltar(),
        )
        return AGUARDANDO_MOTIVO_ATENDIMENTO

    elif "conversar livre" in texto or "conversa" in texto or texto == "4":
        await update.message.reply_text(
            "💬 *Modo conversa livre ativado.*\n"
            "Digite sua mensagem (ou use o botão para voltar ao menu).",
            parse_mode="Markdown",
            reply_markup=teclado_voltar(),
        )
        return CONVERSA_LIVRE

    elif "ajuda" in texto or texto == "5":
        resp = responder_intencao("ajuda", aluno)
        await update.message.reply_text(resp)
        return MENU_PRINCIPAL

    elif "sair" in texto or texto == "0":
        await update.message.reply_text(
            f"Até logo, {aluno['nome'].split()[0]}! 👋\n"
            "Digite /start quando quiser voltar.",
            reply_markup=ReplyKeyboardRemove(),
        )
        memoria.aluno = None
        return ConversationHandler.END

    else:
        modelo = context.bot_data["modelo"]
        intencao = prever_intencao(modelo, texto)
        if intencao == "atendimento_humano":
            await update.message.reply_text(
                "Digite o *motivo* do atendimento (ou *cancelar*):",
                parse_mode="Markdown",
                reply_markup=teclado_voltar(),
            )
            return AGUARDANDO_MOTIVO_ATENDIMENTO
        resp = responder_intencao(intencao, aluno)
        await update.message.reply_text(resp, parse_mode="Markdown")
        salvar_historico(aluno["matricula"], texto, resp, "conversa")
        memoria.adicionar(texto, resp)
        return MENU_PRINCIPAL

async def conversa_livre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    memoria = get_memoria(chat_id)
    aluno = memoria.aluno
    if not aluno:
        await update.message.reply_text("Sessão expirada. Digite /start para começar.")
        return ConversationHandler.END

    texto = update.message.text.strip()
    if texto.lower() in ("voltar", "menu", "sair") or "voltar" in texto.lower():
        await update.message.reply_text("Retornando ao menu principal.", reply_markup=teclado_menu())
        return MENU_PRINCIPAL

    modelo = context.bot_data["modelo"]
    intencao = prever_intencao(modelo, texto)

    if intencao == "atendimento_humano":
        await update.message.reply_text(
            "Digite o *motivo* do atendimento (ou *cancelar*):",
            parse_mode="Markdown",
            reply_markup=teclado_voltar(),
        )
        return AGUARDANDO_MOTIVO_ATENDIMENTO

    resp = responder_intencao(intencao, aluno)
    await update.message.reply_text(resp, parse_mode="Markdown")
    salvar_historico(aluno["matricula"], texto, resp, "conversa")
    memoria.adicionar(texto, resp)
    memoria.ultima_intencao = intencao

    if intencao == "despedida":
        await update.message.reply_text("Encerrando conversa. Até logo! 👋", reply_markup=teclado_menu())
        return MENU_PRINCIPAL
    return CONVERSA_LIVRE

async def receber_motivo_atendimento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    memoria = get_memoria(chat_id)
    aluno = memoria.aluno
    if not aluno:
        await update.message.reply_text("Sessão expirada. Digite /start para começar.")
        return ConversationHandler.END

    motivo = update.message.text.strip()
    if motivo.lower() in ("cancelar", "sair", "voltar", "") or "voltar" in motivo.lower():
        await update.message.reply_text("Solicitação cancelada.", reply_markup=teclado_menu())
        return MENU_PRINCIPAL

    registrar_atendimento_humano(aluno["matricula"], motivo)
    resp = (
        f"✅ *Solicitação registrada com sucesso!*\n\n"
        f"Motivo: {motivo}\n"
        f"A secretaria entrará em contato em breve.\n"
        f"(Protocolo gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')})"
    )
    await update.message.reply_text(resp, parse_mode="Markdown", reply_markup=teclado_menu())
    salvar_historico(aluno["matricula"], f"Atendimento humano: {motivo}", resp, "atendimento")
    memoria.adicionar(f"Atendimento humano: {motivo}", resp)
    return MENU_PRINCIPAL

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    memoria = get_memoria(chat_id)
    memoria.aluno = None
    await update.message.reply_text(
        "Atendimento cancelado. Digite /start para começar novamente.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END

async def erro_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)

# ============================================================
# FLASK (health check para o Render)
# ============================================================
web = Flask(__name__)

@web.route("/")
def home():
    return "✅ Bot Secretaria Escolar no ar!"

@web.route("/health")
def health():
    return "ok", 200

# ============================================================
# MAIN – Render ready
# ============================================================
def run_bot():
    """Roda o bot Telegram em thread separada."""
    if not TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN não definido! Configure a variável de ambiente.")
        return

    logger.info("Inicializando banco e modelo...")
    criar_banco()
    popular_dados_demonstracao()
    modelo = carregar_modelo()
    logger.info("✅ Sistema pronto!")

    application = Application.builder().token(TOKEN).build()
    application.bot_data["modelo"] = modelo

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            AGUARDANDO_MATRICULA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receber_matricula)
            ],
            MENU_PRINCIPAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, menu_principal)
            ],
            CONVERSA_LIVRE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, conversa_livre)
            ],
            AGUARDANDO_MOTIVO_ATENDIMENTO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receber_motivo_atendimento)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancelar),
            CommandHandler("start", start),
        ],
    )

    application.add_handler(conv_handler)
    application.add_error_handler(erro_handler)

    logger.info("🤖 Bot Telegram iniciando polling...")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

def run_flask():
    """Roda o Flask em thread separada"""
    logger.info(f"🌐 Flask rodando na porta {PORT}")
    web.run(host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    # Flask vai pra thread secundária
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Bot fica na thread PRINCIPAL - corrige o erro set_wakeup_fd
    run_bot()
