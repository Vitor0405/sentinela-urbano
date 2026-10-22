# Fontes dos PDFs de documentação

Gera o artigo e o resumo do artigo (em `docs/`) a partir de HTML, usando o Google Chrome sem interface (outro navegador: variável `BROWSER_PATH`).

```bash
npm install                 # uma vez (instala o puppeteer-core; não baixa navegador)
npm run capturas            # com o sistema no ar (docker compose up): refaz as telas em capturas/
npm run artigo              # → ../Sentinela_Urbano_artigo.pdf
npm run resumo              # → ../Sentinela_Urbano_resumo_artigo.pdf
```

- `artigo.html` e `resumo-artigo.html`: textos, com formatação inspirada na ABNT (A4, margens 3/2 cm, Times 12).
- `capturas.mjs`: entra como cada perfil de teste (morador, agente, gestor) e fotografa as telas usadas nas figuras.
- As capturas usam os dados fictícios do seed de desenvolvimento.
