# app.py - Interface principal via Streamlit
import streamlit as st
import requests
import openai
import os
import json
import pdfplumber
import io
import pytesseract
from PIL import Image
from pdf2image import convert_from_bytes
from dotenv import load_dotenv

load_dotenv()

# Variáveis de ambiente
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_APROVACAO = os.getenv("TELEGRAM_CHAT_APROVACAO")
CHAT_PAGAMENTO = os.getenv("TELEGRAM_CHAT_PAGAMENTO")

# Inicializa o estado da sessão
if "faturas_processadas" not in st.session_state:
    st.session_state.faturas_processadas = []
if "fatura_atual" not in st.session_state:
    st.session_state.fatura_atual = None

# Função para extrair texto real do PDF com fallback para OCR

def extrair_texto_legivel(pdf_bytes):
    texto = ''
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                texto += page.extract_text() or ''
    except Exception:
        texto = ''

    if not texto.strip():
        st.warning("📷 Texto não encontrado diretamente no PDF. Aplicando OCR (Tesseract)...")
        imagens = convert_from_bytes(pdf_bytes)
        texto = ''
        for imagem in imagens:
            texto += pytesseract.image_to_string(imagem)

    return texto.strip()

# Função principal de extração via GPT

def extrair_dados_com_gpt(file_bytes):
    conteudo_simples = extrair_texto_legivel(file_bytes)[:3000]  # texto real extraído do PDF ou via OCR
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Você é um extrator de dados financeiros. Sempre responda em JSON válido."},
            {"role": "user", "content": f"""Extraia os seguintes dados da nota fiscal e devolva apenas um JSON válido e estruturado com os campos abaixo:

- tipo_documento
- numero_nota
- serie
- emitente_nome
- emitente_cnpj
- destinatario_nome
- destinatario_cpf_cnpj
- data_emissao
- vencimento
- forma_pagamento
- valor_total
- descricao
- impostos (estrutura como objeto: {{ ICMS, PIS, COFINS, IPI, outros se houver }})
- itens (como lista: descricao, quantidade, valor_unitario, valor_total)

Exemplo esperado:
{{
  "tipo_documento": "NF-e",
  "numero_nota": "330494",
  "serie": "100",
  "emitente_nome": "CMD Automóveis Ltda",
  "emitente_cnpj": "07.023.175/0004-06",
  "destinatario_nome": "Rodrigo Spina Moris",
  "destinatario_cpf_cnpj": "216.478.858-33",
  "data_emissao": "2025-05-14",
  "vencimento": "2025-05-14",
  "forma_pagamento": "À vista",
  "valor_total": 873.71,
  "descricao": "Venda de peças e serviços automotivos.",
  "impostos": {{
    "ICMS": 42.00,
    "PIS": 8.70,
    "COFINS": 14.00
  }},
  "itens": [
    {{ "descricao": "Filtro de óleo", "quantidade": 1, "valor_unitario": 71.90, "valor_total": 71.90 }}
  ]
}}

Conteúdo do documento:
{conteudo_simples}"""}
        ]
    )
    return response.choices[0].message.content

def enviar_telegram(chat_id, mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": mensagem,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload)

# Interface Streamlit
st.title("📄 Sistema Financeiro Autônomo - ERP Chatbot")

uploaded = st.file_uploader("Envie a nota fiscal, boleto ou fatura (PDF ou imagem)")

if uploaded and st.session_state.fatura_atual is None:
    bytes_data = uploaded.read()
    dados_extraidos = extrair_dados_com_gpt(bytes_data)

    st.subheader("🔍 Resposta do GPT-4")
    st.write(dados_extraidos)

    try:
        json_data = json.loads(dados_extraidos)
        st.subheader("✅ Dados estruturados (JSON válido)")
        st.json(json_data)
    except json.JSONDecodeError:
        st.error("❌ A resposta do GPT não está em formato JSON válido.")

    nova_fatura = {
        "id": len(st.session_state.faturas_processadas) + 1,
        "dados": dados_extraidos,
        "status": "pendente"
    }
    st.session_state.faturas_processadas.append(nova_fatura)
    st.session_state.fatura_atual = nova_fatura

    mensagem_aprovacao = f"\U0001F4C4 *Fatura #{nova_fatura['id']} recebida para conferência*\n{dados_extraidos}"
    enviar_telegram(CHAT_APROVACAO, mensagem_aprovacao)
    st.success(f"Fatura #{nova_fatura['id']} enviada para análise de conformidade (Telegram).")

# Botões de interação direta no chatbot
st.markdown("---")
st.subheader("🔢 Simulação de operações financeiras")

fatura = st.session_state.get("fatura_atual")
if fatura:
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Aprovar conformidade da fatura", key="aprovar_btn"):
            fatura = {**fatura, "status": "conferida"}
            st.session_state.fatura_atual = fatura
            st.success(f"Fatura #{fatura['id']} aprovada quanto à conformidade.")
            mensagem_pagamento = f"\U0001F4B8 *Fatura #{fatura['id']} aprovada e enviada para autorização de pagamento*\n{fatura['dados']}"
            enviar_telegram(CHAT_PAGAMENTO, mensagem_pagamento)

        if st.button("❌ Recusar conformidade", key="recusar_conformidade"):
            fatura = {**fatura, "status": "recusada_conformidade"}
            st.session_state.fatura_atual = fatura
            st.error(f"Fatura #{fatura['id']} foi recusada na etapa de conferência.")

    with col2:
        if st.button("💳 Simular pagamento", key="pagar_btn"):
            if fatura.get("status") != "conferida":
                st.warning("❌ A fatura precisa ser conferida/aprovada antes do pagamento.")
            else:
                fatura = {**fatura, "status": "paga"}
                st.session_state.fatura_atual = fatura
                st.success(f"✅ Pagamento da Fatura #{fatura['id']} realizado com sucesso (simulado).")

        if st.button("🚫 Recusar pagamento", key="recusar_pagamento"):
            if fatura.get("status") != "conferida":
                st.warning("❌ A fatura precisa estar aprovada para ser recusada na etapa de pagamento.")
            else:
                fatura = {**fatura, "status": "recusada_pagamento"}
                st.session_state.fatura_atual = fatura
                st.error(f"Fatura #{fatura['id']} foi recusada na etapa de pagamento.")
