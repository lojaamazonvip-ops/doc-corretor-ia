import streamlit as st
import base64
import requests
import img2pdf
import os
import json
import time
import smtplib
import tempfile
import zipfile
import io
import secrets
from datetime import datetime, timedelta, timezone, date
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from PyPDF2 import PdfMerger

# ══════════════════════════════════════════════════════
# SUPABASE
# ══════════════════════════════════════════════════════

SUPABASE_URL    = "https://ryvgqesflxbtqbdhspdy.supabase.co"
SUPABASE_KEY    = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJ5dmdxZXNmbHhidHFiZGhzcGR5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIyOTIyMjMsImV4cCI6MjA4Nzg2ODIyM30.HhW3_bSQ8fZvY17XTwerhXdW7hF2uf3gKUSYm9ixkys"
SB_HEADERS      = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
EMAIL_REMETENTE = "daniellaandrade1989@gmail.com"
EMAIL_SENHA_APP = "fpupijekoocowhcl"
APP_URL_CLIENTE = "https://doc-corretor-ia.streamlit.app"

def buscar_cliente(login, senha):
    url = f"{SUPABASE_URL}/rest/v1/clientes?login=eq.{login}&select=*"
    r   = requests.get(url, headers=SB_HEADERS)
    if r.status_code != 200: return None
    dados = r.json()
    if not dados: return None
    cliente = dados[0]
    if cliente.get("senha","").strip() == senha.strip(): return cliente
    return None

def buscar_cliente_por_email(email):
    url = f"{SUPABASE_URL}/rest/v1/clientes?email=eq.{email}&select=*"
    r   = requests.get(url, headers=SB_HEADERS)
    dados = r.json()
    return dados[0] if dados else None

def registrar_acesso(cliente):
    url = f"{SUPABASE_URL}/rest/v1/acessos"
    requests.post(url, headers={**SB_HEADERS,"Content-Type":"application/json"},
                  json={"cliente_id":cliente["id"],"cliente_nome":cliente["nome"],
                        "cliente_login":cliente["login"]})

def registrar_uso(cliente, qtd_arquivos=0, email_enviado=False):
    url = f"{SUPABASE_URL}/rest/v1/usos"
    requests.post(url, headers={**SB_HEADERS,"Content-Type":"application/json"},
                  json={"cliente_id":cliente["id"],"cliente_nome":cliente["nome"],
                        "cliente_login":cliente["login"],"qtd_arquivos":qtd_arquivos,
                        "email_enviado":email_enviado})

def criar_token_cliente(cliente_id):
    token  = secrets.token_urlsafe(32)
    expira = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    url    = f"{SUPABASE_URL}/rest/v1/tokens_recuperacao"
    requests.post(url, headers={**SB_HEADERS,"Content-Type":"application/json"},
                  json={"tipo":"cliente","referencia":cliente_id,
                        "token":token,"usado":False,"expira_em":expira})
    return token

def validar_token_cliente(token):
    url = f"{SUPABASE_URL}/rest/v1/tokens_recuperacao?token=eq.{token}&usado=eq.false&select=*"
    r   = requests.get(url, headers=SB_HEADERS)
    if r.status_code != 200: return None
    dados = r.json()
    if not dados: return None
    rec    = dados[0]
    expira = datetime.fromisoformat(rec["expira_em"])
    if expira.tzinfo is None: expira = expira.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expira: return None
    return rec

def marcar_token_cliente_usado(token_id):
    url = f"{SUPABASE_URL}/rest/v1/tokens_recuperacao?id=eq.{token_id}"
    requests.patch(url, headers={**SB_HEADERS,"Content-Type":"application/json"},
                   json={"usado":True})

def alterar_senha_cliente(cliente_id, nova_senha):
    url = f"{SUPABASE_URL}/rest/v1/clientes?id=eq.{cliente_id}"
    requests.patch(url, headers={**SB_HEADERS,"Content-Type":"application/json"},
                   json={"senha":nova_senha})

