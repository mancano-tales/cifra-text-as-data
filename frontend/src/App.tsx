import { useState } from "react";
import { useTranslation } from "react-i18next";
import { CodebookEditor } from "./CodebookEditor";
import { CorpusPage } from "./CorpusPage";

type Tab = "corpus" | "codebook";

function App() {
  const { t, i18n } = useTranslation();
  const [tab, setTab] = useState<Tab>("corpus");

  return (
    <>
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark">C</span>
          <span className="app-title">{t("app.title")}</span>
          <span className="app-tagline">{t("app.tagline")}</span>
        </div>
        <div className="header-controls">
          <div className="seg">
            <button className="seg-btn" disabled={tab === "corpus"} onClick={() => setTab("corpus")}>
              {t("app.nav.corpus")}
            </button>
            <span className="seg-sep" />
            <button className="seg-btn" disabled={tab === "codebook"} onClick={() => setTab("codebook")}>
              {t("app.nav.codebook")}
            </button>
          </div>
          <div className="seg" aria-label="Language">
            <button
              className="seg-btn"
              disabled={i18n.resolvedLanguage === "pt-BR"}
              onClick={() => i18n.changeLanguage("pt-BR")}
            >
              PT
            </button>
            <span className="seg-sep" />
            <button
              className="seg-btn"
              disabled={i18n.resolvedLanguage === "en"}
              onClick={() => i18n.changeLanguage("en")}
            >
              EN
            </button>
          </div>
        </div>
      </header>
      <main className="app-main">{tab === "corpus" ? <CorpusPage /> : <CodebookEditor />}</main>
    </>
  );
}

export default App;
