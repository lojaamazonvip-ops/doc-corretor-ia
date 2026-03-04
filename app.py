import streamlit as st
import streamlit.components.v1 as components
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
from datetime import datetime, timedelta, timezone, date
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
    page_title="ImobFlow",
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
    #MainMenu{visibility:hidden!important;display:none!important;}
    header{visibility:hidden!important;display:none!important;}
    footer{visibility:hidden!important;display:none!important;}
    [data-testid="stToolbar"]{display:none!important;}
    [data-testid="stDecoration"]{display:none!important;}
    .stDeployButton{display:none!important;}
    a[href*="streamlit.io"]{display:none!important;}

    /* Botão WhatsApp flutuante */
    .whatsapp-float {
        position: fixed;
        top: 16px;
        right: 16px;
        z-index: 9999;
        display: flex;
        flex-direction: column;
        align-items: center;
        text-decoration: none;
    }
    .whatsapp-float .wa-circle {
        width: 52px;
        height: 52px;
        background: #25d366;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.25);
        transition: transform 0.2s;
    }
    .whatsapp-float:hover .wa-circle {
        transform: scale(1.1);
    }
    .whatsapp-float .wa-circle svg {
        width: 28px; height: 28px; fill: white;
    }
    .whatsapp-float .wa-label {
        margin-top: 4px;
        background: #25d366;
        color: white;
        font-size: 10px;
        font-weight: bold;
        padding: 2px 7px;
        border-radius: 10px;
        white-space: nowrap;
        box-shadow: 0 2px 6px rgba(0,0,0,0.15);
    }
</style>

<!-- Botão WhatsApp flutuante -->
<a class="whatsapp-float"
   href="https://wa.me/5581992952521?text=Ol%C3%A1!%20Tenho%20d%C3%BAvidas%20sobre%20o%20ImobFlow%20IA."
   target="_blank">
  <div class="wa-circle">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
      <path d="M16 0C7.163 0 0 7.163 0 16c0 2.822.738 5.476 2.027 7.784L0 32l8.418-2.004A15.938 15.938 0 0016 32c8.837 0 16-7.163 16-16S24.837 0 16 0zm0 29.333a13.27 13.27 0 01-6.77-1.848l-.485-.287-5.001 1.19 1.234-4.872-.317-.5A13.267 13.267 0 012.667 16C2.667 8.821 8.821 2.667 16 2.667S29.333 8.821 29.333 16 23.179 29.333 16 29.333zm7.274-9.874c-.398-.199-2.354-1.162-2.719-1.294-.365-.133-.631-.199-.897.199-.266.398-1.031 1.294-1.264 1.56-.232.266-.465.299-.863.1-.398-.199-1.681-.619-3.202-1.977-1.183-1.056-1.982-2.36-2.213-2.758-.232-.398-.025-.613.174-.811.179-.178.398-.465.597-.698.199-.232.266-.398.398-.664.133-.266.066-.499-.033-.698-.1-.199-.897-2.162-1.23-2.96-.323-.778-.652-.672-.897-.684l-.764-.013c-.266 0-.697.1-1.063.499-.365.398-1.395 1.362-1.395 3.323 0 1.961 1.428 3.856 1.627 4.122.199.266 2.81 4.29 6.808 5.016.952.163 1.695.261 2.274.334.955.121 1.824.104 2.512-.061.767-.183 2.354-.963 2.686-1.893.332-.93.332-1.727.232-1.893-.099-.166-.365-.266-.763-.465z"/>
    </svg>
  </div>
  <span class="wa-label">Suporte e Dúvidas</span>
