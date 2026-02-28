import streamlit as st
import os
import json
import base64
import smtplib
import zipfile
import tempfile
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path
import google.generativeai as genai

# ─── CONFIG ───────────────────────────────────────────────────────────────────
CONFIG_FILE = "doc_corretor_config.json"
SENHA_ACESSO = "corretor2025"   # ← TROQUE PELA SENHA QUE QUISER

# ─── LOGIN ────────────────────────────────────────────────────────────────────
def check_login():
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False

    if not st.session_state.autenticado:
        st.markdown("""
        <style>
        .login-box {
            max-width: 380px;
            margin: 80px auto;
            padding: 40px;
            border-radius: 16px;
            background: #1e1e2e;
            box-shadow: 0 4px 32px rgba(0,0,0,0.4);
            text-align: center;
        }
        .login-title { font-size: 2rem; font-weight: 700; color: #fff; margin-bottom: 8px; }
        .login-sub { color: #aaa; margin-bottom: 28px; font-size: 0.95rem; }
        </style>
        <div class="login-box">
          <div class="login-title">🗂️ DocCorretor IA</div>
          <div class="login-sub">Sistema de organização de documentos para financiamento</div>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            senha = st.text_input("🔑 Senha de acesso", type="password", key="input_senha")
            if st.button("Entrar", use_container_width=True, type="primary"):
                if senha == SENHA_ACESSO:
                    st.session_state.autenticado = True
                    st.rerun()
                else:
                    st.error("Senha incorreta. Tente novamente.")
        st.stop()

# ─── GEMINI ───────────────────────────────────────────────────────────────────
def get_gemini_keys():
    raw = st.secrets.get("GEMINI_KEYS", "")
    if not raw:
        return []
    return [k.strip() for k in raw.split(",") if k.strip()]

def chamar_gemini(prompt, arquivos_b64=None):
    chaves = get_gemini_keys()
    if not chaves:
        st.error("Chaves Gemini não configuradas. Vá em Settings → Secrets e adicione GEMINI_KEYS.")
        return None

    for i, chave in enumerate(chaves):
        try:
            genai.configure(api_key=chave)
            model = genai.GenerativeModel("gemini-1.5-flash")
            partes = [prompt]
            if arquivos_b64:
                for arq in arquivos_b64:
                    partes.append({
                        "mime_type": arq["mime_type"],
                        "data": arq["data"]
                    })
            resp = model.generate_content(partes)
            return resp.text
        except Exception as e:
            msg = str(e)
            if "429" in msg or "quota" in msg.lower():
                continue
            return None
    return None

# ─── CONFIG SALVA ─────────────────────────────────────────────────────────────
def carregar_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"destinatario": "", "remetente": "", "senha_app": ""}

def salvar_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f)

# ─── PROCESSAR ARQUIVO ────────────────────────────────────────────────────────
def arquivo_para_b64(uploaded_file):
    dados = uploaded_file.read()
    uploaded_file.seek(0)
    b64 = base64.b64encode(dados).decode()
    nome = uploaded_file.name.lower()
    if nome.endswith(".pdf"):
        mime = "application/pdf"
    elif nome.endswith(".png"):
        mime = "image/png"
    elif nome.endswith((".jpg", ".jpeg")):
        mime = "image/jpeg"
    elif nome.endswith(".webp"):
        mime = "image/webp"
    else:
        mime = "application/octet-stream"
    return {"mime_type": mime, "data": b64, "nome": uploaded_file.name}

def gerar_pdf_renomeado(uploaded_file, novo_nome):
    """Renomeia e retorna bytes do arquivo como PDF."""
    dados = uploaded_file.read()
    uploaded_file.seek(0)
    return dados, novo_nome

# ─── EXTRAÇÃO DE DADOS ────────────────────────────────────────────────────────
def extrair_dados(texto_bruto, arquivos_b64):
    prompt = f"""Você é um assistente especializado em análise de documentos para financiamento imobiliário.

Analise o TEXTO BRUTO abaixo e todos os DOCUMENTOS ENVIADOS (imagens e PDFs) e extraia os dados do cliente.

REGRAS:
- Se o campo está no texto E nos documentos → use o mais completo
- Se está só no texto → use do texto
- Se está só nos documentos → use dos documentos
- Se não encontrar → use string vazia ""

TEXTO BRUTO:
{texto_bruto if texto_bruto else "(nenhum texto fornecido)"}

Responda SOMENTE com JSON válido, sem explicações, sem markdown, sem blocos de código:
{{
  "nome_completo": "",
  "cpf": "",
  "rg": "",
  "data_nascimento": "",
  "email": "",
  "telefone": "",
  "nit_pis_nis": "",
  "endereco": "",
  "renda_valor": "",
  "renda_tipo": "",
  "renda_profissao": "",
  "dependentes": "",
  "banco": "",
  "valor_imovel": "",
  "tipo_imovel": "",
  "nome_destinatario": "",
  "nunca_trabalhou_carteira": ""
}}"""

    resultado = chamar_gemini(prompt, arquivos_b64)
    if not resultado:
        return {}
    try:
        limpo = resultado.strip().replace("```json","").replace("```","").strip()
        return json.loads(limpo)
    except:
        return {}

# ─── NOMEAR PDFS ─────────────────────────────────────────────────────────────
def nomear_arquivos(arquivos_upload, dados):
    nome_cliente = dados.get("nome_completo", "Cliente").replace(" ", "_").title()
    prompt_nomes = f"""Você recebe uma lista de arquivos e dados do cliente. Para cada arquivo, gere um nome descritivo em português.

Nome do cliente: {nome_cliente}
Arquivos: {[a.name for a in arquivos_upload]}

Regras de nomenclatura:
- RG ou identidade → RG_NomeCliente.pdf
- CNH → CNH_NomeCliente.pdf
- Certidão de nascimento → CertidaoNascimento_NomePessoa.pdf
- Comprovante de residência → ComprovResidencia_NomeEmpresa_MesAno.pdf
- Extrato bancário → ExtratoBancario_NomeBanco_MesAno.pdf
- NIT/PIS/NIS → NIT_NomeCliente.pdf
- Simulação → SimulacaoHabitacional_Banco.pdf
- CPF → CPF_NomeCliente.pdf
- Outros → use um nome descritivo

Responda SOMENTE com JSON, sem markdown:
{{"nomes": ["nome1.pdf", "nome2.pdf", ...]}}"""

    resultado = chamar_gemini(prompt_nomes)
    if resultado:
        try:
            limpo = resultado.strip().replace("```json","").replace("```","").strip()
            parsed = json.loads(limpo)
            return parsed.get("nomes", [a.name for a in arquivos_upload])
        except:
            pass
    return [a.name for a in arquivos_upload]

# ─── GERAR EMAIL ──────────────────────────────────────────────────────────────
def gerar_email(texto_bruto, dados):
    campos = []
    if dados.get("email"):        campos.append(f"📧 E-mail: {dados['email']}")
    if dados.get("telefone"):     campos.append(f"📱 Telefone: {dados['telefone']}")
    if dados.get("nit_pis_nis"):  campos.append(f"🪪 NIT/PIS/NIS: {dados['nit_pis_nis']}")
    if dados.get("cpf"):          campos.append(f"📋 CPF: {dados['cpf']}")
    if dados.get("renda_valor"):
        detalhe = ""
        tipo = dados.get("renda_tipo","")
        prof = dados.get("renda_profissao","")
        if tipo or prof:
            detalhe = f" ({' – '.join(filter(None,[tipo,prof]))})"
        campos.append(f"💰 Renda mensal: {dados['renda_valor']}{detalhe}")
    nunca = dados.get("nunca_trabalhou_carteira","")
    if str(nunca).lower() in ("true","sim","yes","1"):
        campos.append("Nunca trabalhou de carteira assinada")
    if dados.get("dependentes"):
        campos.append(f"Possui {dados['dependentes']} dependente(s)")

    nome_dest   = dados.get("nome_destinatario","") or "Ana"
    _nome_completo = (dados.get("nome_completo","") or "").split()
    nome_cliente = _nome_completo[0].capitalize() if _nome_completo else "cliente"
    valor_imovel = dados.get("valor_imovel","")
    tipo_imovel  = dados.get("tipo_imovel","") or "novo"

    corpo = f"""Boa tarde, {nome_dest}.

Conforme simulação realizada, segue documentação da cliente {nome_cliente} para aprovação de financiamento de imóvel {tipo_imovel} no valor de {valor_imovel}.

Informações da Cliente:
{chr(10).join(campos)}

Solicito, por gentileza, aprovação conforme simulação encaminhada.

Fico no aguardo do retorno.

Obrigada."""

    assunto = f"Envio de Documentação – {nome_cliente} | Imóvel {tipo_imovel.capitalize()} {valor_imovel}"
    return assunto, corpo

# ─── CHECKLIST ────────────────────────────────────────────────────────────────
def montar_checklist(nomes_gerados, dados):
    renda_tipo = dados.get("renda_tipo","").lower()
    informal = "informal" in renda_tipo or renda_tipo == ""

    itens_req = [
        ("RG ou CNH", ["rg","cnh","identidade","habilitacao"]),
        ("Certidão de Nascimento ou Casamento", ["certidao","nascimento","casamento"]),
        ("Comprovante de Residência", ["comprov","residencia","neoenergia","energia","agua","conta"]),
        ("NIS / PIS / NIT", ["nit","pis","nis"]),
        ("Extratos Bancários (3 meses)", ["extrato","bancario"]),
        ("Simulação Habitacional", ["simulacao","habitacional","caixa","mcmv"]),
    ]
    if informal:
        itens_req.append(("CPF", ["cpf"]))

    nomes_lower = [n.lower() for n in nomes_gerados]

    resultado = []
    for desc, palavras in itens_req:
        encontrado = any(
            any(p in nome for p in palavras)
            for nome in nomes_lower
        )
        resultado.append((desc, encontrado))
    return resultado, informal

# ─── ENVIO DE EMAIL ──────────────────────────────────────────────────────────
def enviar_email(remetente, senha_app, destinatario, assunto, corpo, arquivos_bytes):
    msg = MIMEMultipart()
    msg["From"] = remetente
    msg["To"] = destinatario
    msg["Subject"] = assunto
    msg.attach(MIMEText(corpo, "plain", "utf-8"))

    for nome, dados_bytes in arquivos_bytes:
        part = MIMEApplication(dados_bytes, Name=nome)
        part["Content-Disposition"] = f'attachment; filename="{nome}"'
        msg.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(remetente, senha_app)
        s.sendmail(remetente, destinatario, msg.as_bytes())

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    check_login()

    st.set_page_config(page_title="DocCorretor IA", page_icon="🗂️", layout="centered")
    st.title("🗂️ DocCorretor IA")
    st.caption("Organize documentos e gere emails profissionais em segundos")

    cfg = carregar_config()

    # ── PASSO 1: Upload ────────────────────────────────────────────────────────
    st.markdown("### 📁 Passo 1 — Suba os documentos")
    arquivos = st.file_uploader(
        "Imagens (JPG, PNG) e PDFs",
        type=["pdf","png","jpg","jpeg","webp"],
        accept_multiple_files=True
    )

    # ── PASSO 2: Texto WhatsApp ────────────────────────────────────────────────
    st.markdown("### 📝 Passo 2 — Cole o texto do WhatsApp (opcional)")
    texto_bruto = st.text_area(
        "Cole aqui as anotações ou mensagens",
        height=160,
        placeholder="Ex: [15:55] Mãe: Gmail: thallyaeduarda90@gmail.com\n[16:05] Mãe: 81 9 92967781..."
    )

    # ── PROCESSAR ─────────────────────────────────────────────────────────────
    processar = st.button("🚀 PROCESSAR ARQUIVOS E TEXTO", type="primary", use_container_width=True,
                          disabled=not arquivos)

    if processar and arquivos:
        # --- barra de progresso ---
        barra = st.progress(0, text="⏳ Preparando arquivos...")
        time.sleep(0.3)

        barra.progress(10, text="📄 Lendo documentos...")
        arquivos_b64 = [arquivo_para_b64(a) for a in arquivos]

        barra.progress(30, text="🔍 Extraindo dados do texto e documentos...")
        dados = extrair_dados(texto_bruto, arquivos_b64)

        barra.progress(55, text="🏷️ Nomeando arquivos...")
        nomes_gerados = nomear_arquivos(arquivos, dados)

        barra.progress(75, text="✍️ Gerando email...")
        assunto, corpo = gerar_email(texto_bruto, dados)

        barra.progress(95, text="✅ Quase pronto...")
        time.sleep(0.3)
        barra.progress(100, text="✅ Concluído!")
        time.sleep(0.4)
        barra.empty()

        st.session_state["resultado"] = {
            "dados": dados,
            "nomes_gerados": nomes_gerados,
            "assunto": assunto,
            "corpo": corpo,
            "arquivos": arquivos,
            "arquivos_b64": arquivos_b64,
        }

    # ── RESULTADO ─────────────────────────────────────────────────────────────
    if "resultado" in st.session_state:
        res = st.session_state["resultado"]
        dados = res["dados"]
        nomes_gerados = res["nomes_gerados"]
        arquivos_upload = res["arquivos"]

        checklist, informal = montar_checklist(nomes_gerados, dados)
        renda_label = "INFORMAL" if informal else "FORMAL"

        # ── CHECKLIST ─────────────────────────────────────────────────────────
        st.markdown(f"---\n### 📋 Checklist de Documentos &nbsp;&nbsp; 💼 Renda: **{renda_label}**")
        faltando = [desc for desc, ok in checklist if not ok]
        for desc, ok in checklist:
            icone = "✅" if ok else "❌"
            st.markdown(f"{icone} {desc}")
        if faltando:
            st.warning(f"🚨 {len(faltando)} item(ns) faltando: {', '.join(faltando)}")

        # ── ETAPA 1: documentos com checkbox ──────────────────────────────────
        st.markdown("---\n### 📄 Etapa 1 — Documentos gerados")
        st.caption("Desmarque duplicados ou arquivos incorretos antes de enviar.")

        selecionados = {}
        for i, (arq, nome) in enumerate(zip(arquivos_upload, nomes_gerados)):
            selecionados[i] = st.checkbox(f"📎 {nome}", value=True, key=f"chk_{i}")

        # ── ETAPA 2: email editável ────────────────────────────────────────────
        st.markdown("---\n### 📝 Etapa 2 — Email gerado (editável)")
        assunto_edit = st.text_input("📌 Assunto", value=res["assunto"])
        corpo_edit   = st.text_area("📧 Corpo do email", value=res["corpo"], height=320)

        # ── ETAPA 3: envio ────────────────────────────────────────────────────
        st.markdown("---\n### 📬 Etapa 3 — Envio")
        with st.expander("⚙️ Configurações de email (salvas automaticamente)", expanded=not cfg["destinatario"]):
            dest_in_tmp = st.text_input("📧 Email destino (quem recebe)", value=cfg["destinatario"])
            rem_in_tmp  = st.text_input("📤 Seu Gmail (remetente)", value=cfg["remetente"])
            sen_in_tmp  = st.text_input("🔑 Senha de app Gmail", value=cfg["senha_app"], type="password")
            if st.button("💾 Salvar configurações"):
                cfg = {"destinatario": dest_in_tmp, "remetente": rem_in_tmp, "senha_app": sen_in_tmp}
                salvar_config(cfg)
                st.success("✅ Configurações salvas!")
                st.rerun()

        dest_in = cfg["destinatario"]
        rem_in  = cfg["remetente"]
        sen_in  = cfg["senha_app"]

        col1, col2, col3 = st.columns(3)

        def get_arquivos_selecionados():
            resultado = []
            for i, arq in enumerate(arquivos_upload):
                if selecionados.get(i, True):
                    nome = nomes_gerados[i] if i < len(nomes_gerados) else arq.name
                    arq.seek(0)
                    resultado.append((nome, arq.read()))
            return resultado

        with col1:
            if st.button("📥 Baixar arquivos", use_container_width=True):
                barra_dl = st.progress(0, text="📦 Compactando arquivos...")
                arqs_sel = get_arquivos_selecionados()
                with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                    with zipfile.ZipFile(tmp.name, "w") as zf:
                        for i, (nome, dados_bytes) in enumerate(arqs_sel):
                            zf.writestr(nome, dados_bytes)
                            barra_dl.progress(int((i+1)/len(arqs_sel)*90), text=f"📦 {nome}")
                    barra_dl.progress(100, text="✅ Pronto!")
                    time.sleep(0.5)
                    barra_dl.empty()
                    with open(tmp.name, "rb") as f:
                        st.download_button("⬇️ Clique para baixar o ZIP", f, "documentos.zip", "application/zip")

        with col2:
            if st.button("📧 Enviar por email", use_container_width=True):
                if not rem_in or not sen_in or not dest_in:
                    st.error("Preencha as configurações de email primeiro.")
                else:
                    barra_env = st.progress(0, text="📧 Preparando envio...")
                    arqs_sel = get_arquivos_selecionados()
                    barra_env.progress(40, text="📤 Conectando ao Gmail...")
                    try:
                        barra_env.progress(70, text="📤 Enviando arquivos...")
                        enviar_email(rem_in, sen_in, dest_in, assunto_edit, corpo_edit, arqs_sel)
                        barra_env.progress(100, text="✅ Email enviado!")
                        time.sleep(0.5)
                        barra_env.empty()
                        st.success(f"✅ Email enviado com sucesso para {dest_in}!")
                    except Exception as e:
                        barra_env.empty()
                        if "Authentication" in str(e) or "Username" in str(e):
                            st.error("❌ Autenticação falhou! Use senha de APP do Gmail.\n→ myaccount.google.com → Segurança → Senhas de app")
                        else:
                            st.error(f"❌ Erro ao enviar: {e}")

        with col3:
            if st.button("📥📧 Baixar + Enviar", use_container_width=True):
                if not rem_in or not sen_in or not dest_in:
                    st.error("Preencha as configurações de email primeiro.")
                else:
                    barra_tudo = st.progress(0, text="⏳ Processando...")
                    arqs_sel = get_arquivos_selecionados()

                    # ZIP
                    barra_tudo.progress(20, text="📦 Compactando arquivos...")
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                        with zipfile.ZipFile(tmp.name, "w") as zf:
                            for nome, dados_bytes in arqs_sel:
                                zf.writestr(nome, dados_bytes)
                        barra_tudo.progress(55, text="📤 Enviando email...")
                        try:
                            enviar_email(rem_in, sen_in, dest_in, assunto_edit, corpo_edit, arqs_sel)
                            barra_tudo.progress(100, text="✅ Concluído!")
                            time.sleep(0.5)
                            barra_tudo.empty()
                            st.success(f"✅ Email enviado para {dest_in}!")
                            with open(tmp.name, "rb") as f:
                                st.download_button("⬇️ Baixar ZIP", f, "documentos.zip", "application/zip")
                        except Exception as e:
                            barra_tudo.empty()
                            if "Authentication" in str(e) or "Username" in str(e):
                                st.error("❌ Autenticação falhou! Use senha de APP do Gmail.")
                            else:
                                st.error(f"❌ Erro ao enviar: {e}")

if __name__ == "__main__":
    main()
