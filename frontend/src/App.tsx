import { useState } from "react";
import { CodebookEditor } from "./CodebookEditor";
import { CorpusPage } from "./CorpusPage";

type Tab = "corpus" | "codebook";

function App() {
  const [tab, setTab] = useState<Tab>("corpus");

  return (
    <>
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark">C</span>
          <span className="app-title">Cifra</span>
          <span className="app-tagline">codebook-driven text coding</span>
        </div>
        <div className="seg">
          <button className="seg-btn" disabled={tab === "corpus"} onClick={() => setTab("corpus")}>
            Corpus
          </button>
          <span className="seg-sep" />
          <button className="seg-btn" disabled={tab === "codebook"} onClick={() => setTab("codebook")}>
            Codebook
          </button>
        </div>
      </header>
      <main className="app-main">{tab === "corpus" ? <CorpusPage /> : <CodebookEditor />}</main>
    </>
  );
}

export default App;
