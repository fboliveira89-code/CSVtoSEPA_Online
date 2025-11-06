import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
from io import BytesIO
from datetime import datetime
import re

# =================== FUNÇÕES ===================

def validar_iban(iban: str) -> bool:
    """Valida IBAN (ISO 13616 / mod 97)."""
    if not iban:
        return False
    iban = iban.replace(" ", "").upper()
    if not re.match(r"^[A-Z0-9]+$", iban):
        return False
    if not (15 <= len(iban) <= 34):
        return False
    rearr = iban[4:] + iban[:4]
    try:
        conv = "".join(str(int(ch, 36)) for ch in rearr)
        return int(conv) % 97 == 1
    except Exception:
        return False


def to_amount(x):
    """Converte valores em float de forma robusta (deteta separadores europeus e ingleses)."""
    if pd.isna(x):
        return 0.0
    s = str(x).strip().replace(" ", "")

    if "," in s and "." not in s:
        s = s.replace(",", ".")
    elif "," in s and "." in s and s.find(",") > s.find("."):
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")

    try:
        return round(float(s), 2)
    except ValueError:
        return 0.0


# =================== INTERFACE ===================

st.set_page_config(page_title="Conversor CSV → SEPA (pain.001.001.03)", layout="centered")
st.title("💶 Conversor CSV → SEPA (pain.001.001.03)")
st.write("Preenche os dados da tua empresa, descarrega o modelo CSV e carrega o ficheiro preenchido para gerar o XML SEPA.")

st.header("🏢 Dados da Empresa (Devedor)")
empresa = st.text_input("Nome da Empresa", value="")
nif = st.text_input("NIF", value="")
iban_devedor = st.text_input("IBAN", value="", help="Exemplo: PT50009900009999999999905")

# Novo campo de data de processamento
data_processamento = st.date_input(
    "Data de processamento",
    value=datetime.today().date(),
    help="Data em que o pagamento será processado"
)

iban_ok = validar_iban(iban_devedor) if iban_devedor else False
if iban_devedor and not iban_ok:
    st.error("❌ IBAN do devedor inválido. Verifica o formato (ex: PT50009900009999999999905).")
elif iban_ok:
    st.success("✅ IBAN do devedor válido.")

# Modelo CSV
modelo_csv = "nº;Name;Iban;Value;Ref\n1;Exemplo_Teste;PT50009900009999999999905;10,00;SUPP\n"
st.download_button("⬇️ Descarregar modelo CSV", data=modelo_csv, file_name="modelo.csv", mime="text/csv")

# Upload
ficheiro = st.file_uploader("📂 Carregar ficheiro CSV preenchido", type=["csv"])

