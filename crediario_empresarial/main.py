import os
import sys
import json
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader

import requests
import base64


# Configurações da página
PAGE_WIDTH, PAGE_HEIGHT = A4

# ========================= CONFIGURAÇÕES GLOBAIS =========================
# Cores utilizadas no layout
COLORS = {
    "black01": "#45474B",
    "black02": "#303132",
    "blue01": "#1976D2", 
    "gold01": "#dcbf4a", 
    "white": "#FFFFFF", 
    "grey01": "#A8A9AB"
}

# Configurações do banco e boleto
CONFIG = {
    "banco_nome": "CREDIEXPO",
    "banco_codigo": "8799",
    "linha_digitavel": "",
    "beneficiario": "EXPO CURSOS DE FORMAÇÃO PROFISSIONAL LTDA",
    "beneficiario_fantasia": "INOVI",
    "agencia_codigo": "8799 / 99999-9",
    "local_pagamento": "DIRETO NO ESTABELECIMENTO",
    "banco_cnpj": "14.425.832/0001-64",
}

# Meses em português brasileiro (índice 0 vazio)
MESES_PTBR = [
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]

# ========================= GERENCIAMENTO DE IDs =========================

def obter_proximo_id():
    """
    Calcula o próximo ID sequencial disponível.
    Verifica arquivos JSON em diferentes locais para manter continuidade.
    """
    caminhos = [
        #os.path.join("dados", "boletos.json"),
        os.path.join("Boletos_Gerados", "boletos.json")
    ]
    
    maior_id = 0
    
    for caminho in caminhos:
        if os.path.exists(caminho):
            try:
                with open(caminho, "r", encoding="utf-8") as f:
                    dados = json.load(f)
                    for registro in dados:
                        if "id_boleto" in registro:
                            maior_id = max(maior_id, int(registro["id_boleto"]))
            except (json.JSONDecodeError, KeyError):
                continue  # Ignora arquivos corrompidos ou inválidos
    
    return maior_id + 1

# Inicializa ID sequencial global
SEQUENCIAL_ID = obter_proximo_id()

# ========================= UTILITÁRIOS =========================

def parse_valor(valor_str):
    """Converte string de valor monetário para float (ex: '1.500,00' -> 1500.0)."""
    valor_str = str(valor_str).replace(".", "").replace(",", ".").strip()
    return float(valor_str)

def parse_data(data_str):
    """Converte string de data para objeto datetime (formato: DD/MM/YYYY)."""
    return datetime.strptime(data_str.strip(), "%d/%m/%Y")

def format_valor(valor_float):
    """Formata valor float para string monetária brasileira (ex: 1500.0 -> '1.500,00')."""
    return f"{valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def limpar_texto(texto):
    """
    Remove espaços extras e normaliza texto.
    Exemplo: " João   Silva " → "João Silva"
    """
    return " ".join(str(texto).strip().split())

def formatar_cpf_cnpj(documento):
    """
    Formata CPF/CNPJ automaticamente:
    - CPF: 123.456.789-00 → 123.456.789-00 (11 dígitos)
    - CNPJ: 12.345.678/0001-00 → 12.345.678/0001-00 (14 dígitos)
    Remove caracteres não numéricos e aplica máscara correta.
    """
    # Remove tudo que não é dígito
    apenas_digitos = ''.join(filter(str.isdigit, str(documento)))
    
    if len(apenas_digitos) == 11:  # CPF
        return f"{apenas_digitos[:3]}.{apenas_digitos[3:6]}.{apenas_digitos[6:9]}-{apenas_digitos[9:]}"
    elif len(apenas_digitos) == 14:  # CNPJ
        return f"{apenas_digitos[:2]}.{apenas_digitos[2:5]}.{apenas_digitos[5:8]}/{apenas_digitos[8:12]}-{apenas_digitos[12:]}"
    else:
        # Se não for CPF nem CNPJ, limita a 18 caracteres e remove espaços extras
        return limpar_texto(documento)[:18]
    

def gerar_linha_digitavel(id_boleto, valor):
    """Gera linha digitável do boleto no padrão brasileiro."""
    base = f"104{id_boleto:06d}{int(valor * 100):010d}"
    return f"{base[:5]}.{base[5:10]} {base[10:15]}.{base[15:21]} {base[21:26]}.{base[26:32]} {id_boleto % 10} {base[-10:]}"

def gerar_nosso_numero(id_boleto):
    """Gera nosso número com dígito verificador."""
    return f"82106{id_boleto:06d}-{id_boleto % 9}"

