import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from io import BytesIO

st.set_page_config(page_title="Conversor CSV → SEPA (pain.001.001.03)", layout="centered")

st.title("💶 Conversor CSV → SEPA (pain.001.001.03)")
st.write("Preenche os dados da tua empresa, descarrega o modelo CSV e carrega o ficheiro preenchido para gerar o XML SEPA.")

st.header("🏢 Dados da Empresa (Devedor)")
empresa = st.text_input("Nome da Empresa")
nif = st.text_input("NIF")
iban = st.text_input("IBAN", help="Formato: PT50009900009999999999905")

# Criar modelo CSV em memória
modelo_csv = "nº,Name,Iban,Value,Ref\n"

st.download_button(
    label="⬇️ Descarregar modelo CSV",
    data=modelo_csv,
    file_name="modelo.csv",
    mime="text/csv"
)

ficheiro = st.file_uploader("📂 Carregar ficheiro CSV preenchido", type=["csv"])

if ficheiro is not None:
    try:
        df = pd.read_csv(ficheiro, sep=",")
        st.dataframe(df)

        campos_validos = all(col in df.columns for col in ["nº", "Name", "Iban", "Value", "Ref"])

        if st.button("Gerar ficheiro XML SEPA"):
            if not campos_validos:
                st.error("❌ O ficheiro CSV não contém as colunas obrigatórias: nº, Name, Iban, Value, Ref.")
            elif not empresa or not iban:
                st.warning("⚠️ Preenche o Nome da Empresa e o IBAN antes de gerar o XML.")
            else:
                root = ET.Element("Document", xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03")
                CstmrCdtTrfInitn = ET.SubElement(root, "CstmrCdtTrfInitn")
                GrpHdr = ET.SubElement(CstmrCdtTrfInitn, "GrpHdr")
                ET.SubElement(GrpHdr, "MsgId").text = "MSG001"
                ET.SubElement(GrpHdr, "NbOfTxs").text = str(len(df))
                ET.SubElement(GrpHdr, "CtrlSum").text = str(round(df["Value"].sum(), 2))
                InitgPty = ET.SubElement(GrpHdr, "InitgPty")
                ET.SubElement(InitgPty, "Nm").text = empresa

                PmtInf = ET.SubElement(CstmrCdtTrfInitn, "PmtInf")
                ET.SubElement(PmtInf, "PmtInfId").text = "PMT001"
                ET.SubElement(PmtInf, "PmtMtd").text = "TRF"
                Dbtr = ET.SubElement(PmtInf, "Dbtr")
                ET.SubElement(Dbtr, "Nm").text = empresa
                DbtrAcct = ET.SubElement(PmtInf, "DbtrAcct")
                ET.SubElement(DbtrAcct, "IBAN").text = iban

                for _, row in df.iterrows():
                    CdtTrfTxInf = ET.SubElement(PmtInf, "CdtTrfTxInf")
                    PmtId = ET.SubElement(CdtTrfTxInf, "PmtId")
                    ET.SubElement(PmtId, "EndToEndId").text = str(row["Ref"])
                    Amt = ET.SubElement(CdtTrfTxInf, "Amt")
                    ET.SubElement(Amt, "InstdAmt", Ccy="EUR").text = str(row["Value"])
                    CdtrAcct = ET.SubElement(CdtTrfTxInf, "CdtrAcct")
                    ET.SubElement(CdtrAcct, "IBAN").text = str(row["Iban"])
                    Cdtr = ET.SubElement(CdtTrfTxInf, "Cdtr")
                    ET.SubElement(Cdtr, "Nm").text = str(row["Name"])

                xml_bytes = BytesIO()
                ET.ElementTree(root).write(xml_bytes, encoding="utf-8", xml_declaration=True)

                st.download_button(
                    label="💾 Descarregar XML SEPA",
                    data=xml_bytes.getvalue(),
                    file_name="ficheiro_SEPA.xml",
                    mime="application/xml"
                )

    except Exception as e:
        st.error(f"Erro ao processar o ficheiro: {e}")
