# app.py - Interface principal via Streamlit
import streamlit as st
import requests
import openai
import os
from dotenv import load_dotenv

load_dotenv()

# Variáveis de ambiente
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_APROVACAO = os.getenv("TELEGRAM_CHAT_APROVACAO")
CHAT_PAGAMENTO = os.getenv("TELEGRAM_CHAT_PAGAMENTO")

# Simulação de banco de dados
faturas_processadas = []

# Funções principais
def extrair_dados_com_gpt(file_bytes):
    conteudo_simples = file_bytes.decode("latin1", errors="ignore")[:3000]  # Limitação do prompt
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Você é um extrator de dados financeiros."},
            {"role": "user", "content": f"""Extraia do documento:
            - Tipo de documento
            - Nome do fornecedor
            - Valor total
            - Data de emissão
            - Vencimento
            - Forma de pagamento
            - Categoria

            Texto:
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

uploaded = st.file_uploader("Envie a nota fiscal, boleto ou fatura (PDF ou texto)")

if uploaded:
    bytes_data = uploaded.read()
    dados_extraidos = extrair_dados_com_gpt(bytes_data)
    st.subheader("🔍 Dados extraídos do documento")
    st.json(dados_extraidos)

    id_fatura = len(faturas_processadas) + 1
    fatura = {"id": id_fatura, "dados": dados_extraidos, "status": "pendente"}
    faturas_processadas.append(fatura)

    mensagem_aprovacao = f"\U0001F4C4 *Fatura #{id_fatura} recebida para conferência*\n{dados_extraidos}"
    enviar_telegram(CHAT_APROVACAO, mensagem_aprovacao)
    st.success(f"Fatura #{id_fatura} enviada para análise de conformidade (Telegram).")

    # Botões de interação direta no chatbot
    st.markdown("---")
    st.subheader("🔢 Simulação de operações financeiras")

    if st.button("✅ Aprovar conformidade da fatura"):
        fatura["status"] = "conferida"
        st.success(f"Fatura #{id_fatura} aprovada quanto à conformidade.")

        mensagem_pagamento = f"\U0001F4B8 *Fatura #{id_fatura} aprovada e enviada para autorização de pagamento*\n{dados_extraidos}"
        enviar_telegram(CHAT_PAGAMENTO, mensagem_pagamento)
        st.info("Fatura enviada para o financeiro (Telegram).")

    if st.button("💸 Simular pagamento"):
        if fatura["status"] != "conferida":
            st.warning("❌ A fatura precisa ser conferida/aprovada antes do pagamento.")
        else:
            fatura["status"] = "paga"
            st.success(f"✅ Pagamento da Fatura #{id_fatura} realizado com sucesso (simulado).")