# ========================= GESTÃO DE ARQUIVOS =========================

def obter_pasta_destino(data: datetime):
    """
    Cria e retorna caminho da pasta organizada por ano/mês.
    Exemplo: Boletos_Gerados/2024/03 - Março/
    """
    ano = data.year
    mes = data.month
    nome_mes = MESES_PTBR[mes]
    
    pasta = os.path.join("Boletos_Gerados", str(ano), f"{mes:02d} - {nome_mes}")
    os.makedirs(pasta, exist_ok=True)
    #os.makedirs("dados", exist_ok=True)  # Pasta central de dados
    return pasta

def carregar_registros():
    """Carrega registros existentes do arquivo JSON principal."""
    json_file = "boletos.json"
    if os.path.exists(json_file):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return []

def gerar_numero_documento_unico(id_sugerido):
    """Gera número de documento único evitando duplicatas."""
    registros = carregar_registros()
    existentes = {r["numero_documento"] for r in registros}
    numero = str(1000 + id_sugerido)
    
    while numero in existentes:
        id_sugerido += 1
        numero = str(1000 + id_sugerido)
    
    return numero, id_sugerido

def salvar_json_lote(boletos):
    """
    Salva boletos em JSONs organizados LOCALMENTE + upload SOMENTE dados.json para GitHub
    """
    if not boletos:
        return

    data_ref = parse_data(boletos[0].vencimento)
    pasta_mes = obter_pasta_destino(data_ref)
    
    # Prepara registros para salvar
    novos_registros = []
    for b in boletos:
        novos_registros.append({
            "id_boleto": b.id_boleto,
            "numero_documento": b.numero_documento,
            "pagador_nome": b.pagador_nome,
            "pagador_doc": b.pagador_doc,
            "valor_documento": b.valor_documento,
            "vencimento": b.vencimento,
            "status": "GERADO",
            "data_geracao": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        })

    # 1. Salva JSON mensal LOCAL
    caminho_mes = os.path.join(pasta_mes, "boletos.json")
    dados_mes = []
    if os.path.exists(caminho_mes):
        try:
            with open(caminho_mes, "r", encoding="utf-8") as f:
                dados_mes = json.load(f)
        except json.JSONDecodeError:
            dados_mes = []
    
    dados_mes.extend(novos_registros)
    with open(caminho_mes, "w", encoding="utf-8") as f:
        json.dump(dados_mes, f, ensure_ascii=False, indent=4)

    # 2. Salva JSON consolidado LOCAL (Boletos_Gerados/boletos.json)
    pasta_raiz = "Boletos_Gerados"
    os.makedirs(pasta_raiz, exist_ok=True)
    caminho_local = os.path.join(pasta_raiz, "boletos.json")
    
    dados_completos = []
    if os.path.exists(caminho_local):
        try:
            with open(caminho_local, "r", encoding="utf-8") as f:
                dados_completos = json.load(f)
        except json.JSONDecodeError:
            dados_completos = []
    
    # Merge: adiciona apenas novos boletos (evita duplicatas por ID)
    ids_existentes = {r["id_boleto"] for r in dados_completos}
    for novo in novos_registros:
        if novo["id_boleto"] not in ids_existentes:
            dados_completos.append(novo)
    
    with open(caminho_local, "w", encoding="utf-8") as f:
        json.dump(dados_completos, f, ensure_ascii=False, indent=4)

    # 3. UPLOAD SOMENTE dados.json para GitHub
    upload_github_simplificado(dados_completos)

