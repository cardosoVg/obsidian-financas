#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Obsidian Finanças — GUI unificada
Combina: registrar gasto/entrada e gerar relatório mensal
Compatível com Windows e Linux
"""

import os
import platform
import re
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox

# ──────────────────────────────────────────────
# CONFIGURAÇÕES DE CAMINHO — cross-platform
# ──────────────────────────────────────────────
_HOME = Path.home()
_IS_WINDOWS = platform.system() == "Windows"

# No Windows a pasta padrão é "Documents"; no Linux/macOS é "Documentos"
_DOCS = "Documents" if _IS_WINDOWS else "Documentos"

# Este é o caminho padrão. Se ele existir, o programa já abre nele.
VAULT_BASE = _HOME / _DOCS / "obsidian" / "notes" / "Finanças"
VAULT_REGISTROS = VAULT_BASE / "Registros"
VAULT_MENSAL = VAULT_BASE / "Mensal"

MESES = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}

# ──────────────────────────────────────────────
# PALETA — dark theme inspirado no Obsidian
# ──────────────────────────────────────────────
BG = "#1a1a2e"
SURFACE = "#16213e"
PANEL = "#0f3460"
ACCENT = "#e94560"
ACCENT2 = "#53d8fb"
TEXT = "#e0e0e0"
TEXT_DIM = "#8892a4"
SUCCESS = "#4ade80"
WARNING = "#fbbf24"

# Fontes — leve redução de tamanho no Windows por escala de DPI
_FS = 1 if _IS_WINDOWS else 0
FONT_HEAD = ("Georgia", 20 - _FS, "bold")
FONT_SUB = ("Georgia", 11 - _FS, "italic")
FONT_LBL = ("Courier New", 10 - _FS)
FONT_BTN = ("Courier New", 10 - _FS, "bold")
FONT_TINY = ("Courier New", 9 - _FS)
FONT_MONO = ("Courier New", 11 - _FS)

# ──────────────────────────────────────────────
# BLOCOS DATAVIEW — strings puras (sem f-string)
# Evita conflito de chaves {} com interpolação Python
# ──────────────────────────────────────────────
_DATAVIEWJS_BALANCO = (
    "```dataviewjs\n"
    "let p = dv.current();\n"
    "let registros = dv.pages('\"Finanças/Registros\"').where(r => r.data && r.data.month == p.data.month && r.data.year == p.data.year);\n"
    "\n"
    'let entradas = registros.where(r => r.tipo == "Entrada").valor.array().reduce((acc, val) => acc + (val || 0), 0);\n'
    'let saidasFixas = registros.where(r => r.tipo == "Saída").valor.array().reduce((acc, val) => acc + (val || 0), 0);\n'
    'let pagasNoCheck = registros.where(r => r.tipo == "A Pagar").filter(r => r.file.tasks.length > 0 && r.file.tasks.every(t => t.completed)).valor.array().reduce((acc, val) => acc + (val || 0), 0);\n'
    "\n"
    "let saldoInic = parseFloat(p.saldo_inicial) || 0;\n"
    "let totalSaidas = saidasFixas + pagasNoCheck;\n"
    "let saldoTotal = saldoInic + entradas - totalSaidas;\n"
    "\n"
    "dv.paragraph(`\n"
    "| Indicador | Valor |\n"
    "| --- | --- |\n"
    "| 🏦 **Saldo Inicial** | R$ ${saldoInic.toLocaleString('pt-BR', {minimumFractionDigits: 2})} |\n"
    "| 📈 **Entradas** | R$ ${entradas.toLocaleString('pt-BR', {minimumFractionDigits: 2})} |\n"
    "| 📉 **Saídas (Pagas)** | R$ ${totalSaidas.toLocaleString('pt-BR', {minimumFractionDigits: 2})} |\n"
    "| --- | --- |\n"
    "| 💵 **SALDO ATUAL TOTAL** | **R$ ${saldoTotal.toLocaleString('pt-BR', {minimumFractionDigits: 2})}** |\n"
    "`);\n"
    "```"
)

_DATAVIEW_EXTRATO = (
    "```dataview\n"
    "TABLE valor, categoria, tipo, data\n"
    'FROM "Finanças/Registros"\n'
    "WHERE data.month = this.data.month AND data.year = this.data.year\n"
    "SORT data DESC\n"
    "```"
)

_DATAVIEWJS_PENDENTES = (
    "```dataviewjs\n"
    "let pendentes = dv.pages('\"Finanças/Registros\"')\n"
    '    .where(p => p.tipo == "A Pagar" && p.data.month == dv.current().data.month && p.data.year == dv.current().data.year)\n'
    "    .file.tasks.where(t => !t.completed);\n"
    "\n"
    "if (pendentes.length > 0) {\n"
    "    dv.taskList(pendentes, false);\n"
    "} else {\n"
    '    dv.paragraph("✅ Todas as contas deste mês estão pagas!");\n'
    "}\n"
    "```"
)


# ──────────────────────────────────────────────
# LÓGICA — REGISTRAR GASTO
# ──────────────────────────────────────────────
def registrar_gasto(nome: str, valor_input: str, categoria: str, tipo_opt: str) -> str:
    tipos = {"1": "Saída", "2": "Entrada", "3": "A Pagar"}
    tipo = tipos.get(tipo_opt, "Saída")

    hoje = date.today()
    ano = str(hoje.year)
    mes_num = f"{hoje.month:02d}"
    nome_mes = MESES[hoje.month]
    data_str = hoje.strftime("%Y-%m-%d")

    valor = valor_input.strip().replace(",", ".")
    try:
        float(valor)
    except ValueError:
        raise ValueError("Valor inválido. Use números como 50.00 ou 50,00")

    nome_limpo = re.sub(r"[^a-zA-Z0-9 ]", "", nome).replace(" ", "-")
    destino = VAULT_REGISTROS / ano / f"{mes_num}-{nome_mes}"
    destino.mkdir(parents=True, exist_ok=True)

    file_name = f"{data_str}_{nome_limpo}.md"
    corpo = f"- [ ] Pagar {nome} (R$ {valor})" if tipo == "A Pagar" else ""

    # Concatenação simples — sem f-string no bloco de dados
    linhas = [
        "---",
        f"valor: {valor}",
        f"categoria: {categoria}",
        f"data: {data_str}",
        f"tipo: {tipo}",
        "---",
        f"# {nome}",
        "",
        corpo,
        "",
    ]
    conteudo = "\n".join(linhas)
    (destino / file_name).write_text(conteudo, encoding="utf-8")
    return str(destino / file_name)


# ──────────────────────────────────────────────
# LÓGICA — CRIAR MÊS
# ──────────────────────────────────────────────
def criar_mes() -> tuple:
    hoje = date.today()
    mes_at_num = hoje.month
    ano_at = hoje.year
    nome_mes_at = MESES[mes_at_num]
    mes_at_str = f"{mes_at_num:02d}"

    mes_pas_num = mes_at_num - 1 or 12
    ano_pas = ano_at if mes_at_num > 1 else ano_at - 1
    nome_mes_pas = MESES[mes_pas_num]
    mes_pas_str = f"{mes_pas_num:02d}"

    pasta_pas = VAULT_REGISTROS / str(ano_pas) / f"{mes_pas_str}-{nome_mes_pas}"
    file_mes_pas = f"{nome_mes_pas} {ano_pas}.md"
    caminho_pas = VAULT_MENSAL / file_mes_pas

    # Saldo herdado
    ini_pas = 0.0
    if caminho_pas.exists():
        for line in caminho_pas.read_text(encoding="utf-8").splitlines():
            if line.startswith("saldo_inicial:") or line.startswith("saldo_final:"):
                try:
                    ini_pas = float(line.split(":", 1)[1].strip().replace(",", "."))
                except (ValueError, IndexError):
                    pass
                break

    # Soma registros do mês anterior
    entradas = saidas = pagar = 0.0
    if pasta_pas.exists():
        for arq in pasta_pas.glob("*.md"):
            try:
                texto = arq.read_text(encoding="utf-8")
            except OSError:
                continue
            tipo_m = re.search(r"^tipo:\s*(.+)", texto, re.MULTILINE)
            valor_m = re.search(r"^valor:\s*(.+)", texto, re.MULTILINE)
            if tipo_m and valor_m:
                t = tipo_m.group(1).strip()
                try:
                    v = float(valor_m.group(1).strip().replace(",", "."))
                except ValueError:
                    v = 0.0
                if t == "Entrada":
                    entradas += v
                elif t == "Saída":
                    saidas += v
                elif t == "A Pagar":
                    pagar += v

    saldo_calculado = ini_pas + entradas - saidas - pagar
    file_name = f"{nome_mes_at} {ano_at}.md"

    VAULT_MENSAL.mkdir(parents=True, exist_ok=True)

    # Cabeçalho YAML + título (f-string segura: sem blocos JS aqui)
    cabecalho = "\n".join(
        [
            "---",
            f"data: {ano_at}-{mes_at_str}-01",
            f'mes_anterior: "[[{file_mes_pas}]]"',
            f"saldo_inicial: {saldo_calculado:.2f}",
            "---",
            "",
            f"# 📊 Relatório Financeiro - {nome_mes_at} {ano_at}",
            "",
            "## 💰 Balanço Geral",
            "",
        ]
    )

    secao_extrato = "\n".join(
        [
            "",
            "---",
            "",
            "## 📅 Extrato Detalhado (Mês Atual)",
            "",
        ]
    )

    secao_pendentes = "\n".join(
        [
            "",
            "---",
            "",
            "## 📅 Contas Pendentes",
            "> Marque o checkbox para dar baixa sem sair desta nota.",
            "",
        ]
    )

    conteudo = (
        cabecalho
        + _DATAVIEWJS_BALANCO
        + secao_extrato
        + _DATAVIEW_EXTRATO
        + secao_pendentes
        + _DATAVIEWJS_PENDENTES
        + "\n"
    )

    (VAULT_MENSAL / file_name).write_text(conteudo, encoding="utf-8")
    return str(VAULT_MENSAL / file_name), saldo_calculado


# ──────────────────────────────────────────────
# GUI
# ──────────────────────────────────────────────
class ObsidianApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Obsidian Finanças")
        self.configure(bg=BG)

        # DPI awareness no Windows — evita interface borrada
        if _IS_WINDOWS:
            try:
                from ctypes import windll

                windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                pass

        # Dimensões e centralização
        w, h = 520, 620
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
        self.minsize(w, h)
        self.resizable(True, False)

        self._build_header()
        self._build_case_selector()
        self._frame_gasto = self._build_frame_gasto()
        self._frame_mes = self._build_frame_mes()
        self._build_footer()

        self._show_frame(None)

    def selecionar_vault(self):
        caminho = filedialog.askdirectory(title="Selecione a pasta raiz 'Finanças'")
        if caminho:
            global VAULT_BASE, VAULT_REGISTROS, VAULT_MENSAL

            # Atualiza as variáveis globais que os outros métodos usam
            VAULT_BASE = Path(caminho)
            VAULT_REGISTROS = VAULT_BASE / "Registros"
            VAULT_MENSAL = VAULT_BASE / "Mensal"

            # Atualiza o texto do rodapé dinamicamente
            self.lbl_path.config(text=f"vault -> ...{os.sep}{VAULT_BASE.name}")
            self._show_toast("Vault configurado com sucesso!", SUCCESS)

    # ── Header ──────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self, bg=PANEL, pady=14)
        hdr.pack(fill="x")
        tk.Label(
            hdr, text="⟁ Obsidian Finanças", font=FONT_HEAD, bg=PANEL, fg=ACCENT2
        ).pack()
        tk.Label(
            hdr,
            text="gerenciador de vault financeiro",
            font=FONT_SUB,
            bg=PANEL,
            fg=TEXT_DIM,
        ).pack()

    # ── Seletor de modo ──────────────────────
    def _build_case_selector(self):
        frm = tk.Frame(self, bg=BG, pady=18)
        frm.pack(fill="x", padx=30)

        tk.Label(
            frm, text="SELECIONE A OPERAÇÃO", font=FONT_TINY, bg=BG, fg=TEXT_DIM
        ).pack(anchor="w", pady=(0, 8))

        btn_frm = tk.Frame(frm, bg=BG)
        btn_frm.pack(fill="x")
        self._mode = tk.StringVar(value="")

        def make_btn(label, sub, val, col, is_first):
            f = tk.Frame(
                btn_frm,
                bg=SURFACE,
                cursor="hand2",
                highlightthickness=1,
                highlightbackground=PANEL,
            )
            f.pack(
                side="left", expand=True, fill="both", padx=(0 if is_first else 6, 0)
            )

            tl = tk.Label(
                f,
                text=label,
                font=("Courier New", 12, "bold"),
                bg=SURFACE,
                fg=col,
                pady=10,
            )
            tl.pack()
            sl = tk.Label(f, text=sub, font=FONT_TINY, bg=SURFACE, fg=TEXT_DIM)
            sl.pack(pady=(0, 8))

            def select(e=None):
                self._mode.set(val)
                self._show_frame(val)
                for child in btn_frm.winfo_children():
                    child.configure(highlightbackground=PANEL)
                f.configure(highlightbackground=col)

            for w in (f, tl, sl):
                w.bind("<Button-1>", select)

        make_btn("[ 1 ]  Registrar", "gasto / entrada / a pagar", "1", ACCENT, True)
        make_btn("[ 2 ]  Criar Mês", "relatório mensal", "2", ACCENT2, False)

    # ── Frame Registrar Gasto ────────────────
    def _build_frame_gasto(self):
        frm = tk.Frame(self, bg=BG)
        pad = tk.Frame(frm, bg=BG, padx=30)
        pad.pack(fill="both", expand=True)

        def lbl(text):
            tk.Label(
                pad, text=text, font=FONT_LBL, bg=BG, fg=TEXT_DIM, anchor="w"
            ).pack(fill="x")

        def entry_field(var, placeholder=""):
            e = tk.Entry(
                pad,
                textvariable=var,
                bg=SURFACE,
                fg=TEXT,
                insertbackground=ACCENT2,
                relief="flat",
                font=FONT_MONO,
                highlightthickness=1,
                highlightbackground=PANEL,
            )
            e.pack(fill="x", ipady=6, pady=(2, 10))

            def focus_in(_):
                if e.get() == placeholder:
                    e.delete(0, "end")
                    e.configure(fg=TEXT)

            def focus_out(_):
                if not e.get():
                    e.insert(0, placeholder)
                    e.configure(fg=TEXT_DIM)

            if placeholder:
                e.insert(0, placeholder)
                e.configure(fg=TEXT_DIM)
                e.bind("<FocusIn>", focus_in)
                e.bind("<FocusOut>", focus_out)
            return e

        tk.Label(
            pad, text="─── Novo Registro ───", font=FONT_TINY, bg=BG, fg=ACCENT, pady=4
        ).pack(anchor="w")

        self.v_nome = tk.StringVar()
        self.v_valor = tk.StringVar()
        self.v_cat = tk.StringVar()
        self.v_tipo = tk.StringVar(value="1")

        lbl("Nome do item")
        entry_field(self.v_nome, "ex: Mercado, Salario...")

        lbl("Valor (R$)")
        entry_field(self.v_valor, "ex: 150.00")

        lbl("Categoria")
        entry_field(self.v_cat, "ex: Alimentacao, Transporte...")

        lbl("Tipo")
        tipo_frm = tk.Frame(pad, bg=BG)
        tipo_frm.pack(fill="x", pady=(2, 12))

        for txt, val, cor in [
            ("Saida", "1", ACCENT),
            ("Entrada", "2", SUCCESS),
            ("A Pagar", "3", WARNING),
        ]:
            tk.Radiobutton(
                tipo_frm,
                text=txt,
                variable=self.v_tipo,
                value=val,
                bg=BG,
                fg=cor,
                selectcolor=SURFACE,
                activebackground=BG,
                activeforeground=cor,
                font=("Courier New", 10, "bold"),
            ).pack(side="left", padx=(0, 16))

        _PH = {
            "ex: Mercado, Salario...",
            "ex: 150.00",
            "ex: Alimentacao, Transporte...",
        }

        def salvar():
            nome = self.v_nome.get().strip()
            valor = self.v_valor.get().strip()
            cat = self.v_cat.get().strip()
            tipo = self.v_tipo.get()

            if not nome or nome in _PH:
                messagebox.showwarning(
                    "Campo vazio", "Preencha o nome do item.", parent=self
                )
                return
            if not valor or valor in _PH:
                messagebox.showwarning("Campo vazio", "Preencha o valor.", parent=self)
                return
            if not cat or cat in _PH:
                messagebox.showwarning(
                    "Campo vazio", "Preencha a categoria.", parent=self
                )
                return
            try:
                path = registrar_gasto(nome, valor, cat, tipo)
                self._show_toast(f"Registrado!\n{Path(path).name}", SUCCESS)
                self.v_nome.set("")
                self.v_valor.set("")
                self.v_cat.set("")
            except Exception as ex:
                messagebox.showerror("Erro", str(ex), parent=self)

        tk.Button(
            pad,
            text="-->  REGISTRAR",
            command=salvar,
            bg=ACCENT,
            fg="white",
            relief="flat",
            font=FONT_BTN,
            activebackground="#c73652",
            activeforeground="white",
            cursor="hand2",
            pady=10,
        ).pack(fill="x", pady=(4, 0))

        return frm

    # ── Frame Criar Mês ──────────────────────
    def _build_frame_mes(self):
        frm = tk.Frame(self, bg=BG)
        pad = tk.Frame(frm, bg=BG, padx=30)
        pad.pack(fill="both", expand=True)

        hoje = date.today()
        nome_mes = MESES[hoje.month]
        ano = hoje.year

        tk.Label(
            pad,
            text="─── Gerar Relatorio ───",
            font=FONT_TINY,
            bg=BG,
            fg=ACCENT2,
            pady=4,
        ).pack(anchor="w")

        info_box = tk.Frame(
            pad, bg=SURFACE, highlightthickness=1, highlightbackground=PANEL
        )
        info_box.pack(fill="x", pady=10)

        tk.Label(
            info_box,
            text=f"  {nome_mes} {ano}",
            font=("Georgia", 16, "bold"),
            bg=SURFACE,
            fg=ACCENT2,
            pady=12,
        ).pack()

        tk.Label(
            info_box,
            text="Sera criado o arquivo mensal do mes atual\ncom saldo herdado do mes anterior.",
            font=FONT_TINY,
            bg=SURFACE,
            fg=TEXT_DIM,
            justify="center",
            pady=6,
        ).pack(pady=(0, 12))

        self._lbl_preview = tk.Label(
            pad, text="", font=FONT_TINY, bg=BG, fg=TEXT_DIM, justify="left"
        )
        self._lbl_preview.pack(anchor="w", pady=(6, 0))

        def gerar():
            try:
                path, saldo = criar_mes()
                preview = (
                    f"  arquivo  ->  {Path(path).name}\n"
                    f"  pasta    ->  ...{os.sep}Financas{os.sep}Mensal\n"
                    f"  saldo    ->  R$ {saldo:.2f}"
                )
                self._lbl_preview.configure(text=preview, fg=TEXT_DIM)
                self._show_toast(f"Relatorio gerado!\n{Path(path).name}", ACCENT2)
            except Exception as ex:
                messagebox.showerror("Erro", str(ex), parent=self)

        tk.Button(
            pad,
            text="-->  GERAR RELATORIO",
            command=gerar,
            bg=ACCENT2,
            fg=BG,
            relief="flat",
            font=FONT_BTN,
            activebackground="#3ab8d8",
            activeforeground=BG,
            cursor="hand2",
            pady=10,
        ).pack(fill="x", pady=(14, 0))

        return frm

    # ── Toast ────────────────────────────────
    def _show_toast(self, msg: str, color: str):
        toast = tk.Toplevel(self)
        toast.overrideredirect(True)
        toast.configure(bg=SURFACE)
        toast.attributes("-topmost", True)

        tk.Label(
            toast,
            text=msg,
            font=FONT_TINY,
            bg=SURFACE,
            fg=color,
            padx=20,
            pady=14,
            justify="left",
        ).pack()

        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 300) // 2
        y = self.winfo_y() + self.winfo_height() - 10
        toast.geometry(f"300x70+{x}+{y}")
        toast.after(2800, toast.destroy)

    # ── Controle de frames ───────────────────
    def _show_frame(self, mode):
        self._frame_gasto.pack_forget()
        self._frame_mes.pack_forget()
        if mode == "1":
            self._frame_gasto.pack(fill="both", expand=True)
        elif mode == "2":
            self._frame_mes.pack(fill="both", expand=True)

    def _build_footer(self):
        ft = tk.Frame(self, bg=PANEL, pady=6)
        ft.pack(side="bottom", fill="x")

        # Botão de engrenagem no canto direito
        btn_config = tk.Button(
            ft,
            text="⚙",
            command=self.selecionar_vault,
            bg=PANEL,
            fg=TEXT_DIM,
            activebackground=PANEL,
            activeforeground=ACCENT2,
            font=("Courier New", 12),
            borderwidth=0,
            cursor="hand2",
        )
        btn_config.pack(side="right", padx=10)

        # Label do caminho (agora é um atributo self. para podermos atualizar)
        vault_exibicao = f"...{os.sep}{VAULT_BASE.parent.name}{os.sep}{VAULT_BASE.name}"
        self.lbl_path = tk.Label(
            ft,
            text=f"vault  ->  {vault_exibicao}",
            font=FONT_TINY,
            bg=PANEL,
            fg=TEXT_DIM,
        )
        self.lbl_path.pack(side="left", padx=15)


# ──────────────────────────────────────────────
if __name__ == "__main__":
    app = ObsidianApp()
    app.mainloop()
