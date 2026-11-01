# Fluxo e responsabilidades

```text
CSV movies/ratings
       |
       v
validacao de contrato ----- dados invalidos --> erro legivel
       |
       +--> corte por usuario --> modelo + baseline --> evaluation.json
       |
       +--> treinamento completo --> model.joblib + metadata.json
                                         |
                                         v
                               API FastAPI (somente leitura do modelo)
                                 |                    |
                            recomendacoes      POST /feedback
                                 ^                    |
                                 |                    v
                                 +----------- SQLite / WAL
```

O módulo `data` valida e identifica os arquivos. `model` encapsula os vizinhos e o ranking. `evaluation` tem o próprio artefato construído apenas com treino. `store` mantém o histórico de feedback; `api` traduz contratos HTTP e erros.

O banco guarda eventos de avaliação com uma chave de idempotência única e hash do corpo normalizado. `BEGIN IMMEDIATE` serializa a verificação da chave e sua inserção, evitando dois eventos em retries concorrentes. O perfil online usa a avaliação mais recente de cada filme, ordenada pelo ID transacional, sobreposta ao perfil do artefato. A nota substitui a anterior, mas o evento antigo permanece auditável no banco.

Não há worker de treinamento dentro da API. Um novo modelo é treinado em outro comando e carregado quando o serviço reinicia. Esse desenho evita que uma consulta HTTP dispare treinamento ou que usuários recebam modelos parcialmente atualizados.