def upload_github_simplificado(dados):
    """
    Upload dados.json → GitHub (corrigido)
    """
    # ===== COLE SEU TOKEN AQUI =====
    GITHUB_TOKEN = "GITHUB_TOKEN"
    REPO_NOME = "Sulivanprog/crediario_empresarial"
    
    print(f"🔍 Testando token para {REPO_NOME}...")
    
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Teste token
    if requests.get("https://api.github.com/user", headers=headers).status_code != 200:
        print("❌ 1️⃣ TOKEN INVÁLIDO")
        print("👉 github.com/settings/tokens → Generate new → repo")
        return
    
    # Teste repo
    if requests.get(f"https://api.github.com/repos/{REPO_NOME}", headers=headers).status_code != 200:
        print("❌ 2️⃣ REPO NÃO EXISTE")
        print(f"👉 Crie: github.com/new → '{REPO_NOME.split('/')[1]}'")
        return
    
    try:
        # Prepara JSON
        dados_json = json.dumps(dados, ensure_ascii=False, indent=2)
        content_b64 = base64.b64encode(dados_json.encode('utf-8')).decode()
        
        url = f"https://api.github.com/repos/{REPO_NOME}/contents/dados.json"
        
        # SHA atual
        resp_get = requests.get(url, headers=headers)
        data = {
            "message": f"Boletos: {len(dados)} registros - {datetime.now().strftime('%d/%m %H:%M')}",
            "content": content_b64
        }
        
        if resp_get.status_code == 200:
            data["sha"] = resp_get.json()["sha"]
            print("📤 Atualizando...")
        else:
            print("📤 Criando...")
        
        # UPLOAD
        resp = requests.put(url, headers=headers, json=data)
        
        if resp.status_code in [200, 201]:
            url_raw = f"https://raw.githubusercontent.com/{REPO_NOME}/main/dados.json"
            print(f"✅ SUCESSO! {len(dados)} boletos enviados")
            print(f"📱 Excel: {url_raw}")
            print("🔄 Ctrl+Shift+F5 no Excel para atualizar")
        else:
            print(f"❌ HTTP {resp.status_code}")
            print(resp.text[:500])
            
    except Exception as e:
        print(f"❌ Erro: {e}")


# ========================= FUNÇÕES DE DESENHO =========================

def box(c, x, y, w, h, color=HexColor(COLORS["grey01"]), largura=0.2):
    """Desenha retângulo com borda configurável."""
    c.setStrokeColor(color)
    c.setLineWidth(largura)
    c.rect(x, y, w, h, stroke=1, fill=0)

def t(c, x, y, txt, size=7, bold=False):
    """Desenha texto alinhado à esquerda."""
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.drawString(x, y, str(txt))

def tr(c, x, y, txt, size=7, bold=False):
    """Desenha texto alinhado à direita."""
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.drawRightString(x, y, str(txt))

def tm(c, x, y, txt, size=8):
    """Desenha texto em fonte monoespaçada (Courier)."""
    c.setFont("Courier", size)
    c.drawString(x, y, str(txt))

def draw_logo(c, caminho_imagem, x, y, altura_max):
    """
    Desenha logo mantendo proporção original.
    Ajusta altura automaticamente preservando aspect ratio.
    """
    if not os.path.exists(caminho_imagem):
        return

    img = ImageReader(caminho_imagem)
    largura, altura = img.getSize()
    
    proporcao = altura_max / altura
    largura_ajustada = largura * proporcao
    
    c.drawImage(img, x, y, width=largura_ajustada, height=altura_max, mask='auto')

def draw_watermark(c, x, y, w, h, tipo="boleto"):
    """
    Desenha marca d'água com detecção automática de executável.
    """
    # Caminho relativo para desenvolvimento
    caminho_relativo = os.path.join("logo_marca", "marca.png")
    
    # Caminho para executável PyInstaller
    if getattr(sys, 'frozen', False):
        # Se está rodando como executável
        base_path = sys._MEIPASS
        caminho_exe = os.path.join(base_path, "logo_marca", "marca.png")
    else:
        # Se está rodando como script Python
        base_path = os.path.abspath(".")
        caminho_exe = caminho_relativo
    
    # Tenta os dois caminhos
    for caminho in [caminho_relativo, caminho_exe]:
        if os.path.exists(caminho):
            try:
                c.saveState()
                img = ImageReader(caminho)
                
                # Configurações por tipo (mantém igual)
                if tipo == "boleto":
                    largura, altura = w * 0.6, h * 0.9
                    pos_x, pos_y = x + (w - largura) / 2, y + (h - altura) / 2
                    alpha = 0.08
                elif tipo == "recibo":
                    largura, altura = w * 1.0, h * 0.6
                    pos_x, pos_y = x + (w - largura) / 2, y + (h - altura) / 2
                    alpha = 0.08
                else:
                    largura, altura = w * 0.5, h * 0.5
                    pos_x, pos_y = x, y
                    alpha = 0.05
                
                try:
                    c.setFillAlpha(alpha)
                except AttributeError:
                    pass
                
                c.drawImage(img, pos_x, pos_y, width=largura, height=altura, mask='auto')
                c.restoreState()
                return  # Sucesso, sai da função
            except Exception:
                continue  # Tenta próximo caminho
    
    # Se não encontrou imagem, desenha texto alternativo
    c.saveState()
    c.setFillColor(colors.lightgrey)
    c.setFont("Helvetica", 20)
    c.setFillAlpha(0.1)
    c.rotate(45)
    c.drawCentredText(x + w/2, y + h/2, "CREDIEXPO")
    c.restoreState()

