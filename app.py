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
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from PyPDF2 import PdfMerger
from pathlib import Path

# ══════════════════════════════════════════════════════
# CONFIGURAÇÃO DA PÁGINA
# ══════════════════════════════════════════════════════

st.set_page_config(
    page_title="DocCorretor IA",
    page_icon="📁",
    layout="centered"
)

st.markdown("""
<style>
    .main { max-width: 750px; }
    .stTextArea textarea { font-size: 14px; }
    .stButton>button { width: 100%; }
    .checklist-ok    { color: #2e7d32; font-weight: bold; }
    .checklist-falta { color: #c62828; font-weight: bold; }
    .checklist-aviso { color: #e65100; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# CHAVES API — lidas dos Secrets do Streamlit
# ══════════════════════════════════════════════════════

API_KEYS = [k.strip() for k in st.secrets.get("GEMINI_KEYS", "").split(",") if k.strip()]
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
        if 'candidates' not in rjson: raise ValueError(f"Resposta inesperada")
        return rjson['candidates'][0]['content']['parts'][0]['text']
    raise ValueError("❌ Todas as tentativas falharam.")


# ══════════════════════════════════════════════════════
# BLOCO 2 — PROCESSAMENTO DE DOCUMENTOS
# ══════════════════════════════════════════════════════

def processar_documentos(arquivos_bytes):
    """
    arquivos_bytes: lista de (nome, bytes, tipo)
    Retorna: lista de (nome_pdf, bytes_pdf)
    """
    pdfs_finais = []
    tmp = tempfile.mkdtemp()

    # Salva arquivos no temp
    caminhos = {}
    for nome, conteudo, _ in arquivos_bytes:
        caminho = os.path.join(tmp, nome)
        with open(caminho, "wb") as f: f.write(conteudo)
        caminhos[nome] = caminho

    imgs  = [(n,c) for n,c,t in arquivos_bytes if t=="imagem"]
    pdfs  = [(n,c) for n,c,t in arquivos_bytes if t=="pdf"]

    # ── PDFs ──
    if pdfs:
        prompt = f"""
Especialista em documentos imobiliários brasileiros.
⚠️ REGRAS: Leia completamente. NUNCA duplique. Cada arquivo em EXATAMENTE UM grupo. Use ID_ARQUIVO exato.
📋 BANCO: {BANCO_STR}
🔄 VERIFIQUE FRENTE/VERSO E UNA: {FRENTE_VERSO_STR}
NOMENCLATURA: TipoDocumento_NomeCompleto_Detalhe
Ex: RG_Maria_Silva | Extrato_Bancario_Nubank_Jan2026 | Certidao_Nascimento_Pedro_Lima
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

    # ── Imagens ──
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
                # Salva imagens no temp e converte
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
# BLOCO 3 — EXTRAÇÃO DE DADOS
# ══════════════════════════════════════════════════════

def extrair_dados(texto_bruto, arquivos_bytes, pdfs_gerados):
    prompt = f"""
Especialista em documentos imobiliários brasileiros.
Extraia informações de DUAS FONTES:
- Informação no TEXTO → usa do texto
- Informação nos DOCUMENTOS → usa dos documentos
- Nas DUAS → usa o mais completo
- Não encontrou → deixa ""

TEXTO BRUTO:
{texto_bruto}

EXTRAIA: nome_completo, cpf, rg, data_nascimento, email, telefone, nit_pis_nis,
endereco, estado_civil, renda_valor, renda_tipo, renda_profissao, dependentes,
banco, valor_imovel, tipo_imovel, nome_destinatario, nunca_trabalhou_carteira, observacoes

RETORNE APENAS JSON:
{{
  "nome_completo":"","cpf":"","rg":"","data_nascimento":"",
  "email":"","telefone":"","nit_pis_nis":"","endereco":"",
  "estado_civil":"","renda_valor":"","renda_tipo":"","renda_profissao":"",
  "dependentes":"","banco":"","valor_imovel":"","tipo_imovel":"",
  "nome_destinatario":"","nunca_trabalhou_carteira":"","observacoes":""
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
        return json.loads(resp.replace('```json','').replace('```','').strip())
    except: return {}


# ══════════════════════════════════════════════════════
# BLOCO 4 — GERAÇÃO DO EMAIL
# ══════════════════════════════════════════════════════

def gerar_email(texto_bruto, dados, pdfs_selecionados):
    campos = []
    # Email — avisa se não encontrado
    if dados.get("email"):
        campos.append(f"• 📧 E-mail: {dados['email']}")
    else:
        campos.append("• 📧 E-mail: ⚠️ NÃO ENCONTRADO — preencha antes de enviar")
    # Telefone — avisa se não encontrado
    if dados.get("telefone"):
        campos.append(f"• 📱 Telefone: {dados['telefone']}")
    else:
        campos.append("• 📱 Telefone: ⚠️ NÃO ENCONTRADO — preencha antes de enviar")
    if dados.get("nit_pis_nis"): campos.append(f"• 🪪 NIT/PIS/NIS: {dados['nit_pis_nis']}")
    if dados.get("renda_valor"):
        tipo = dados.get("renda_tipo",""); prof = dados.get("renda_profissao","")
        det  = f" ({tipo} – {prof})" if tipo or prof else ""
        campos.append(f"• 💰 Renda mensal: {dados['renda_valor']}{det}")
    if str(dados.get("nunca_trabalhou_carteira","")).lower() in ("true","sim","yes","1"):
        campos.append("• Nunca trabalhou de carteira assinada")
    if dados.get("dependentes"):  campos.append(f"• Possui {dados['dependentes']} dependente(s)")
    # CPF, estado_civil e observacoes removidos — não vão para o email

    campos_str   = "\n".join(campos) if campos else "[dados não identificados]"
    nome_cliente = dados.get("nome_completo","a cliente").split()[0] if dados.get("nome_completo") else "a cliente"
    nome_dest    = dados.get("nome_destinatario","")
    saudacao     = f"Boa tarde, {nome_dest}." if nome_dest else "Boa tarde."
    valor_imovel = dados.get("valor_imovel","")
    tipo_imovel  = dados.get("tipo_imovel","")
    ctx_imovel   = f" de imóvel {tipo_imovel} no valor de {valor_imovel}" if valor_imovel else ""
    docs_lista   = "\n".join([f"- {n}" for n,_ in pdfs_selecionados])

    prompt = f"""
Gere um email profissional CURTO e direto seguindo EXATAMENTE este modelo:

Assunto: [objetivo claro em até 10 palavras]

{saudacao}

Conforme simulação realizada, segue documentação da cliente {nome_cliente} para aprovação de financiamento{ctx_imovel}.

Informações da cliente:

{campos_str}

Solicito, por gentileza, aprovação conforme simulação encaminhada.

Fico no aguardo do retorno.
Obrigada.

REGRAS: Use o modelo acima. Não adicione parágrafos extras. Remova campos vazios. NÃO invente nada.
DADOS: {json.dumps(dados, ensure_ascii=False)}
TEXTO ORIGINAL: {texto_bruto}
DOCUMENTOS ANEXADOS: {docs_lista}

RETORNE APENAS O EMAIL.
"""
    try:
        return chamar_gemini([{"text": prompt}]).strip()
    except: return ""


# ══════════════════════════════════════════════════════
# BLOCO 5 — CHECKLIST
# ══════════════════════════════════════════════════════

def calcular_checklist(nomes_pdfs):
    docs = set(n.replace('.pdf','').lower() for n in nomes_pdfs)
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
# BLOCO 6 — ENVIO POR EMAIL
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
# BLOCO 7 — INTERFACE STREAMLIT
# ══════════════════════════════════════════════════════

st.title("📁 DocCorretor IA")
st.caption("Organize, identifique e envie documentos imobiliários com IA")
st.divider()

# ── Configurações de email (sidebar — salvas na sessão) ──
with st.sidebar:
    st.header("⚙️ Configurações de Envio")
    st.caption("Preencha uma vez — fica salvo enquanto o app estiver aberto.")
    cfg_destino   = st.text_input("📧 Email destino",  value=st.session_state.get("cfg_destino",""),  placeholder="destinatario@email.com")
    cfg_remetente = st.text_input("📤 Seu Gmail",      value=st.session_state.get("cfg_remetente",""),placeholder="seuemail@gmail.com")
    cfg_senha     = st.text_input("🔑 Senha de app",   value=st.session_state.get("cfg_senha",""),    type="password", placeholder="Senha de app Gmail")
    if st.button("💾 Salvar configuração"):
        st.session_state["cfg_destino"]   = cfg_destino
        st.session_state["cfg_remetente"] = cfg_remetente
        st.session_state["cfg_senha"]     = cfg_senha
        st.success("✅ Configuração salva!")
    st.divider()
    st.caption("💡 Senha de app ≠ senha do Gmail\nmyaccount.google.com → Segurança → Senhas de app")

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
    placeholder="Ex:\nGmail: cliente@gmail.com\nNIT 160.74503.57-6\n81 9 9296-7781\nRenda informal R$2.550 designer de unhas, 1 dependente, imóvel novo R$205.000..."
)

# ── PASSO 3: Processar ──
st.divider()
processar = st.button("🚀 PROCESSAR ARQUIVOS E TEXTO", type="primary", use_container_width=True)

if processar:
    if not arquivos_upload:
        st.error("⚠️ Faça o upload de pelo menos um arquivo antes de processar.")
    else:
        # Prepara lista de arquivos
        extensoes_img = ('.jpg','.jpeg','.png','.bmp','.webp','.tiff')
        arquivos_bytes = []
        for arq in arquivos_upload:
            conteudo = arq.read()
            tipo     = "pdf" if arq.name.lower().endswith('.pdf') else "imagem"
            arquivos_bytes.append((arq.name, conteudo, tipo))

        with st.spinner("⏳ Processando documentos com IA... aguarde"):
            pdfs_gerados = processar_documentos(arquivos_bytes)

        with st.spinner("🔍 Extraindo dados e gerando email..."):
            dados  = extrair_dados(texto_bruto, arquivos_bytes, pdfs_gerados)
            gerado = gerar_email(texto_bruto, dados, pdfs_gerados)

        # Salva no session_state para persistir
        st.session_state["pdfs_gerados"] = pdfs_gerados
        st.session_state["email_gerado"] = gerado
        st.session_state["processado"]   = True

# ── Resultados (aparecem após processar) ──
if st.session_state.get("processado"):
    pdfs_gerados = st.session_state["pdfs_gerados"]
    email_gerado = st.session_state["email_gerado"]

    st.divider()

    # ── Checklist ──
    checklist = calcular_checklist([n for n,_ in pdfs_gerados])
    icone = "✅" if checklist['completo'] else "🚨"
    with st.expander(f"{icone} CHECKLIST — Renda: {checklist['tipo']}", expanded=True):
        for i in checklist['ok']:      st.markdown(f"<span class='checklist-ok'>{i}</span>",    unsafe_allow_html=True)
        for i in checklist['faltando']:
            cor = "checklist-aviso" if "⚠️" in i else "checklist-falta"
            st.markdown(f"<span class='{cor}'>{i}</span>", unsafe_allow_html=True)

    st.divider()

    # ── ETAPA 1: Documentos com checkbox ──
    st.subheader("📄 Etapa 1 — Documentos gerados")
    st.caption("Desmarque o que estiver duplicado ou incorreto")

    selecionados = []
    for nome, conteudo in pdfs_gerados:
        col1, col2 = st.columns([0.7, 0.3])
        with col1:
            marcado = st.checkbox(f"📎 {nome}", value=True, key=f"cb_{nome}")
        with col2:
            st.download_button(
                "⬇️ Baixar",
                data=conteudo,
                file_name=nome,
                mime="application/pdf",
                key=f"dl_{nome}"
            )
        if marcado: selecionados.append((nome, conteudo))

    st.divider()

    # ── ETAPA 2: Email ──
    st.subheader("📝 Etapa 2 — Email gerado (editável)")

    # Extrai assunto
    assunto_inicial = "Documentação do Cliente"
    corpo_inicial   = email_gerado
    for linha in email_gerado.split('\n')[:5]:
        if 'assunto' in linha.lower():
            assunto_inicial = linha.split(':',1)[-1].strip().replace('**','').strip()
            corpo_inicial   = email_gerado.replace(linha,'').strip()
            break

    assunto_edit = st.text_input("Assunto", value=assunto_inicial)
    corpo_edit   = st.text_area("Corpo do email", value=corpo_inicial, height=280)

    st.divider()

    # ── ETAPA 3: Envio ──
    st.subheader("📬 Etapa 3 — Envio")

    opcao = st.radio(
        "O que deseja fazer?",
        ["📥 Apenas baixar todos os arquivos",
         "📧 Apenas enviar por email",
         "📥📧 Baixar E enviar por email"],
        horizontal=True
    )

    col_exec, col_cancel = st.columns([1,1])

    with col_exec:
        if st.button("✅ CONFIRMAR E EXECUTAR", type="primary", use_container_width=True):
            destino   = st.session_state.get("cfg_destino","")
            remetente = st.session_state.get("cfg_remetente","")
            senha     = st.session_state.get("cfg_senha","")

            if "📥" in opcao:
                # Cria ZIP com todos os selecionados
                import io
                zip_buf = io.BytesIO()
                with zipfile.ZipFile(zip_buf, "w") as zf:
                    for nome, conteudo in selecionados:
                        zf.writestr(nome, conteudo)
                zip_buf.seek(0)
                st.download_button(
                    "⬇️ Baixar todos como ZIP",
                    data=zip_buf,
                    file_name="documentos_cliente.zip",
                    mime="application/zip"
                )

            if "📧" in opcao or "enviar" in opcao.lower():
                if not destino or '@' not in destino:
                    st.error("❌ Configure o email destino na barra lateral.")
                elif not remetente or '@' not in remetente:
                    st.error("❌ Configure seu Gmail na barra lateral.")
                elif not senha:
                    st.error("❌ Configure a senha de app na barra lateral.")
                else:
                    try:
                        with st.spinner("📧 Enviando email..."):
                            enviar_email(selecionados, destino, remetente, senha, assunto_edit, corpo_edit)
                        st.success(f"✅ Email enviado para {destino} com {len(selecionados)} arquivo(s)!")
                    except smtplib.SMTPAuthenticationError:
                        st.error("❌ Autenticação falhou! Use senha de APP do Gmail.\nmyaccount.google.com → Segurança → Senhas de app")
                    except Exception as e:
                        st.error(f"❌ Erro ao enviar: {e}")

    with col_cancel:
        if st.button("🔄 Novo processo", use_container_width=True):
            for key in ["pdfs_gerados","email_gerado","processado"]:
                if key in st.session_state: del st.session_state[key]
            st.rerun()