</a>
""", unsafe_allow_html=True)

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
    pdfs_finais = []
    tmp = tempfile.mkdtemp()

    caminhos = {}
    for nome, conteudo, _ in arquivos_bytes:
        caminho = os.path.join(tmp, nome)
        with open(caminho, "wb") as f: f.write(conteudo)
        caminhos[nome] = caminho

    imgs  = [(n,c) for n,c,t in arquivos_bytes if t=="imagem"]
    pdfs  = [(n,c) for n,c,t in arquivos_bytes if t=="pdf"]

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
# BLOCO 3 — EXTRAÇÃO DE DADOS
# ══════════════════════════════════════════════════════

# ⚠️ WHITELIST — apenas estes campos chegam ao texto.
# observacoes, cpf, rg, endereco, estado_civil, banco
# são BLOQUEADOS e NUNCA aparecem no email gerado.
CAMPOS_PERMITIDOS = {
    "nome_completo", "email", "telefone", "nit_pis_nis",
    "renda_valor", "renda_tipo", "renda_profissao",
    "dependentes", "valor_imovel", "tipo_imovel",
    "nunca_trabalhou_carteira", "nome_destinatario"
}

def extrair_dados(texto_bruto, arquivos_bytes, pdfs_gerados):
    prompt = f"""
Especialista em documentos imobiliários brasileiros.
Extraia informações de DUAS FONTES:
- Texto → usa do texto
- Documentos → usa dos documentos
- Nas DUAS → usa o mais completo
- Não encontrou → deixa ""

TEXTO:
{texto_bruto}

⚠️ EXTRAIA SOMENTE estes campos — NADA MAIS:
nome_completo, email, telefone, nit_pis_nis,
renda_valor, renda_tipo, renda_profissao,
dependentes, valor_imovel, tipo_imovel,
nunca_trabalhou_carteira

🚫 NÃO extraia: observacoes, cpf, rg, data_nascimento,
endereco, estado_civil, banco, histórico bancário,
detalhes de simulação, informações de terceiros.