def draw_recibo_pagador(c, x, y, w, h, b):
    """
    Desenha recibo do pagador (lado esquerdo do boleto).
    Inclui dados do beneficiário, pagador e valores.
    """
    pad = 3 * mm
    
    # Caixa principal do recibo
    box(c, x, y, w, h, HexColor(COLORS["black01"]), 0.5)
    draw_watermark(c, x, y, w, h, tipo="recibo")
    
    # Título
    t(c, x + pad, y + h - 5 * mm, "RECIBO DO PAGADOR", 8, True)
    
    y_cursor = y + h - 10 * mm
    
    # Beneficiário
    t(c, x + pad, y_cursor, "Beneficiário:", 7, True)
    y_cursor -= 3 * mm
    t(c, x + pad, y_cursor, "Inovi", 8)
    y_cursor -= 3.5 * mm
    t(c, x + pad, y_cursor, CONFIG["banco_cnpj"], 8)
    
    # Nosso número
    y_cursor -= 4.5 * mm
    t(c, x + pad, y_cursor, "Número Doc.", 7, True)
    y_cursor -= 3.5 * mm
    t(c, x + pad, y_cursor, b.nosso_numero, 8)
    
    y_cursor -= 4.5 * mm
    t(c, x + pad, y_cursor, "Nosso Número", 7, True)
    y_cursor -= 3.5 * mm
    t(c, x + pad, y_cursor, b.nosso_numero, 8)
    
    # Pagador
    y_cursor -= 4.5 * mm
    t(c, x + pad, y_cursor, "Pagador", 7, True)
    y_cursor -= 3.5 * mm
    t(c, x + pad, y_cursor, b.pagador_nome, 8)
    
    # CPF/CNPJ formatado e limitado ✅
    y_cursor -= 4.5 * mm
    t(c, x + pad, y_cursor, "CPF/CNPJ", 7, True)
    y_cursor -= 3.5 * mm
    t(c, x + pad, y_cursor, b.pagador_doc[:18], 8)  # Limita a 18 caracteres
    
    
    # Valores
    y_cursor -= 4.5 * mm
    t(c, x + pad, y_cursor, "Valor Documento", 7, True)
    y_cursor -= 3.5 * mm
    t(c, x + pad, y_cursor, f"R$ {b.valor_documento}", 8, True)
    
    y_cursor -= 4.5 * mm
    t(c, x + pad, y_cursor, "Vencimento", 7)
    y_cursor -= 3.5 * mm
    t(c, x + pad, y_cursor, b.vencimento, 8, True)

    y_cursor -= 4.5 * mm
    t(c, x + pad, y_cursor, "Pago em", 7)
    y_cursor -= 3.5 * mm
    t(c, x + pad, y_cursor, "___/___/______", 8)
    
    y_cursor -= 4.5 * mm
    t(c, x + pad, y_cursor, "Recebido por", 7)
    y_cursor -= 4 * mm
    t(c, x + pad, y_cursor, "________________________", 8)
    
    # Rodapé com nome do banco
    y_cursor -= 8 * mm
    t(c, x + pad, y_cursor, "CREDIEXPO", 10, True)
    
    # Linha divisória
    c.setDash(2, 2)
    c.line(x + w + 2.5, y, x + w + 2.5, y + h)
    c.setDash()

