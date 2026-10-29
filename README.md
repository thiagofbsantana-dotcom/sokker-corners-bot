# Alertas de escanteios HT/FT — SokkerPro M4 → Telegram

Consulta `https://m4.sokkerpro.com/livescores` e `https://m4.sokkerpro.com/fixture/{id}` e envia alertas estatísticos ao grupo Telegram. HT: ≥4 escanteios acumulados entre 25' e 44'; FT: ≥8 entre 65' e 89'. Valores ajustáveis. Não consulta odds, não cria mercado de apostas em casa de apostas e não garante resultados.

**Estado:** esqueleto seguro, não validado em produção. A autenticação M4 e o formato do JSON não foram fornecidos/documentados e o acesso sem ela foi bloqueado. Antes de habilitar o agendamento, valide o cabeçalho e os campos de resposta com acesso autorizado; adapte `parse_corners`, `minute_and_teams` e `fixtures_from_live` conforme o esquema real. Dados ausentes causam descarte, nunca alertas fabricados.

## Configuração

1. Crie um bot no BotFather, adicione-o ao grupo e conceda permissão de postar. Revogue qualquer token previamente compartilhado em conversa.
2. Em **Settings → Secrets and variables → Actions**, salve como **Secrets**: `TELEGRAM_BOT_TOKEN`, `M4_AUTH_HEADER` (nome do cabeçalho comprovado), `M4_AUTH_VALUE` (valor completo do cabeçalho; ex.: prefixo e token, se exigido). Não coloque valores em arquivos, issues ou logs.
3. Como **Variables**: `TELEGRAM_CHAT_ID` (ID numérico do grupo), `HT_MIN_CORNERS=4`, `FT_MIN_CORNERS=8`.
4. Confirme a autorização M4 e o formato de `/fixture/{id}`. Execute manualmente via **Actions → Run workflow**, examine logs sem compartilhar credenciais, e só então mantenha o agendamento ativo.

O GitHub Actions agenda a cada cinco minutos, mas execuções agendadas podem atrasar ou ser descartadas. O arquivo `state.json` registra partidas e fases notificadas; por ser público, contém IDs de partidas (não segredos). Em execuções concorrentes ou falha no push, pode ocorrer alerta duplicado; para garantias fortes, use um banco transacional externo. Execuções futuras podem manter esse histórico indefinidamente, que deve ser podado quando necessário.

## Rodar localmente

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN='token novo e privado'
export TELEGRAM_CHAT_ID='id do grupo'
export M4_AUTH_HEADER='nome do cabeçalho confirmado'
export M4_AUTH_VALUE='valor completo confirmado'
python bot.py
```

**Segurança:** nada de credenciais do Cleubiano. Não faça commit de `.env`, tokens, cookies ou senhas. O bot falha de forma segura quando M4 não está configurada. Não compartilhe tokens por chat.