RETORNE APENAS JSON:
{{
  "nome_completo":"","email":"","telefone":"","nit_pis_nis":"",
  "renda_valor":"","renda_tipo":"","renda_profissao":"",
  "dependentes":"","valor_imovel":"","tipo_imovel":"",
  "nunca_trabalhou_carteira":""
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
        resp        = chamar_gemini(parts)
        dados_brutos = json.loads(resp.replace('```json','').replace('```','').strip())
        # ⚠️ FILTRO DUPLO: remove qualquer campo fora da whitelist
        return {k: dados_brutos.get(k, "") for k in CAMPOS_PERMITIDOS}
    except:
        return {k: "" for k in CAMPOS_PERMITIDOS}


# ══════════════════════════════════════════════════════
# BLOCO 4 — GERAÇÃO DO EMAIL
# ══════════════════════════════════════════════════════

def fmt_brl(valor):
    try:
        v = float(str(valor).replace(",",".").replace("R$","").replace(" ","").strip())
        s = f"{v:,.2f}".replace(",","X").replace(".",",").replace("X",".")
        return f"R$ {s}"
    except: return str(valor)

def gerar_email(texto_bruto, dados, pdfs_selecionados):
    """Monta texto diretamente — sem Gemini — campos obrigatórios sempre presentes."""
    hora = datetime.now(timezone(timedelta(hours=-3))).hour
    if 6 <= hora < 12:    saud = "Bom dia"
    elif 12 <= hora < 18: saud = "Boa tarde"
    else:                 saud = "Boa noite"

    nome_dest    = dados.get("nome_destinatario","").strip()
    saud_txt     = f"{saud}, {nome_dest}." if nome_dest else f"{saud}."
    nome_cliente = dados.get("nome_completo","a cliente").split()[0] if dados.get("nome_completo") else "a cliente"

    valor_imovel = dados.get("valor_imovel","")
    if valor_imovel and not str(valor_imovel).startswith("R$"):
        valor_imovel = fmt_brl(valor_imovel)
    tipo_imovel = dados.get("tipo_imovel","")
    ctx_imovel  = f" de imóvel {tipo_imovel} no valor de {valor_imovel}" if valor_imovel else ""

    assunto = f"Documentação {nome_cliente}"
    if tipo_imovel:  assunto += f" — Imóvel {tipo_imovel.capitalize()}"
    if valor_imovel: assunto += f" {valor_imovel}"

    campos = []
    # NIT/PIS/NIS — sempre presente
    campos.append(f"• 🪪 NIT/PIS/NIS: {dados.get('nit_pis_nis','')}")
    # Renda
    if dados.get("renda_valor"):
        renda = dados["renda_valor"]
        if not str(renda).startswith("R$"): renda = fmt_brl(renda)
        tipo  = dados.get("renda_tipo","")
        det   = f" ({tipo})" if tipo else ""
        campos.append(f"• 💰 Renda mensal: {renda}{det}")
    # Carteira
    if str(dados.get("nunca_trabalhou_carteira","")).lower() in ("true","sim","yes","1"):
        campos.append("• Nunca trabalhou de carteira assinada")
    # Dependentes
    dep = dados.get("dependentes","")
    if dep and str(dep) not in ("0",""):
        campos.append(f"• Possui {dep} dependente(s)")
    # Email — SEMPRE presente
    campos.append(f"• 📧 E-mail: {dados.get('email','')}")
    # Telefone — SEMPRE presente
    campos.append(f"• 📱 Telefone: {dados.get('telefone','')}")

    campos_str = "\n".join(campos)

    return f"""Assunto: {assunto}

{saud_txt}

Conforme simulação realizada, segue documentação da cliente {nome_cliente} para aprovação de financiamento{ctx_imovel}.

Informações da cliente:

{campos_str}

Solicito, por gentileza, aprovação conforme simulação encaminhada.

Fico no aguardo do retorno.
Obrigada."""


# ══════════════════════════════════════════════════════
# BLOCO 5 — CHECKLIST
# ══════════════════════════════════════════════════════

def calcular_checklist(nomes_pdfs, dados=None):
    docs = set(n.replace('.pdf','').lower() for n in nomes_pdfs)
    tem_h = any('holerite' in d for d in docs)
    tem_e = any('extrato'  in d for d in docs)
    tipo  = "FORMAL" if tem_h else ("INFORMAL" if tem_e else "NÃO IDENTIFICADA")

    obrig = {
        "CPF"                      : ["cpf"],
        "RG ou CNH"                : ["rg","cnh"],
        "Certidão de Estado Civil" : ["certidao_nascimento","certidao_casamento"],
        "Comprovante de Residência": ["comprovante_residencia"],
        "NIS / BIZ / NIT"          : ["nis_cadunico","biz","nit","pis","pasep"],
    }
    if tipo=="FORMAL":
        obrig["Carteira de Trabalho"]         = ["carteira_de_trabalho"]
        obrig["3 Últimos Holerites"]          = ["holerite"]
    elif tipo=="INFORMAL":
        nunca_clt = str((dados or {}).get("nunca_trabalhou_carteira","")).lower()
        if nunca_clt not in ("true","sim","yes","1"):
            obrig["Carteira de Trabalho (+3 anos FGTS)"] = ["carteira_de_trabalho"]
        obrig["3 Últimos Extratos Bancários"] = ["extrato_bancario","extrato"]
    else:
        obrig["Comprovante de Renda"] = ["holerite","extrato"]
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
    if dados:
        if dados.get("email"):    ok.append("✅ E-mail do participante")
        else: faltando.append("❌ E-mail do participante — obrigatório")
        if dados.get("telefone"): ok.append("✅ Telefone do participante")
        else: faltando.append("❌ Telefone do participante — obrigatório")
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

st.title("📁 ImobFlow")
st.caption("Organize, identifique e envie documentos imobiliários com IA")

# ── Banner contador de dias (só para FREE) ──
# Lê direto do session_state APÓS check_login() ter autenticado
_cliente_top = st.session_state.get("cliente", {})
_plano_top   = _cliente_top.get("plano", "free")
_venc_top    = _cliente_top.get("data_vencimento", "")
_is_pro_top  = _plano_top in ("mensal", "semestral", "anual")

if not _is_pro_top and _venc_top:
    try:
        _dias = (date.fromisoformat(_venc_top) - date.today()).days
        if _dias > 3:
            st.info(f"🆓 **Teste gratuito** — ⏳ **{_dias} dias restantes** para expirar seu acesso.")
        elif _dias > 0:
            st.warning(f"⚠️ **ATENÇÃO: {_dias} dia(s) restante(s)!** Faça upgrade agora para não perder o acesso.")
        elif _dias == 0:
            st.error("🚨 **Seu acesso expira HOJE!** Faça upgrade imediatamente.")
        else:
            st.error("❌ **Acesso expirado.** Faça upgrade para continuar usando.")
    except:
        pass

st.divider()

with st.sidebar:
    cliente_sb  = st.session_state.get("cliente", {})
    nome_sb     = cliente_sb.get("nome","")
    plano_sb    = cliente_sb.get("plano","free")
    venc_sb     = cliente_sb.get("data_vencimento","")
    is_pro_sb   = plano_sb in ("mensal","semestral","anual")

    st.markdown(f"### 👤 {nome_sb}")
    if is_pro_sb:
        st.caption(f"⭐ Plano PRO — {plano_sb.capitalize()}")
    else:
        try:
            dias_rest = (date.fromisoformat(venc_sb) - date.today()).days
            if dias_rest > 3:
                st.warning(f"🆓 Teste gratuito\n⏳ **{dias_rest} dias restantes**")
            elif dias_rest > 0:
                st.error(f"🚨 **ATENÇÃO: {dias_rest} dia(s) restante(s)!**\nSeu acesso expira em breve.")
            else:
                st.error("❌ **Acesso expirado!**\nFaça upgrade para continuar.")
        except:
            st.caption("🆓 Plano Free")

    st.divider()
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
    st.divider()
    if st.button("🚪 Sair", use_container_width=True):
        for k in ["autenticado","cliente","cfg_destino","cfg_remetente","cfg_senha",
                  "pdfs_gerados","email_gerado","processado","dados"]:
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
    placeholder="Ex:\nGmail: cliente@gmail.com\nNIT 160.74503.57-6\n81 9 9296-7781\nRenda informal R$2.550, 1 dependente, imóvel novo R$205.000..."
)

# ── PASSO 3: Destinatário ──
st.subheader("👤 Passo 3 — Nome do destinatário (opcional)")
st.text_input(
    "Nome de quem vai receber o email",
    placeholder="Ex: Ana, Carlos, Caixa Econômica...",
    key="nome_destinatario_input"
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

        barra = st.progress(0, text="📄 Lendo e organizando documentos...")
        pdfs_gerados = processar_documentos(arquivos_bytes)
        barra.progress(50, text="🔍 Extraindo dados do cliente...")
        nome_dest_input = st.session_state.get("nome_destinatario_input","")
        dados  = extrair_dados(texto_bruto, arquivos_bytes, pdfs_gerados)
        dados["nome_destinatario"] = nome_dest_input
        barra.progress(85, text="✍️ Gerando texto...")
        gerado = gerar_email(texto_bruto, dados, pdfs_gerados)
        barra.progress(100, text="✅ Concluído!")
        time.sleep(0.4); barra.empty()

        st.session_state["pdfs_gerados"] = pdfs_gerados
        st.session_state["email_gerado"] = gerado
        st.session_state["dados"]        = dados
        st.session_state["processado"]   = True
        cliente_sess = st.session_state.get("cliente")
        if cliente_sess:
            registrar_uso(cliente_sess, qtd_arquivos=len(arquivos_bytes))

# ── Resultados ──
if st.session_state.get("processado"):
    pdfs_gerados = st.session_state["pdfs_gerados"]
    email_gerado = st.session_state["email_gerado"]
    dados        = st.session_state.get("dados", {})

    st.divider()

    checklist = calcular_checklist([n for n,_ in pdfs_gerados], dados)
    icone = "✅" if checklist['completo'] else "🚨"
    with st.expander(f"{icone} CHECKLIST — Renda: {checklist['tipo']}", expanded=True):
        for i in checklist['ok']:
            st.markdown(f"<span class='checklist-ok'>{i}</span>", unsafe_allow_html=True)
        for i in checklist['faltando']:
            cor = "checklist-aviso" if "⚠️" in i else "checklist-falta"
            st.markdown(f"<span class='{cor}'>{i}</span>", unsafe_allow_html=True)

    st.divider()

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

    if selecionados:
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf:
            for nome, conteudo in selecionados:
                zf.writestr(nome, conteudo)
        zip_buf.seek(0)
        st.download_button("⬇️ Baixar toda documentação em ZIP", data=zip_buf,
                           file_name="documentos_cliente.zip", mime="application/zip",
                           use_container_width=True, key="zip_final")

    st.divider()

    st.subheader("📝 Etapa 2 — Texto gerado (editável)")

    assunto_inicial = "Documentação do Cliente"
    corpo_inicial   = email_gerado
    for linha in email_gerado.split('\n')[:5]:
        if 'assunto' in linha.lower():
            assunto_inicial = linha.split(':',1)[-1].strip().replace('**','').strip()
            corpo_inicial   = email_gerado.replace(linha,'').strip()
            break

    assunto_edit = st.text_input("Assunto", value=assunto_inicial)
    corpo_edit   = st.text_area("Corpo do email", value=corpo_inicial, height=280)

    if st.button("📋 Copiar texto", use_container_width=True):
        st.code(f"Assunto: {assunto_edit}\n\n{corpo_edit}", language=None)
        st.caption("☝️ Selecione tudo (Ctrl+A) e copie (Ctrl+C)")

    st.divider()

    st.subheader("📬 Etapa 3 — Enviar por email")
    cliente_sess = st.session_state.get("cliente", {})
    plano_atual  = cliente_sess.get("plano","free")
    is_pro       = plano_atual in ("mensal","semestral","anual")

    if not is_pro:
        LINK_MENSAL    = "https://kiwify.com.br/PLACEHOLDER_MENSAL"
        LINK_SEMESTRAL = "https://kiwify.com.br/PLACEHOLDER_SEMESTRAL"
        LINK_ANUAL     = "https://kiwify.com.br/PLACEHOLDER_ANUAL"
        st.markdown("---")
        st.markdown("### 🚀 Faça upgrade para enviar emails")
        st.caption("Escolha seu plano e continue usando sem limites:")

        st.markdown(f"""<a href="{LINK_MENSAL}" target="_blank" style="display:block;text-align:center;
            padding:12px;background:#1976d2;color:white;border-radius:8px;
            text-decoration:none;font-weight:bold;margin-bottom:8px;">
            📅 Mensal — R$ 97,00/mês</a>""", unsafe_allow_html=True)

        st.markdown(f"""<a href="{LINK_SEMESTRAL}" target="_blank" style="display:block;text-align:center;
            padding:12px;background:#388e3c;color:white;border-radius:8px;
            text-decoration:none;font-weight:bold;margin-bottom:8px;">
            📆 Semestral — R$ 83,00/mês</a>""", unsafe_allow_html=True)

        st.markdown(f"""<a href="{LINK_ANUAL}" target="_blank" style="display:block;text-align:center;
            padding:12px;background:#f57c00;color:white;border-radius:8px;
            text-decoration:none;font-weight:bold;margin-bottom:8px;">
            🏆 Anual — R$ 75,00/mês &nbsp; ⭐ Mais escolhido</a>""", unsafe_allow_html=True)
        st.markdown("---")
    else:
        st.caption("Configure o email destino e seu Gmail na barra lateral antes de enviar.")
        if st.button("📧 Enviar por email", type="primary", use_container_width=True):
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
                    with st.spinner("📧 Enviando email..."):
                        enviar_email(selecionados, destino, remetente, senha, assunto_edit, corpo_edit)
                    st.success(f"✅ Email enviado para {destino} com {len(selecionados)} arquivo(s)!")
                    if cliente_sess:
                        registrar_uso(cliente_sess, qtd_arquivos=len(selecionados), email_enviado=True)
                except smtplib.SMTPAuthenticationError:
                    st.error("❌ Autenticação falhou! Use senha de APP do Gmail.")
                except Exception as e:
                    st.error(f"❌ Erro ao enviar: {e}")

    st.divider()
    if st.button("🔄 Novo processo", use_container_width=True):
        for key in ["pdfs_gerados","email_gerado","processado","dados"]:
            if key in st.session_state: del st.session_state[key]
        st.rerun()