def enviar_link_recuperacao(email_destino, token):
    link = f"{APP_URL_CLIENTE}?token={token}"
    html = f"""
    <h2>DocCorretor IA — Recuperação de Senha</h2>
    <p>Clique no link abaixo para redefinir sua senha.<br>
    O link expira em <strong>30 minutos</strong>.</p>
    <a href="{link}" style="background:#1976d2;color:#fff;padding:12px 24px;
    border-radius:6px;text-decoration:none;font-size:16px;">🔑 Redefinir Senha</a>
    <p style="color:#888;font-size:12px;">Se não solicitou, ignore este email.</p>
    """
    msg = MIMEMultipart("alternative")
    msg["From"]    = EMAIL_REMETENTE
    msg["To"]      = email_destino
    msg["Subject"] = "DocCorretor IA — Recuperação de Senha"
    msg.attach(MIMEText(html,"html","utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com",465) as s:
        s.login(EMAIL_REMETENTE, EMAIL_SENHA_APP)
        s.sendmail(EMAIL_REMETENTE, email_destino, msg.as_bytes())

SESSAO_CLIENTE_TOKEN = "sessao_cliente_ativa_2025"

def check_login():
    params    = st.query_params
    token_url = params.get("token","")
    sessao    = params.get("s","")

    if sessao == SESSAO_CLIENTE_TOKEN and not st.session_state.get("autenticado"):
        login_salvo = params.get("u","")
        if login_salvo:
            url = f"{SUPABASE_URL}/rest/v1/clientes?login=eq.{login_salvo}&select=*"
            r   = requests.get(url, headers=SB_HEADERS)
            if r.status_code == 200 and r.json():
                cliente = r.json()[0]
                if cliente.get("ativo") and date.fromisoformat(cliente["data_vencimento"]) >= date.today():
                    st.session_state["autenticado"] = True
                    st.session_state["cliente"]     = cliente

    if token_url and not st.session_state.get("autenticado"):
        st.set_page_config(page_title="DocCorretor IA", page_icon="📁", layout="centered")
        st.markdown("<style>section[data-testid='stMain'] > div{max-width:420px;margin:70px auto;}</style>",
                    unsafe_allow_html=True)
        st.markdown("## 🗂️ DocCorretor IA")
        st.markdown("#### Redefinir senha")
        st.divider()
        rec = validar_token_cliente(token_url)
        if not rec or rec.get("tipo") != "cliente":
            st.error("❌ Link inválido ou expirado.")
            st.stop()
        nova1 = st.text_input("Nova senha", type="password")
        nova2 = st.text_input("Confirme a nova senha", type="password")
        if st.button("✅ Salvar nova senha", use_container_width=True, type="primary"):
            if not nova1 or len(nova1) < 6: st.error("Senha deve ter pelo menos 6 caracteres.")
            elif nova1 != nova2: st.error("As senhas não coincidem.")
            else:
                alterar_senha_cliente(rec["referencia"], nova1)
                marcar_token_cliente_usado(rec["id"])
                st.success("✅ Senha redefinida! Faça login normalmente.")
                st.query_params.clear()
        st.stop()

    if not st.session_state.get("autenticado", False):
        st.set_page_config(page_title="DocCorretor IA", page_icon="📁", layout="centered")
        st.markdown("<style>section[data-testid='stMain'] > div{max-width:420px;margin:70px auto;}</style>",
                    unsafe_allow_html=True)
        st.markdown("## 🗂️ DocCorretor IA")
        st.caption("Sistema de organização de documentos para financiamento")
        st.divider()
        tela = st.radio("", ["🔑 Entrar","🔓 Esqueci minha senha"], horizontal=True, label_visibility="collapsed")

        if tela == "🔑 Entrar":
            login = st.text_input("👤 Login")
            senha = st.text_input("🔑 Senha", type="password")
            if st.button("Entrar", use_container_width=True, type="primary"):
                cliente = buscar_cliente(login.strip(), senha.strip())
                if not cliente: st.error("Login ou senha incorretos.")
                elif not cliente.get("ativo"): st.error("❌ Acesso bloqueado. Entre em contato com o suporte.")
                elif date.fromisoformat(cliente["data_vencimento"]) < date.today():
                    st.error("❌ Sua assinatura venceu. Entre em contato para renovar.")
                else:
                    st.session_state["autenticado"] = True
                    st.session_state["cliente"]     = cliente
                    st.query_params["s"] = SESSAO_CLIENTE_TOKEN
                    st.query_params["u"] = cliente["login"]
                    registrar_acesso(cliente)
                    st.rerun()
        else:
            st.info("Digite o email cadastrado na sua conta.")
            email_rec = st.text_input("📧 Email cadastrado")
            if st.button("📧 Enviar link de recuperação", use_container_width=True, type="primary"):
                cliente = buscar_cliente_por_email(email_rec.strip())
                if not cliente: st.error("Email não encontrado.")
                else:
                    try:
                        token = criar_token_cliente(cliente["id"])
                        enviar_link_recuperacao(email_rec.strip(), token)
                        st.success(f"✅ Link enviado para {email_rec}! Expira em 30 minutos.")
                    except Exception as e:
                        st.error(f"❌ Erro ao enviar email: {e}")
        st.stop()

check_login()

# ══════════════════════════════════════════════════════
# CONFIGURAÇÃO DA PÁGINA
# ══════════════════════════════════════════════════════

st.set_page_config(page_title="DocCorretor IA", page_icon="📁", layout="centered")

st.markdown("""
<style>
    .main { max-width: 750px; }
    .stTextArea textarea { font-size: 14px; }
    .stButton>button { width: 100%; }
    .checklist-ok    { color: #2e7d32; font-weight: bold; }
    .checklist-falta { color: #c62828; font-weight: bold; }
    .checklist-aviso { color: #e65100; font-weight: bold; }
    #MainMenu{visibility:hidden!important;display:none!important;}
    header{visibility:hidden!important;display:none!important;}
    footer{visibility:hidden!important;display:none!important;}
    [data-testid="stToolbar"]{display:none!important;}
    [data-testid="stDecoration"]{display:none!important;}
    .stDeployButton{display:none!important;}
    a[href*="streamlit.io"]{display:none!important;}
</style>
""", unsafe_allow_html=True)

import streamlit.components.v1 as components
components.html("""
<script>
function hideMenu(){
    const doc=window.parent.document;
    ['header','#MainMenu','footer','[data-testid="stToolbar"]',
     '[data-testid="stDecoration"]','.stDeployButton'].forEach(s=>{
        doc.querySelectorAll(s).forEach(el=>{
            el.style.setProperty('display','none','important');
        });
    });
    doc.querySelectorAll('a[href*="streamlit"]').forEach(el=>{
        el.style.setProperty('display','none','important');
    });
}
hideMenu();
new MutationObserver(hideMenu).observe(window.parent.document.body,{childList:true,subtree:true});
</script>
""", height=0)

# ══════════════════════════════════════════════════════
# CHAVES API
# ══════════════════════════════════════════════════════

API_KEYS = [k.strip() for k in st.secrets.get("GEMINI_KEYS","").split(",") if k.strip()]
if not API_KEYS:
    st.error("⚠️ Chaves Gemini não configuradas. Vá em Settings → Secrets e adicione GEMINI_KEYS.")
    st.stop()

# ══════════════════════════════════════════════════════
# BANCO DE DADOS DE DOCUMENTOS
# ══════════════════════════════════════════════════════

BANCO_DOCUMENTOS = [
    "RG","CPF","CNH","Passaporte","Certidao_Nascimento","Certidao_Casamento",
    "Certidao_Divorcio","Certidao_Obito","Certidao_Uniao_Estavel",
    "Comprovante_Residencia","Holerite","Contracheque","Decore",
    "Extrato_Bancario","Extrato_FGTS","Imposto_de_Renda","Recibo_Autonomo",
    "Pro_Labore","Contrato_Social","CNPJ","Cartao_CNPJ","Balanco_Patrimonial",
    "DRE","Certidao_Negativa_Debitos_Federais","Certidao_Negativa_Estadual",
    "Certidao_Negativa_Municipal","Certidao_Negativa_Receita_Federal",
    "Certidao_Negativa_INSS","Certidao_Negativa_FGTS","Certidao_Negativa_Trabalhista",
    "Certidao_Negativa_Protesto","Certidao_Acoes_Civeis","Certidao_Acoes_Criminais",
    "Certidao_Distribuicao","SPC","Serasa","Consulta_SCR_Bacen",
    "Escritura_Imovel","Matricula_Imovel","Certidao_Inteiro_Teor",
    "Certidao_Onus_Reais","Certidao_Acoes_Reais","Certidao_Vintenaria",
    "Certidao_Quitacao_IPTU","Carne_IPTU","Certidao_Quitacao_Condominio",
    "Declaracao_Quitacao_Condominial","Habite_se","Alvara_Construcao",
    "Projeto_Arquitetonico_Aprovado","Memorial_Descritivo","ART","RRT",
    "CREA","CAU","Planta_Imovel","Levantamento_Topografico",
    "Laudo_Avaliacao","Laudo_Vistoria","Laudo_Avaliacao_Caixa","PTAM",
    "Contrato_Compra_Venda","Promessa_Compra_Venda",
    "Instrumento_Particular_Compra_Venda","Escritura_Publica_Compra_Venda",
    "Contrato_Financiamento","Contrato_Locacao","Contrato_Comodato",
    "Contrato_Permuta","Contrato_Doacao","Distrato","Aditivo_Contratual",
    "Procuracao_Publica","Procuracao_Particular","Substabelecimento",
    "Declaracao_Estado_Civil","Declaracao_Residencia","Declaracao_Renda",
    "Declaracao_Nao_Proprietario","Declaracao_Primeiro_Imovel",
    "Declaracao_Dependentes","Autorizacao_Debito_Conta","Ficha_Cadastral",
    "Ficha_Visita","Proposta_Locacao","Proposta_Compra",
    "Contrato_Intermediacao_Imobiliaria","Autorizacao_Venda","Autorizacao_Locacao",
    "Laudo_Entrega_Chaves","Laudo_Devolucao_Chaves","Termo_Vistoria_Entrada",
    "Termo_Vistoria_Saida","Termo_Entrega_Chaves","Recibo_Sinal","Recibo_Aluguel",
    "Boleto_Aluguel","Seguro_Fianca","Seguro_Incendio","Apolice_Seguro",
    "Carta_Fianca_Bancaria","Termo_Caucao","Comprovante_Caucao","NIS_CadUnico",
    "BIZ","NIT","PIS","PASEP","Carteira_de_Trabalho","Extrato_PIS",
    "Simulacao_Habitacional","Carta_Credito","Carta_Aprovacao_Credito",
    "Carta_Credito_FGTS","Extrato_Analitico_FGTS","Autorizacao_Uso_FGTS",
    "Termo_Quitacao_Financiamento","CND_Imovel","RIP","SPU",
    "Certidao_Aforamento","Certidao_Marinha","Laudemio",
    "Certidao_Regularizacao_Fundiaria","REURB","Contrato_Alienacao_Fiduciaria",
    "Termo_Quitacao_Alienacao_Fiduciaria","Boletim_Ocorrencia","Inventario",
    "Formal_Partilha","Alvara_Judicial","Termo_Tutela","Termo_Curatela",
    "Certidao_Interdicao","RG_Menor","Autorizacao_Pais_Menor",
    "Certidao_Regularidade_CREA","Certidao_Regularidade_CRECI",
    "Registro_CRECI","ATO_CRECI","Documento_Nao_Identificado",
]
DOCUMENTOS_COM_FRENTE_VERSO = [
    "RG","CNH","CPF","Carteira_de_Trabalho","Extrato_FGTS","PIS","PASEP",
    "NIS_CadUnico","BIZ","Cartao_CNPJ","CREA","CAU","Passaporte",
    "Cartao_SUS","Cartao_Beneficio_INSS","Cartao_Cidadao",
]
BANCO_STR        = ", ".join(BANCO_DOCUMENTOS)
FRENTE_VERSO_STR = ", ".join(DOCUMENTOS_COM_FRENTE_VERSO)


# ══════════════════════════════════════════════════════
# BLOCO 1 — API GEMINI
# ══════════════════════════════════════════════════════

def e_limite_esgotado(m):
    m = m.lower()
    return any(f in m for f in ["free tier","daily limit","quota exceeded",
        "exceeded your current quota","resource_exhausted","per day"])

def buscar_modelo(key):
    try:
        r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={key}").json()
        for m in r.get('models',[]):
            if "generateContent" in m['supportedGenerationMethods'] and "flash" in m['name']:
                return m['name']
    except: pass
    return "models/gemini-1.5-flash"

def chamar_gemini(lista_parts):
    key_index = 0
    for tentativa in range(len(API_KEYS)*3):
        if key_index >= len(API_KEYS):
            raise Exception("❌ Todas as chaves esgotadas.")
        key    = API_KEYS[key_index]
        modelo = buscar_modelo(key)
        url    = f"https://generativelanguage.googleapis.com/v1beta/{modelo}:generateContent?key={key}"
        payload = {
            "contents": [{"parts": lista_parts}],
            "safetySettings": [
                {"category":"HARM_CATEGORY_HARASSMENT",       "threshold":"BLOCK_NONE"},
                {"category":"HARM_CATEGORY_HATE_SPEECH",      "threshold":"BLOCK_NONE"},
                {"category":"HARM_CATEGORY_SEXUALLY_EXPLICIT","threshold":"BLOCK_NONE"},
                {"category":"HARM_CATEGORY_DANGEROUS_CONTENT","threshold":"BLOCK_NONE"},
            ]
        }
        rjson = requests.post(url, json=payload).json()
        if 'error' in rjson:
            codigo = rjson['error'].get('code',0)
            msg    = rjson['error'].get('message','')
            if codigo == 429:
                if e_limite_esgotado(msg): key_index += 1
                else: time.sleep(35)
            else: raise ValueError(f"Erro [{codigo}]: {msg}")
            continue
        if 'candidates' not in rjson: raise ValueError("Resposta inesperada")
        return rjson['candidates'][0]['content']['parts'][0]['text']
    raise ValueError("❌ Todas as tentativas falharam.")


# ══════════════════════════════════════════════════════
# BLOCO 2 — PROCESSAMENTO DE DOCUMENTOS
# ══════════════════════════════════════════════════════

def processar_documentos(arquivos_bytes):
    pdfs_finais = []
    tmp = tempfile.mkdtemp()

    imgs = [(n,c) for n,c,t in arquivos_bytes if t=="imagem"]
    pdfs = [(n,c) for n,c,t in arquivos_bytes if t=="pdf"]

    if pdfs:
        prompt = f"""
Especialista em documentos imobiliários brasileiros.
⚠️ REGRAS: Leia completamente. NUNCA duplique. Cada arquivo em EXATAMENTE UM grupo. Use ID_ARQUIVO exato.
📋 BANCO: {BANCO_STR}
🔄 VERIFIQUE FRENTE/VERSO E UNA: {FRENTE_VERSO_STR}
NOMENCLATURA: TipoDocumento_NomeCompleto_Detalhe
Ex: RG_Maria_Silva | Extrato_Bancario_Nubank_Jan2026
Frente+Verso=mesmo grupo | Holerites meses diferentes=separados | RG e CPF=sempre separados
RETORNE JSON: {{"grupos":[{{"pdf_final":"Nome","arquivos":["arq.pdf"],"observacao":"motivo"}}]}}
"""
        try:
            parts = [{"text": prompt}]
            for nome, conteudo in pdfs:
                b64 = base64.b64encode(conteudo).decode('utf-8')
                parts += [{"text":f"ID_ARQUIVO: {nome}"},
                          {"inline_data":{"mime_type":"application/pdf","data":b64}}]
            resp  = chamar_gemini(parts)
            dados = json.loads(resp.replace('```json','').replace('```','').strip())
            vistos = {}
            for g in dados['grupos']:
                limpo = []
                for arq in g['arquivos']:
                    if arq not in vistos: vistos[arq]=g['pdf_final']; limpo.append(arq)
                g['arquivos'] = limpo
            nomes_pdf = {n: c for n,c in pdfs}
            for g in dados['grupos']:
                nome_final = f"{g['pdf_final']}.pdf"
                grupo_arqs = [n for n in g['arquivos'] if n in nomes_pdf]
                if not grupo_arqs: continue
                if len(grupo_arqs) == 1:
                    pdfs_finais.append((nome_final, nomes_pdf[grupo_arqs[0]]))
                else:
                    saida = os.path.join(tmp, nome_final)
                    merger = PdfMerger()
                    for n in grupo_arqs:
                        p = os.path.join(tmp, n)
                        with open(p,"wb") as f: f.write(nomes_pdf[n])
                        merger.append(p)
                    merger.write(saida); merger.close()
                    with open(saida,"rb") as f: pdfs_finais.append((nome_final, f.read()))
        except Exception as e:
            st.warning(f"Erro ao agrupar PDFs: {e}")

    if imgs:
        parts = []
        for nome, conteudo in imgs:
            b64 = base64.b64encode(conteudo).decode('utf-8')
            parts += [{"inline_data":{"mime_type":"image/jpeg","data":b64}},
                      {"text":f"ID_ARQUIVO: {nome}"}]
        prompt_img = f"""
Especialista em documentos imobiliários. MÁXIMA PRECISÃO.
⚠️ NUNCA duplique. Cada imagem em EXATAMENTE UM grupo. Use ID_ARQUIVO exato.
📋 BANCO: {BANCO_STR}
🔄 FRENTE/VERSO — AGRUPE: {FRENTE_VERSO_STR}
NOMENCLATURA: TipoDocumento_NomeCompleto_Detalhe
RETORNE JSON: {{"grupos":[{{"pdf":"Nome","arquivos":["arq.jpg"]}}]}}
"""
        try:
            resp  = chamar_gemini([{"text":prompt_img}]+parts)
            dados = json.loads(resp.replace('```json','').replace('```','').strip())
            vistos = {}
            for g in dados['grupos']:
                limpo = []
                for arq in g['arquivos']:
                    if arq not in vistos: vistos[arq]=g['pdf']; limpo.append(arq)
                g['arquivos'] = limpo
            nomes_img = {n: c for n,c in imgs}
            for g in dados['grupos']:
                nome_pdf   = f"{g['pdf']}.pdf"
                arqs_grupo = [n for n in g['arquivos'] if n in nomes_img]
                if not arqs_grupo: continue
                caminhos_tmp = []
                for n in arqs_grupo:
                    p = os.path.join(tmp, n)
                    with open(p,"wb") as f: f.write(nomes_img[n])
                    caminhos_tmp.append(p)
                pdf_bytes = img2pdf.convert(caminhos_tmp)
                pdfs_finais.append((nome_pdf, pdf_bytes))
        except Exception as e:
            st.warning(f"Erro ao processar imagens: {e}")

    return pdfs_finais


# ══════════════════════════════════════════════════════
# BLOCO 3 — EXTRAÇÃO DE DADOS DE CONTATO (WHITELIST)
# ══════════════════════════════════════════════════════

# ⚠️ WHITELIST ESTRITA — apenas estes 4 campos são permitidos na extração.
# Qualquer outro dado encontrado será descartado automaticamente.
CAMPOS_CONTATO_PERMITIDOS = {"nome_completo", "pis_nis_nit", "telefone", "email"}

def extrair_dados(texto_bruto, arquivos_bytes, pdfs_gerados):
    """
    Extrai SOMENTE: nome_completo, pis_nis_nit, telefone, email.
    Whitelist estrita — nenhum outro campo é retornado.
    """
    prompt = f"""
Você é um extrator de dados de documentos imobiliários brasileiros.

⚠️ WHITELIST ESTRITA — extraia SOMENTE estes 4 campos:
1. nome_completo — nome completo do(s) participante(s)
2. pis_nis_nit   — número PIS, NIS ou NIT
3. telefone      — com DDD formatado: (00) 9 0000-0000
4. email         — endereço de email

🚫 PROIBIDO: CPF, RG, endereço, renda, banco, valor imóvel, estado civil, etc.
🚫 Qualquer outro dado encontrado deve ser IGNORADO.

FONTES:
- TEXTO: {texto_bruto}
- DOCUMENTOS: analisados abaixo

RETORNE APENAS JSON:
{{
  "nome_completo": "",
  "pis_nis_nit": "",
  "telefone": "",
  "email": ""
}}
"""
    parts = [{"text": prompt}]
    for nome, conteudo, tipo in arquivos_bytes:
        b64  = base64.b64encode(conteudo).decode('utf-8')
        mime = "application/pdf" if tipo=="pdf" else "image/jpeg"
        parts += [{"text":f"DOCUMENTO: {nome}"},{"inline_data":{"mime_type":mime,"data":b64}}]
    for nome, conteudo in pdfs_gerados:
        b64 = base64.b64encode(conteudo).decode('utf-8')
        parts += [{"text":f"DOCUMENTO: {nome}"},{"inline_data":{"mime_type":"application/pdf","data":b64}}]
    try:
        resp  = chamar_gemini(parts)
        dados = json.loads(resp.replace('```json','').replace('```','').strip())
        return validar_dados_contato(dados)
    except:
        return {k: "" for k in CAMPOS_CONTATO_PERMITIDOS}

def validar_dados_contato(dados_brutos):
    """
    ⚠️ Remove qualquer campo fora da whitelist de contato.
    Garante que SOMENTE os 4 campos autorizados cheguem ao texto.
    """
    return {campo: dados_brutos.get(campo, "") for campo in CAMPOS_CONTATO_PERMITIDOS}


# ══════════════════════════════════════════════════════
# BLOCO 4 — EXTRAÇÃO DA SIMULAÇÃO (WHITELIST)
# ══════════════════════════════════════════════════════

# ⚠️ WHITELIST ESTRITA — apenas estes campos podem entrar no texto automático.
CAMPOS_SIMULACAO_PERMITIDOS = {
    "tipo_imovel", "valor_imovel", "dependentes",
    "multiplos_participantes", "participantes"
}

def extrair_dados_simulacao(texto_bruto, arquivos_bytes, pdfs_gerados):
    """
    Extrai SOMENTE os campos da simulação para geração do texto.
    Qualquer campo fora da whitelist é bloqueado antes do texto.
    """
    prompt = f"""
Especialista em simulações de financiamento habitacional Caixa Econômica Federal.

⚠️ WHITELIST ESTRITA — extraia SOMENTE:
1. tipo_imovel             — "novo" ou "usado"
2. valor_imovel            — ex: R$ 205.000,00
3. dependentes             — número inteiro (0 se nenhum)
4. multiplos_participantes — true ou false
5. participantes           — lista com:
   - nome        (nome completo)
   - fgts_3anos  (true = trabalhou +3 anos carteira FGTS)
   - renda_valor (ex: R$ 2.550,00)
   - renda_tipo  ("formal" ou "informal")

🚫 PROIBIDO: CPF, RG, email, telefone, NIT, endereço, banco, estado civil, etc.

FONTES:
- TEXTO: {texto_bruto}
- DOCUMENTOS: analisados abaixo

RETORNE APENAS JSON:
{{
  "tipo_imovel": "",
  "valor_imovel": "",
  "dependentes": 0,
  "multiplos_participantes": false,
  "participantes": [{{"nome":"","fgts_3anos":false,"renda_valor":"","renda_tipo":""}}]
}}
"""
    parts = [{"text": prompt}]
    for nome, conteudo, tipo in arquivos_bytes:
        b64  = base64.b64encode(conteudo).decode('utf-8')
        mime = "application/pdf" if tipo=="pdf" else "image/jpeg"
        parts += [{"text":f"DOCUMENTO: {nome}"},{"inline_data":{"mime_type":mime,"data":b64}}]
    for nome, conteudo in pdfs_gerados:
        b64 = base64.b64encode(conteudo).decode('utf-8')
        parts += [{"text":f"DOCUMENTO: {nome}"},{"inline_data":{"mime_type":"application/pdf","data":b64}}]
    try:
        resp  = chamar_gemini(parts)
        dados = json.loads(resp.replace('```json','').replace('```','').strip())
        return validar_dados_simulacao(dados)
    except:
        return None

def validar_dados_simulacao(dados_brutos):
    """
    ⚠️ Remove qualquer campo fora da whitelist da simulação.
    Aplica whitelist também dentro de cada participante.
    """
    participantes_brutos = dados_brutos.get("participantes", [])
    participantes_limpos = [
        {
            "nome"       : p.get("nome",""),
            "fgts_3anos" : p.get("fgts_3anos", False),
            "renda_valor": p.get("renda_valor",""),
            "renda_tipo" : p.get("renda_tipo",""),
        }
        for p in participantes_brutos
    ]
    return {
        "tipo_imovel"           : dados_brutos.get("tipo_imovel",""),
        "valor_imovel"          : dados_brutos.get("valor_imovel",""),
        "dependentes"           : dados_brutos.get("dependentes", 0),
        "multiplos_participantes": dados_brutos.get("multiplos_participantes", False),
        "participantes"         : participantes_limpos,
    }


# ══════════════════════════════════════════════════════
# BLOCO 5 — GERAÇÃO DO TEXTO AUTOMÁTICO
# ══════════════════════════════════════════════════════

def saudacao_por_horario():
    """Saudação automática baseada no horário de Brasília."""
    hora = datetime.now(timezone(timedelta(hours=-3))).hour
    if 6 <= hora < 12:  return "Bom dia"
    if 12 <= hora < 18: return "Boa tarde"
    return "Boa noite"

def gerar_texto_automatico(dados_simulacao, dados_contato, nome_destinatario,
                            nome_corretor, creci):
    """
    Gera o texto usando SOMENTE os campos das whitelists.
    Nenhuma informação fora do permitido chega ao prompt.
    """
    if not dados_simulacao:
        return "Não foi possível extrair os dados da simulação. Verifique os documentos enviados."

    saudacao      = saudacao_por_horario()
    destinat      = f", {nome_destinatario}" if nome_destinatario else ""
    tipo_imovel   = dados_simulacao.get("tipo_imovel","")
    valor_imovel  = dados_simulacao.get("valor_imovel","")
    dependentes   = int(dados_simulacao.get("dependentes") or 0)
    multiplos     = dados_simulacao.get("multiplos_participantes", False)
    participantes = dados_simulacao.get("participantes", [])

    # Nome do titular para o assunto e título
    titular       = participantes[0]["nome"] if participantes else "cliente"
    primeiro_nome = titular.split()[0] if titular else "cliente"

    # Monta bloco de participantes — SOMENTE campos whitelist
    linhas_part = []
    for i, p in enumerate(participantes):
        prefixo  = f"Participante {i+1}: " if multiplos else ""
        fgts_txt = "Trabalhou mais de 3 anos com carteira assinada (FGTS: sim)" \
                   if p.get("fgts_3anos") else "Nunca trabalhou de carteira assinada (FGTS: não)"
        dep_txt  = f"Possui {dependentes} dependente(s)" if (i == 0 and dependentes > 0) else \
                   ("Sem dependentes" if i == 0 else "")
        linha = f"• {prefixo}{p.get('nome','')}\n"
        linha += f"  - Renda: {p.get('renda_valor','')} ({p.get('renda_tipo','')})\n"
        linha += f"  - {fgts_txt}\n"
        if dep_txt: linha += f"  - {dep_txt}\n"
        linhas_part.append(linha)
    bloco_participantes = "\n".join(linhas_part)

    # Monta bloco de contato — SOMENTE campos whitelist
    linhas_contato = []
    if dados_contato.get("email"):
        linhas_contato.append(f"• 📧 E-mail: {dados_contato['email']}")
    if dados_contato.get("telefone"):
        linhas_contato.append(f"• 📱 Telefone: {dados_contato['telefone']}")
    if dados_contato.get("pis_nis_nit"):
        linhas_contato.append(f"• 🪪 PIS/NIS/NIT: {dados_contato['pis_nis_nit']}")
    bloco_contato = "\n".join(linhas_contato)

    # Assinatura do corretor
    assinatura = f"Att,\n{nome_corretor}"
    if creci: assinatura += f" — CRECI {creci}"

    ctx_imovel = ""
    if tipo_imovel and valor_imovel:
        ctx_imovel = f" de imóvel {tipo_imovel} no valor de {valor_imovel}"
    elif valor_imovel:
        ctx_imovel = f" no valor de {valor_imovel}"

    assunto = f"Documentação {primeiro_nome}"
    if tipo_imovel: assunto += f" — Imóvel {tipo_imovel.capitalize()}"
    if valor_imovel: assunto += f" {valor_imovel}"

    corpo = f"""{saudacao}{destinat}.

Conforme simulação realizada, segue documentação da cliente {primeiro_nome} para aprovação de financiamento{ctx_imovel}.

{"**Participantes:**" if multiplos else "**Informações da cliente:**"}

{bloco_participantes}"""

    if bloco_contato:
        corpo += f"\n**Dados de contato:**\n{bloco_contato}\n"

    corpo += f"""
Solicito, por gentileza, aprovação conforme simulação encaminhada.

Fico no aguardo do retorno.

{assinatura}"""

    return f"Assunto: {assunto}\n\n{corpo.strip()}"


# ══════════════════════════════════════════════════════
# BLOCO 6 — CHECKLIST
# ══════════════════════════════════════════════════════

def calcular_checklist(nomes_pdfs):
    docs  = set(n.replace('.pdf','').lower() for n in nomes_pdfs)
    tem_h = any('holerite' in d for d in docs)
    tem_e = any('extrato'  in d for d in docs)
    tipo  = "FORMAL" if tem_h else ("INFORMAL" if tem_e else "NÃO IDENTIFICADA")
    obrig = {
        "CPF"                      : ["cpf"],
        "RG ou CNH"                : ["rg","cnh"],
        "Certidão de Estado Civil" : ["certidao_nascimento","certidao_casamento"],
        "Comprovante de Residência": ["comprovante_residencia"],
        "Carteira de Trabalho"     : ["carteira_de_trabalho"],
        "NIS / BIZ / NIT"          : ["nis_cadunico","biz","nit","pis","pasep"],
    }
    if tipo=="FORMAL":     obrig["3 Últimos Holerites"]          = ["holerite"]
    elif tipo=="INFORMAL": obrig["3 Últimos Extratos Bancários"] = ["extrato_bancario","extrato"]
    else:                  obrig["Comprovante de Renda"]         = ["holerite","extrato"]
    obrig["Simulação Habitacional"] = ["simulacao_habitacional"]
    ok=[]; faltando=[]
    for nome, chaves in obrig.items():
        enc = any(any(c in d for d in docs) for c in chaves)
        if nome in ("3 Últimos Holerites","3 Últimos Extratos Bancários"):
            c=chaves[0]; qtd=sum(1 for d in docs if c in d)
            if qtd>=3:  ok.append(f"✅ {nome} ({qtd})")
            elif qtd>0: faltando.append(f"⚠️ {nome} — faltam {3-qtd} ({qtd} encontrado(s))")
            else:       faltando.append(f"❌ {nome}")
        else:
            (ok if enc else faltando).append(f"{'✅' if enc else '❌'} {nome}")
    return {"tipo":tipo,"ok":ok,"faltando":faltando,"completo":len(faltando)==0}


# ══════════════════════════════════════════════════════
# BLOCO 7 — ENVIO POR EMAIL
# ══════════════════════════════════════════════════════

def enviar_email(pdfs_selecionados, destino, remetente, senha, assunto, corpo):
    msg = MIMEMultipart()
    msg['From']=remetente; msg['To']=destino; msg['Subject']=assunto
    msg.attach(MIMEText(corpo,'plain','utf-8'))
    for nome, conteudo in pdfs_selecionados:
        if len(conteudo)/(1024*1024) > 10: continue
        p = MIMEBase('application','octet-stream'); p.set_payload(conteudo)
        encoders.encode_base64(p)
        p.add_header('Content-Disposition',f'attachment; filename="{nome}"')
        msg.attach(p)
    with smtplib.SMTP_SSL('smtp.gmail.com',465) as s:
        s.login(remetente, senha); s.send_message(msg)


# ══════════════════════════════════════════════════════
# BLOCO 8 — INTERFACE STREAMLIT
# ══════════════════════════════════════════════════════

cliente       = st.session_state.get("cliente", {})
plano_atual   = cliente.get("plano","free")
is_pro        = plano_atual == "pro"
nome_corretor = cliente.get("nome","")
creci         = cliente.get("creci","")

st.title("📁 DocCorretor IA")
st.caption("Organize, identifique e envie documentos imobiliários com IA")
st.divider()

# ── Sidebar ──
with st.sidebar:
    st.markdown(f"### 👤 {nome_corretor}")
    plano_badge = "🟢 PRO" if is_pro else "🟡 FREE"
    st.caption(f"Plano: {plano_badge} | Vence: {cliente.get('data_vencimento','')}")
    st.divider()
    st.header("⚙️ Configurações de Envio")
    st.caption("Preencha uma vez — fica salvo enquanto o app estiver aberto.")
    cfg_destino   = st.text_input("📧 Email destino",  value=st.session_state.get("cfg_destino",""),  placeholder="destinatario@email.com")
    cfg_remetente = st.text_input("📤 Seu Gmail",      value=st.session_state.get("cfg_remetente", cliente.get("gmail_remetente","")), placeholder="seuemail@gmail.com")
    cfg_senha     = st.text_input("🔑 Senha de app",   value=st.session_state.get("cfg_senha", cliente.get("gmail_senha_app","")), type="password", placeholder="Senha de app Gmail")
    if st.button("💾 Salvar configuração"):
        st.session_state["cfg_destino"]   = cfg_destino
        st.session_state["cfg_remetente"] = cfg_remetente
        st.session_state["cfg_senha"]     = cfg_senha
        st.success("✅ Configuração salva!")
    st.divider()
    st.caption("💡 Senha de app ≠ senha do Gmail\nmyaccount.google.com → Segurança → Senhas de app")
    st.divider()
    if st.button("🚪 Sair", use_container_width=True):
        for k in ["autenticado","cliente","cfg_destino","cfg_remetente","cfg_senha",
                  "pdfs_gerados","email_gerado","processado"]:
            st.session_state.pop(k, None)
        st.query_params.clear()
        st.rerun()

# ── PASSO 1: Upload ──
st.subheader("📂 Passo 1 — Upload dos documentos")
arquivos_upload = st.file_uploader(
    "Selecione imagens e/ou PDFs do cliente",
    accept_multiple_files=True,
    type=["jpg","jpeg","png","bmp","webp","tiff","pdf"]
)

# ── PASSO 2: Texto ──
st.subheader("📝 Passo 2 — Texto do WhatsApp (opcional)")
texto_bruto = st.text_area(
    "Cole aqui mensagens, anotações, informações do cliente",
    height=120,
    placeholder="Ex:\nGmail: cliente@gmail.com\nNIT 160.74503.57-6\n81 9 9296-7781\nRenda informal R$2.550, imóvel novo R$205.000, 1 dependente..."
)

# ── PASSO 3: Destinatário ──
st.subheader("👤 Passo 3 — Nome do destinatário")
nome_destinatario = st.text_input(
    "Nome de quem vai receber o email",
    placeholder="Ex: Ana, Carlos, Caixa Econômica..."
)

# ── PROCESSAR ──
st.divider()
processar = st.button("🚀 PROCESSAR ARQUIVOS E TEXTO", type="primary", use_container_width=True)

if processar:
    if not arquivos_upload:
        st.error("⚠️ Faça o upload de pelo menos um arquivo antes de processar.")
    else:
        arquivos_bytes = []
        for arq in arquivos_upload:
            conteudo = arq.read()
            tipo     = "pdf" if arq.name.lower().endswith('.pdf') else "imagem"
            arquivos_bytes.append((arq.name, conteudo, tipo))

        barra = st.progress(0, text="📄 Organizando documentos...")
        pdfs_gerados = processar_documentos(arquivos_bytes)

        barra.progress(35, text="🔍 Extraindo dados de contato...")
        dados_contato = extrair_dados(texto_bruto, arquivos_bytes, pdfs_gerados)

        barra.progress(60, text="📋 Lendo dados da simulação...")
        dados_simulacao = extrair_dados_simulacao(texto_bruto, arquivos_bytes, pdfs_gerados)

        barra.progress(85, text="✍️ Gerando texto profissional...")
        gerado = gerar_texto_automatico(
            dados_simulacao, dados_contato,
            nome_destinatario, nome_corretor, creci
        )

        barra.progress(100, text="✅ Concluído!")
        time.sleep(0.5); barra.empty()

        st.session_state["pdfs_gerados"] = pdfs_gerados
        st.session_state["email_gerado"] = gerado
        st.session_state["processado"]   = True

        cliente_sess = st.session_state.get("cliente")
        if cliente_sess:
            registrar_uso(cliente_sess, qtd_arquivos=len(arquivos_bytes))

# ── Resultados ──
if st.session_state.get("processado"):
    pdfs_gerados = st.session_state["pdfs_gerados"]
    email_gerado = st.session_state["email_gerado"]

    st.divider()

    # Checklist
    checklist = calcular_checklist([n for n,_ in pdfs_gerados])
    icone = "✅" if checklist['completo'] else "🚨"
    with st.expander(f"{icone} CHECKLIST — Renda: {checklist['tipo']}", expanded=True):
        for i in checklist['ok']:
            st.markdown(f"<span class='checklist-ok'>{i}</span>", unsafe_allow_html=True)
        for i in checklist['faltando']:
            cor = "checklist-aviso" if "⚠️" in i else "checklist-falta"
            st.markdown(f"<span class='{cor}'>{i}</span>", unsafe_allow_html=True)

    st.divider()

    # Etapa 1 — Documentos
    st.subheader("📄 Etapa 1 — Documentos gerados")
    st.caption("Desmarque o que estiver duplicado ou incorreto")
    selecionados = []
    for nome, conteudo in pdfs_gerados:
        col1, col2 = st.columns([0.7, 0.3])
        with col1:
            marcado = st.checkbox(f"📎 {nome}", value=True, key=f"cb_{nome}")
        with col2:
            st.download_button("⬇️ Baixar", data=conteudo, file_name=nome,
                               mime="application/pdf", key=f"dl_{nome}")
        if marcado: selecionados.append((nome, conteudo))

    st.divider()

    # Etapa 2 — Texto gerado
    st.subheader("📝 Etapa 2 — Texto gerado (editável)")
    assunto_inicial = "Documentação do Cliente"
    corpo_inicial   = email_gerado
    for linha in email_gerado.split('\n')[:5]:
        if 'assunto' in linha.lower():
            assunto_inicial = linha.split(':',1)[-1].strip().replace('**','').strip()
            corpo_inicial   = email_gerado.replace(linha,'').strip()
            break

    assunto_edit = st.text_input("Assunto", value=assunto_inicial)
    corpo_edit   = st.text_area("Corpo do email", value=corpo_inicial, height=300)

    st.divider()

    # Etapa 3 — Envio
    st.subheader("📬 Etapa 3 — Envio")

    if not is_pro:
        st.info("📧 **Envio por email disponível no plano PRO.**\nVocê pode baixar os arquivos normalmente.\nFale com o suporte para fazer upgrade.")

    opcoes = ["📥 Apenas baixar todos os arquivos"]
    if is_pro:
        opcoes += ["📧 Apenas enviar por email", "📥📧 Baixar E enviar por email"]

    opcao = st.radio("O que deseja fazer?", opcoes, horizontal=True)

    col_exec, col_cancel = st.columns([1,1])

    with col_exec:
        if st.button("✅ CONFIRMAR E EXECUTAR", type="primary", use_container_width=True):

            if "📥" in opcao:
                zip_buf = io.BytesIO()
                with zipfile.ZipFile(zip_buf, "w") as zf:
                    for nome, conteudo in selecionados:
                        zf.writestr(nome, conteudo)
                zip_buf.seek(0)
                st.download_button("⬇️ Baixar todos como ZIP", data=zip_buf,
                                   file_name="documentos_cliente.zip",
                                   mime="application/zip")

            if is_pro and ("📧" in opcao or "enviar" in opcao.lower()):
                destino   = st.session_state.get("cfg_destino","")
                remetente = st.session_state.get("cfg_remetente","")
                senha     = st.session_state.get("cfg_senha","")
                if not destino or '@' not in destino:
                    st.error("❌ Configure o email destino na barra lateral.")
                elif not remetente or '@' not in remetente:
                    st.error("❌ Configure seu Gmail na barra lateral.")
                elif not senha:
                    st.error("❌ Configure a senha de app na barra lateral.")
                else:
                    try:
                        barra_env = st.progress(0, text="📧 Conectando ao Gmail...")
                        time.sleep(0.3)
                        barra_env.progress(40, text="📤 Anexando arquivos...")
                        enviar_email(selecionados, destino, remetente, senha,
                                     assunto_edit, corpo_edit)
                        barra_env.progress(100, text="✅ Email enviado!")
                        time.sleep(0.5); barra_env.empty()
                        st.success(f"✅ Email enviado para {destino} com {len(selecionados)} arquivo(s)!")
                        cliente_sess = st.session_state.get("cliente")
                        if cliente_sess:
                            registrar_uso(cliente_sess, qtd_arquivos=len(selecionados),
                                          email_enviado=True)
                    except smtplib.SMTPAuthenticationError:
                        st.error("❌ Autenticação falhou! Use senha de APP do Gmail.")
                    except Exception as e:
                        st.error(f"❌ Erro ao enviar: {e}")

    with col_cancel:
        if st.button("🔄 Novo processo", use_container_width=True):
            for key in ["pdfs_gerados","email_gerado","processado"]:
                if key in st.session_state: del st.session_state[key]
            st.rerun()