def draw_boleto(c, x, y, w, h, b):
    """
    Desenha boleto principal (lado direito).
    Inclui header, dados, instruções, pagador e financeiro.
    """
    pad = 3 * mm
    header_h = 11 * mm
    row_h = 7.2 * mm
    instr_h = 14 * mm
    sac_h = 16 * mm
    footer_h = 18 * mm
    
    left_w = w * 0.70
    right_w = w * 0.30
    
    # Marca d'água
    draw_watermark(c, x, y, w, h)
    
    # Header do boleto
    t(c, x + pad, y + h - 4 * mm, CONFIG["banco_nome"], 10, True)
    t(c, x + 35 * mm, y + h - 4 * mm, CONFIG["banco_codigo"], 10, True)
    tr(c, x + w - pad, y + h - 4 * mm, CONFIG["linha_digitavel"], 9, True)
    
    top = y + h - header_h
    
    # Linha 1: Beneficiário e Agência
    box(c, x, top - row_h, left_w, row_h)
    box(c, x + left_w, top - row_h, right_w, row_h)
    t(c, x + pad, top - 2.8 * mm, "BENEFICIÁRIO", 6)
    beneficiario_txt= f"{CONFIG["beneficiario"]} - {CONFIG["beneficiario_fantasia"]}"
    t(c, x + pad, top - 6 * mm, beneficiario_txt, 8, True)
    t(c, x + left_w + pad, top - 2.8 * mm, "AGÊNCIA / CÓDIGO DO BENEFICIÁRIO", 6)
    t(c, x + left_w + pad, top - 6 * mm, CONFIG["agencia_codigo"], 8, True)
    top -= row_h
    
    # Linha 2: Datas e Nosso Número
    box(c, x, top - row_h, left_w, row_h)
    box(c, x + left_w, top - row_h, right_w, row_h)
    t(c, x + pad, top - 2.8 * mm, "DATA DOC.", 6)
    t(c, x + pad, top - 6 * mm, b.data_documento, 8)
    t(c, x + 45 * mm, top - 2.8 * mm, "NÚMERO DOC.", 6)
    t(c, x + 45 * mm, top - 6 * mm, b.numero_documento, 8)
    t(c, x + 80 * mm, top - 2.8 * mm, "DATA DE VENCIMENTO", 6)
    t(c, x + 80 * mm, top - 6 * mm, b.vencimento, 8, True)
    t(c, x + left_w + pad, top - 2.8 * mm, "NOSSO NÚMERO", 6)
    t(c, x + left_w + pad, top - 6 * mm, b.nosso_numero, 8)
    top -= row_h
    
    # Linha 3: Espécie, Parcelas e Valor
    box(c, x, top - row_h, left_w, row_h)
    box(c, x + left_w, top - row_h, right_w, row_h)
    t(c, x + pad, top - 2.8 * mm, "ESPÉCIE DOC./ ACEITE", 6)
    t(c, x + pad, top - 6 * mm, f"{b.especie} / {b.aceite}", 7)

    t(c, x + 60 * mm, top - 2.8 * mm, "PARCELAS", 6)
    t(c, x + 60 * mm, top - 6 * mm, b.parcelas, 8)
    t(c, x + left_w + pad, top - 2.8 * mm, "VALOR DOCUMENTO", 6)
    t(c, x + left_w + pad, top - 6 * mm, b.valor_documento, 8, True)
    top -= row_h
    
    # Instruções ao pagador
    box(c, x, top - instr_h, w, instr_h)
    t(c, x + pad, top - 4 * mm, "INSTRUÇÕES", 6, True)
    
    y_texto = top - 7 * mm
    linhas = b.instrucoes_cliente.split("\n")
    for linha in linhas:
        t(c, x + pad, y_texto, linha, 6)
        y_texto -= 3 * mm
    top -= instr_h
    
    # Dados do pagador (SAC)
    box(c, x, top - sac_h, w, sac_h)
    t(c, x + pad, top - 4 * mm, "PAGADOR", 6, True)
    
    # Dados do pagador com limitação 
    pagador_nome = b.pagador_nome[:35]  # Limita nome exibido
    t(c, x + pad, top - 8 * mm, pagador_nome, 6, True)

    pagador_doc = f"CPF/CNPJ: {b.pagador_doc[:18]}"
    t(c, x + 70 * mm, top - 9 * mm, pagador_doc, 6)  #CPF/CNPJ limitado
    
    pagador_end_l1 = f"{b.pagador_logradouro[:50]}, {b.pagador_numero[:8]}".upper()[:45]
    t(c, x + pad, top - 11 * mm, pagador_end_l1, 6)
    
    pagador_end_l2 = f"{b.pagador_bairro[:20]} - {b.pagador_cidade[:20]} - {b.pagador_uf}".upper()[:50]
    t(c, x + pad, top - 14 * mm, pagador_end_l2, 6)
    
    # Financeiro (coluna direita)
    sx = x + left_w
    sy = top - sac_h
    
    labels = [
        "(-) DESCONTO/ABATIMENTO",
        "(-) OUTRAS DEDUÇÕES", 
        "(+) OUTROS ACRÉSCIMOS",
        "(=) VALOR COBRADO",
    ]
    
    values = [b.desconto, b.deducoes, b.acrescimos, b.valor_cobrado]
    cell_h = 5.5 * mm
    
    for i in range(4):
        yy = sy + sac_h - (i + 1) * cell_h
        box(c, sx, yy, right_w, cell_h)
        t(c, sx + pad, yy + 1.8 * mm, labels[i], 6)
        tr(c, x + w - pad, yy + 1.8 * mm, values[i], 8, True)
    
    # Footer com local de pagamento e linha digitável
    box(c, x, y, w, footer_h)
    t(c, x + pad, y + footer_h - 5 * mm, CONFIG["local_pagamento"], 7)
    t(c, x + pad, y + footer_h - 10 * mm, "LINHA DIGITÁVEL", 6, True)
    tm(c, x + pad, y + 3 * mm, CONFIG["linha_digitavel"], 8)
    
    # Borda externa do boleto completo
    box(c, x, y, w, h, HexColor(COLORS["black01"]), 0.5)

