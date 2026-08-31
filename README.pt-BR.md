<!-- 🇧🇷 Português — [🇺🇸 English version](README.md) -->

# text-as-data

Todo cientista social que já leu jornal com uma planilha aberta ao lado conhece
o trabalho: uma notícia relata uma declaração, um protesto, uma ocupação de
terra — e alguém precisa transformar aquele parágrafo em uma linha de dados.
Data, local, ator, e uma coluna que exige julgamento de verdade: isso *é* um
protesto? aquela fala *é* a favor ou contra a política em questão?

Esse trabalho tem nome na ciência política computacional — **automated event
coding**, ou de forma mais ampla, **text-as-data** — e é uma área ativa
justamente porque a parte difícil nunca foi digitar a planilha. A parte
difícil é fazer a categorização bater com o conceito teórico que você tem em
mente, não com uma versão genérica e simplificada dele.

Com LLMs, a promessa é automatizar exatamente essa etapa: dar ao modelo um
*codebook* — a definição do seu conceito, do jeito que você explicaria para
um assistente de pesquisa humano — e deixar que ele aplique essa
categorização em milhares de textos. **A armadilha é que o modelo pode
"concordar" com seu codebook no prompt e mesmo assim aplicar, na prática, o
conceito genérico que aprendeu no treinamento** — um problema de validade de
construto, não de acurácia técnica (ver Halterman & Keith, *"Codebook LLMs:
Evaluating LLMs as Measurement Tools for Political Science Concepts"*,
Political Analysis, 2025).

## O que este repositório pretende ser

Um pipeline pequeno e honesto sobre essa armadilha: texto não-estruturado
entra, tabela estruturada sai, e a validação contra uma amostra codificada
por humano **não é um script à parte que ninguém roda** — é parte do
pipeline, desde o primeiro commit. A ideia não é substituir a leitura crítica
do pesquisador, é dar a ele uma ferramenta que assume, por construção, que a
classificação automática pode estar sistematicamente errada de um jeito
sutil, e que isso precisa ser medido antes de virar dado publicável.

Ainda não está amarrado a um projeto específico — nasceu de uma conversa
sobre automatizar codificação de notícias de jornal, mas o desenho é
agnóstico de domínio de propósito. Os candidatos naturais de aplicação são
ocupações de terra (linha DATALUTA), posicionamento em política industrial/
antitruste, ou eventos de segurança pública (linha CCDEP/SEADE) — nenhum
escolhido ainda.

## Como funciona, em uma imagem

```
textos.csv (id, texto)
     │
     ▼
codebook   — o construto teórico: schema (o formato da tabela de saída),
             instruções (a definição do conceito, escrita para um humano
             seguir) e exemplos (few-shot) que fecham os casos de borda
     │
     ▼
extração   — chama um LLM, valida a resposta contra o schema
     │
     ▼
validação  — compara contra rótulos humanos: acurácia, Cohen's kappa,
             e a lista de casos onde modelo e humano discordaram
```

O `codebook` fica separado do motor de extração/validação de propósito: é a
peça que muda a cada projeto novo, enquanto o motor por baixo não deveria
precisar mudar.

## Estado atual

MVP funcional, mas deliberadamente pequeno: os três módulos
(`codebook`/`extraction`/`validation`) têm testes passando, e há um exemplo
de teste sintético e trivial (`examples/toy_example/`) que serve só para
provar que o pipeline roda ponta a ponta — não é um caso de pesquisa real.
Coleta de texto (scraping de jornal, rede social) fica de fora por enquanto:
o pipeline assume que o texto já chegou pronto num CSV.

Todo o código, comentários e documentação técnica deste repositório estão em
inglês — este README em português existe à parte porque a história por trás
do projeto merece ser contada na língua em que ela nasceu.

Para instruções de instalação e uso, veja a [versão em inglês](README.md).