if ficheiro is not None:
    try:
        # Tenta UTF-8 e fallback para ISO-8859-1
        try:
            df = pd.read_csv(ficheiro, sep=None, engine="python", encoding="utf-8")
        except UnicodeDecodeError:
            ficheiro.seek(0)
            df = pd.read_csv(ficheiro, sep=None, engine="python", encoding="ISO-8859-1")

        st.dataframe(df)

        obrig = ["nº", "Name", "Iban", "Value", "Ref"]
        if not all(c in df.columns for c in obrig):
            st.error(f"❌ O ficheiro CSV tem de conter as colunas: {', '.join(obrig)}.")
            st.stop()

        df["Value"] = df["Value"].apply(to_amount)
        df["Iban"] = df["Iban"].astype(str)

        valid_mask = df["Iban"].apply(validar_iban)
        invalid_rows = df.loc[~valid_mask]
        if not invalid_rows.empty:
            st.warning(f"⚠️ Foram ignoradas {len(invalid_rows)} linha(s) com IBAN de credor inválido.")
        df_valid = df.loc[valid_mask].copy()

        total_valor = round(df_valid["Value"].sum(), 2)
        st.markdown(f"💰 **Total calculado:** {total_valor:.2f} €")

        if st.button("Gerar ficheiro XML SEPA"):
            if not empresa or not iban_ok:
                st.error("❌ Preenche o Nome da Empresa e um IBAN do devedor válido.")
                st.stop()
            if df_valid.empty:
                st.error("❌ Não há transações válidas (verifica IBANs e valores).")
                st.stop()

            # =================== GERA XML SEPA ===================
            ns = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.03"
            ET.register_namespace("", ns)
            Document = ET.Element("{%s}Document" % ns)
            CstmrCdtTrfInitn = ET.SubElement(Document, "{%s}CstmrCdtTrfInitn" % ns)

            # --- Cabeçalho ---
            GrpHdr = ET.SubElement(CstmrCdtTrfInitn, "{%s}GrpHdr" % ns)
            ET.SubElement(GrpHdr, "{%s}MsgId" % ns).text = "MSG-" + datetime.now().strftime("%Y%m%d%H%M%S")
            ET.SubElement(GrpHdr, "{%s}CreDtTm" % ns).text = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            ET.SubElement(GrpHdr, "{%s}NbOfTxs" % ns).text = str(len(df_valid))
            ET.SubElement(GrpHdr, "{%s}CtrlSum" % ns).text = f"{total_valor:.2f}"

            InitgPty = ET.SubElement(GrpHdr, "{%s}InitgPty" % ns)
            ET.SubElement(InitgPty, "{%s}Nm" % ns).text = empresa
            if nif.strip():
                Id = ET.SubElement(InitgPty, "{%s}Id" % ns)
                OrgId = ET.SubElement(Id, "{%s}OrgId" % ns)
                Othr = ET.SubElement(OrgId, "{%s}Othr" % ns)
                ET.SubElement(Othr, "{%s}Id" % ns).text = nif.strip()

            # --- Pagamentos ---
            PmtInf = ET.SubElement(CstmrCdtTrfInitn, "{%s}PmtInf" % ns)
            ET.SubElement(PmtInf, "{%s}PmtInfId" % ns).text = "PMT-" + datetime.now().strftime("%Y%m%d")
            ET.SubElement(PmtInf, "{%s}PmtMtd" % ns).text = "TRF"
            ET.SubElement(PmtInf, "{%s}BtchBookg" % ns).text = "true"
            ET.SubElement(PmtInf, "{%s}NbOfTxs" % ns).text = str(len(df_valid))
            ET.SubElement(PmtInf, "{%s}CtrlSum" % ns).text = f"{total_valor:.2f}"

            PmtTpInf = ET.SubElement(PmtInf, "{%s}PmtTpInf" % ns)
            SvcLvl = ET.SubElement(PmtTpInf, "{%s}SvcLvl" % ns)
            ET.SubElement(SvcLvl, "{%s}Cd" % ns).text = "SEPA"

            # ✅ Usa a data escolhida pelo utilizador
            ET.SubElement(PmtInf, "{%s}ReqdExctnDt" % ns).text = data_processamento.strftime("%Y-%m-%d")

            # Devedor
            Dbtr = ET.SubElement(PmtInf, "{%s}Dbtr" % ns)
            ET.SubElement(Dbtr, "{%s}Nm" % ns).text = empresa
            if nif.strip():
                DbtrId = ET.SubElement(Dbtr, "{%s}Id" % ns)
                DbtrOrgId = ET.SubElement(DbtrId, "{%s}OrgId" % ns)
                DbtrOthr = ET.SubElement(DbtrOrgId, "{%s}Othr" % ns)
                ET.SubElement(DbtrOthr, "{%s}Id" % ns).text = nif.strip()

            DbtrAcct = ET.SubElement(PmtInf, "{%s}DbtrAcct" % ns)
            DbtrAcctId = ET.SubElement(DbtrAcct, "{%s}Id" % ns)
            ET.SubElement(DbtrAcctId, "{%s}IBAN" % ns).text = iban_devedor.replace(" ", "")

            DbtrAgt = ET.SubElement(PmtInf, "{%s}DbtrAgt" % ns)
            FinInstnId = ET.SubElement(DbtrAgt, "{%s}FinInstnId" % ns)
            Othr = ET.SubElement(FinInstnId, "{%s}Othr" % ns)
            ET.SubElement(Othr, "{%s}Id" % ns).text = "NOTPROVIDED"

            ET.SubElement(PmtInf, "{%s}ChrgBr" % ns).text = "SLEV"

            # Transações
            for _, row in df_valid.iterrows():
                CdtTrfTxInf = ET.SubElement(PmtInf, "{%s}CdtTrfTxInf" % ns)

                PmtId = ET.SubElement(CdtTrfTxInf, "{%s}PmtId" % ns)
                ET.SubElement(PmtId, "{%s}EndToEndId" % ns).text = str(row.get("Ref", "NOREF"))

                Amt = ET.SubElement(CdtTrfTxInf, "{%s}Amt" % ns)
                InstdAmt = ET.SubElement(Amt, "{%s}InstdAmt" % ns, Ccy="EUR")
                InstdAmt.text = f"{to_amount(row['Value']):.2f}"

                CdtrAgt = ET.SubElement(CdtTrfTxInf, "{%s}CdtrAgt" % ns)
                FinInstnId = ET.SubElement(CdtrAgt, "{%s}FinInstnId" % ns)
                Othr = ET.SubElement(FinInstnId, "{%s}Othr" % ns)
                ET.SubElement(Othr, "{%s}Id" % ns).text = "NOTPROVIDED"

                Cdtr = ET.SubElement(CdtTrfTxInf, "{%s}Cdtr" % ns)
                ET.SubElement(Cdtr, "{%s}Nm" % ns).text = str(row["Name"])

                CdtrAcct = ET.SubElement(CdtTrfTxInf, "{%s}CdtrAcct" % ns)
                CdtrAcctId = ET.SubElement(CdtrAcct, "{%s}Id" % ns)
                ET.SubElement(CdtrAcctId, "{%s}IBAN" % ns).text = str(row["Iban"]).replace(" ", "")

                RmtInf = ET.SubElement(CdtTrfTxInf, "{%s}RmtInf" % ns)
                ET.SubElement(RmtInf, "{%s}Ustrd" % ns).text = str(row.get("Ref", ""))

            rough = ET.tostring(Document, encoding="utf-8")
            dom = minidom.parseString(rough)
            pretty_xml = dom.toprettyxml(indent="  ", encoding="utf-8")

            st.success("✅ Ficheiro SEPA gerado com sucesso!")
            st.download_button(
                "💾 Descarregar XML SEPA",
                data=pretty_xml,
                file_name="ficheiro_SEPA.xml",
                mime="application/xml"
            )

    except Exception as e:
        st.error(f"Erro ao processar o ficheiro: {e}")
