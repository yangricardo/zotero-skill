#!/usr/bin/env bash
# Baixa as fontes originais da pesquisa "EmendasRAG enxuto" (28/10/2026).
# Uso: bash baixar_fontes.sh [pasta_destino]
set -u
DEST="${1:-./fontes-rag-enxuto}"; mkdir -p "$DEST"; cd "$DEST"
dl(){ curl -fsSL -A "Mozilla/5.0" --max-time 120 -o "$1" "$2" && echo "OK   $1" || echo "FALHOU $1  <- $2"; }
dl 01_FiscalIA_SEMISH2026_pagina.html             https://sol.sbc.org.br/index.php/semish/article/view/43502
dl 02_TableRAG_arXiv2506.10380.pdf                https://arxiv.org/pdf/2506.10380v1
dl 03_GRASP_arXiv2503.23299.pdf                   https://arxiv.org/pdf/2503.23299v1
dl 04_Finardi2024_RAG_PTBR_arXiv2401.07883.pdf    https://arxiv.org/pdf/2401.07883
dl 05_Serafim_embeddings_PT_arXiv2407.19527.pdf   https://arxiv.org/pdf/2407.19527
dl 06_TB_continuidade_orcamento_secreto.pdf       https://transparencia.org.br/downloads/publicacoes/continuidadedoorcamentosecreto.pdf
dl 07_TB_emendas_pix_2024.pdf                     https://transparencia.org.br/downloads/publicacoes/emendaspix2024.pdf
dl 08_TB_CA_TIBR_sugestoes_transparencia_2024.pdf "https://blog.transparencia.org.br/wp-content/uploads/2024/09/Sugest%C3%B5es-de-transpar%C3%AAncia-das-emendas-parlamentares.pdf"
dl 09_PSOL_aditamento_ADPF854_2021.pdf            https://static.poder360.com.br/2021/11/Psol-emenda-de-relator-STF.pdf
dl 10_Camara_NT46-2024_decisoes_STF.html          https://www2.camara.leg.br/orcamento-da-uniao/estudos/2024/analise-das-principais-decisoes-do-stf-acerca-de-emendas-parlamentares-atualizacao-26-09-24
dl 11_TCU_relatorio_consolidado_2026.html         https://portal.tcu.gov.br/imprensa/noticias/tcu-apresenta-relatorio-consolidado-de-auditorias-em-emendas-parlamentares
dl 12_CGU_dicionario_dados_emendas.html           https://portaldatransparencia.gov.br/pagina-interna/603482-dicionario-de-dados-emendas-parlamentares
dl 13_CGU_download_emendas.html                   https://portaldatransparencia.gov.br/download-de-dados/emendas-parlamentares
dl 14_UFC_TCC_2025_emendas.pdf                    https://repositorio.ufc.br/bitstream/riufc/83741/1/2025_tcc_jfgoisjunior.pdf
dl 15_Camara_CONOF_06-2023_emendas.html           https://www2.camara.leg.br/orcamento-da-uniao/estudos/2023/estudo-conof_cd-_-no-06-2023-_-emendas-orcamentarias-e-politicas-publicas
dl 16_Goias_agente_IA_MCP_emendas.html            https://goias.gov.br/ligo/estudo-para-criar-um-agente-de-ia-com-mcp-que-respondera-sobre-emendas-parlamentares-do-portal-da-transparencia/
dl 17_RAGAS_metricas.html                         https://docs.ragas.io/en/stable/concepts/metrics/
# Dados brutos (arquivo grande, ~dezenas de MB): descomente para baixar
# dl emendas_parlamentares.zip https://portaldatransparencia.gov.br/download-de-dados/emendas-parlamentares/UNICO
