# Modelo item-item

## Objetivo

Ordenar filmes ainda não avaliados a partir de sinais positivos de outros usuários. O modelo não prevê estrelas, não garante diversidade e não tenta medir satisfação futura diretamente.

## Entradas e representação

- Catálogo: `movieId`, `title`; `genres` é aceito, mas não usado no modelo.
- Eventos: `userId`, `movieId`, `rating`, `timestamp` Unix em segundos.
- Avaliações de pelo menos quatro estrelas viram `1` na matriz filme × usuário.
- Similaridade: cosseno, busca exata sobre matriz esparsa, até 30 vizinhos por filme por padrão.
- Score colaborativo: soma das similaridades com os filmes positivos, dividida pelo número de filmes positivos do perfil.
- Score de popularidade: usuários com avaliação positiva do filme / usuários no treino.

O ranking usa primeiro candidatos colaborativos e só depois preenche vagas com popularidade. Os scores entre as duas origens não devem ser comparados como probabilidades.

## Separação de treino e teste

Para cada usuário com pelo menos duas avaliações positivas em timestamps distintos, retém-se a última positiva como item relevante. O treino desse usuário contém apenas eventos com timestamp estritamente anterior. Usuários sem esse requisito continuam no treino, mas não entram nas métricas.

Todo o treinamento do modelo e do baseline acontece depois do corte. Os títulos e IDs do catálogo completo são conhecidos. O corte é por usuário: dados futuros de outros usuários ainda podem estar presentes. Essa limitação precisa ser considerada ao interpretar o resultado.

## Métricas

Para cada usuário elegível, há um único item relevante e uma lista de até `k` candidatos:

- `Precision@k`: acertos / (número de usuários × k). Vagas não preenchidas contam como não acertos. O máximo é `1/k` neste protocolo.
- `Recall@k`: acertos / número de usuários. Com um item relevante, equivale à taxa de acerto.
- `MRR@k`: média de `1/posição` do item retido; zero quando ele não aparece.
- `Catalog coverage`: itens distintos recomendados / itens no catálogo.
- `Mean list length`: tamanho médio da lista efetivamente retornada.

O relatório contém a quantidade de avaliações no treino/teste, hiperparâmetros, identificação dos dados e definições das métricas. Não há intervalos de confiança nem seleção de hiperparâmetros em partição separada; os parâmetros atuais são fixos e o relatório não deve ser usado para escolher o melhor parâmetro repetidamente sobre o mesmo teste.

## Limitações

O demo possui grupos de preferência sintéticos muito fáceis de recuperar. Resultados altos nesse cenário apenas verificam o comportamento esperado da implementação. Bases reais introduzem preferências misturadas, exposição seletiva, popularidade desigual e usuários com poucas interações.

O feedback persistido pode atualizar o perfil de uma consulta, mas não muda a representação global dos itens. Retreinamento, avaliação A/B, inferência causal, busca aproximada, autenticação e mecanismos de privacidade ficam fora do escopo implementado.

## Reprodutibilidade

Os CSVs sintéticos e a seed `42` estão versionados. `generate-demo` reconstrói a fixture. `train` salva modelo, hash dos CSVs, data de treinamento, quantidade de eventos e hiperparâmetros. `evaluate` refaz o corte e produz as métricas sem carregar o artefato treinado no dataset completo.
