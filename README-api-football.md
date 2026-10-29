# Caminho alternativo: API-Football e painel de configuração

Este módulo é **separado** do protótipo M4 já publicado. Não substitui `bot.py`, não usa chaves M4 e **não está ativado no GitHub**. A API-Football documenta `GET /fixtures?live=all` e `GET /fixtures/statistics?fixture={id}` (estatística `Corner Kicks`); o parâmetro `half=true` está disponível para dados de primeiro/segundo tempo de 2024 em diante. O código consulta escanteios acumulados no primeiro tempo e no jogo inteiro. Cobertura varia por temporada/liga.

## Painel local

Instale `pip install -r requirements.txt`, depois `streamlit run panel.py`. Ele grava somente regras em `config.json`; não armazena senhas ou tokens. Se configurar o bot via Actions, faça commit de `config.json` sem dados sensíveis. Nunca hospede o painel aberto na internet sem autenticação. `config.example.json` vem desativado e em simulação. Copie-o para `config.json` e ajuste pelo painel. Ao habilitar consultas mantenha `dry_run=true` até o teste real passar.

## Secrets para GitHub Actions

- `API_FOOTBALL_KEY`: chave da sua conta API-Football, obtida no dashboard do serviço; precisa acesso aos endpoints Fixtures e Statistics.
- `TG_SOKKERPRO_TOKEN`: token NOVO do BotFather, após revogar o token publicado no chat.
- `TG_GROUP_ID`: ID numérico do grupo Telegram. Pode ser Variable em vez de Secret, mas Secret é permitido.

Cadastre em Settings → Secrets and variables → Actions → New repository secret. **Nunca comite valores.** O workflow `api-football-manual.yml` tem somente `workflow_dispatch`, sem agenda; confirme nos logs retorno não vazio, escanteios reais, consumo de cota, e só então considere enviar alertas. O `contents: read` é suficiente durante o teste. Antes de qualquer agenda com histórico por commit, um workflow específico precisará `contents: write` e configuração de persistência revisada.

O plano gratuito tem **100 chamadas/dia**, conforme a página de preços consultada em 29/10/2026. Cada execução custa uma chamada para listar jogos + até `max_matches` chamadas de estatísticas. Exemplo: 1 + 6 = até 7 chamadas/execução; executar de 5 em 5 minutos extrapola facilmente a cota. Ajuste ligas, número de partidas e frequência antes de agendar. Nunca interprete resposta vazia inesperada como sucesso.

Fontes: https://api-sports.io/documentation/football/v3 e https://www.api-football.com/pricing
