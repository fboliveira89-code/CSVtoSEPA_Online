import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
from io import BytesIO
from datetime import datetime
import os
import re

# ==============================
# FUNÇÃO DE VALIDAÇÃO IBAN
# ==============================
def validar_iban(iban: str) -> bool:
    """
    Valida um IBAN segundo a norma ISO 13616.
    Suporta Portugal e outros países europeus.
    """
    iban = iban.replace(' ', '').upper()
    if not re.match(r'^[A-Z0-9]+$', iban):
        return False
    if len(iban) < 15 or len(iban) > 34:
        return False
    # mover os 4 primeiros caracteres para o fim
    rearranjado = iban[4:] + iban[:4]
    # converter letras em números
    convertido = ''.join(str(int(ch, 36)) for ch in rearranjado)
    # verificar o resto
    return int(convertido) % 97 == 1

# ==============================
# CONFIGURAÇÃO INICIAL
# ==============================
st.set_page_config(page_title="Conversor CSV → SEPA", layout="centered")
st.title("💶 Conversor CSV → SEPA (pain.001.001.03)")
st.write("Preenche os dados da tua empresa, descarrega o modelo CSV e carrega o ficheiro preenchido para gerar o XML SEPA.")

# ==============================
# CAMPOS DE DADOS DA EMPRESA
# ==============================
st.subheader("🏢 Dados da Empresa (Devedor)")

empresa_nome = st.text_input("Nome da Empresa", value="")
empresa_nif = st.text_input("NIF", value="")
empresa_iban = st.text_input("IBAN", value="")

iban_valido = validar_iban(empresa_iban) if empresa_iban else True

if empresa_iban and not iban_valido:
    st.error("❌ IBAN inválido! Verifica o formato (ex: PT50009900009999999999905)")
elif empresa_iban:
    st.success("✅ IBAN válido.")

if not empresa_nome or not empresa_iban or not iban_valido:
    campos_validos = False
else:
    campos_validos = True

# ==============================
# CAMINHO DO MODELO CSV
# ==============================
path_modelo = r"C:\Scripts\CSVtoSEPA_Online\modelo.csv"

if not os.path.exists(path_modelo):
    st.error(f"⚠️ O ficheiro modelo.csv não foi encontrado em: {path_modelo}")
    st.stop()

# ==============================
# BOTÃO PARA DESCARREGAR MODELO CSV
# ==============================
with open(path_modelo, "rb") as f:
    st.download_button(
        label="📥 Descarregar modelo CSV",
        data=f,
        file_name="modelo.csv",
        mime="text/csv"
    )

# ==============================
# UPLOAD DO FICHEIRO CSV
# ==============================
ficheiro = st.file_uploader("📤 Carregar ficheiro CSV preenchido", type=["csv"])

