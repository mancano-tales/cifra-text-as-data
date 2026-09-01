import { useState } from "react";
import { CodebookEditor } from "./CodebookEditor";
import { CorpusPage } from "./CorpusPage";

type Tab = "corpus" | "codebook";

function App() {
  const [tab, setTab] = useState<Tab>("corpus");

  return (
    <div style={{ maxWidth: "900px", margin: "0 auto", padding: "1rem" }}>
      <h1>Codifica</h1>
      <nav>
        <button onClick={() => setTab("corpus")} disabled={tab === "corpus"}>
          Corpus
        </button>{" "}
        <button onClick={() => setTab("codebook")} disabled={tab === "codebook"}>
          Codebook
        </button>
      </nav>
      {tab === "corpus" ? <CorpusPage /> : <CodebookEditor />}
    </div>
  );
}

export default App;