def draw_boleto_com_recibo(c, x, y, w, h, b):
    """Desenha boleto completo com recibo integrado (layout lado a lado)."""
    recibo_w = w * 0.22
    gap = 2 * mm
    boleto_w = w - recibo_w - gap
    
    draw_recibo_pagador(c, x, y, recibo_w, h, b)
    draw_boleto(c, x + recibo_w + gap, y, boleto_w, h, b)


# ========================= CLASSE BOLETO =========================

class Boleto:
    """
    Representa um boleto bancário completo com todos os dados necessários.
    Gera automaticamente nosso número, linha digitável e datas de vencimento.
    """
    
    def __init__(self, idx, nome, doc, logradouro, numero, bairro, cidade, uf, 
                 instrucoes, parcela_num, total_parcelas, valor, data_base):
        global SEQUENCIAL_ID
        
        # ID único sequencial
        self.id_boleto = SEQUENCIAL_ID
        SEQUENCIAL_ID += 1
        
        # Informações básicas
        self.parcelas = f"{parcela_num:02d}/{total_parcelas:02d}"
        self.data_documento = datetime.today().strftime("%d/%m/%Y")
        self.numero_documento, self.id_boleto = gerar_numero_documento_unico(self.id_boleto)
        
        # Configurações padrão
        self.especie = "DM"
        self.aceite = "NÃO"
        self.nosso_numero = gerar_nosso_numero(self.id_boleto)
        
        # Data de vencimento (30 dias por parcela)
        self.vencimento = (data_base + timedelta(days=30 * (parcela_num - 1))).strftime("%d/%m/%Y")
        
        # Valores formatados
        self.valor_documento = format_valor(valor)
        self.desconto = "0,00"
        self.deducoes = "0,00"
        self.acrescimos = "0,00"
        self.valor_cobrado = self.valor_documento
        
        # Dados do pagador
        # Dados do pagador (COM FORMATAÇÃO CPF/CNPJ)
        self.pagador_nome = limpar_texto(nome)[:35]  # Limita nome a 35 caracteres
        self.pagador_doc = formatar_cpf_cnpj(doc)    # ✅ Formatação automática CPF/CNPJ
        self.pagador_logradouro = limpar_texto(logradouro)[:50]
        self.pagador_numero = limpar_texto(numero)[:8]
        self.pagador_bairro = limpar_texto(bairro)[:20]
        self.pagador_cidade = limpar_texto(cidade)[:20]
        self.pagador_uf = limpar_texto(uf)[:2].upper()
        
        # Instruções personalizadas
        self.instrucoes_cliente = instrucoes
        
        # Gera linha digitável
        CONFIG["linha_digitavel"] = gerar_linha_digitavel(self.id_boleto, valor)

# ========================= GERAÇÃO DE PDF =========================

def gerar_pdf(boletos):
    """
    Gera PDF com múltiplos boletos organizados em páginas A4.
    Layout otimizado: 3 boletos por página.
    """
    if not boletos:
        return

    # Determina pasta de destino baseada na data de vencimento
    data_ref = parse_data(boletos[0].vencimento)
    pasta = obter_pasta_destino(data_ref)
    
    # Nome do arquivo baseado no pagador e ID
    nome_base = boletos[0].pagador_nome.replace(" ", "_")
    nome_arquivo = f"Boletos_{nome_base}_{boletos[0].id_boleto:03d}.pdf"
    caminho_pdf = os.path.join(pasta, nome_arquivo)
    
    # Cria canvas PDF
    c = canvas.Canvas(caminho_pdf, pagesize=A4)
    
    # Layout da página
    margin = 8 * mm
    gap = 4 * mm
    usable_h = PAGE_HEIGHT - (2 * margin)
    boleto_h = (usable_h - (2 * gap)) / 3
    
    w = PAGE_WIDTH - 2 * margin
    x = margin
    
    # Desenha cada boleto
    for i, b in enumerate(boletos):
        slot = i % 3  # Posição na página (0, 1, 2)
        
        # Nova página a cada 3 boletos
        if i > 0 and slot == 0:
            c.showPage()
        
        y = PAGE_HEIGHT - margin - (slot + 1) * boleto_h - (slot * gap)
        draw_boleto_com_recibo(c, x, y, w, boleto_h, b)
    
    c.save()