if ficheiro and campos_validos:
    try:
        df = pd.read_csv(ficheiro, sep=";", encoding="latin1")
    except Exception as e:
        st.error(f"Erro ao ler o ficheiro CSV: {e}")
        st.stop()

    st.dataframe(df)

    if st.button("Gerar ficheiro XML SEPA"):
        # ==============================
        # GERAÇÃO DO XML SEPA
        # ==============================
        ns = {"": "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"}
        ET.register_namespace('', ns[""])
        Document = ET.Element("Document", xmlns=ns[""])
        CstmrCdtTrfInitn = ET.SubElement(Document, "CstmrCdtTrfInitn")

        # --- Cabeçalho ---
        GrpHdr = ET.SubElement(CstmrCdtTrfInitn, "GrpHdr")
        ET.SubElement(GrpHdr, "MsgId").text = "MSG-" + datetime.now().strftime("%Y%m%d%H%M%S")
        ET.SubElement(GrpHdr, "CreDtTm").text = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        ET.SubElement(GrpHdr, "NbOfTxs").text = str(len(df))
        ET.SubElement(GrpHdr, "CtrlSum").text = str(round(df["Value"].sum(), 2))
        InitgPty = ET.SubElement(GrpHdr, "InitgPty")
        ET.SubElement(InitgPty, "Nm").text = empresa_nome

        # --- Informação do pagamento ---
        PmtInf = ET.SubElement(CstmrCdtTrfInitn, "PmtInf")
        ET.SubElement(PmtInf, "PmtInfId").text = "PMT-" + datetime.now().strftime("%Y%m%d")
        ET.SubElement(PmtInf, "PmtMtd").text = "TRF"
        ET.SubElement(PmtInf, "BtchBookg").text = "true"
        ET.SubElement(PmtInf, "NbOfTxs").text = str(len(df))
        ET.SubElement(PmtInf, "CtrlSum").text = str(round(df["Value"].sum(), 2))

        PmtTpInf = ET.SubElement(PmtInf, "PmtTpInf")
        SvcLvl = ET.SubElement(PmtTpInf, "SvcLvl")
        ET.SubElement(SvcLvl, "Cd").text = "SEPA"

        ET.SubElement(PmtInf, "ReqdExctnDt").text = datetime.now().strftime("%Y-%m-%d")

        # --- Dados da empresa (devedor) ---
        Dbtr = ET.SubElement(PmtInf, "Dbtr")
        ET.SubElement(Dbtr, "Nm").text = empresa_nome

        DbtrAcct = ET.SubElement(PmtInf, "DbtrAcct")
        Id = ET.SubElement(DbtrAcct, "Id")
        ET.SubElement(Id, "IBAN").text = empresa_iban

        DbtrAgt = ET.SubElement(PmtInf, "DbtrAgt")
        FinInstnId = ET.SubElement(DbtrAgt, "FinInstnId")
        ET.SubElement(FinInstnId, "Nm").text = "Banco Desconhecido"

        ET.SubElement(PmtInf, "ChrgBr").text = "SLEV"

        # --- Transações individuais ---
        for _, row in df.iterrows():
            CdtTrfTxInf = ET.SubElement(PmtInf, "CdtTrfTxInf")

            PmtId = ET.SubElement(CdtTrfTxInf, "PmtId")
            ET.SubElement(PmtId, "EndToEndId").text = str(row.get("Ref", "NOREF"))

            Amt = ET.SubElement(CdtTrfTxInf, "Amt")
            InstdAmt = ET.SubElement(Amt, "InstdAmt", Ccy="EUR")
            InstdAmt.text = f"{float(row['Value']):.2f}"

            CdtrAgt = ET.SubElement(CdtTrfTxInf, "CdtrAgt")
            FinInstnId = ET.SubElement(CdtrAgt, "FinInstnId")
            ET.SubElement(FinInstnId, "Nm").text = "Banco Beneficiário"

            Cdtr = ET.SubElement(CdtTrfTxInf, "Cdtr")
            ET.SubElement(Cdtr, "Nm").text = str(row["Name"])

            CdtrAcct = ET.SubElement(CdtTrfTxInf, "CdtrAcct")
            Id = ET.SubElement(CdtrAcct, "Id")
            ET.SubElement(Id, "IBAN").text = str(row["Iban"])

            RmtInf = ET.SubElement(CdtTrfTxInf, "RmtInf")
            ET.SubElement(RmtInf, "Ustrd").text = str(row.get("Ref", ""))

        # --- Converter o XML em formato legível ---
        rough_string = ET.tostring(Document, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        pretty_xml = reparsed.toprettyxml(indent="  ")

        xml_bytes = BytesIO()
        xml_bytes.write(pretty_xml.encode('utf-8'))
        xml_bytes.seek(0)

        st.success("✅ Ficheiro XML SEPA gerado com sucesso!")
        st.download_button(
            label="💾 Descarregar XML SEPA",
            data=xml_bytes,
            file_name="ficheiro_SEPA.xml",
            mime="application/xml"
        )

