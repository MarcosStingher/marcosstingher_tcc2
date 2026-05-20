# TCC2 — UML em Modelagem de Software

**Análise bibliométrica de publicações acadêmicas entre 2010 e 2024**

- **Autor:** Marcos Antonio Barbosa Stingher
- **Curso:** Sistemas de Informação
- **Instituição:** Universidade do Oeste de Santa Catarina (UNOESC) — Campus Chapecó
  
---

## Sobre este repositório

Este repositório contém os **artefatos digitais** do TCC2: três dashboards HTML interativos com os resultados da análise bibliométrica e o pipeline Python que os gerou. O objetivo é dar à banca avaliadora acesso direto às visualizações e, ao mesmo tempo, oferecer transparência metodológica completa, sendo que todo o código de processamento e o corpus de 207 artigos estão versionados aqui.

O documento textual do TCC (DOCX) foi entregue pelo canal oficial da UNOESC, mas também está duplicado aqui, nomeado TCC2_MARCOS_STINGHER.docx.

## Como visualizar

Os HTMLs são **autocontidos** — bastam um navegador moderno (Chrome, Firefox, Safari ou Edge) e clique duplo. Não há servidor, build ou dependências.

**Lista de páginas HTML produzidas:**

1. **[`resumo_executivo.html`](resumo_executivo.html)**: Painel-síntese da defesa. KPIs, timeline das três fases, questões de pesquisa respondidas, Top 10 autores e venues, principais achados. Bom ponto de partida.
2. **[`dashboard_uml.html`](dashboard_uml.html)**: Dashboard analítico com tabela filtrável dos 207 artigos, gráficos interativos (publicações por fase, tipo, base, Top 20 autores, Top 15 periódicos, palavras-chave, evolução temática).
3. **[`insights_uml.html`](insights_uml.html)**: Análise aprofundada com rede de co-ocorrência em D3.js, achados e padrões por fase, bigramas e análise idiomática.

Todos os HTMLs suportam alternância entre modo claro e escuro.

## Estrutura do repositório

| Arquivo | Descrição |
|---|---|
| `resumo_executivo.html` | Painel-resumo para defesa (21 KB) |
| `dashboard_uml.html` | Dashboard principal interativo (121 KB) |
| `insights_uml.html` | Insights aprofundados com rede D3.js (59 KB) |
| `analise_bibliometrica.py` | Pipeline que processa o corpus e gera `dashboard_uml.html` |
| `gerar_insights.py` | Pipeline que gera `insights_uml.html` a partir do JSON processado |
| `dados_processados.json` | Corpus consolidado: 207 artigos com título, ano, tipo, venue, autores, fonte, fase, DOI e abstract |

## Corpus analisado

- **207 artigos** (após deduplicação de 235 coletados)
- **Período:** 2010–2024 (15 anos)
- **Bases de dados:**
  - SciSpace Full-Text — 96 artigos
  - SciSpace — 83 artigos
  - PubMed — 15 artigos
  - Google Scholar — 13 artigos
- **Divisão em fases:**
  - Fase 1 — Consolidação (2010–2014): 80 artigos (38,6%)
  - Fase 2 — Expansão MDE (2015–2019): 73 artigos (35,3%)
  - Fase 3 — Especialização (2020–2024): 54 artigos (26,1%)
- **513 autores únicos** e **86 venues únicos** identificados

## Reprodutibilidade

A análise pode ser reproduzida a partir do corpus consolidado.

**Pré-requisitos:** Python 3.10+ e `pandas`.

```bash
pip install pandas
python3 gerar_insights.py          # regera insights_uml.html a partir do JSON
```

`analise_bibliometrica.py` espera, originalmente, uma pasta `ANÁLISE/` com os CSVs brutos exportados das quatro bases. Esses CSVs não estão neste repositório por questão de tamanho e direitos das bases; o `dados_processados.json` representa o estado consolidado e auditável do corpus utilizado no TCC.

## Stack técnica

- **Python 3** — coleta, deduplicação, normalização e geração dos HTMLs (templates inline)
- **Chart.js 4.4.2** — gráficos interativos (timeline, donuts, barras, multi-série)
- **D3.js v7** — rede force-directed de co-ocorrência terminológica
- HTML autocontido — sem framework web, sem build pipeline

A escolha por essa stack (em substituição a ferramentas tradicionais como VOSviewer/Bibliometrix/Excel) é justificada na Seção 3.5 do TCC, atendendo a recomendação da banca.

## Licença

Material acadêmico produzido no contexto do Trabalho de Conclusão de Curso. Uso permitido para fins de avaliação acadêmica e referência; reprodução total ou parcial requer citação ao autor e à UNOESC.