# ========================= INTERFACE GRÁFICA =========================

def criar_interface():
    """
    Interface COMPLETA com LabelFrame AMOSTRAL + função gerar_boletos inclusa.
    """
    root = tk.Tk()
    root.title("Sistema de Geração de crediários - CREDIEXPO")
    root.geometry("1100x820")
    root.resizable(False, False)
    
    fonte = ("Helvetica", 10)
    fonte_tt = ("Helvetica", 9, "bold")
    
    # Frame principal
    main_frame = ttk.Frame(root, padding=20)
    main_frame.pack(expand=True, fill="both")
    
    # ===========================================
    # CONTAINER HORIZONTAL: CATEGORIA 1 + AMOSTRA
    # ===========================================
    container_categoria1 = ttk.Frame(main_frame)
    container_categoria1.pack(fill="x", pady=(0, 15))
    
    # ESQUERDA: Dados editáveis (60%)
    frame_esquerda = ttk.Frame(container_categoria1)
    frame_esquerda.pack(side="left", fill="both", expand=True, padx=(0, 10))
    
    frame_pagador = ttk.LabelFrame(frame_esquerda, text="👤 DADOS DO PAGADOR", padding=15)
    frame_pagador.pack(fill="both", expand=True)
    
    grid_pagador = ttk.Frame(frame_pagador)
    grid_pagador.pack(fill="both", expand=True)
    
    # VARIÁVEIS DOS CAMPOS
    campos_pagador = {
        "Nome Completo": tk.StringVar(value="Celena Batista dos Santos"),
        "CPF/CNPJ": tk.StringVar(value="179.084.137-10"),
        "Logradouro": tk.StringVar(value="Avenida Adalberto Simão Nader"),
        "Número": tk.StringVar(value="565"),
        "Bairro": tk.StringVar(value="Mata da Praia"),
        "Cidade": tk.StringVar(value="Vitória"),
        "UF": tk.StringVar(value="ES"),
    }
    
    widgets = {}
    row = 0
    
    for rotulo, var in campos_pagador.items():
        ttk.Label(grid_pagador, text=f"{rotulo}:", font=fonte_tt, foreground=COLORS["blue01"], width=15).grid(
            row=row, column=0, sticky="w", padx=(0, 10), pady=5
        )
        entry = ttk.Entry(grid_pagador, textvariable=var, font=fonte, width=35,foreground=COLORS["black02"])
        entry.grid(row=row, column=1, sticky="ew", padx=(0, 0), pady=5)
        widgets[rotulo] = entry
        row += 1
    
    grid_pagador.columnconfigure(1, weight=1)
    
    # DIREITA: AMOSTRA FIXA (40%)
    frame_amostra = ttk.LabelFrame(container_categoria1, text="🏢 BENEFICIÁRIO (FIXO)", padding=15)
    frame_amostra.pack(side="right", fill="y")
    frame_amostra.configure(width=380)
    
    amostra_dados = [
        ("Beneficiário:", CONFIG["beneficiario"]),
        ("CNPJ:", CONFIG["banco_cnpj"]),
        ("Banco:", CONFIG["banco_nome"]),
        ("Agência:", CONFIG["agencia_codigo"]),
        ("Local Pagto:", CONFIG["local_pagamento"]),
    ]
    
    for i, (rotulo, valor) in enumerate(amostra_dados):
        ttk.Label(frame_amostra, text=rotulo, font=fonte_tt, foreground=COLORS["blue01"]).grid(
            row=i*2, column=0, sticky="w", pady=2)
        ttk.Label(frame_amostra, text=valor, font=fonte, foreground= COLORS["black01"]).grid(
            row=i*2+1, column=0, sticky="w", pady=(0, 8))
    
    # ===========================================
    # CATEGORIA 2: VALORES
    # ===========================================
    frame_valores = ttk.LabelFrame(main_frame, text="💰 VALORES E PARCELAS", padding=15)
    frame_valores.pack(fill="x", pady=(0, 15))
    
    campos_valores = {
        "Parcelas": tk.StringVar(value="12"),
        "Valor/Parcela (R$)": tk.StringVar(value="150,00"),
        "Data 1ª Parcela": tk.StringVar(value=datetime.today().strftime("%d/%m/%Y")),
    }
    
    grid_valores = ttk.Frame(frame_valores)
    grid_valores.pack(fill="both", expand=True)
    
    row = 0
    for rotulo, var in campos_valores.items():
        ttk.Label(grid_valores, text=f"{rotulo}:", font=fonte_tt, foreground=COLORS["blue01"], width=20).grid(
            row=row, column=0, sticky="w", padx=(0, 10), pady=8
        )
        entry = ttk.Entry(grid_valores, textvariable=var, font=fonte, foreground=COLORS["black02"], width=25)
        entry.grid(row=row, column=1, sticky="w", padx=(0, 0), pady=8)
        widgets[rotulo] = entry
        row += 1
    
    # ===========================================
    # CATEGORIA 3: INSTRUÇÕES
    # ===========================================
    frame_instrucoes = ttk.LabelFrame(main_frame, text="📋 INSTRUÇÕES AO PAGADOR", padding=15)
    frame_instrucoes.pack(fill="x", pady=(0, 20))
    
    lbl_instr = ttk.Label(frame_instrucoes, text="Instruções que aparecerão no boleto:", font=fonte_tt, foreground=COLORS["blue01"])
    lbl_instr.pack(anchor="w", pady=(0, 5))
    
    txt_instrucoes = tk.Text(frame_instrucoes, height=4, font=fonte, wrap="word", 
                           relief="solid", borderwidth=1, bg=COLORS["white"],foreground=COLORS["black02"],
                           highlightbackground= COLORS["grey01"])
    txt_instrucoes.pack(fill="x", pady=(0, 10))
    txt_instrucoes.insert("1.0", "MULTA DE 2% APÓS VENCIMENTO.\nJUROS DE 1% AO MÊS.")
    widgets["Instruções"] = txt_instrucoes
    
    # ===========================================
    # BOTÃO + FUNÇÕES LOCAIS
    # ===========================================
    separator = ttk.Separator(main_frame, orient="horizontal")
    separator.pack(fill="x", pady=(10, 20))
    
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill="x")
    
    # FUNÇÃO limpar_texto LOCAL
    def limpar_texto(texto):
        return " ".join(str(texto).strip().split())
    
    # FUNÇÃO gerar_boletos LOCAL (AGORA DEFINIDA!)
    def gerar_boletos():
        try:
            qtd_parcelas = int(campos_valores["Parcelas"].get())
            valor_parcela = parse_valor(campos_valores["Valor/Parcela (R$)"].get())
            data_primeira = parse_data(campos_valores["Data 1ª Parcela"].get())
            
            boletos = [
                Boleto(
                    i,
                    limpar_texto(campos_pagador["Nome Completo"].get()).title(),
                    limpar_texto(campos_pagador["CPF/CNPJ"].get()),
                    limpar_texto(campos_pagador["Logradouro"].get()).title(),
                    limpar_texto(campos_pagador["Número"].get()),
                    limpar_texto(campos_pagador["Bairro"].get()).title(),
                    limpar_texto(campos_pagador["Cidade"].get()).title(),
                    limpar_texto(campos_pagador["UF"].get()).upper(),
                    limpar_texto(widgets["Instruções"].get("1.0", "end-1c")).upper(),
                    i + 1, qtd_parcelas, valor_parcela, data_primeira
                )
                for i in range(qtd_parcelas)
            ]
            
            gerar_pdf(boletos)
            salvar_json_lote(boletos)
            
            messagebox.showinfo(
                "✅ Sucesso!",
                f"🎉 {len(boletos)} Crediários gerados!\n📁 Boletos_Gerados/..."
            )
        except ValueError as e:
            messagebox.showerror("❌ Erro", f"Dados inválidos: {str(e)}")
        except Exception as e:
            messagebox.showerror("❌ Erro", f"Erro: {str(e)}")
    
    # BOTÃO com função LOCAL
    ttk.Button(btn_frame, text="🚀 GERAR CREDIÁRIOS", command=gerar_boletos).pack(pady=15)
    
    # EVENTO CPF/CNPJ
    def validar_cpf_cnpj(event=None):
        doc_raw = campos_pagador["CPF/CNPJ"].get()
        doc_formatado = formatar_cpf_cnpj(doc_raw)
        campos_pagador["CPF/CNPJ"].set(doc_formatado)
    
    widgets["CPF/CNPJ"].bind('<KeyRelease>', validar_cpf_cnpj)
    
    root.mainloop()

# ========================= EXECUÇÃO PRINCIPAL =========================

if __name__ == "__main__":
    criar_interface()
